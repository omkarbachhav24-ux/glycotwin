"""Twin engine: registry, ingestion pipeline, replay and simulation control.

The pipeline for every event follows competition.txt section 7:
  1 receive, 2 validate, 3 handle duplicate, delayed or missing data,
  4 update the rolling window, 5 run the models, 6 persist the prediction,
  7 publish to the dashboard.
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from ml import config as ml_config

from ..models.tables import Observation, Prediction
from .explain import label_for
from .model_service import ModelService
from .serialization import jsonable
from .twin_state import TwinState
from .ws_manager import manager

logger = logging.getLogger("glycotwin.engine")


@dataclass
class StreamController:
    patient_id: str
    mode: str = "idle"
    running: bool = False
    speed: float = 1.0
    cursor: int = 0
    task: asyncio.Task | None = field(default=None, repr=False)


class TwinEngine:
    """Owns twin state for every patient and drives the replay or simulation."""

    def __init__(self, model_service: ModelService, session_factory):
        self.models = model_service
        self.session_factory = session_factory
        self.twins: dict[str, TwinState] = {}
        self.streams: dict[str, StreamController] = {}
        self.source: dict[str, pd.DataFrame] = {}
        self.profiles: dict[str, dict] = {}

    # ----------------------------- setup ------------------------------ #

    def register_patient(self, profile: dict, source: pd.DataFrame) -> None:
        pid = profile["patient_id"]
        self.profiles[pid] = profile
        self.twins[pid] = TwinState(profile)
        self.source[pid] = source.sort_values("timestamp").reset_index(drop=True)
        self.streams[pid] = StreamController(patient_id=pid)

    def prime(self, patient_id: str, points: int = 36) -> None:
        """Warm the twin with recent history and issue a first forecast.

        The window starts shortly after a recorded meal so the dashboard opens
        on an informative stretch of the series rather than on a flat
        overnight baseline with no meal context. The first prediction is
        computed here, otherwise the console would load with an empty forecast.
        """
        twin = self.twins[patient_id]
        src = self.source[patient_id]

        start = self._warm_start_index(src, points)
        for _, row in src.iloc[start:start + points].iterrows():
            twin.accept(row.to_dict())
        self.streams[patient_id].cursor = min(start + points, len(src))

        # Persist the primed window so the console has a chart on first load
        # rather than an empty panel until a stream is started.
        self._persist_window(patient_id, list(twin.window))

        quality = twin.data_quality()
        if quality["status"] != "insufficient_history" and len(twin.window):
            twin.latest_prediction = self.models.predict(
                twin.window_frame(), self.profiles[patient_id], quality)
        twin.updated_at = datetime.utcnow()

    def _persist_window(self, patient_id: str, events: list[dict]) -> None:
        """Bulk insert the warm up readings. Skips anything already stored."""
        session = self.session_factory()
        try:
            existing = {
                row[0] for row in session.query(Observation.timestamp)
                .filter(Observation.patient_id == patient_id).all()
            }
            rows = []
            for event in events:
                ts = _as_datetime(event["timestamp"])
                if ts in existing:
                    continue
                rows.append(Observation(
                    patient_id=patient_id,
                    timestamp=ts,
                    received_at=datetime.utcnow(),
                    glucose_mg_dl=_num(event.get("glucose_mg_dl")),
                    heart_rate_bpm=_num(event.get("heart_rate_bpm")),
                    steps_last_5_min=_num(event.get("steps_last_5_min")),
                    sleep_duration_hours=_num(event.get("sleep_duration_hours")),
                    minutes_since_meal=_num(event.get("minutes_since_meal")),
                    last_meal_carbs_g=_num(event.get("last_meal_carbs_g")),
                    data_source=str(event.get("data_source", "replayed")),
                    is_valid=True,
                    ingest_delay_seconds=int(event.get("ingest_delay_seconds") or 0),
                ))
            if rows:
                session.bulk_save_objects(rows)
                session.commit()
        finally:
            session.close()

    @staticmethod
    def _warm_start_index(src: pd.DataFrame, points: int) -> int:
        """First index giving a full window that ends 20 to 70 minutes after a meal."""
        if "minutes_since_meal" not in src.columns:
            return 0
        since = pd.to_numeric(src["minutes_since_meal"], errors="coerce")
        glucose = pd.to_numeric(src["glucose_mg_dl"], errors="coerce")
        candidates = [i for i in since.index[(since >= 20) & (since <= 70)] if i >= points]
        if not candidates:
            return 0
        # Prefer a window that ends below the excursion threshold, so the
        # crossing model applies and the risk panel has something to say.
        below = [i for i in candidates
                 if pd.notna(glucose.iloc[i]) and glucose.iloc[i] <= 175]
        chosen = below[0] if below else candidates[0]
        return int(chosen) - points + 1

    # --------------------------- ingestion ---------------------------- #

    def ingest(self, patient_id: str, event: dict, scenario: str = "baseline",
               persist: bool = True) -> dict:
        """Run one event through validation, state update, models and storage."""
        twin = self.twins[patient_id]
        accepted, reason = twin.accept(event)

        session = self.session_factory() if persist else None
        try:
            if session is not None:
                session.add(Observation(
                    patient_id=patient_id,
                    timestamp=_as_datetime(event["timestamp"]),
                    received_at=datetime.utcnow(),
                    glucose_mg_dl=_num(event.get("glucose_mg_dl")),
                    heart_rate_bpm=_num(event.get("heart_rate_bpm")),
                    steps_last_5_min=_num(event.get("steps_last_5_min")),
                    sleep_duration_hours=_num(event.get("sleep_duration_hours")),
                    minutes_since_meal=_num(event.get("minutes_since_meal")),
                    last_meal_carbs_g=_num(event.get("last_meal_carbs_g")),
                    data_source=str(event.get("data_source", "simulated")),
                    is_valid=accepted,
                    rejection_reason=None if accepted else reason,
                    ingest_delay_seconds=int(event.get("ingest_delay_seconds") or 0),
                ))
                session.commit()

            quality = twin.data_quality()
            if not accepted:
                return jsonable({"accepted": False, "reason": reason,
                                 "data_quality": quality,
                                 "prediction": twin.latest_prediction})

            if quality["status"] == "insufficient_history":
                twin.updated_at = datetime.utcnow()
                return {"accepted": True, "reason": reason, "data_quality": quality,
                        "prediction": None}

            prediction = self.models.predict(
                twin.window_frame(), self.profiles[patient_id], quality, scenario)
            twin.latest_prediction = prediction
            twin.updated_at = datetime.utcnow()

            if session is not None and scenario == "baseline":
                session.add(Prediction(
                    patient_id=patient_id,
                    generated_at=_as_datetime(prediction["generated_at"]),
                    observation_timestamp=_as_datetime(prediction["observation_timestamp"]),
                    model_version=prediction["model_version"],
                    current_glucose=prediction["current_glucose"],
                    forecast={str(f["horizon_minutes"]): {
                        "point": f["point_mg_dl"], "lower": f["lower_mg_dl"],
                        "upper": f["upper_mg_dl"]} for f in prediction["forecast"]},
                    excursion_probability=prediction["excursion_probability"],
                    excursion_predicted=prediction["excursion_predicted"],
                    time_to_threshold_minutes=prediction["time_to_threshold_minutes"],
                    risk_band=prediction["risk_band"],
                    contributors={"top": prediction["contributors"]},
                    data_quality=quality,
                    scenario=scenario,
                ))
                session.commit()

            return jsonable({"accepted": True, "reason": reason,
                             "data_quality": quality, "prediction": prediction})
        finally:
            if session is not None:
                session.close()

    # ------------------------- stream control ------------------------- #

    async def start_stream(self, patient_id: str, mode: str, speed: float,
                           restart: bool, interval: float) -> None:
        await self.stop_stream(patient_id)
        ctl = self.streams[patient_id]
        if restart:
            ctl.cursor = 0
            self.twins[patient_id] = TwinState(self.profiles[patient_id])
            self.prime(patient_id)
        ctl.mode = mode
        ctl.running = True
        ctl.speed = max(0.25, min(speed, 20.0))
        ctl.task = asyncio.create_task(self._run_stream(patient_id, interval))

    async def stop_stream(self, patient_id: str) -> None:
        ctl = self.streams.get(patient_id)
        if ctl and ctl.task and not ctl.task.done():
            ctl.running = False
            ctl.task.cancel()
            try:
                await ctl.task
            except asyncio.CancelledError:
                pass
        if ctl:
            ctl.running = False
            ctl.task = None

    async def _run_stream(self, patient_id: str, interval: float) -> None:
        ctl = self.streams[patient_id]
        try:
            while ctl.running:
                event = self._next_event(patient_id)
                if event is None:
                    ctl.running = False
                    await manager.broadcast(patient_id, {
                        "type": "stream_complete",
                        "status": self.stream_status(patient_id)})
                    break

                result = await asyncio.to_thread(self.ingest, patient_id, event)
                await manager.broadcast(patient_id, {
                    "type": "twin_update",
                    "accepted": result["accepted"],
                    "reason": result["reason"],
                    "observation": _jsonable(event),
                    "prediction": result["prediction"],
                    "data_quality": result["data_quality"],
                    "trend": self.twins[patient_id].recent_trend(),
                    "status": self.stream_status(patient_id),
                })
                await asyncio.sleep(max(0.05, interval / ctl.speed))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            ctl.running = False
            logger.exception("Stream failed for %s", patient_id)
            await manager.broadcast(patient_id, {
                "type": "stream_error",
                "message": f"{type(exc).__name__}: {exc}",
                "status": self.stream_status(patient_id),
            })

    def _next_event(self, patient_id: str) -> dict | None:
        """Replay returns the next recorded row. Simulation perturbs it.

        Simulation mode is a synthetic generator on top of the recorded series,
        not a second physiological model. It also injects the occasional
        defect so the data quality panel has something to show.
        """
        ctl = self.streams[patient_id]
        src = self.source[patient_id]
        if ctl.cursor >= len(src):
            return None
        row = src.iloc[ctl.cursor].to_dict()
        ctl.cursor += 1

        if ctl.mode == "simulate":
            row = dict(row)
            row["data_source"] = "simulated"
            row["glucose_mg_dl"] = round(
                float(row["glucose_mg_dl"]) + random.gauss(0, 2.5), 1)
            roll = random.random()
            if roll < 0.02:
                row["glucose_mg_dl"] = 612.0          # invalid, must be rejected
            elif roll < 0.05:
                row["heart_rate_bpm"] = None          # missing optional signal
            elif roll < 0.08:
                row["ingest_delay_seconds"] = random.randint(400, 1500)
        else:
            row["data_source"] = "replayed"
        return row

    def stream_status(self, patient_id: str) -> dict:
        ctl = self.streams[patient_id]
        twin = self.twins[patient_id]
        return {
            "patient_id": patient_id,
            "mode": ctl.mode,
            "running": ctl.running,
            "speed": ctl.speed,
            "cursor_index": ctl.cursor,
            "total_points": len(self.source[patient_id]),
            "last_event_timestamp": twin.last_observation_at,
        }

    def recompute_predictions(self) -> int:
        """Re-run the models for every primed twin against the current settings.

        Called when the alert threshold moves. Without this the console would
        sit with no prediction until the next reading arrives, which on a
        paused stream could be never.
        """
        updated = 0
        for patient_id, twin in self.twins.items():
            if len(twin.window) < ml_config.MIN_HISTORY_STEPS:
                continue
            quality = twin.data_quality()
            if quality["status"] == "insufficient_history":
                continue
            twin.latest_prediction = self.models.predict(
                twin.window_frame(), self.profiles[patient_id], quality)
            twin.updated_at = datetime.utcnow()
            updated += 1
        return updated

    # -------------------------- counterfactual ------------------------ #

    SCENARIOS = {
        "added_walk": "A recorded walking bout over the last 30 minutes",
        "lighter_meal": "Fewer carbohydrates in the last recorded meal",
        "delayed_meal": "The last meal recorded later than it was",
        "longer_sleep": "More sleep recorded for last night",
    }

    def _check_ranges(self, before: pd.DataFrame, after: pd.DataFrame) -> list[dict]:
        """Compare modified features against the ranges seen during training.

        Gradient boosted trees do not extrapolate. Once an input passes the
        largest split the model ever learned, the prediction stops responding
        and the number becomes meaningless. Any scenario that pushes a feature
        past the training range is reported rather than silently returned.
        """
        ranges = getattr(self.models, "feature_ranges", {}) or {}
        notes = []
        for feature, bounds in ranges.items():
            if feature not in before.columns or feature not in after.columns:
                continue
            old = before[feature].iloc[-1]
            new_value = after[feature].iloc[-1]
            if pd.isna(old) or pd.isna(new_value) or float(old) == float(new_value):
                continue
            outside = not (bounds["min"] <= float(new_value) <= bounds["max"])
            extreme = float(new_value) > bounds["p99"] or float(new_value) < bounds["p01"]
            notes.append({
                "feature": feature,
                "label": label_for(feature),
                "before": round(float(old), 1),
                "after": round(float(new_value), 1),
                "training_p01_p99": [bounds["p01"], bounds["p99"]],
                "status": ("outside_training_range" if outside
                           else "extreme_but_observed" if extreme else "within_range"),
            })
        return notes

    def counterfactual(self, patient_id: str, scenario: str,
                       magnitude: float = 1.0) -> dict:
        """Re-run the model on a modified recent window.

        This compares two model outputs. It is not evidence that the change
        would produce the outcome in a patient, and the model was fitted on a
        synthetic generator, so an association it learned need not be causal.
        competition.txt section 9.
        """
        twin = self.twins[patient_id]
        if len(twin.window) < ml_config.MIN_HISTORY_STEPS:
            raise ValueError("Not enough history for a scenario comparison.")

        magnitude = float(np.clip(magnitude, 0.25, 2.0))
        baseline_window = twin.window_frame()
        baseline_quality = twin.data_quality()
        baseline = twin.latest_prediction or self.models.predict(
            baseline_window, self.profiles[patient_id], baseline_quality)

        modified = baseline_window.copy()
        last_30min = modified.index[-6:]
        description = ""

        if scenario == "added_walk":
            # About 250 steps per 5 minutes for half an hour, a brisk walk.
            # Kept inside the step counts the cohort contains.
            added = 250.0 * magnitude
            modified.loc[last_30min, "steps_last_5_min"] = (
                modified.loc[last_30min, "steps_last_5_min"].fillna(0) + added)
            modified.loc[last_30min, "heart_rate_bpm"] = (
                modified.loc[last_30min, "heart_rate_bpm"].fillna(75) + 18 * magnitude)
            description = (f"A brisk {int(30 * magnitude)} minute walk recorded over the last "
                           "half hour, with the heart rate rise that would accompany it.")
        elif scenario == "lighter_meal":
            factor = max(0.1, 1.0 - 0.4 * magnitude)
            modified["last_meal_carbs_g"] = modified["last_meal_carbs_g"].fillna(0) * factor
            description = (f"The last recorded meal carried {int((1 - factor) * 100)} percent "
                           "fewer carbohydrates.")
        elif scenario == "delayed_meal":
            shift = 40.0 * magnitude
            modified["minutes_since_meal"] = (
                modified["minutes_since_meal"].fillna(600) - shift).clip(lower=0)
            description = f"The last meal happened {int(shift)} minutes later than recorded."
        elif scenario == "longer_sleep":
            modified["sleep_duration_hours"] = (
                modified["sleep_duration_hours"].fillna(6.5) + 1.2 * magnitude).clip(upper=9.5)
            description = f"{1.2 * magnitude:.1f} more hours of sleep recorded last night."
        else:
            raise ValueError(f"Unknown scenario: {scenario}")

        alternative = self.models.predict(
            modified, self.profiles[patient_id], baseline_quality, scenario=scenario)

        before_feats = self.models.feature_frame(baseline_window, self.profiles[patient_id])
        after_feats = self.models.feature_frame(modified, self.profiles[patient_id])
        range_notes = self._check_ranges(before_feats, after_feats)

        diff = []
        for b, a in zip(baseline["forecast"], alternative["forecast"]):
            diff.append({
                "horizon_minutes": b["horizon_minutes"],
                "baseline_mg_dl": b["point_mg_dl"],
                "scenario_mg_dl": a["point_mg_dl"],
                "difference_mg_dl": round(a["point_mg_dl"] - b["point_mg_dl"], 1),
            })

        caveats = [
            "This compares two model outputs under different inputs. It is not "
            "evidence that the change would cause this outcome in a patient.",
        ]
        if any(n["status"] != "within_range" for n in range_notes):
            caveats.append(
                "One or more inputs sit at or beyond the edge of the training data. "
                "The model cannot extrapolate past what it saw, so treat this "
                "comparison as unreliable.")
        if scenario == "added_walk":
            caveats.append(
                "Activity and time of day move together in this cohort, so the model's "
                "response to steps reflects that association rather than an isolated "
                "effect of exercise.")

        return jsonable({
            "patient_id": patient_id,
            "scenario": scenario,
            "scenario_label": self.SCENARIOS.get(scenario, scenario),
            "magnitude": magnitude,
            "description": description,
            "baseline": baseline,
            "alternative": alternative,
            "difference": diff,
            "input_changes": range_notes,
            "probability_change": (
                round(alternative["excursion_probability"] - baseline["excursion_probability"], 4)
                if alternative["excursion_probability"] is not None
                and baseline["excursion_probability"] is not None else None),
            "caveats": caveats,
            "disclaimer": (
                "HYPOTHETICAL model output. Changing an input and seeing a different "
                "forecast does not show that the change would cause that outcome in a "
                "patient. Not evidence of treatment effect."),
        })


def _as_datetime(value) -> datetime | None:
    """Accept a datetime or an ISO string. Predictions leave the model service
    already JSON safe, so timestamps arrive as strings on the way to the DB."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return pd.to_datetime(value).to_pydatetime()


def _num(value):
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) else f


def _jsonable(event: dict) -> dict:
    return jsonable(event)
