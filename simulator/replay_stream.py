"""Replay recorded synthetic observations into a running GlycoTwin API.

The backend can drive replay itself through POST /api/patients/{id}/stream.
This script does the same thing from outside the process, which is useful for
demonstrating that ingestion is a real HTTP boundary rather than an internal
function call.

Each twin is primed with a warm window when the API starts, so posting events
with earlier timestamps is handled as late arrival: they are placed in
timestamp order and the forecast continues to describe the newest reading the
twin holds.

    python simulator/replay_stream.py --patient SYNTH-004 --limit 200
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--patient", default="SYNTH-004")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--interval", type=float, default=0.4,
                        help="Seconds between posted events")
    parser.add_argument("--source", default=str(ROOT / "data" / "raw_stream.csv.gz"))
    args = parser.parse_args()

    df = pd.read_csv(args.source, parse_dates=["timestamp"])
    df = df[df.patient_id == args.patient].sort_values("timestamp").head(args.limit)
    if df.empty:
        raise SystemExit(f"No rows for {args.patient} in {args.source}")

    accepted = rejected = 0
    with httpx.Client(base_url=args.api, timeout=30) as client:
        for row in df.to_dict(orient="records"):
            payload = {
                "patient_id": args.patient,
                "timestamp": pd.to_datetime(row["timestamp"]).isoformat(),
                "glucose_mg_dl": _opt(row.get("glucose_mg_dl")),
                "heart_rate_bpm": _opt(row.get("heart_rate_bpm")),
                "steps_last_5_min": _opt(row.get("steps_last_5_min")),
                "sleep_duration_hours": _opt(row.get("sleep_duration_hours")),
                "minutes_since_meal": _opt(row.get("minutes_since_meal")),
                "last_meal_carbs_g": _opt(row.get("last_meal_carbs_g")),
                "data_source": "replayed",
                "ingest_delay_seconds": int(row.get("ingest_delay_seconds") or 0),
            }
            res = client.post(f"/api/patients/{args.patient}/observations", json=payload)
            res.raise_for_status()
            body = res.json()
            if body["accepted"]:
                accepted += 1
                pred = body.get("prediction")
                if pred:
                    prob = pred["excursion_probability"]
                    # The forecast always belongs to the newest reading the twin
                    # holds, which is not this event when an older timestamp is
                    # posted into an already warmed window.
                    print(f"sent {payload['timestamp']}  ->  twin at "
                          f"{pred['observation_timestamp']}  "
                          f"{pred['current_glucose']:6.1f} mg/dL  "
                          f"60 min {pred['forecast'][1]['point_mg_dl']:6.1f}  "
                          f"risk {'--' if prob is None else f'{prob:.2f}'} "
                          f"[{pred['risk_band']}]")
            else:
                rejected += 1
                print(f"{payload['timestamp']}  rejected: {body['reason']}")
            time.sleep(args.interval)

    print(f"\nPosted {len(df)} events. Accepted {accepted}, rejected {rejected}.")


def _opt(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return float(value)


if __name__ == "__main__":
    main()
