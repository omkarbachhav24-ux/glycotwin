"""Temporal feature engineering.

Every feature is computed from information available at or before the
prediction timestamp. No future value, including a meal logged after the
prediction time, enters the feature set. competition.txt section 6.1.

The same function builds the training matrix and the live feature vector in
the backend, so training and serving cannot drift apart.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def _rolling(group: pd.Series, window_steps: int, fn: str) -> pd.Series:
    roll = group.rolling(window=window_steps, min_periods=max(2, window_steps // 3))
    return getattr(roll, fn)()


def build_features(obs: pd.DataFrame, ehr: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return the observation frame with temporal and static features attached.

    obs must be sorted by patient_id then timestamp and regularly sampled at
    config.SAMPLE_MINUTES. Rows whose history is incomplete keep NaN features;
    LightGBM handles those natively and the serving path reports them as a
    data quality warning instead of guessing.
    """
    df = obs.sort_values(["patient_id", "timestamp"]).reset_index(drop=True).copy()
    g = df.groupby("patient_id", sort=False)["glucose_mg_dl"]

    for lag in config.LAG_STEPS:
        df[f"glucose_lag_{lag * config.SAMPLE_MINUTES}min"] = g.shift(lag)

    # Rate of change in mg/dL per minute over three look backs.
    for minutes in (15, 30, 60):
        steps = minutes // config.SAMPLE_MINUTES
        df[f"glucose_roc_{minutes}min"] = (
            df["glucose_mg_dl"] - g.shift(steps)) / minutes

    for minutes in config.ROLLING_WINDOWS_MIN:
        steps = minutes // config.SAMPLE_MINUTES
        df[f"glucose_mean_{minutes}min"] = g.transform(lambda s, w=steps: _rolling(s, w, "mean"))
        df[f"glucose_std_{minutes}min"] = g.transform(lambda s, w=steps: _rolling(s, w, "std"))
        df[f"glucose_max_{minutes}min"] = g.transform(lambda s, w=steps: _rolling(s, w, "max"))
        df[f"glucose_min_{minutes}min"] = g.transform(lambda s, w=steps: _rolling(s, w, "min"))

    # Acceleration: is the rise speeding up or flattening out.
    df["glucose_accel_30min"] = df["glucose_roc_15min"] - df["glucose_roc_30min"]

    # Distance from the excursion threshold, the single most direct signal.
    df["distance_to_threshold"] = config.EXCURSION_THRESHOLD_MG_DL - df["glucose_mg_dl"]

    # Context signals.
    steps_series = df.groupby("patient_id", sort=False)["steps_last_5_min"]
    df["steps_sum_30min"] = steps_series.transform(lambda s: _rolling(s, 6, "sum"))
    df["steps_sum_120min"] = steps_series.transform(lambda s: _rolling(s, 24, "sum"))
    hr_series = df.groupby("patient_id", sort=False)["heart_rate_bpm"]
    df["hr_mean_30min"] = hr_series.transform(lambda s: _rolling(s, 6, "mean"))
    df["hr_delta_30min"] = df["heart_rate_bpm"] - df["hr_mean_30min"]

    # Time of day as a cyclic pair so midnight and 23:55 sit next to each other.
    minute_of_day = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
    df["tod_sin"] = np.sin(2 * np.pi * minute_of_day / 1440)
    df["tod_cos"] = np.cos(2 * np.pi * minute_of_day / 1440)

    # Meal context, capped because a very old meal carries no information.
    df["minutes_since_meal"] = df["minutes_since_meal"].clip(upper=600)
    df["last_meal_carbs_g"] = df["last_meal_carbs_g"].fillna(0.0)
    df["meal_recent"] = (df["minutes_since_meal"] <= 120).astype(float)

    if ehr is not None:
        static_cols = (["patient_id"] + config.STATIC_FEATURES + config.CATEGORICAL_FEATURES)
        df = df.merge(ehr[static_cols], on="patient_id", how="left")
        for col in config.CATEGORICAL_FEATURES:
            df[col] = df[col].astype("category")
        # Where does this reading sit relative to the patient's own baseline.
        df["delta_from_baseline"] = df["glucose_mg_dl"] - df["baseline_fasting_glucose"]

    return df


def feature_columns(df: pd.DataFrame) -> list[str]:
    """Columns the models consume, in a stable order."""
    exclude = {
        "patient_id", "timestamp", "data_source", "is_asleep", "defect",
        "ingest_delay_seconds", "steps_last_5_min", "heart_rate_bpm",
        "event_eligible",
    }
    exclude |= {c for c in df.columns if c.startswith("target_")}
    cols = [c for c in df.columns if c not in exclude]
    return sorted(cols)


def add_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Attach forecast targets and the excursion event label.

    Targets are forward shifts and are used for training and scoring only.
    They never appear in feature_columns.
    """
    df = df.copy()
    g = df.groupby("patient_id", sort=False)["glucose_mg_dl"]

    for horizon, steps in config.HORIZON_STEPS.items():
        df[f"target_glucose_{horizon}min"] = g.shift(-steps)

    # Event: does any reading in the next EVENT_HORIZON_MIN cross the threshold.
    steps = config.EVENT_HORIZON_STEPS
    future_max = (
        df[::-1]
        .groupby("patient_id", sort=False)["glucose_mg_dl"]
        .transform(lambda s: s.shift(1).rolling(steps, min_periods=steps).max())[::-1]
    )
    df["target_future_max_60min"] = future_max
    df["target_excursion_60min"] = (future_max > config.EXCURSION_THRESHOLD_MG_DL).astype(float)
    df.loc[future_max.isna(), "target_excursion_60min"] = np.nan

    # Minutes until the first crossing inside the event window. Used to report
    # how much warning an alert gives, which a binary label cannot show.
    steps = config.EVENT_HORIZON_STEPS
    future = np.full((len(df), steps), np.nan)
    g = df.groupby("patient_id", sort=False)["glucose_mg_dl"]
    for k in range(1, steps + 1):
        future[:, k - 1] = g.shift(-k).to_numpy()
    crossed = future > config.EXCURSION_THRESHOLD_MG_DL
    any_cross = crossed.any(axis=1)
    first_idx = np.where(any_cross, crossed.argmax(axis=1) + 1, np.nan)
    # Named with the target_ prefix so feature_columns excludes it. It is
    # derived from future readings and must never reach the model.
    df["target_minutes_to_crossing"] = first_idx * config.SAMPLE_MINUTES

    # Scored population for the classifier: currently at or below threshold.
    df["event_eligible"] = (df["glucose_mg_dl"] <= config.EXCURSION_THRESHOLD_MG_DL)
    return df
