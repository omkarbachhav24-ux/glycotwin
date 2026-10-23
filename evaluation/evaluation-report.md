# GlycoTwin evaluation report

Generated from `evaluation/metrics.json` on 2026-10-23 12:21 UTC.
Model `glycotwin-0.1.0`, trained 2026-10-23 11:59:10 UTC.

Do not read these figures as clinical performance. The cohort is produced by a
mechanistic simulator in `data/generator/generate_cohort.py`, so the models have
learned that generator. See the limitations section of the README.

## What was predicted

- Excursion threshold: 180.0 mg/dL
- Event horizon: 60 minutes
- Forecast horizons: 30, 60, 120 minutes
- Event scored on: readings currently at or below the threshold
- Uncertainty: 80 percent, quantile regression at 0.10 and 0.90, widened by conformal calibration on validation patients
- Features: 44
- Observations after validation: 161,280

Primary: patient level holdout, test patients unseen in training and threshold selection. Secondary: chronological holdout on the final 3 days of the training patients. The operating threshold comes from validation patients only.

Patient split: 26 train,
6 validation, 8 test.
Test patients: SYNTH-001, SYNTH-005, SYNTH-011, SYNTH-013, SYNTH-021, SYNTH-029, SYNTH-031, SYNTH-033.

## Primary result, held out patients

| Horizon | MAE | RMSE | Persistence MAE | Ridge MAE | Gain over persistence | 80% interval coverage |
| --- | --- | --- | --- | --- | --- | --- |
| 30min | 6.269 | 8.437 | 10.645 | 8.044 | 41.11% | 0.765 |
| 60min | 11.439 | 16.471 | 17.265 | 13.09 | 33.74% | 0.758 |
| 120min | 16.119 | 22.229 | 24.883 | 17.156 | 35.22% | 0.749 |

The model beats the persistence baseline at every horizon, which is the test
that matters for an autocorrelated signal. Ridge sits between the two.

### Excursion detection

Scored on 27,168 readings that were at or below the threshold at prediction
time, of which 11.8% were followed by a crossing within
60 minutes. Operating threshold
0.34, chosen on validation patients.

| Metric | LightGBM, calibrated | Slope extrapolation baseline |
| --- | --- | --- |
| Precision | 0.7951 | 0.4891 |
| Recall (sensitivity) | 0.5592 | 0.3476 |
| Specificity | 0.9806 | 0.9512 |
| F1 | 0.6566 | 0.4064 |
| PR-AUC | 0.7619 | 0.4237 |
| ROC-AUC | 0.9448 | 0.7729 |
| Brier score | 0.0527 | 0.0972 |
| Expected calibration error | 0.0179 | not applicable |

Confusion matrix at that operating point: 1800 true positives,
464 false positives, 1419 missed events, 23485 true negatives.

At this operating point the model catches a little over half the crossings and
is right about four times in five when it raises one. Moving the threshold down
would catch more and cost precision. The point is chosen by F1 on validation
patients, which is a neutral default rather than a clinical judgement about
which error is worse.

### Probability calibration, test patients

| Predicted band | Mean predicted | Observed rate | Readings |
| --- | --- | --- | --- |
| 0.0 to 0.1 | 0.020 | 0.019 | 20,945 |
| 0.1 to 0.2 | 0.124 | 0.217 | 2,859 |
| 0.2 to 0.3 | 0.237 | 0.370 | 917 |
| 0.3 to 0.4 | 0.354 | 0.375 | 315 |
| 0.4 to 0.5 | 0.447 | 0.536 | 250 |
| 0.5 to 0.6 | 0.546 | 0.596 | 178 |
| 0.6 to 0.7 | 0.631 | 0.539 | 76 |
| 0.7 to 0.8 | 0.748 | 0.726 | 434 |
| 0.8 to 0.9 | 0.855 | 0.842 | 120 |
| 0.9 to 1.0 | 0.952 | 0.977 | 1,074 |

