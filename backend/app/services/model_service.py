"""Prediction service.

Loads the trained artifacts once and turns a rolling window of observations
into a forecast, an excursion probability, an uncertainty band and per
prediction feature contributions.

Features are built with ml.feature_engineering, the same module used in
training, so serving cannot drift from the training definition.
competition.txt sections 6 and 11.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd

from ml import config as ml_config
from ml import feature_engineering as fe

from .explain import label_for, narrative
from .serialization import jsonable

_LOCK = threading.Lock()


class ModelService:
    """Thread safe wrapper around the trained LightGBM artifacts."""

    def __init__(self, artifact_path):
        self.artifact_path = artifact_path
        self.bundle = joblib.load(artifact_path)
        self.features: list[str] = self.bundle["features"]
        self.model_version: str = self.bundle["model_version"]
        self.horizons: list[int] = self.bundle["horizons"]
        self.threshold: float = self.bundle["excursion_threshold"]
        self.operating_threshold: float = self.bundle["operating_threshold"]
        # Kept so the console can show what the training run chose, and offer
        # a way back to it after a clinician moves the line.
        self.default_operating_threshold: float = self.bundle["operating_threshold"]
        self.conformal_deltas: dict[int, float] = {
            int(k): float(v) for k, v in self.bundle.get("conformal_deltas", {}).items()
        }
        self.trained_at = self.bundle.get("trained_at")
        self.feature_ranges: dict = self.bundle.get("feature_ranges", {})
        self._classifier = self.bundle["classifier"]
        self._calibrator = self.bundle["calibrator"]
        self._forecasters = self.bundle["forecasters"]

    # ------------------------------------------------------------------ #

    def _feature_row(self, window: pd.DataFrame, profile: dict) -> pd.DataFrame:
        """Build the feature vector for the most recent observation in window."""
        ehr = pd.DataFrame([{
            "patient_id": profile["patient_id"],
            **{k: profile[k] for k in ml_config.STATIC_FEATURES},
            **{k: profile[k] for k in ml_config.CATEGORICAL_FEATURES},
        }])
        built = fe.build_features(window, ehr)
        row = built.iloc[[-1]].copy()
        for col in self.features:
            if col not in row.columns:
                row[col] = np.nan
        for col in ml_config.CATEGORICAL_FEATURES:
            if col in row.columns:
                row[col] = row[col].astype("category")
        return row[self.features]

    def feature_frame(self, window: pd.DataFrame, profile: dict) -> pd.DataFrame:
        """Public access to the engineered feature row, used by scenario checks."""
        return self._feature_row(window, profile)

    def _contributions(self, X: pd.DataFrame, top_n: int = 5) -> list[dict]:
        """LightGBM per prediction contributions for the excursion classifier."""
        raw = self._classifier.booster_.predict(X, pred_contrib=True)[0]
        contribs = raw[:-1]
        order = np.argsort(-np.abs(contribs))[:top_n]
        out = []
        for i in order:
            feature = self.features[i]
            value = X.iloc[0, i]
            if isinstance(value, float) and np.isnan(value):
                value = None
            elif hasattr(value, "item"):
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    value = None
            out.append({
                "feature": feature,
                "label": label_for(feature),
                "value": round(value, 2) if isinstance(value, float) else None,
                "contribution": round(float(contribs[i]), 4),
                "direction": "raises" if contribs[i] > 0 else "lowers",
            })
        return out

    @staticmethod
    def _risk_band(prob: float | None, above_threshold: bool,
                   operating_threshold: float) -> str:
        if above_threshold:
            return "above_threshold"
        if prob is None:
            return "unknown"
        if prob >= operating_threshold:
            return "high"
        if prob >= operating_threshold / 2:
            return "moderate"
        return "low"

    def _time_to_threshold(self, forecast: list[dict], current: float) -> float | None:
        """First horizon at which the point forecast crosses the threshold.

        Linear interpolation between horizons. An estimate from the forecast
        curve, not a separate time to event model.
        """
        if current > self.threshold:
            # Already above. A crossing time is not meaningful here.
            return None
        prev_t, prev_v = 0.0, current
        for f in forecast:
            if f["point_mg_dl"] > self.threshold:
                if prev_v >= self.threshold:
                    return float(prev_t)
                span = f["point_mg_dl"] - prev_v
                if span <= 0:
                    return float(f["horizon_minutes"])
                frac = (self.threshold - prev_v) / span
                return round(prev_t + frac * (f["horizon_minutes"] - prev_t), 1)
            prev_t, prev_v = float(f["horizon_minutes"]), f["point_mg_dl"]
        return None

    # ------------------------------------------------------------------ #

    def predict(self, window: pd.DataFrame, profile: dict,
                data_quality: dict, scenario: str = "baseline") -> dict:
        """Produce a full prediction payload for the latest row of window."""
        with _LOCK:
            X = self._feature_row(window, profile)

            latest = window.iloc[-1]
            current = float(latest["glucose_mg_dl"])
            obs_ts = pd.to_datetime(latest["timestamp"]).to_pydatetime()

            forecast = []
            for horizon in self.horizons:
                point = float(self._forecasters[f"{horizon}_point"].predict(X)[0])
                lower = float(self._forecasters[f"{horizon}_lower"].predict(X)[0])
                upper = float(self._forecasters[f"{horizon}_upper"].predict(X)[0])
                delta = self.conformal_deltas.get(horizon, 0.0)
                lower, upper = lower - delta, upper + delta
                # Guard against quantile crossing, which LightGBM does not forbid.
                lower, upper = min(lower, point), max(upper, point)
                forecast.append({
                    "horizon_minutes": horizon,
                    "point_mg_dl": round(point, 1),
                    "lower_mg_dl": round(lower, 1),
                    "upper_mg_dl": round(upper, 1),
                    "target_timestamp": obs_ts + timedelta(minutes=horizon),
                })

            above = current > self.threshold
            probability = None
            if not above and data_quality["status"] in ("ok", "stale"):
                raw = float(self._classifier.predict_proba(X)[0, 1])
                probability = float(np.clip(self._calibrator.predict([raw])[0], 0.0, 1.0))

            contributors = self._contributions(X) if data_quality["status"] != "insufficient_history" else []
            band = self._risk_band(probability, above, self.operating_threshold)

            return jsonable({
                "generated_at": datetime.utcnow(),
                "observation_timestamp": obs_ts,
                "model_version": self.model_version,
                "current_glucose": round(current, 1),
                "forecast": forecast,
                "excursion_probability": round(probability, 4) if probability is not None else None,
                "excursion_predicted": bool(
                    probability is not None and probability >= self.operating_threshold),
                "time_to_threshold_minutes": self._time_to_threshold(forecast, current),
                "risk_band": band,
                "excursion_threshold_mg_dl": self.threshold,
                "contributors": contributors,
                "explanation": narrative(current, probability, band, contributors,
                                         ml_config.EVENT_HORIZON_MIN, self.threshold),
                "data_quality": data_quality,
                "scenario": scenario,
            })
