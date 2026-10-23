"""Persistence layer. competition.txt section 11, persistence layer.

Stores patient profiles, every accepted observation, and every prediction with
its generation timestamp, model version, uncertainty and data quality status.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, JSON
)
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class Patient(Base):
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    age: Mapped[int] = mapped_column(Integer)
    sex: Mapped[str] = mapped_column(String(16))
    bmi: Mapped[float] = mapped_column(Float)
    years_since_diagnosis: Mapped[float] = mapped_column(Float)
    hba1c_percent: Mapped[float] = mapped_column(Float)
    medication_category: Mapped[str] = mapped_column(String(64))
    comorbidities: Mapped[str] = mapped_column(String(64))
    baseline_fasting_glucose: Mapped[float] = mapped_column(Float)
    data_source: Mapped[str] = mapped_column(String(64), default="synthetic_generator_v1")


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    glucose_mg_dl: Mapped[float | None] = mapped_column(Float, nullable=True)
    heart_rate_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    steps_last_5_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_duration_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    minutes_since_meal: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_meal_carbs_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_source: Mapped[str] = mapped_column(String(32), default="simulated")
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ingest_delay_seconds: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (Index("ix_obs_patient_time", "patient_id", "timestamp"),)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"), index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    observation_timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    model_version: Mapped[str] = mapped_column(String(32))
    current_glucose: Mapped[float] = mapped_column(Float)
    forecast: Mapped[dict] = mapped_column(JSON)          # horizon -> point, lower, upper
    excursion_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    excursion_predicted: Mapped[bool] = mapped_column(Boolean, default=False)
    time_to_threshold_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_band: Mapped[str] = mapped_column(String(16), default="unknown")
    contributors: Mapped[dict] = mapped_column(JSON, default=dict)
    data_quality: Mapped[dict] = mapped_column(JSON, default=dict)
    scenario: Mapped[str] = mapped_column(String(32), default="baseline")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_pred_patient_time", "patient_id", "observation_timestamp"),)
