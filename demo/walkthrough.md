# Demo walkthrough

A script for showing GlycoTwin working, mapped to the 20 minute structure in
competition.txt section 19. Everything below runs locally with no network
access and no external data.

Record a full replay rather than relying on a live connection, as section 19
advises, so the demonstration reproduces even if something is unavailable on
the day.

## Before you start

```bash
pip install -r requirements.txt
python data/generator/generate_cohort.py      # about 30 seconds
python -m ml.train                            # about 75 seconds, prints the headline metrics
docker compose up --build
```

Open the console at http://localhost:3000 and the API docs at
http://localhost:8000/docs.

Pick **SYNTH-001** in the patient selector. It is one of the held out test
patients, so nothing shown about it was seen during training.

---

## 0:00 to 2:00, the problem

Stay on the console before touching anything. The first screen already makes
the point: a measured value, three forecasts, and a risk estimate with a reason
attached. Say what the banner says: synthetic data, research prototype, not a
medical device.

Switch the twin panel between **Proportion** and **Standing** once. The first
is the hero, the second is the one to use when explaining where the sensor sits.

## 2:00 to 4:00, the twin and the architecture

Open `architecture/system-architecture.pdf`. Walk the six components left to
right, then the seven step pipeline in the lower band. The point to land:
the twin is state that evolves on every reading, not a dashboard bolted to a
model.

## 4:00 to 6:00, data and privacy

Open `data/README.md`. Cover why the cohort is generated rather than
downloaded, what the generator models, and what it does not. Be direct that
every number later in the demo measures recovery of a simulator.

Show `data/synthetic_examples/SYNTH-001_two_days.csv` for a concrete look at
the input, and `data/cohort_summary.json` for the distribution.

## 6:00 to 9:00, model and evaluation

Open http://localhost:3000/results. Work down the page:

- The target was fixed before training, including the decision to score the
  event only on readings at or below 180 mg/dL.
- Forecast accuracy against the persistence and ridge baselines on unseen
  patients.
- Excursion detection and the calibration table.
- The chronological holdout, which agrees with the patient split.
- Per patient spread, which the pooled averages hide.

Every figure on that page is read from `evaluation/metrics.json` as the
training run wrote it.

## 9:00 to 14:00, the console live

Back on the dashboard. In **Stream controls**, press **Replay recorded data**
at 5x.

Point out as it runs:

- Measured readings extend the solid trace; the dashed forecast and its band
  move ahead of it. They are never merged into one line.
- The risk panel and its explanation update on every reading.
- **What moved this prediction** reorders as the situation changes.
- **Prediction history** fills with every forecast the twin has produced.
- **Twin timeline** starts pairing past forecasts with what was later measured,
  and shows a live MAE on this patient.

Let it run until the twin timeline has 30 or more scored forecasts. On a replay
of a held out patient the live 60 minute MAE lands near the offline figure,
which is the check worth narrating: the running system agrees with the
evaluation.

## 13:00 to 14:30, choosing the alert threshold

Scroll to **Alert threshold**. This is the panel worth lingering on, because it
is where the project stops being a model and starts being a decision.

Move the slider down to 0.10. Crossings caught jumps toward 88%, and alerts per
patient per day climbs to about 8 with only four in ten being true. Move it up
to 0.80 and the alerts fall to roughly 2 per day at 93% true, while well over
half the crossings are missed. Point out that the probability itself never
changed, only the line drawn through it, and that the risk band on the patient
above updates live as the line moves.

Say plainly that the default came from F1 on validation patients, which is a
statistical default and not a clinical judgement, and that choosing properly
needs a clinician. Return to the default before moving on.

## 14:00 to 17:00, ingestion under bad data

Press **Pause**, then **Simulate live sensor**. This mode injects invalid,
missing and late readings on purpose.

Watch the **Data quality** panel. Rejected readings are counted, gaps are
reported, and stale data is called stale. Nothing is filled in with an invented
value.

To show the same thing at the API boundary, from a second terminal:

```bash
python simulator/generate_stream.py --patient SYNTH-006 --defect-rate 0.3
```

Each posted event prints whether it was accepted or rejected and why. Worth
calling out that validation lives in `ml/preprocessing.py` and runs in both
training and serving, so the rules cannot diverge.

## 17:00 to 18:30, explanation, uncertainty, scenarios

- In **Excursion risk**, read the plain language explanation and the projected
  crossing time, and say that it is interpolated off the forecast curve rather
  than produced by a time to event model.
- In the chart, point at the band and state the honest result: the nominal 80%
  interval covers about 75% on unseen patients, and why conformal calibration
  narrows but does not close that gap.
- In **Hypothetical scenarios**, run **Add a brisk walk**. Show the difference
  table, then the input check table underneath showing each modified input
  against the training range, then the hypothetical notice. Say plainly that
  the effect is small and that activity and time of day are confounded in this
  cohort, so this is a model response and not a treatment effect.

## 18:30 to 20:00, results and limitations

Return to the limitations section of `README.md` and read the list. Close on
what would make the next version credible: a licensed CGM dataset under a data
use agreement, an operating point chosen with clinical input rather than F1,
and per patient interval calibration.

---

## If something goes wrong

| Symptom | Cause and fix |
| --- | --- |
| Console shows "Cannot reach the API" | The API is not up yet. Check http://localhost:8000/api/health. |
| Results page says no evaluation results | `python -m ml.train` has not been run, so `evaluation/metrics.json` is missing. |
| API exits on start with a missing artifact error | Same cause. Train before starting the API. |
| Chart is empty on load | The twin was not primed. Restart the API; it primes every patient at startup. |
| Stream will not start | Another stream is running for that patient. Press Pause, then start again. |
