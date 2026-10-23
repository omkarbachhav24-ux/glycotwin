"""Shared configuration for the GlycoTwin ML pipeline.

Threshold and horizon choices are justified in README.md under
"Clinical target definition". They were set after inspecting the generated
cohort, as competition.txt section 13 stage 1 requires.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARTIFACT_DIR = ROOT / "model_artifacts"
EVAL_DIR = ROOT / "evaluation"

MODEL_VERSION = "glycotwin-0.1.0"

SAMPLE_MINUTES = 5

# Forecast horizons in minutes, per competition.txt section 4.
HORIZONS_MIN = [30, 60, 120]
HORIZON_STEPS = {h: h // SAMPLE_MINUTES for h in HORIZONS_MIN}

# Hyperglycaemic excursion threshold. 180 mg/dL is the standard upper bound of
# the time in range target band (70 to 180 mg/dL) used in CGM consensus
# reporting. The cohort spends about 20 percent of readings above it, so the
# event is frequent enough to learn and rare enough to be worth predicting.
EXCURSION_THRESHOLD_MG_DL = 180.0

# Event horizon for the classifier: does glucose cross the threshold within
# the next 60 minutes. Scored only on rows that are currently at or below the
# threshold, so the task is predicting a crossing rather than restating a
# reading that is already high.
EVENT_HORIZON_MIN = 60
EVENT_HORIZON_STEPS = EVENT_HORIZON_MIN // SAMPLE_MINUTES

# Low glucose is a secondary target only. The cohort has very few readings
# below 70 mg/dL, so no event model is trained for it. Reported as a limitation.
HYPO_THRESHOLD_MG_DL = 70.0

# Lags in samples, covering the previous hour of glucose history.
LAG_STEPS = [1, 2, 3, 4, 6, 9, 12]
ROLLING_WINDOWS_MIN = [30, 60, 120]

# Valid physiological ranges for ingestion validation.
VALID_GLUCOSE_RANGE = (40.0, 400.0)
VALID_HR_RANGE = (30.0, 220.0)
VALID_STEPS_RANGE = (0.0, 3000.0)

# Data freshness thresholds used by the twin state service and the dashboard.
STALE_AFTER_MINUTES = 15
UNUSABLE_AFTER_MINUTES = 45

# Minimum history before a forecast is issued at all.
MIN_HISTORY_STEPS = 13

# Patient level split sizes. Chosen so the test set holds entirely unseen
# patients, per competition.txt section 6.3.
N_TEST_PATIENTS = 8
N_VAL_PATIENTS = 6
SPLIT_SEED = 7

# Chronological holdout: final days of each training patient's series.
CHRONO_HOLDOUT_DAYS = 3

CATEGORICAL_FEATURES = ["medication_category", "sex", "comorbidities"]

STATIC_FEATURES = [
    "age", "bmi", "hba1c_percent", "years_since_diagnosis", "baseline_fasting_glucose",
]
