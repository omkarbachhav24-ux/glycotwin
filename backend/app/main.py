"""GlycoTwin FastAPI application.

Research proof of concept. Not a medical device, not a diagnostic tool, and
not a substitute for clinical care.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .api.ws import ws_router
from .db import Base, SessionLocal, engine as db_engine
from .seed import load_source_frames, seed_patients
from .services.engine import TwinEngine
from .services.model_service import ModelService
from .settings import settings

DISCLAIMER = ("GlycoTwin is a research proof of concept built on synthetic data. "
              "It is not a medical device, not a diagnostic tool, and not a "
              "substitute for clinical care.")

PROFILE_FIELDS = [
    "patient_id", "age", "sex", "bmi", "years_since_diagnosis", "hba1c_percent",
    "medication_category", "comorbidities", "baseline_fasting_glucose", "data_source",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(db_engine)

    if not settings.artifact_path.exists():
        raise RuntimeError(
            f"No model artifacts at {settings.artifact_path}. "
            "Run: python -m ml.train")

    models = ModelService(settings.artifact_path)
    twin_engine = TwinEngine(models, SessionLocal)

    ehr, obs = load_source_frames()
    from .models.tables import Patient
    with SessionLocal() as session:
        if session.query(Patient).count() == 0:
            seed_patients(ehr)

    for profile in ehr[PROFILE_FIELDS].to_dict(orient="records"):
        pid = profile["patient_id"]
        series = obs[obs.patient_id == pid].copy()
        if series.empty:
            continue
        twin_engine.register_patient(profile, series)
        twin_engine.prime(pid)

    app.state.engine = twin_engine
    print(f"GlycoTwin ready. {len(twin_engine.twins)} twins primed, "
          f"model {models.model_version}")
    yield

    for patient_id in list(twin_engine.streams):
        await twin_engine.stop_stream(patient_id)


app = FastAPI(
    title="GlycoTwin API",
    description=DISCLAIMER,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(ws_router)


@app.get("/")
def root():
    return {"service": "GlycoTwin API", "docs": "/docs", "disclaimer": DISCLAIMER}
