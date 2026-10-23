"""Loading, validation and cleaning for the GlycoTwin pipeline.

The same validation rules run here and in the backend ingestion service, so
what the model was trained on matches what the running twin accepts.
competition.txt sections 7 and 13 stage 3.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config


@dataclass
class ValidationReport:
    total_rows: int = 0
    accepted_rows: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    duplicates_removed: int = 0
    gaps_detected: int = 0
    largest_gap_minutes: float = 0.0

    def as_dict(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "accepted_rows": self.accepted_rows,
            "rejected": self.rejected,
            "duplicates_removed": self.duplicates_removed,
            "gaps_detected": self.gaps_detected,
            "largest_gap_minutes": round(self.largest_gap_minutes, 1),
        }


def validate_observation(glucose, heart_rate=None, steps=None) -> tuple[bool, str]:
    """Single observation check. Returns (is_valid, reason)."""
    lo, hi = config.VALID_GLUCOSE_RANGE
    if glucose is None or (isinstance(glucose, float) and np.isnan(glucose)):
        return False, "missing_glucose"
    if not lo <= float(glucose) <= hi:
        return False, "glucose_out_of_range"
    if heart_rate is not None and not pd.isna(heart_rate):
        hlo, hhi = config.VALID_HR_RANGE
        if not hlo <= float(heart_rate) <= hhi:
            return False, "heart_rate_out_of_range"
    if steps is not None and not pd.isna(steps):
        slo, shi = config.VALID_STEPS_RANGE
        if not slo <= float(steps) <= shi:
            return False, "steps_out_of_range"
    return True, "ok"


def clean_observations(df: pd.DataFrame) -> tuple[pd.DataFrame, ValidationReport]:
    """Drop invalid and duplicate rows, sort by time, measure gaps.

    Invalid rows are removed rather than imputed. Missing glucose is never
    filled with an invented value, per competition.txt section 5.1.
    """
    report = ValidationReport(total_rows=len(df))
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    before = len(df)
    df = df.drop_duplicates(subset=["patient_id", "timestamp"], keep="first")
    report.duplicates_removed = before - len(df)

    reasons = []
    for row in df.itertuples(index=False):
        ok, reason = validate_observation(
            getattr(row, "glucose_mg_dl", None),
            getattr(row, "heart_rate_bpm", None),
            getattr(row, "steps_last_5_min", None),
        )
        reasons.append(reason if not ok else "ok")
    df["_reason"] = reasons

    rejected = df[df["_reason"] != "ok"]
    report.rejected = {k: int(v) for k, v in rejected["_reason"].value_counts().items()}
    df = df[df["_reason"] == "ok"].drop(columns=["_reason"])

    df = df.sort_values(["patient_id", "timestamp"]).reset_index(drop=True)

    deltas = df.groupby("patient_id")["timestamp"].diff().dt.total_seconds() / 60.0
    gaps = deltas[deltas > config.SAMPLE_MINUTES * 1.5]
    report.gaps_detected = int(len(gaps))
    report.largest_gap_minutes = float(gaps.max()) if len(gaps) else 0.0
    report.accepted_rows = len(df)
    return df, report


def load_cohort(data_dir=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load observations and EHR profiles. Returns (observations, ehr)."""
    data_dir = data_dir or config.DATA_DIR
    obs = pd.read_csv(data_dir / "observations.csv.gz", parse_dates=["timestamp"])
    ehr = pd.read_csv(data_dir / "ehr_profiles.csv")
    return obs, ehr
