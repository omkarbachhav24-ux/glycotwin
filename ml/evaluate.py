"""Metric computation for forecasts and excursion events.

All figures reported anywhere in this project come from these functions run
on held out data. Nothing is hand written. competition.txt section 6.3.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score, brier_score_loss, confusion_matrix, f1_score,
    precision_score, recall_score, roc_auc_score,
)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_true, y_pred = y_true[mask], y_pred[mask]
    if len(y_true) == 0:
        return {"n": 0, "mae": None, "rmse": None}
    err = y_pred - y_true
    return {
        "n": int(len(y_true)),
        "mae": round(float(np.mean(np.abs(err))), 3),
        "rmse": round(float(np.sqrt(np.mean(err ** 2))), 3),
        "bias": round(float(np.mean(err)), 3),
    }


def metrics_by_range(y_true: np.ndarray, y_pred: np.ndarray,
                     current: np.ndarray) -> dict:
    """Error split by the glucose band the patient was in at prediction time."""
    bands = {
        "below_140": current < 140,
        "140_to_180": (current >= 140) & (current <= 180),
        "above_180": current > 180,
    }
    return {name: regression_metrics(y_true[m], y_pred[m]) for name, m in bands.items()}


def metrics_by_patient(df: pd.DataFrame, y_col: str, pred_col: str) -> dict:
    """Spread of error across held out patients, not just the pooled average."""
    per = []
    for pid, grp in df.groupby("patient_id"):
        m = regression_metrics(grp[y_col].to_numpy(), grp[pred_col].to_numpy())
        if m["mae"] is not None:
            per.append({"patient_id": pid, "mae": m["mae"], "rmse": m["rmse"], "n": m["n"]})
    maes = [p["mae"] for p in per]
    return {
        "per_patient": per,
        "mae_min": round(float(np.min(maes)), 3) if maes else None,
        "mae_median": round(float(np.median(maes)), 3) if maes else None,
        "mae_max": round(float(np.max(maes)), 3) if maes else None,
    }


def interval_coverage(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> dict:
    mask = ~(np.isnan(y_true) | np.isnan(lower) | np.isnan(upper))
    y_true, lower, upper = y_true[mask], lower[mask], upper[mask]
    if len(y_true) == 0:
        return {"coverage": None, "mean_width": None}
    inside = (y_true >= lower) & (y_true <= upper)
    return {
        "coverage": round(float(inside.mean()), 4),
        "mean_width": round(float(np.mean(upper - lower)), 3),
    }


def calibration_bins(y_true: np.ndarray, prob: np.ndarray, n_bins: int = 10) -> dict:
    """Reliability table plus expected calibration error."""
    edges = np.linspace(0, 1, n_bins + 1)
    idx = np.clip(np.digitize(prob, edges[1:-1]), 0, n_bins - 1)
    rows, ece = [], 0.0
    for b in range(n_bins):
        m = idx == b
        if not m.any():
            continue
        mean_p = float(prob[m].mean())
        frac_pos = float(y_true[m].mean())
        rows.append({
            "bin_lower": round(float(edges[b]), 2),
            "bin_upper": round(float(edges[b + 1]), 2),
            "n": int(m.sum()),
            "mean_predicted": round(mean_p, 4),
            "observed_rate": round(frac_pos, 4),
        })
        ece += (m.sum() / len(prob)) * abs(mean_p - frac_pos)
    return {"bins": rows, "expected_calibration_error": round(float(ece), 4)}


def classification_metrics(y_true: np.ndarray, prob: np.ndarray,
                           threshold: float) -> dict:
    mask = ~(np.isnan(y_true) | np.isnan(prob))
    y_true, prob = y_true[mask].astype(int), prob[mask]
    if len(y_true) == 0 or len(np.unique(y_true)) < 2:
        return {"n": int(len(y_true)), "note": "insufficient class variety"}
    pred = (prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "n": int(len(y_true)),
        "event_rate": round(float(y_true.mean()), 4),
        "operating_threshold": round(float(threshold), 3),
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, pred, zero_division=0)), 4),
        "sensitivity": round(float(tp / (tp + fn)) if (tp + fn) else 0.0, 4),
        "specificity": round(float(tn / (tn + fp)) if (tn + fp) else 0.0, 4),
        "pr_auc": round(float(average_precision_score(y_true, prob)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, prob)), 4),
        "brier_score": round(float(brier_score_loss(y_true, prob)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "calibration": calibration_bins(y_true, prob),
    }


def threshold_sweep(y_true: np.ndarray, prob: np.ndarray,
                    patient_days: float | None = None,
                    step: float = 0.05) -> list[dict]:
    """Performance across candidate alert thresholds.

    A single operating point hides the only question that matters when an
    alert reaches a clinician: how many crossings are caught, and how much
    noise comes with them. This returns the whole curve, including alert
    burden expressed per patient per day, so the choice can be made on
    clinical grounds rather than by whichever threshold maximises F1.
    """
    mask = ~(np.isnan(y_true) | np.isnan(prob))
    y_true, prob = y_true[mask].astype(int), prob[mask]
    if len(y_true) == 0 or len(np.unique(y_true)) < 2:
        return []

    rows = []
    for t in np.arange(step, 1.0, step):
        pred = (prob >= t).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
        row = {
            "threshold": round(float(t), 2),
            "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y_true, pred, zero_division=0)), 4),
            "specificity": round(float(tn / (tn + fp)) if (tn + fp) else 0.0, 4),
            "f1": round(float(f1_score(y_true, pred, zero_division=0)), 4),
            "alerts": int(tp + fp),
            "missed_events": int(fn),
            "alert_rate": round(float((tp + fp) / len(y_true)), 4),
        }
        if patient_days:
            row["alerts_per_patient_day"] = round(float((tp + fp) / patient_days), 2)
            row["missed_per_patient_day"] = round(float(fn / patient_days), 2)
        rows.append(row)
    return rows


def operating_point_analysis(patient_ids: np.ndarray, timestamps, y_true: np.ndarray,
                             prob: np.ndarray, minutes_to_crossing: np.ndarray,
                             patient_days: float, refractory_minutes: int = 60,
                             step: float = 0.05) -> list[dict]:
    """Alert burden and warning time, counted the way a clinician would see them.

    Readings arrive every 5 minutes, so a single rising episode trips the
    threshold many times in a row. Counting each of those as a separate alert
    overstates the burden badly. Here consecutive alerts within
    refractory_minutes of the last one are treated as the same alert, and the
    result is reported as episodes per patient per day alongside the median
    warning time an alert gives before the crossing.
    """
    import pandas as pd

    frame = pd.DataFrame({
        "patient_id": patient_ids,
        "timestamp": pd.to_datetime(timestamps),
        "y": y_true,
        "prob": prob,
        "lead": minutes_to_crossing,
    }).dropna(subset=["y", "prob"]).sort_values(["patient_id", "timestamp"])

    rows = []
    for t in np.arange(step, 1.0, step):
        frame["fired"] = frame["prob"] >= t
        episodes = 0
        true_episodes = 0
        leads: list[float] = []
        for _, grp in frame.groupby("patient_id", sort=False):
            last: pd.Timestamp | None = None
            for ts, fired, y, lead in zip(grp.timestamp, grp.fired, grp.y, grp.lead):
                if not fired:
                    continue
                if last is not None and (ts - last).total_seconds() / 60 < refractory_minutes:
                    continue
                last = ts
                episodes += 1
                if y == 1:
                    true_episodes += 1
                    if not np.isnan(lead):
                        leads.append(float(lead))
        rows.append({
            "threshold": round(float(t), 2),
            "alert_episodes": int(episodes),
            "alert_episodes_per_patient_day": round(episodes / patient_days, 2),
            "true_alert_episodes": int(true_episodes),
            "episode_precision": round(true_episodes / episodes, 4) if episodes else None,
            "median_warning_minutes": round(float(np.median(leads)), 1) if leads else None,
        })
    return rows


def best_f1_threshold(y_true: np.ndarray, prob: np.ndarray) -> float:
    """Pick the operating point on validation data, never on the test set."""
    mask = ~(np.isnan(y_true) | np.isnan(prob))
    y_true, prob = y_true[mask].astype(int), prob[mask]
    best, best_t = -1.0, 0.5
    for t in np.arange(0.05, 0.95, 0.01):
        score = f1_score(y_true, (prob >= t).astype(int), zero_division=0)
        if score > best:
            best, best_t = score, float(t)
    return round(best_t, 2)
