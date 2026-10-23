"""Load the synthetic cohort into the database and prime the twins.

Idempotent: re-running clears the observation and prediction tables and
reloads the patient profiles. competition.txt section 16 deliverable 5.
"""
from __future__ import annotations

import pandas as pd

from .db import Base, SessionLocal, engine as db_engine
from .models.tables import Observation, Patient, Prediction
from .settings import settings

PROFILE_COLUMNS = [
    "patient_id", "age", "sex", "bmi", "years_since_diagnosis", "hba1c_percent",
    "medication_category", "comorbidities", "baseline_fasting_glucose", "data_source",
]


def load_source_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Observations come from the raw stream, defects and all.

    The clean file is what the models were trained on. The raw file is what a
    running system would receive, so the demonstration replays that
    one and lets validation do its job.
    """
    ehr = pd.read_csv(settings.data_dir / "ehr_profiles.csv")
    raw_path = settings.data_dir / "raw_stream.csv.gz"
    obs_path = settings.data_dir / "observations.csv.gz"
    source = raw_path if raw_path.exists() else obs_path
    obs = pd.read_csv(source, parse_dates=["timestamp"])
    if "ingest_delay_seconds" not in obs.columns:
        obs["ingest_delay_seconds"] = 0
    return ehr, obs


def reset_database() -> None:
    Base.metadata.create_all(db_engine)
    with SessionLocal() as session:
        session.query(Prediction).delete()
        session.query(Observation).delete()
        session.query(Patient).delete()
        session.commit()


def seed_patients(ehr: pd.DataFrame) -> None:
    with SessionLocal() as session:
        for row in ehr[PROFILE_COLUMNS].to_dict(orient="records"):
            session.add(Patient(**row))
        session.commit()


def main() -> None:
    ehr, obs = load_source_frames()
    reset_database()
    seed_patients(ehr)
    print(f"Seeded {len(ehr)} synthetic patients, "
          f"{len(obs)} raw stream rows available for replay.")


if __name__ == "__main__":
    main()
