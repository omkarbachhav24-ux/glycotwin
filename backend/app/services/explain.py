"""Plain language labels for model features.

The dashboard explanation panel shows what moved a prediction. Feature names
alone are not readable by a clinician, so each one carries a short phrase.
Nothing here changes the model output, it only describes it.
"""
from __future__ import annotations

FEATURE_LABELS: dict[str, str] = {
    "glucose_mg_dl": "Current glucose",
    "distance_to_threshold": "Distance below the 180 mg/dL threshold",
    "delta_from_baseline": "Gap from this patient's fasting baseline",
    "glucose_roc_15min": "Glucose trend over 15 minutes",
    "glucose_roc_30min": "Glucose trend over 30 minutes",
    "glucose_roc_60min": "Glucose trend over 60 minutes",
    "glucose_accel_30min": "Whether the rise is speeding up",
    "minutes_since_meal": "Time since the last recorded meal",
    "last_meal_carbs_g": "Carbohydrates in the last recorded meal",
    "meal_recent": "A meal was recorded in the last 2 hours",
    "steps_sum_30min": "Steps in the last 30 minutes",
    "steps_sum_120min": "Steps in the last 2 hours",
    "hr_mean_30min": "Average heart rate over 30 minutes",
    "hr_delta_30min": "Heart rate above its recent average",
    "sleep_duration_hours": "Sleep duration last night",
    "tod_sin": "Time of day",
    "tod_cos": "Time of day",
    "hba1c_percent": "HbA1c on record",
    "baseline_fasting_glucose": "Recorded fasting baseline",
    "age": "Age",
    "bmi": "BMI",
    "years_since_diagnosis": "Years since diagnosis",
    "medication_category": "Recorded medication category",
    "comorbidities": "Recorded comorbidity",
    "sex": "Sex on record",
}

for _w in (30, 60, 120):
    FEATURE_LABELS[f"glucose_mean_{_w}min"] = f"Average glucose over {_w} minutes"
    FEATURE_LABELS[f"glucose_std_{_w}min"] = f"Glucose variability over {_w} minutes"
    FEATURE_LABELS[f"glucose_max_{_w}min"] = f"Highest glucose in the last {_w} minutes"
    FEATURE_LABELS[f"glucose_min_{_w}min"] = f"Lowest glucose in the last {_w} minutes"
for _lag in (5, 10, 15, 20, 30, 45, 60):
    FEATURE_LABELS[f"glucose_lag_{_lag}min"] = f"Glucose {_lag} minutes ago"


def label_for(feature: str) -> str:
    return FEATURE_LABELS.get(feature, feature.replace("_", " ").capitalize())


def narrative(current: float, probability: float | None, risk_band: str,
              contributors: list[dict], horizon_minutes: int,
              threshold: float) -> str:
    """One or two sentences describing the current prediction.

    Deliberately descriptive. It states what the model saw, never what the
    clinician should do, and never mentions medication or dosing.
    """
    if risk_band == "above_threshold":
        return (f"Glucose is already above {threshold:.0f} mg/dL at {current:.0f} mg/dL, so "
                "the crossing model does not apply here. The forecast curve still shows "
                "where the model expects glucose to go next.")
    if probability is None:
        return ("Not enough recent history to produce an excursion estimate. "
                "The forecast shown is based on the readings available.")

    raising = [c for c in contributors if c["direction"] == "raises"][:2]
    lowering = [c for c in contributors if c["direction"] == "lowers"][:1]

    pct = f"{probability * 100:.0f}%"
    head = {
        "high": f"The model puts the chance of crossing {threshold:.0f} mg/dL within "
                f"{horizon_minutes} minutes at {pct}, which is above its alert threshold.",
        "moderate": f"The model puts the chance of crossing {threshold:.0f} mg/dL within "
                    f"{horizon_minutes} minutes at {pct}.",
        "low": f"The model sees a low chance of crossing {threshold:.0f} mg/dL in the next "
               f"{horizon_minutes} minutes, at {pct}.",
        "above_threshold": f"Glucose is already above {threshold:.0f} mg/dL at "
                           f"{current:.0f} mg/dL, so the crossing model does not apply here. "
                           f"The forecast curve still shows where the model expects it to go.",
    }[risk_band]

    parts = [head]
    if raising:
        names = " and ".join(c["label"].lower() for c in raising)
        parts.append(f"The largest upward influences are {names}.")
    if lowering:
        parts.append(f"Pulling the other way: {lowering[0]['label'].lower()}.")
    return " ".join(parts)
