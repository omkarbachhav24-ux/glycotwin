"""Emit synthetic sensor events, including deliberate defects, into the API.

Unlike replay_stream.py this does not follow a recorded series. It perturbs the
recorded values and injects invalid, missing, duplicate and late readings at a
configurable rate, so the validation path and the data quality panel can be
exercised on demand.

    python simulator/generate_stream.py --patient SYNTH-006 --defect-rate 0.2
"""
from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--patient", default="SYNTH-006")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--interval", type=float, default=0.4)
    parser.add_argument("--defect-rate", type=float, default=0.15,
                        help="Share of events carrying an injected defect")
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    df = pd.read_csv(ROOT / "data" / "observations.csv.gz", parse_dates=["timestamp"])
    df = df[df.patient_id == args.patient].sort_values("timestamp").head(args.limit)
    if df.empty:
        raise SystemExit(f"No rows for {args.patient}")

    counts = {"ok": 0, "invalid": 0, "missing_signal": 0, "late": 0, "duplicate": 0}
    previous = None

    with httpx.Client(base_url=args.api, timeout=30) as client:
        for row in df.to_dict(orient="records"):
            payload = {
                "patient_id": args.patient,
                "timestamp": pd.to_datetime(row["timestamp"]).isoformat(),
                "glucose_mg_dl": round(float(row["glucose_mg_dl"]) + rng.gauss(0, 2.5), 1),
                "heart_rate_bpm": _opt(row.get("heart_rate_bpm")),
                "steps_last_5_min": _opt(row.get("steps_last_5_min")),
                "sleep_duration_hours": _opt(row.get("sleep_duration_hours")),
                "minutes_since_meal": _opt(row.get("minutes_since_meal")),
                "last_meal_carbs_g": _opt(row.get("last_meal_carbs_g")),
                "data_source": "simulated",
                "ingest_delay_seconds": 0,
            }

            kind = "ok"
            if rng.random() < args.defect_rate:
                kind = rng.choice(["invalid", "missing_signal", "late", "duplicate"])
                if kind == "invalid":
                    payload["glucose_mg_dl"] = rng.choice([612.0, -4.0, 0.0])
                elif kind == "missing_signal":
                    payload["heart_rate_bpm"] = None
                elif kind == "late":
                    payload["ingest_delay_seconds"] = rng.randint(400, 1800)
                elif kind == "duplicate" and previous is not None:
                    payload["timestamp"] = previous

            res = client.post(f"/api/patients/{args.patient}/observations", json=payload)
            res.raise_for_status()
            body = res.json()
            counts[kind] += 1
            status = "accepted" if body["accepted"] else f"rejected ({body['reason']})"
            print(f"{payload['timestamp']}  {kind:14s} {status}")
            if kind != "duplicate":
                previous = payload["timestamp"]
            time.sleep(args.interval)

    print("\nEvents sent by kind:", counts)


def _opt(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return float(value)


if __name__ == "__main__":
    main()
