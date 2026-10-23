"""Train the GlycoTwin forecasters and excursion classifier.

Protocol, following competition.txt section 6.3:
  - Patient level holdout is the primary evaluation. Test patients are never
    seen during training, feature selection or threshold selection.
  - A chronological holdout is reported as a secondary check, training on the
    earlier part of each training patient's series and scoring the final days.
  - A persistence baseline and a ridge benchmark are scored on the same rows
    as the gradient boosted models.
  - Adjacent readings from one patient never land on both sides of a split.

Run:  python -m ml.train
"""
from __future__ import annotations

import json
import time
import warnings
from datetime import datetime, timezone

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import Ridge

from . import config, evaluate, feature_engineering as fe, preprocessing

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", message=".*deprecated.*")

LGB_REG_PARAMS = dict(
    objective="l2", learning_rate=0.05, num_leaves=63, min_child_samples=40,
    feature_fraction=0.85, bagging_fraction=0.85, bagging_freq=1,
    lambda_l2=1.0, n_estimators=900, verbose=-1,
)
LGB_CLS_PARAMS = dict(
    objective="binary", learning_rate=0.05, num_leaves=63, min_child_samples=40,
    feature_fraction=0.85, bagging_fraction=0.85, bagging_freq=1,
    lambda_l2=1.0, n_estimators=900, verbose=-1,
)
QUANTILES = {"lower": 0.10, "upper": 0.90}


def split_patients(patient_ids: list[str]) -> dict[str, list[str]]:
    rng = np.random.default_rng(config.SPLIT_SEED)
    ids = sorted(patient_ids)
    shuffled = list(rng.permutation(ids))
    test = sorted(shuffled[: config.N_TEST_PATIENTS])
    val = sorted(shuffled[config.N_TEST_PATIENTS: config.N_TEST_PATIENTS + config.N_VAL_PATIENTS])
    train = sorted(shuffled[config.N_TEST_PATIENTS + config.N_VAL_PATIENTS:])
    return {"train": train, "val": val, "test": test}


def fit_forecasters(train_df, val_df, features, horizons=None):
    """One point model plus two quantile models per horizon."""
    horizons = horizons or config.HORIZONS_MIN
    models = {}
    for horizon in horizons:
        target = f"target_glucose_{horizon}min"
        tr = train_df[train_df[target].notna()]
        va = val_df[val_df[target].notna()]

        point = lgb.LGBMRegressor(**LGB_REG_PARAMS)
        point.fit(tr[features], tr[target],
                  eval_set=[(va[features], va[target])],
                  eval_metric="l1",
                  callbacks=[lgb.early_stopping(60, verbose=False)])
        models[(horizon, "point")] = point

        for name, alpha in QUANTILES.items():
            q = lgb.LGBMRegressor(**{**LGB_REG_PARAMS, "objective": "quantile",
                                     "alpha": alpha, "n_estimators": 500})
            q.fit(tr[features], tr[target],
                  eval_set=[(va[features], va[target])],
                  callbacks=[lgb.early_stopping(50, verbose=False)])
            models[(horizon, name)] = q
        print(f"    horizon {horizon:3d} min  best_iter={point.best_iteration_}")
    return models


def conformal_deltas(models, val_df, features, alpha=0.20) -> dict[int, float]:
    """Conformalized quantile regression widths.

    Raw quantile models under cover on unseen patients, so the interval is
    widened by the (1 - alpha) quantile of the validation conformity score
    max(lower - y, y - upper). Calibration uses validation patients only, and
    the resulting width is applied unchanged to test patients.

    Romano, Patterson and Candes, Conformalized Quantile Regression, 2019.
    """
    deltas = {}
    for horizon in config.HORIZONS_MIN:
        target = f"target_glucose_{horizon}min"
        va = val_df[val_df[target].notna()]
        y = va[target].to_numpy()
        lo = models[(horizon, "lower")].predict(va[features])
        hi = models[(horizon, "upper")].predict(va[features])
        scores = np.maximum(lo - y, y - hi)
        n = len(scores)
        level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
        deltas[horizon] = float(np.quantile(scores, level))
    return deltas


