"""
GlycoTwin synthetic cohort generator.

Produces a fully synthetic Type 2 diabetes cohort:
  - EHR profiles (demographics, diagnosis, labs, medication categories)
  - 5 minute CGM-like glucose series
  - Wearable context: steps, heart rate, sleep
  - Meal events with carbohydrate estimates
  - A "raw" stream copy carrying injected data quality defects

Nothing here is real patient data. This is a mechanistic toy model tuned to
produce plausible looking curves, not a validated physiological simulator.
Models trained on it learn this generator, not human metabolism. See
data/README.md for the assumptions and their limits.

Design reference: competition.txt sections 5.1, 5.2, 7, 12.1.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SAMPLE_MINUTES = 5
SAMPLES_PER_HOUR = 60 // SAMPLE_MINUTES
SAMPLES_PER_DAY = 24 * SAMPLES_PER_HOUR

MED_CATEGORIES = [
    ("metformin_only", 0.42),
    ("metformin_plus_su", 0.24),
    ("metformin_plus_dpp4", 0.16),
    ("metformin_plus_sglt2", 0.12),
    ("basal_insulin_plus_oral", 0.06),
]

COMORBIDITIES = ["hypertension", "dyslipidaemia", "obesity", "nafld", "none"]


@dataclass
class PatientProfile:
    patient_id: str
    age: int
    sex: str
    bmi: float
    years_since_diagnosis: float
    hba1c_percent: float
    medication_category: str
    comorbidities: str
    baseline_fasting_glucose: float
    insulin_sensitivity: float
    carb_sensitivity: float
    response_rate: float
    meal_clearance_minutes: float
    dawn_amplitude: float
    sensor_noise_sd: float
    data_source: str = "synthetic_generator_v1"


def estimated_mean_glucose(hba1c: float) -> float:
    """ADAG relationship, 28.7 * A1c - 46.7. Anchors a synthetic baseline only."""
    return 28.7 * hba1c - 46.7


def make_profile(rng: np.random.Generator, index: int) -> PatientProfile:
    hba1c = float(np.clip(rng.normal(7.6, 0.85), 6.1, 10.2))
    age = int(np.clip(rng.normal(54, 11), 28, 82))
    bmi = float(np.clip(rng.normal(27.8, 4.2), 18.5, 42.0))
    years = float(np.clip(rng.gamma(2.2, 2.6), 0.3, 27.0))

    cats, weights = zip(*MED_CATEGORIES)
    med = str(rng.choice(cats, p=np.array(weights) / sum(weights)))

    # Fasting baseline sits below estimated mean glucose, which is driven by
    # post meal excursions.
    fasting = float(np.clip(estimated_mean_glucose(hba1c) - rng.normal(42, 9), 85, 168))

    # Worse control means larger meal excursions that clear more slowly.
    carb_sens = float(np.clip(0.80 + 0.14 * (hba1c - 7.5) + 0.012 * (bmi - 27.0),
                              0.45, 1.45)) * float(rng.normal(1.0, 0.09))
    meal_clear = float(np.clip(rng.normal(165, 22) + 11 * (hba1c - 7.5), 110, 245))
    insulin_sens = float(np.clip(rng.normal(1.0, 0.18) * (1.22 - 0.035 * (bmi - 25)), 0.45, 1.5))

    return PatientProfile(
        patient_id=f"SYNTH-{index:03d}",
        age=age,
        sex=str(rng.choice(["female", "male"])),
        bmi=round(bmi, 1),
        years_since_diagnosis=round(years, 1),
        hba1c_percent=round(hba1c, 1),
        medication_category=med,
        comorbidities=str(rng.choice(COMORBIDITIES, p=[0.3, 0.22, 0.24, 0.12, 0.12])),
        baseline_fasting_glucose=round(fasting, 1),
        insulin_sensitivity=round(insulin_sens, 3),
        carb_sensitivity=round(float(np.clip(carb_sens, 0.4, 1.6)), 3),
        response_rate=round(float(np.clip(rng.normal(0.26, 0.04), 0.15, 0.38)), 4),
        meal_clearance_minutes=round(meal_clear, 1),
        dawn_amplitude=round(float(np.clip(rng.normal(14, 5), 2, 30)), 2),
        sensor_noise_sd=round(float(np.clip(rng.normal(3.4, 0.8), 1.8, 6.0)), 2),
    )


def meal_excursion_shape(minutes_since_meal: np.ndarray, peak_minutes: float,
                         duration_minutes: float) -> np.ndarray:
    """Gamma shaped excursion normalised so its peak equals 1.0.

    Rises to the peak at peak_minutes, then decays, reaching near zero by
    roughly duration_minutes.
    """
    k = 2.8
    theta = max(peak_minutes / (k - 1.0), 1e-6)
    x = np.clip(minutes_since_meal, 0.0, None)
    scale = duration_minutes / 190.0  # stretch or compress the tail per patient
    xs = x / max(scale, 0.3)
    curve = (xs ** (k - 1)) * np.exp(-xs / theta)
    peak_value = ((theta * (k - 1)) ** (k - 1)) * math.exp(-(k - 1))
    return curve / peak_value


def simulate_patient(profile: PatientProfile, days: int, start: datetime,
                     rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    n = days * SAMPLES_PER_DAY
    times = [start + timedelta(minutes=SAMPLE_MINUTES * i) for i in range(n)]
    tod_minutes = np.array([t.hour * 60 + t.minute for t in times], dtype=float)
    elapsed_minutes = np.arange(n, dtype=float) * SAMPLE_MINUTES

    sleep_start = 23 * 60 + rng.normal(0, 35)
    sleep_end = 6 * 60 + 30 + rng.normal(0, 30)
    asleep = (tod_minutes >= sleep_start) | (tod_minutes <= sleep_end)

    # Meals: breakfast, lunch, snack, dinner with jittered timing and carbs.
    meal_plan = [(8 * 60, 50, 22), (13 * 60 + 30, 68, 26), (17 * 60, 22, 14), (20 * 60 + 30, 62, 24)]
    meals = []
    for day in range(days):
        for base_minute, mean_carbs, carb_sd in meal_plan:
            if rng.random() < 0.08:
                continue
            minute = base_minute + rng.normal(0, 38)
            carbs = float(np.clip(rng.normal(mean_carbs, carb_sd), 5, 140))
            meals.append({
                "timestamp": start + timedelta(days=day, minutes=float(minute)),
                "carbohydrates_g": round(carbs, 1),
            })
    meals.sort(key=lambda m: m["timestamp"])

    # Activity: background movement plus one to three bouts per day.
    steps = np.clip(rng.poisson(22, n).astype(float), 0, None)
    steps[asleep] = 0.0
    activity_intensity = np.zeros(n)
    for day in range(days):
        for _ in range(int(rng.integers(1, 4))):
            bout_start_minute = rng.uniform(6.5 * 60, 21 * 60)
            bout_len = int(rng.integers(3, 15))
            idx = day * SAMPLES_PER_DAY + int(bout_start_minute // SAMPLE_MINUTES)
            if idx + bout_len >= n:
                continue
            intensity = float(rng.uniform(0.35, 1.0))
            steps[idx:idx + bout_len] += rng.normal(420 * intensity, 60, bout_len).clip(0)
            activity_intensity[idx:idx + bout_len] += intensity

    # Glucose lowering effect of activity, delayed and smeared over ~45 minutes.
    kernel = np.exp(-np.arange(12) / 4.0)
    kernel /= kernel.sum()
    activity_effect = np.convolve(activity_intensity, kernel, mode="full")[:n]

    # Additive meal excursion in mg/dL above baseline.
    meal_contrib = np.zeros(n)
    for meal in meals:
        offset_min = (meal["timestamp"] - start).total_seconds() / 60.0
        rel = elapsed_minutes - offset_min
        mask = (rel >= 0) & (rel <= 330)
        if not mask.any():
            continue
        peak_min = float(np.clip(rng.normal(62, 11), 35, 100))
        amplitude = profile.carb_sensitivity * meal["carbohydrates_g"] * 1.28
        meal_contrib[mask] += amplitude * meal_excursion_shape(
            rel[mask], peak_min, profile.meal_clearance_minutes)

    dawn = profile.dawn_amplitude * np.exp(-((tod_minutes - 300) ** 2) / (2 * 75 ** 2))
    activity_drop = 24.0 * activity_effect * profile.insulin_sensitivity

    # Slow baseline wander, days to days variation in control.
    wander = np.zeros(n)
    for i in range(1, n):
        wander[i] = 0.9995 * wander[i - 1] + rng.normal(0, 0.45)
    wander = np.clip(wander, -22, 22)

    noise = np.zeros(n)
    for i in range(1, n):
        noise[i] = 0.88 * noise[i - 1] + rng.normal(0, 1.6)

    target = profile.baseline_fasting_glucose + wander + dawn + meal_contrib - activity_drop

    # First order lag toward the target gives autocorrelation and a realistic
    # delay between a meal and the observed rise.
    glucose = np.zeros(n)
    glucose[0] = profile.baseline_fasting_glucose
    alpha = profile.response_rate
    for i in range(1, n):
        glucose[i] = glucose[i - 1] + alpha * (target[i] - glucose[i - 1]) + 0.30 * noise[i]
    glucose = np.clip(glucose, 45, 400)

    sensor = np.clip(glucose + rng.normal(0, profile.sensor_noise_sd, n), 40, 400)

    heart_rate = (
        float(np.clip(rng.normal(72 - 0.08 * (profile.age - 54), 1.0), 54, 92))
        + 28 * activity_intensity
        - 9 * asleep
        + rng.normal(0, 3.0, n)
    )
    heart_rate = np.clip(heart_rate, 42, 180)

    sleep_hours = np.zeros(n)
    nightly = {d: float(np.clip(rng.normal(6.8, 1.0), 3.5, 9.5)) for d in range(days + 2)}
    for i, t in enumerate(times):
        sleep_hours[i] = nightly[(t - start).days]

    minutes_since_meal = np.full(n, np.nan)
    last_carbs = np.full(n, np.nan)
    meal_idx, cur_meal = 0, None
    for i, t in enumerate(times):
        while meal_idx < len(meals) and meals[meal_idx]["timestamp"] <= t:
            cur_meal = meals[meal_idx]
            meal_idx += 1
        if cur_meal is not None:
            minutes_since_meal[i] = (t - cur_meal["timestamp"]).total_seconds() / 60.0
            last_carbs[i] = cur_meal["carbohydrates_g"]

    clean = pd.DataFrame({
        "patient_id": profile.patient_id,
        "timestamp": times,
        "glucose_mg_dl": np.round(sensor, 1),
        "heart_rate_bpm": np.round(heart_rate, 0),
        "steps_last_5_min": np.round(steps, 0),
        "sleep_duration_hours": np.round(sleep_hours, 2),
        "minutes_since_meal": np.round(minutes_since_meal, 1),
        "last_meal_carbs_g": np.round(last_carbs, 1),
        "is_asleep": asleep.astype(int),
        "data_source": "simulated",
    })

    meals_df = pd.DataFrame(meals)
    if not meals_df.empty:
        meals_df.insert(0, "patient_id", profile.patient_id)
    return clean, meals_df


def inject_defects(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Raw stream copy with dropouts, duplicates, late and invalid readings.

    The ingestion validator and the dashboard data quality panel both need
    something real to react to. competition.txt sections 7 and 8 module 8.
    """
    frames = []
    for patient_id, group in df.groupby("patient_id", sort=True):
        raw = group.reset_index(drop=True).copy()
        raw["ingest_delay_seconds"] = 0
        raw["defect"] = ""
        n = len(raw)

        drop_mask = np.zeros(n, dtype=bool)
        for _ in range(int(rng.integers(3, 7))):
            s = int(rng.integers(0, max(1, n - 20)))
            drop_mask[s:s + int(rng.integers(4, 15))] = True

        keep = raw.loc[~drop_mask].copy()
        pool = np.arange(len(keep))

        bad_idx = rng.choice(pool, size=min(6, len(pool)), replace=False)
        keep.iloc[bad_idx, keep.columns.get_loc("glucose_mg_dl")] = rng.choice(
            [-5.0, 0.0, 612.0, 999.0], size=len(bad_idx))
        keep.iloc[bad_idx, keep.columns.get_loc("defect")] = "out_of_range"

        late_idx = rng.choice(pool, size=min(30, len(pool)), replace=False)
        keep.iloc[late_idx, keep.columns.get_loc("ingest_delay_seconds")] = rng.integers(
            400, 1800, size=len(late_idx))
        cur = keep.iloc[late_idx, keep.columns.get_loc("defect")].to_numpy()
        keep.iloc[late_idx, keep.columns.get_loc("defect")] = np.where(
            cur == "", "late_arrival", cur)

        dup_idx = rng.choice(pool, size=min(12, len(pool)), replace=False)
        dups = keep.iloc[dup_idx].copy()
        dups["defect"] = "duplicate"

        out = pd.concat([keep, dups], ignore_index=True).sort_values("timestamp")
        out["patient_id"] = patient_id
        frames.append(out)

    return pd.concat(frames, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the GlycoTwin synthetic cohort")
    parser.add_argument("--patients", type=int, default=40)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--seed", type=int, default=20261023)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    start = datetime(2026, 9, 1, 0, 0, 0)

    profiles, obs_frames, meal_frames = [], [], []
    for i in range(1, args.patients + 1):
        profile = make_profile(rng, i)
        obs, meals = simulate_patient(profile, args.days, start, rng)
        profiles.append(profile)
        obs_frames.append(obs)
        if not meals.empty:
            meal_frames.append(meals)
        if not args.quiet:
            print(f"  {profile.patient_id}  HbA1c={profile.hba1c_percent}  "
                  f"mean={obs.glucose_mg_dl.mean():6.1f} mg/dL  "
                  f"above180={100 * (obs.glucose_mg_dl > 180).mean():5.1f}%  "
                  f"below70={100 * (obs.glucose_mg_dl < 70).mean():4.1f}%")

    ehr = pd.DataFrame([asdict(p) for p in profiles])
    observations = pd.concat(obs_frames, ignore_index=True)
    meals_all = pd.concat(meal_frames, ignore_index=True) if meal_frames else pd.DataFrame()
    raw = inject_defects(observations, rng)

    out = args.out
    (out / "synthetic_examples").mkdir(parents=True, exist_ok=True)
    ehr.to_csv(out / "ehr_profiles.csv", index=False)
    observations.to_csv(out / "observations.csv.gz", index=False, compression="gzip")
    meals_all.to_csv(out / "meal_events.csv.gz", index=False, compression="gzip")
    raw.to_csv(out / "raw_stream.csv.gz", index=False, compression="gzip")

    sample_id = ehr.patient_id.iloc[0]
    observations[observations.patient_id == sample_id].head(576).to_csv(
        out / "synthetic_examples" / f"{sample_id}_two_days.csv", index=False)
    ehr.head(3).to_csv(out / "synthetic_examples" / "ehr_profiles_sample.csv", index=False)

    per_patient_above = observations.groupby("patient_id").glucose_mg_dl.apply(
        lambda s: float((s > 180).mean()))
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_version": "synthetic_generator_v1",
        "seed": args.seed,
        "patients": int(args.patients),
        "days_per_patient": int(args.days),
        "sampling_interval_minutes": SAMPLE_MINUTES,
        "total_observations": int(len(observations)),
        "mean_glucose_mg_dl": round(float(observations.glucose_mg_dl.mean()), 2),
        "median_glucose_mg_dl": round(float(observations.glucose_mg_dl.median()), 2),
        "share_above_180": round(float((observations.glucose_mg_dl > 180).mean()), 4),
        "share_below_70": round(float((observations.glucose_mg_dl < 70).mean()), 4),
        "per_patient_share_above_180": {
            "min": round(float(per_patient_above.min()), 4),
            "median": round(float(per_patient_above.median()), 4),
            "max": round(float(per_patient_above.max()), 4),
        },
        "meal_events": int(len(meals_all)),
        "raw_stream_rows": int(len(raw)),
        "raw_defect_counts": {k: int(v) for k, v in raw.defect.value_counts().items()},
    }
    (out / "cohort_summary.json").write_text(json.dumps(summary, indent=2))
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
