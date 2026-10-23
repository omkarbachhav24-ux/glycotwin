# Data

Everything in this directory is synthetic. No real patient record, no
de-identified clinical extract, and no licensed research dataset is included or
required.

## Why synthetic rather than OhioT1DM or PhysioNet

The source brief (competition.txt section 12.2) lists OhioT1DM, PhysioNet and
UCI as candidate sources, and notes that OhioT1DM is Type 1 data. Those
datasets need a signed data use agreement, so they cannot be redistributed in a
public repository and cannot be downloaded unattended during a build. This
prototype therefore ships a generator instead, so anyone can reproduce the full
pipeline from a clean checkout with one command.

The trade is stated plainly: a model trained here has learned a simulator. See
the limitations section of the main README.

## Generating the cohort

```bash
python data/generator/generate_cohort.py --patients 40 --days 14 --seed 20261023
```

Outputs, all regenerated deterministically from the seed:

| File | Contents |
| --- | --- |
| `ehr_profiles.csv` | One row per synthetic patient: demographics, HbA1c, medication category, comorbidity, and the simulator parameters used |
| `observations.csv.gz` | Clean 5 minute series: glucose, heart rate, steps, sleep, meal context |
| `raw_stream.csv.gz` | The same series with dropouts, duplicates, out of range values and late arrivals injected |
| `meal_events.csv.gz` | Meal timestamps and carbohydrate estimates |
| `cohort_summary.json` | Row counts and distribution summary for the generated cohort |
| `synthetic_examples/` | Small readable samples committed for inspection |

Models are trained on `observations.csv.gz`. The API replays
`raw_stream.csv.gz`, so the running system receives the defective version and
validation has real work to do.

## What the generator models

Glucose follows a first order lag toward a target built from a per patient
fasting baseline, a slow random walk, a dawn rise, additive meal excursions with
a gamma shaped absorption curve, and a delayed lowering effect from activity.
Sensor noise is added on top of the underlying value. Heart rate, steps and
sleep are generated alongside and share the same daily structure.

Per patient parameters (carbohydrate sensitivity, clearance time, insulin
sensitivity, dawn amplitude) are drawn from HbA1c and BMI, so patients with
worse recorded control show larger and slower post meal excursions.

Resulting cohort at the committed seed: mean 154.6 mg/dL, 19.8% of readings
above 180 mg/dL, 0.05% below 70 mg/dL, with the per patient share above 180
ranging from 0% to 78.5%.

## What the generator does not model

It is a plausible looking curve generator, not physiology. There is no
pharmacokinetic model, no insulin action model, no stress, illness, hormonal
cycle or glycaemic index effect, and no sensor drift, compression low or
calibration error. Medication category is recorded in the profile and used as a
model feature but does not drive the simulated glucose. Low glucose is rare by
construction, which is why no hypoglycaemia model is trained.

## Synthea

The brief suggests Synthea for synthetic EHR records (section 12.1). This
project uses its own generator instead, so that the clinical profile and the
glucose series come from one consistent patient model. Joining a Synthea record
to an unrelated glucose trace would mean asserting that records from different
sources describe the same person, which section 12.2 of the brief warns against.
The `ehr_profiles.csv` schema is close enough to a Synthea patient summary that
swapping the source is a contained change.
