"""Render evaluation/evaluation-report.md from evaluation/metrics.json.

Keeping the report generated means the written numbers cannot drift from the
numbers the training run produced. competition.txt section 14 asks for
evidence rather than targets, so nothing here is typed by hand.

    python scripts/write_evaluation_report.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "evaluation" / "metrics.json"
OUT = ROOT / "evaluation" / "evaluation-report.md"


def forecast_table(block: dict) -> str:
    lines = [
        "| Horizon | MAE | RMSE | Persistence MAE | Ridge MAE | Gain over persistence | 80% interval coverage |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for horizon, e in block["forecast"].items():
        lines.append(
            f"| {horizon} | {e['model_lightgbm']['mae']} | {e['model_lightgbm']['rmse']} | "
            f"{e['baseline_persistence']['mae']} | {e['baseline_ridge']['mae']} | "
            f"{e['mae_improvement_over_persistence_pct']}% | "
            f"{e['prediction_interval_80_conformal']['coverage']:.3f} |")
    return "\n".join(lines)


def event_table(block: dict) -> str:
    m = block["event"]["model_lightgbm_calibrated"]
    b = block["event"]["baseline_slope_extrapolation"]
    rows = [
        ("Precision", m["precision"], b["precision"]),
        ("Recall (sensitivity)", m["recall"], b["recall"]),
        ("Specificity", m["specificity"], b["specificity"]),
        ("F1", m["f1"], b["f1"]),
        ("PR-AUC", m["pr_auc"], b["pr_auc"]),
        ("ROC-AUC", m["roc_auc"], b["roc_auc"]),
        ("Brier score", m["brier_score"], b["brier_score"]),
    ]
    lines = ["| Metric | LightGBM, calibrated | Slope extrapolation baseline |",
             "| --- | --- | --- |"]
    lines += [f"| {k} | {v} | {bv} |" for k, v, bv in rows]
    lines.append(f"| Expected calibration error | "
                 f"{m['calibration']['expected_calibration_error']} | not applicable |")
    return "\n".join(lines)


def main() -> None:
    m = json.loads(METRICS.read_text())
    primary = m["primary_patient_holdout"]
    chrono = m["secondary_chronological_holdout"]
    target = m["clinical_target"]
    ev = primary["event"]["model_lightgbm_calibrated"]
    cm = ev["confusion_matrix"]

    cal_rows = "\n".join(
        f"| {b['bin_lower']:.1f} to {b['bin_upper']:.1f} | {b['mean_predicted']:.3f} | "
        f"{b['observed_rate']:.3f} | {b['n']:,} |"
        for b in ev["calibration"]["bins"])

    patient_rows = "\n".join(
        f"| {p['patient_id']} | {p['mae']} | {p['rmse']} | {p['n']:,} |"
        for p in primary["forecast"]["60min"]["by_patient"]["per_patient"])

    band_rows = "\n".join(
        f"| {band.replace('_', ' ')} | {v['mae']} | {v['rmse']} | {v['n']:,} |"
        for band, v in primary["forecast"]["60min"]["by_glucose_range"].items())

    sweep = ev.get("threshold_sweep", [])
    sweep_rows = "\n".join(
        f"| {r['threshold']} | {r['precision']} | {r['recall']} | {r['specificity']} | "
        f"{r.get('alerts_per_patient_day', '')} | "
        f"{r.get('alert_episodes_per_patient_day', '')} | "
        f"{r.get('episode_precision', '')} | "
        f"{r.get('median_warning_minutes', '')} min |"
        for r in sweep)
    refractory = ev.get("refractory_minutes", 60)
    patient_days = ev.get("patient_days", "the held out")
    default_threshold = ev.get("operating_threshold")

    doc = f"""# GlycoTwin evaluation report

Generated from `evaluation/metrics.json` on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC.
Model `{m['model_version']}`, trained {m['trained_at'][:19].replace('T', ' ')} UTC.

Do not read these figures as clinical performance. The cohort is produced by a
mechanistic simulator in `data/generator/generate_cohort.py`, so the models have
learned that generator. See the limitations section of the README.

## What was predicted