def fit_ridge(train_df, val_df, features, horizon):
    """Simple statistical benchmark. Median imputation, no scaling needed for ridge."""
    target = f"target_glucose_{horizon}min"
    numeric = [f for f in features if train_df[f].dtype.name != "category"]
    tr = train_df[train_df[target].notna()]
    med = tr[numeric].median()
    model = Ridge(alpha=1.0)
    model.fit(tr[numeric].fillna(med), tr[target])
    return model, numeric, med


def fit_classifier(train_df, val_df, features):
    target = "target_excursion_60min"
    tr = train_df[train_df.event_eligible & train_df[target].notna()]
    va = val_df[val_df.event_eligible & val_df[target].notna()]

    clf = lgb.LGBMClassifier(**LGB_CLS_PARAMS)
    clf.fit(tr[features], tr[target].astype(int),
            eval_set=[(va[features], va[target].astype(int))],
            eval_metric="average_precision",
            callbacks=[lgb.early_stopping(60, verbose=False)])

    # Isotonic calibration fitted on validation patients only.
    raw_val = clf.predict_proba(va[features])[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(raw_val, va[target].astype(int))
    calibrated_val = calibrator.predict(raw_val)
    threshold = evaluate.best_f1_threshold(va[target].to_numpy(), calibrated_val)
    print(f"    classifier best_iter={clf.best_iteration_}  operating threshold={threshold}")
    return clf, calibrator, threshold, va


def persistence_forecast(df, horizon):
    """Future glucose equals the latest reading. competition.txt section 6.2."""
    return df["glucose_mg_dl"].to_numpy()


def persistence_event_probability(df):
    """Baseline event rule: extrapolate the last 30 minutes of slope forward.

    Converted to a pseudo probability by a logistic on the projected overshoot
    so it can be scored with the same PR-AUC as the model.
    """
    projected = df["glucose_mg_dl"].to_numpy() + df["glucose_roc_30min"].fillna(0).to_numpy() * 60
    overshoot = projected - config.EXCURSION_THRESHOLD_MG_DL
    return 1.0 / (1.0 + np.exp(-overshoot / 12.0))


def score_split(df, models, ridge_bundle, features, clf, calibrator, threshold,
                label, deltas=None) -> dict:
    # Alert burden is only meaningful per patient per day, so the sweep needs
    # to know how much observation time the split covers.
    span_days = (df.timestamp.max() - df.timestamp.min()).total_seconds() / 86400
    patient_days = max(span_days * df.patient_id.nunique(), 1e-6)
    out = {"split": label, "patients": sorted(df.patient_id.unique().tolist()),
           "forecast": {}, "event": {}}

    for horizon in config.HORIZONS_MIN:
        target = f"target_glucose_{horizon}min"
        sub = df[df[target].notna()].copy()
        y = sub[target].to_numpy()

        sub["pred"] = models[(horizon, "point")].predict(sub[features])
        sub["lower"] = models[(horizon, "lower")].predict(sub[features])
        sub["upper"] = models[(horizon, "upper")].predict(sub[features])
        sub["persistence"] = persistence_forecast(sub, horizon)
        delta = (deltas or {}).get(horizon, 0.0)
        sub["lower_cal"] = sub["lower"] - delta
        sub["upper_cal"] = sub["upper"] + delta

        ridge_model, numeric, med = ridge_bundle[horizon]
        sub["ridge"] = ridge_model.predict(sub[numeric].fillna(med))

        entry = {
            "model_lightgbm": evaluate.regression_metrics(y, sub["pred"].to_numpy()),
            "baseline_persistence": evaluate.regression_metrics(y, sub["persistence"].to_numpy()),
            "baseline_ridge": evaluate.regression_metrics(y, sub["ridge"].to_numpy()),
            "by_glucose_range": evaluate.metrics_by_range(
                y, sub["pred"].to_numpy(), sub["glucose_mg_dl"].to_numpy()),
            "by_patient": evaluate.metrics_by_patient(sub, target, "pred"),
            "prediction_interval_80_raw_quantile": evaluate.interval_coverage(
                y, sub["lower"].to_numpy(), sub["upper"].to_numpy()),
            "prediction_interval_80_conformal": evaluate.interval_coverage(
                y, sub["lower_cal"].to_numpy(), sub["upper_cal"].to_numpy()),
            "conformal_delta_mg_dl": round(float(delta), 3),
        }
        mae_model = entry["model_lightgbm"]["mae"]
        mae_base = entry["baseline_persistence"]["mae"]
        entry["mae_improvement_over_persistence_pct"] = (
            round(100 * (mae_base - mae_model) / mae_base, 2) if mae_base else None)
        out["forecast"][f"{horizon}min"] = entry

    ev = df[df.event_eligible & df.target_excursion_60min.notna()].copy()
    if len(ev):
        prob = calibrator.predict(clf.predict_proba(ev[features])[:, 1])
        y_ev = ev["target_excursion_60min"].to_numpy()
        out["event"]["model_lightgbm_calibrated"] = evaluate.classification_metrics(
            y_ev, prob, threshold)
        base_prob = persistence_event_probability(ev)
        out["event"]["baseline_slope_extrapolation"] = evaluate.classification_metrics(
            y_ev, base_prob, 0.5)
        sweep = evaluate.threshold_sweep(y_ev, prob, patient_days=patient_days)
        episodes = evaluate.operating_point_analysis(
            ev.patient_id.to_numpy(), ev.timestamp.to_numpy(), y_ev, prob,
            ev.get("target_minutes_to_crossing", pd.Series(np.nan, index=ev.index)).to_numpy(),
            patient_days=patient_days)
        by_threshold = {e["threshold"]: e for e in episodes}
        for row in sweep:
            row.update({k: v for k, v in by_threshold.get(row["threshold"], {}).items()
                        if k != "threshold"})
        out["event"]["threshold_sweep"] = sweep
        out["event"]["refractory_minutes"] = 60
        out["event"]["patient_days"] = round(float(patient_days), 1)
    return out


def main() -> None:
    started = time.time()
    print("Loading cohort")
    obs, ehr = preprocessing.load_cohort()
    obs, report = preprocessing.clean_observations(obs)
    print(f"  {report.accepted_rows} observations accepted")

    print("Building features")
    df = fe.build_features(obs, ehr)
    df = fe.add_targets(df)
    features = fe.feature_columns(df)
    print(f"  {len(features)} features")

    splits = split_patients(df.patient_id.unique().tolist())
    print(f"  train={len(splits['train'])} val={len(splits['val'])} test={len(splits['test'])} patients")

    train_df = df[df.patient_id.isin(splits["train"])]
    val_df = df[df.patient_id.isin(splits["val"])]
    test_df = df[df.patient_id.isin(splits["test"])]

    print("Training forecasters (patient level split)")
    models = fit_forecasters(train_df, val_df, features)
    ridge_bundle = {h: fit_ridge(train_df, val_df, features, h) for h in config.HORIZONS_MIN}
    deltas = conformal_deltas(models, val_df, features)
    print("  conformal interval widening (mg/dL): "
          + ", ".join(f"{h}min +-{d:.1f}" for h, d in deltas.items()))

    print("Training excursion classifier")
    clf, calibrator, threshold, _ = fit_classifier(train_df, val_df, features)

    print("Scoring")
    results = {
        "model_version": config.MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "clinical_target": {
            "excursion_threshold_mg_dl": config.EXCURSION_THRESHOLD_MG_DL,
            "event_horizon_minutes": config.EVENT_HORIZON_MIN,
            "forecast_horizons_minutes": config.HORIZONS_MIN,
            "event_scored_population": "readings currently at or below the threshold",
            "prediction_interval": (
                "80 percent, quantile regression at 0.10 and 0.90, widened by "
                "conformal calibration on validation patients"),
        },
        "data": {
            "source": "synthetic_generator_v1, fully simulated cohort",
            "observations": int(report.accepted_rows),
            "validation_report": report.as_dict(),
            "patients": {k: v for k, v in splits.items()},
        },
        "n_features": len(features),
        "features": features,
        "evaluation_protocol": (
            "Primary: patient level holdout, test patients unseen in training and "
            "threshold selection. Secondary: chronological holdout on the final "
            f"{config.CHRONO_HOLDOUT_DAYS} days of the training patients. The operating "
            "threshold comes from validation patients only."
        ),
        "primary_patient_holdout": score_split(
            test_df, models, ridge_bundle, features, clf, calibrator, threshold,
            "test_patients", deltas),
        "validation_patients": score_split(
            val_df, models, ridge_bundle, features, clf, calibrator, threshold,
            "val_patients", deltas),
    }

    # Secondary chronological evaluation, retrained so no future day leaks in.
    print("Chronological holdout retrain")
    cutoff = df.timestamp.max() - pd.Timedelta(days=config.CHRONO_HOLDOUT_DAYS)
    chrono_train = train_df[train_df.timestamp < cutoff]
    chrono_val = val_df[val_df.timestamp < cutoff]
    chrono_test = train_df[train_df.timestamp >= cutoff]
    chrono_models = fit_forecasters(chrono_train, chrono_val, features)
    chrono_ridge = {h: fit_ridge(chrono_train, chrono_val, features, h) for h in config.HORIZONS_MIN}
    chrono_deltas = conformal_deltas(chrono_models, chrono_val, features)
    c_clf, c_cal, c_thr, _ = fit_classifier(chrono_train, chrono_val, features)
    results["secondary_chronological_holdout"] = score_split(
        chrono_test, chrono_models, chrono_ridge, features, c_clf, c_cal, c_thr,
        f"final_{config.CHRONO_HOLDOUT_DAYS}_days_of_training_patients", chrono_deltas)
    results["secondary_chronological_holdout"]["cutoff_timestamp"] = cutoff.isoformat()

    # Observed ranges for the features that what-if scenarios modify. The
    # counterfactual endpoint uses these to flag inputs pushed outside the
    # range the model was trained on, where tree predictions
    # saturate and mean little.
    scenario_features = [
        "steps_sum_30min", "steps_sum_120min", "last_meal_carbs_g",
        "minutes_since_meal", "sleep_duration_hours", "hr_mean_30min",
    ]
    quantiles = {}
    for col in scenario_features:
        if col in train_df.columns:
            series = train_df[col].dropna()
            quantiles[col] = {
                "p01": round(float(series.quantile(0.01)), 2),
                "p50": round(float(series.quantile(0.50)), 2),
                "p90": round(float(series.quantile(0.90)), 2),
                "p99": round(float(series.quantile(0.99)), 2),
                "min": round(float(series.min()), 2),
                "max": round(float(series.max()), 2),
            }
    results["training_feature_ranges"] = quantiles

    importance = sorted(
        zip(features, models[(60, "point")].feature_importances_.tolist()),
        key=lambda x: -x[1])
    results["feature_importance_60min_gain"] = [
        {"feature": f, "importance": int(v)} for f, v in importance[:20]]

    config.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model_version": config.MODEL_VERSION,
        "features": features,
        "forecasters": {f"{h}_{k}": m for (h, k), m in models.items()},
        "classifier": clf,
        "calibrator": calibrator,
        "operating_threshold": threshold,
        "conformal_deltas": deltas,
        "feature_ranges": quantiles,
        "horizons": config.HORIZONS_MIN,
        "excursion_threshold": config.EXCURSION_THRESHOLD_MG_DL,
        "trained_at": results["trained_at"],
    }, config.ARTIFACT_DIR / "glycotwin_models.joblib", compress=3)

    (config.EVAL_DIR / "metrics.json").write_text(json.dumps(results, indent=2))
    print(f"\nDone in {time.time() - started:.1f}s")

    prim = results["primary_patient_holdout"]
    print("\nPatient holdout, unseen patients")
    for h in config.HORIZONS_MIN:
        e = prim["forecast"][f"{h}min"]
        print(f"  {h:3d} min  LightGBM MAE {e['model_lightgbm']['mae']:6.2f}  "
              f"RMSE {e['model_lightgbm']['rmse']:6.2f}   "
              f"persistence MAE {e['baseline_persistence']['mae']:6.2f}   "
              f"improvement {e['mae_improvement_over_persistence_pct']}%")
    for h in config.HORIZONS_MIN:
        e = prim["forecast"][f"{h}min"]
        print(f"  {h:3d} min interval coverage raw "
              f"{e['prediction_interval_80_raw_quantile']['coverage']} -> conformal "
              f"{e['prediction_interval_80_conformal']['coverage']} "
              f"(width {e['prediction_interval_80_conformal']['mean_width']})")
    ev = prim["event"]["model_lightgbm_calibrated"]
    print(f"  event 60 min  PR-AUC {ev['pr_auc']}  precision {ev['precision']}  "
          f"recall {ev['recall']}  spec {ev['specificity']}  ECE "
          f"{ev['calibration']['expected_calibration_error']}")


if __name__ == "__main__":
    main()