Expected calibration error 0.0179.

### Spread across held out patients, 60 minute horizon

| Patient | MAE | RMSE | Readings |
| --- | --- | --- | --- |
| SYNTH-001 | 11.783 | 18.376 | 4,020 |
| SYNTH-005 | 10.773 | 15.191 | 4,020 |
| SYNTH-011 | 11.406 | 17.435 | 4,020 |
| SYNTH-013 | 10.02 | 13.872 | 4,020 |
| SYNTH-021 | 11.955 | 16.699 | 4,020 |
| SYNTH-029 | 14.121 | 17.489 | 4,020 |
| SYNTH-031 | 10.234 | 14.715 | 4,020 |
| SYNTH-033 | 11.223 | 17.445 | 4,020 |

Range of per patient MAE:
10.02 to
14.121 mg/dL. Pooled averages
hide that spread, so both are reported.

### Error by glucose band at prediction time, 60 minute horizon

| Band | MAE | RMSE | Readings |
| --- | --- | --- | --- |
| below 140 | 12.03 | 16.841 | 13,347 |
| 140 to 180 | 10.916 | 16.145 | 13,821 |
| above 180 | 11.309 | 16.367 | 4,992 |

### Choosing the operating point

Measured on the held out patients, on a 0.05 grid. Alert burden is counted as
episodes: consecutive firings within 60 minutes of the last one are
treated as the same alert, because readings arrive every 5 minutes and one
rising episode otherwise trips the threshold many times over.

| Threshold | Precision | Recall | Specificity | Flagged readings per patient day | Alert episodes per patient day | Episode precision | Median warning |
| --- | --- | --- | --- | --- | --- | --- | --- |


Across the held out patient days. Median warning time barely moves across the
range, so a lower threshold buys more caught crossings rather than earlier ones.
The default of 0.34 comes from F1 on validation patients, which is
a statistical default rather than a clinical judgement about whether a missed
crossing or a false alarm is worse.

## Secondary result, chronological holdout

Retrained without the final 3 days so no future
reading leaks in, then scored on those days. Cutoff
2026-09-11 23:55.

| Horizon | MAE | RMSE | Persistence MAE | Ridge MAE | Gain over persistence | 80% interval coverage |
| --- | --- | --- | --- | --- | --- | --- |
| 30min | 5.413 | 7.284 | 9.636 | 7.547 | 43.83% | 0.834 |
| 60min | 10.142 | 14.515 | 15.694 | 12.583 | 35.38% | 0.824 |
| 120min | 14.422 | 20.185 | 22.262 | 16.194 | 35.22% | 0.813 |

| Metric | LightGBM, calibrated | Slope extrapolation baseline |
| --- | --- | --- |
| Precision | 0.7371 | 0.4706 |
| Recall (sensitivity) | 0.6702 | 0.284 |
| Specificity | 0.9556 | 0.9406 |
| F1 | 0.7021 | 0.3543 |
| PR-AUC | 0.7823 | 0.4077 |
| ROC-AUC | 0.9459 | 0.787 |
| Brier score | 0.0633 | 0.1233 |
| Expected calibration error | 0.0212 | not applicable |

Both protocols agree, which suggests the gain over persistence is not an
artefact of one way of splitting the data.

## Known weaknesses in these numbers

1. Interval coverage falls short of the nominal 80% on unseen patients
   (30min: 0.765, 60min: 0.758, 120min: 0.749).
   Conformal calibration on validation patients improves it over the raw
   quantiles (30min: 0.690, 60min: 0.654, 120min: 0.652)
   but does not close the gap, because a new patient breaks the exchangeability
   the conformal guarantee assumes. Stated intervals are therefore narrower than
   they should be.
2. The cohort is synthetic, so every figure measures how well the model recovers
   a simulator, not a physiology.
3. Low glucose events are too rare in this cohort to support a hypoglycaemia
   model, so none was trained. Only high excursions are predicted.
