"""The Digital Twin state service.

Holds, for each patient, the clinical profile, a rolling window of validated
observations, the latest forecast, and the data quality status. A new
observation validates, updates the rolling window, recomputes the forecast and
persists the result. competition.txt sections 5.3 and 7.
"""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timedelta

import pandas as pd

from ml import config as ml_config
from ml.preprocessing import validate_observation

from .serialization import jsonable

WINDOW_POINTS = 48          # 4 hours at 5 minute sampling
REQUIRED_SIGNALS = ["glucose_mg_dl", "heart_rate_bpm", "steps_last_5_min"]


class TwinState:
    """One patient's evolving state."""

    def __init__(self, profile: dict):
        self.profile = profile
        self.patient_id = profile["patient_id"]
        self.window: deque[dict] = deque(maxlen=WINDOW_POINTS)
        self.latest_prediction: dict | None = None
        self.rejected_recent: deque[tuple[datetime, str]] = deque(maxlen=200)
        self.duplicates_seen = 0
        self.last_observation_at: datetime | None = None
        self.updated_at: datetime | None = None
        self.lock = threading.Lock()

    # ------------------------------------------------------------------ #

    def accept(self, event: dict) -> tuple[bool, str]:
        """Validate and apply one sensor event.

        Returns (accepted, reason). Rejected events are counted for the data
        quality panel but never enter the rolling window, and are never
        replaced with an invented value.
        """
        ts = pd.to_datetime(event["timestamp"]).to_pydatetime()

        ok, reason = validate_observation(
            event.get("glucose_mg_dl"),
            event.get("heart_rate_bpm"),
            event.get("steps_last_5_min"),
        )
        if not ok:
            self.rejected_recent.append((ts, reason))
            return False, reason

        if self.window:
            # Duplicates are checked against every timestamp held, not only the
            # most recent one. A repeat of an older reading is still a repeat,
            # and out of order arrival makes that the common case.
            if any(pd.to_datetime(e["timestamp"]).to_pydatetime() == ts for e in self.window):
                self.duplicates_seen += 1
                return False, "duplicate_timestamp"
            last_ts = pd.to_datetime(self.window[-1]["timestamp"]).to_pydatetime()
            if ts < last_ts:
                # Out of order arrival. Insert in place so rolling features
                # stay in timestamp order rather than arrival order.
                items = list(self.window)
                items.append(event)
                items.sort(key=lambda e: pd.to_datetime(e["timestamp"]))
                self.window = deque(items[-WINDOW_POINTS:], maxlen=WINDOW_POINTS)
                self.last_observation_at = pd.to_datetime(
                    self.window[-1]["timestamp"]).to_pydatetime()
                return True, "late_arrival_reordered"

        self.window.append(event)
        self.last_observation_at = ts
        return True, "ok"

    # ------------------------------------------------------------------ #

    def data_quality(self, now: datetime | None = None) -> dict:
        """Freshness, history depth, missing signals and recent rejections."""
        warnings: list[str] = []
        history = len(self.window)

        if history == 0:
            return {
                "status": "insufficient_history",
                "minutes_since_last_observation": None,
                "history_points": 0,
                "missing_signals": REQUIRED_SIGNALS,
                "warnings": ["No observations received yet for this patient."],
                "rejected_last_hour": 0,
            }

        # Freshness is measured on the stream clock, the timestamp of the most
        # recent observation against the one before it, because replay and
        # simulation run on synthetic time rather than wall clock time.
        latest_ts = pd.to_datetime(self.window[-1]["timestamp"]).to_pydatetime()
        reference = now or latest_ts
        minutes_since = (reference - latest_ts).total_seconds() / 60.0

        gap_minutes = 0.0
        if history >= 2:
            prev_ts = pd.to_datetime(self.window[-2]["timestamp"]).to_pydatetime()
            gap_minutes = (latest_ts - prev_ts).total_seconds() / 60.0
            if gap_minutes > ml_config.SAMPLE_MINUTES * 2:
                warnings.append(
                    f"Gap of {gap_minutes:.0f} minutes before the latest reading.")

        latest = self.window[-1]
        missing = [s for s in REQUIRED_SIGNALS
                   if latest.get(s) is None or pd.isna(latest.get(s))]
        if missing:
            warnings.append("Missing in the latest reading: " + ", ".join(missing) + ".")

        if latest.get("minutes_since_meal") is None or pd.isna(latest.get("minutes_since_meal")):
            warnings.append("No meal has been recorded, so meal context is unavailable.")

        if history < ml_config.MIN_HISTORY_STEPS:
            status = "insufficient_history"
            warnings.append(
                f"Only {history} of {ml_config.MIN_HISTORY_STEPS} readings needed for a "
                "full feature window.")
        elif max(minutes_since, gap_minutes) > ml_config.UNUSABLE_AFTER_MINUTES:
            status = "unusable"
            warnings.append("Data is too old to support a reliable forecast.")
        elif max(minutes_since, gap_minutes) > ml_config.STALE_AFTER_MINUTES:
            status = "stale"
            warnings.append("The latest reading is older than the expected sampling interval.")
        else:
            status = "ok"

        cutoff = latest_ts - timedelta(hours=1)
        rejected = sum(1 for ts, _ in self.rejected_recent if ts >= cutoff)
        if rejected:
            warnings.append(f"{rejected} reading(s) rejected by validation in the last hour.")

        delay = latest.get("ingest_delay_seconds") or 0
        if delay and delay > 300:
            warnings.append(f"Latest reading arrived {int(delay) // 60} minutes late.")

        return {
            "status": status,
            "minutes_since_last_observation": round(minutes_since, 1),
            "history_points": history,
            "missing_signals": missing,
            "warnings": warnings,
            "rejected_last_hour": rejected,
        }

    # ------------------------------------------------------------------ #

    def window_frame(self) -> pd.DataFrame:
        df = pd.DataFrame(list(self.window))
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["patient_id"] = self.patient_id
        for col in ("glucose_mg_dl", "heart_rate_bpm", "steps_last_5_min",
                    "sleep_duration_hours", "minutes_since_meal", "last_meal_carbs_g"):
            if col not in df.columns:
                df[col] = float("nan")
        return df.sort_values("timestamp").reset_index(drop=True)

    def recent_trend(self) -> dict:
        """Rising, falling or stable, from validated observations only."""
        if len(self.window) < 4:
            return {"direction": "unknown", "rate_mg_dl_per_min": None,
                    "change_30min": None}
        df = self.window_frame()
        recent = df.tail(7)
        span_min = (recent.timestamp.iloc[-1] - recent.timestamp.iloc[0]).total_seconds() / 60
        if span_min <= 0:
            return {"direction": "unknown", "rate_mg_dl_per_min": None, "change_30min": None}
        change = float(recent.glucose_mg_dl.iloc[-1] - recent.glucose_mg_dl.iloc[0])
        rate = change / span_min
        if rate > 0.6:
            direction = "rising"
        elif rate < -0.6:
            direction = "falling"
        else:
            direction = "stable"
        return {
            "direction": direction,
            "rate_mg_dl_per_min": round(rate, 2),
            "change_30min": round(change, 1),
        }

    def snapshot(self) -> dict:
        """What the twin currently believes about this patient."""
        df = self.window_frame() if self.window else pd.DataFrame()
        rolling = {}
        if len(df):
            for minutes in (30, 60, 120):
                steps = minutes // ml_config.SAMPLE_MINUTES
                tail = df.glucose_mg_dl.tail(steps)
                if len(tail) >= 2:
                    rolling[f"mean_{minutes}min"] = round(float(tail.mean()), 1)
                    rolling[f"max_{minutes}min"] = round(float(tail.max()), 1)
                    rolling[f"min_{minutes}min"] = round(float(tail.min()), 1)
        latest = jsonable(self.window[-1]) if self.window else {}
        return jsonable({
            "patient_id": self.patient_id,
            "profile": self.profile,
            "latest_observation": latest or None,
            "latest_glucose": latest.get("glucose_mg_dl") if latest else None,
            "rolling_glucose": rolling,
            "trend": self.recent_trend(),
            "data_quality": self.data_quality(),
            "latest_prediction": self.latest_prediction,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "history_points": len(self.window),
        })
