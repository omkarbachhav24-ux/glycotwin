"""REST API. competition.txt section 16 deliverable 3."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models.schemas import (
    CounterfactualRequest, OperatingPointUpdate, PatientSummary, SensorEvent,
    StreamCommand, StreamStatus,
)
from ..models.tables import Observation, Prediction
from ..services.ws_manager import manager
from ..settings import settings

router = APIRouter(prefix="/api")


def engine(request: Request):
    eng = getattr(request.app.state, "engine", None)
    if eng is None:
        raise HTTPException(503, "Twin engine is not ready yet.")
    return eng


@router.get("/health")
def health(request: Request):
    eng = getattr(request.app.state, "engine", None)
    return {
        "status": "ok" if eng else "starting",
        "model_version": eng.models.model_version if eng else None,
        "model_trained_at": eng.models.trained_at if eng else None,
        "patients_loaded": len(eng.twins) if eng else 0,
        "server_time": datetime.utcnow().isoformat(),
        "disclaimer": ("Research proof of concept. Not a medical device, not a "
                       "diagnostic tool, not a substitute for clinical care."),
    }


@router.get("/patients", response_model=list[PatientSummary])
def list_patients(eng=Depends(engine)):
    return [PatientSummary(**p) for p in eng.profiles.values()]


@router.get("/patients/{patient_id}/twin")
def get_twin(patient_id: str, eng=Depends(engine)):
    if patient_id not in eng.twins:
        raise HTTPException(404, "Unknown patient.")
    snap = eng.twins[patient_id].snapshot()
    snap["stream"] = eng.stream_status(patient_id)
    snap["model"] = {
        "version": eng.models.model_version,
        "trained_at": eng.models.trained_at,
        "excursion_threshold_mg_dl": eng.models.threshold,
        "operating_threshold": eng.models.operating_threshold,
        "horizons_minutes": eng.models.horizons,
        "event_horizon_minutes": 60,
    }
    return snap


@router.get("/patients/{patient_id}/observations")
def get_observations(patient_id: str, hours: float = Query(6.0, ge=0.5, le=72.0),
                     eng=Depends(engine), session: Session = Depends(get_session)):
    if patient_id not in eng.twins:
        raise HTTPException(404, "Unknown patient.")
    rows = session.execute(
        select(Observation)
        .where(Observation.patient_id == patient_id, Observation.is_valid.is_(True))
        .order_by(desc(Observation.timestamp))
        .limit(int(hours * 12))
    ).scalars().all()
    rows = sorted(rows, key=lambda r: r.timestamp)
    return [{
        "timestamp": r.timestamp,
        "glucose_mg_dl": r.glucose_mg_dl,
        "heart_rate_bpm": r.heart_rate_bpm,
        "steps_last_5_min": r.steps_last_5_min,
        "minutes_since_meal": r.minutes_since_meal,
        "data_source": r.data_source,
    } for r in rows]


@router.get("/patients/{patient_id}/predictions")
def get_predictions(patient_id: str, limit: int = Query(40, ge=1, le=500),
                    session: Session = Depends(get_session)):
    rows = session.execute(
        select(Prediction)
        .where(Prediction.patient_id == patient_id, Prediction.scenario == "baseline")
        .order_by(desc(Prediction.observation_timestamp))
        .limit(limit)
    ).scalars().all()
    return [{
        "generated_at": r.generated_at,
        "observation_timestamp": r.observation_timestamp,
        "model_version": r.model_version,
        "current_glucose": r.current_glucose,
        "forecast": r.forecast,
        "excursion_probability": r.excursion_probability,
        "excursion_predicted": r.excursion_predicted,
        "time_to_threshold_minutes": r.time_to_threshold_minutes,
        "risk_band": r.risk_band,
        "data_quality_status": (r.data_quality or {}).get("status"),
    } for r in rows]


@router.get("/patients/{patient_id}/prediction-outcomes")
def prediction_outcomes(patient_id: str, limit: int = Query(60, ge=5, le=400),
                        session: Session = Depends(get_session)):
    """Past forecasts paired with what was observed afterwards.

    This is the twin timeline in competition.txt section 8 module 6. It lets a
    reviewer see the model's own track record on this patient rather than only
    its current claim.
    """
    preds = session.execute(
        select(Prediction)
        .where(Prediction.patient_id == patient_id, Prediction.scenario == "baseline")
        .order_by(desc(Prediction.observation_timestamp)).limit(limit)
    ).scalars().all()
    obs = session.execute(
        select(Observation)
        .where(Observation.patient_id == patient_id, Observation.is_valid.is_(True))
        .order_by(desc(Observation.timestamp)).limit(limit * 6)
    ).scalars().all()
    by_time = {o.timestamp: o.glucose_mg_dl for o in obs}

    out = []
    for p in sorted(preds, key=lambda r: r.observation_timestamp):
        entry = {
            "observation_timestamp": p.observation_timestamp,
            "current_glucose": p.current_glucose,
            "risk_band": p.risk_band,
            "excursion_probability": p.excursion_probability,
        }
        for horizon, values in (p.forecast or {}).items():
            target_time = p.observation_timestamp + __import__("datetime").timedelta(
                minutes=int(horizon))
            actual = by_time.get(target_time)
            entry[f"forecast_{horizon}"] = values.get("point")
            entry[f"actual_{horizon}"] = actual
            entry[f"error_{horizon}"] = (
                round(values.get("point") - actual, 1) if actual is not None else None)
        out.append(entry)
    return out


@router.post("/patients/{patient_id}/observations")
def post_observation(patient_id: str, event: SensorEvent, eng=Depends(engine)):
    """Ingest a single sensor event. Validation decides whether it is used."""
    if patient_id not in eng.twins:
        raise HTTPException(404, "Unknown patient.")
    payload = event.model_dump()
    payload["patient_id"] = patient_id
    result = eng.ingest(patient_id, payload)
    return result


@router.post("/patients/{patient_id}/stream", response_model=StreamStatus)
async def control_stream(patient_id: str, command: StreamCommand, eng=Depends(engine)):
    if patient_id not in eng.twins:
        raise HTTPException(404, "Unknown patient.")
    await eng.start_stream(patient_id, command.mode, command.speed, command.restart,
                           settings.default_stream_interval_seconds)
    return StreamStatus(**eng.stream_status(patient_id))


@router.post("/patients/{patient_id}/stream/pause", response_model=StreamStatus)
async def pause_stream(patient_id: str, eng=Depends(engine)):
    if patient_id not in eng.twins:
        raise HTTPException(404, "Unknown patient.")
    await eng.stop_stream(patient_id)
    return StreamStatus(**eng.stream_status(patient_id))


@router.get("/patients/{patient_id}/stream", response_model=StreamStatus)
def stream_status(patient_id: str, eng=Depends(engine)):
    if patient_id not in eng.twins:
        raise HTTPException(404, "Unknown patient.")
    return StreamStatus(**eng.stream_status(patient_id))


@router.post("/patients/{patient_id}/counterfactual")
def counterfactual(patient_id: str, req: CounterfactualRequest, eng=Depends(engine)):
    if patient_id not in eng.twins:
        raise HTTPException(404, "Unknown patient.")
    try:
        return eng.counterfactual(patient_id, req.scenario, req.magnitude)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get("/operating-point")
def get_operating_point(eng=Depends(engine)):
    """The current alert threshold and the measured trade across candidates.

    The sweep comes from the held out test patients in the last training run.
    Alert burden is reported per patient per day, and as episodes, where
    repeated firings inside one rising episode count once, because that is
    what reaches a clinician.
    """
    sweep, refractory, patient_days = [], None, None
    if settings.metrics_path.exists():
        block = json.loads(settings.metrics_path.read_text())
        event = block.get("primary_patient_holdout", {}).get("event", {})
        sweep = event.get("threshold_sweep", [])
        refractory = event.get("refractory_minutes")
        patient_days = event.get("patient_days")
    return {
        "threshold": eng.models.operating_threshold,
        "default_threshold": eng.models.default_operating_threshold,
        "selection_note": (
            "The default was chosen by F1 on validation patients, which is a neutral "
            "statistical default rather than a clinical judgement about whether a "
            "missed crossing or a false alarm is worse."),
        "refractory_minutes": refractory,
        "evaluation_patient_days": patient_days,
        "sweep": sweep,
    }


@router.put("/operating-point")
def set_operating_point(update: OperatingPointUpdate, eng=Depends(engine)):
    """Set the alert threshold for this session.

    This changes which predictions are flagged and how the risk band reads. It
    does not retrain or recalibrate anything: the probability is unchanged, only
    the line drawn through it moves. The change lasts for the life of the
    process and is not written to the database.
    """
    eng.models.operating_threshold = float(update.threshold)
    updated = eng.recompute_predictions()
    return {
        "threshold": eng.models.operating_threshold,
        "default_threshold": eng.models.default_operating_threshold,
        "twins_recomputed": updated,
        "note": ("Predictions already stored keep the band they were written with. "
                 "Live twins were recomputed against the new threshold."),
    }


@router.get("/metrics")
def metrics():
    """Evaluation results from the last training run, served as produced."""
    if not settings.metrics_path.exists():
        raise HTTPException(404, "No evaluation metrics found. Run python -m ml.train.")
    return json.loads(settings.metrics_path.read_text())


@router.get("/cohort-summary")
def cohort_summary():
    path = settings.data_dir / "cohort_summary.json"
    if not path.exists():
        raise HTTPException(404, "No cohort summary found.")
    return json.loads(path.read_text())
