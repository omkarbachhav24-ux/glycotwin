"""API schemas. Units and source metadata travel with every sensor event,
per competition.txt section 7."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SensorEvent(BaseModel):
    patient_id: str
    timestamp: datetime
    glucose_mg_dl: float | None = None
    heart_rate_bpm: float | None = None
    steps_last_5_min: float | None = None
    sleep_duration_hours: float | None = None
    minutes_since_meal: float | None = None
    last_meal_carbs_g: float | None = None
    data_source: Literal["simulated", "replayed", "manual"] = "simulated"
    glucose_unit: Literal["mg_dL"] = "mg_dL"
    ingest_delay_seconds: int = 0


class PatientSummary(BaseModel):
    patient_id: str
    age: int
    sex: str
    bmi: float
    hba1c_percent: float
    years_since_diagnosis: float
    medication_category: str
    comorbidities: str
    baseline_fasting_glucose: float
    data_source: str


class HorizonForecast(BaseModel):
    horizon_minutes: int
    point_mg_dl: float
    lower_mg_dl: float
    upper_mg_dl: float
    target_timestamp: datetime


class Contributor(BaseModel):
    feature: str
    label: str
    value: float | None
    contribution: float
    direction: Literal["raises", "lowers"]


class DataQuality(BaseModel):
    status: Literal["ok", "stale", "unusable", "insufficient_history"]
    minutes_since_last_observation: float | None
    history_points: int
    missing_signals: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rejected_last_hour: int = 0


class PredictionOut(BaseModel):
    patient_id: str
    generated_at: datetime
    observation_timestamp: datetime
    model_version: str
    current_glucose: float
    forecast: list[HorizonForecast]
    excursion_probability: float | None
    excursion_predicted: bool
    time_to_threshold_minutes: float | None
    risk_band: str
    excursion_threshold_mg_dl: float
    contributors: list[Contributor]
    explanation: str
    data_quality: DataQuality
    scenario: str = "baseline"


class StreamStatus(BaseModel):
    patient_id: str
    mode: Literal["idle", "replay", "simulate"]
    running: bool
    speed: float
    cursor_index: int
    total_points: int
    last_event_timestamp: datetime | None


class OperatingPointUpdate(BaseModel):
    """Change the alert threshold for this session."""
    threshold: float = Field(ge=0.01, le=0.99)


class StreamCommand(BaseModel):
    mode: Literal["replay", "simulate"] = "replay"
    speed: float = 1.0
    restart: bool = False


class CounterfactualRequest(BaseModel):
    """A hypothetical change to recent inputs. Never a treatment recommendation.

    competition.txt section 9: results are model based scenarios, not evidence
    of a treatment effect.
    """
    scenario: Literal["added_walk", "lighter_meal", "delayed_meal", "longer_sleep"]
    magnitude: float = 1.0