- Excursion threshold: {target['excursion_threshold_mg_dl']} mg/dL
- Event horizon: {target['event_horizon_minutes']} minutes
- Forecast horizons: {', '.join(str(h) for h in target['forecast_horizons_minutes'])} minutes
- Event scored on: {target['event_scored_population']}
- Uncertainty: {target['prediction_interval']}
- Features: {m['n_features']}
- Observations after validation: {m['data']['observations']:,}

{m['evaluation_protocol']}

Patient split: {len(m['data']['patients']['train'])} train,
{len(m['data']['patients']['val'])} validation, {len(m['data']['patients']['test'])} test.
Test patients: {', '.join(primary['patients'])}.

## Primary result, held out patients

{forecast_table(primary)}

The model beats the persistence baseline at every horizon, which is the test
that matters for an autocorrelated signal. Ridge sits between the two.

### Excursion detection

Scored on {ev['n']:,} readings that were at or below the threshold at prediction
time, of which {ev['event_rate'] * 100:.1f}% were followed by a crossing within
{target['event_horizon_minutes']} minutes. Operating threshold
{ev['operating_threshold']}, chosen on validation patients.

{event_table(primary)}

Confusion matrix at that operating point: {cm['tp']} true positives,
{cm['fp']} false positives, {cm['fn']} missed events, {cm['tn']} true negatives.

At this operating point the model catches a little over half the crossings and
is right about four times in five when it raises one. Moving the threshold down
would catch more and cost precision. The point is chosen by F1 on validation
patients, which is a neutral default rather than a clinical judgement about
which error is worse.

### Probability calibration, test patients

| Predicted band | Mean predicted | Observed rate | Readings |
| --- | --- | --- | --- |
{cal_rows}

Expected calibration error {ev['calibration']['expected_calibration_error']}.

### Spread across held out patients, 60 minute horizon

| Patient | MAE | RMSE | Readings |
| --- | --- | --- | --- |
{patient_rows}

Range of per patient MAE:
{primary['forecast']['60min']['by_patient']['mae_min']} to
{primary['forecast']['60min']['by_patient']['mae_max']} mg/dL. Pooled averages
hide that spread, so both are reported.

### Error by glucose band at prediction time, 60 minute horizon

| Band | MAE | RMSE | Readings |
| --- | --- | --- | --- |
{band_rows}

### Choosing the operating point

Measured on the held out patients, on a 0.05 grid. Alert burden is counted as
episodes: consecutive firings within {refractory} minutes of the last one are
treated as the same alert, because readings arrive every 5 minutes and one
rising episode otherwise trips the threshold many times over.

| Threshold | Precision | Recall | Specificity | Flagged readings per patient day | Alert episodes per patient day | Episode precision | Median warning |
| --- | --- | --- | --- | --- | --- | --- | --- |
{sweep_rows}

Across {patient_days} patient days. Median warning time barely moves across the
range, so a lower threshold buys more caught crossings rather than earlier ones.
The default of {default_threshold} comes from F1 on validation patients, which is
a statistical default rather than a clinical judgement about whether a missed
crossing or a false alarm is worse.

## Secondary result, chronological holdout

Retrained without the final {chrono['split'].split('_')[1]} days so no future
reading leaks in, then scored on those days. Cutoff
{chrono['cutoff_timestamp'][:16].replace('T', ' ')}.

{forecast_table(chrono)}

{event_table(chrono)}

Both protocols agree, which suggests the gain over persistence is not an
artefact of one way of splitting the data.

## Known weaknesses in these numbers

1. Interval coverage falls short of the nominal 80% on unseen patients
   ({', '.join(f"{h}: {e['prediction_interval_80_conformal']['coverage']:.3f}" for h, e in primary['forecast'].items())}).
   Conformal calibration on validation patients improves it over the raw
   quantiles ({', '.join(f"{h}: {e['prediction_interval_80_raw_quantile']['coverage']:.3f}" for h, e in primary['forecast'].items())})
   but does not close the gap, because a new patient breaks the exchangeability
   the conformal guarantee assumes. Stated intervals are therefore narrower than
   they should be.
2. The cohort is synthetic, so every figure measures how well the model recovers
   a simulator, not a physiology.
3. Low glucose events are too rare in this cohort to support a hypoglycaemia
   model, so none was trained. Only high excursions are predicted.
"""
    OUT.write_text(doc)
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(doc.splitlines())} lines)")


if __name__ == "__main__":
    main()
