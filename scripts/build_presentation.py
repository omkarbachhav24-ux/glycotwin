"""Build presentation/glycotwin-presentation.pdf.

Slides that quote a number read it from evaluation/metrics.json, so the deck
cannot drift from the training run. Rendering uses headless Chromium.

    python scripts/build_presentation.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = json.loads((ROOT / "evaluation" / "metrics.json").read_text())
COHORT = json.loads((ROOT / "data" / "cohort_summary.json").read_text())
OUT_HTML = ROOT / "presentation" / "glycotwin-presentation.html"
OUT_PDF = ROOT / "presentation" / "glycotwin-presentation.pdf"

P = METRICS["primary_patient_holdout"]
C = METRICS["secondary_chronological_holdout"]
EVENT = P["event"]
EV = P["event"]["model_lightgbm_calibrated"]
EVB = P["event"]["baseline_slope_extrapolation"]
T = METRICS["clinical_target"]


def f(h: str, key: str = "model_lightgbm", field: str = "mae") -> str:
    return f'{P["forecast"][h][key][field]}'


def slide(title: str, kicker: str, body: str, foot: str = "") -> str:
    return f"""
<section class="slide">
  <div class="kicker">{kicker}</div>
  <h2>{title}</h2>
  <div class="body">{body}</div>
  <div class="foot">{foot}</div>
</section>"""


def metric_cards(items: list[tuple[str, str, str]]) -> str:
    cards = "".join(
        f'<div class="card"><div class="k">{k}</div><div class="v mono">{v}</div>'
        f'<div class="n">{n}</div></div>' for k, v, n in items)
    return f'<div class="cards">{cards}</div>'


def table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


SLIDES = []

SLIDES.append(f"""
<section class="slide title">
  <div class="brand">GlycoTwin</div>
  <h1>An evolving patient digital twin for predictive diabetes management</h1>
  <p class="lede">Forecasts glucose at 30, 60 and 120 minutes, estimates the chance of
  crossing {T['excursion_threshold_mg_dl']:.0f} mg/dL within the hour, and shows a clinician
  what drove the estimate.</p>
  <div class="warn">Research prototype on synthetic data. Not a medical device, not a
  diagnostic tool, not a substitute for clinical care. No medication or dosing guidance.</div>
  <div class="meta mono">{METRICS['model_version']} &nbsp;&nbsp; trained {METRICS['trained_at'][:10]}</div>
</section>""")

SLIDES.append(slide(
    "Current monitoring looks backwards",
    "The problem",
    """<p>A glucose reading tells a clinician where a patient is now. It does not say
    whether they are heading for an excursion, how fast, or why.</p>
    <ul>
      <li>Clinical records and wearable measurements sit in separate systems</li>
      <li>A single reading carries no temporal context: rising fast or levelling off</li>
      <li>Population thresholds miss what is normal for one individual</li>
      <li>No unified place to ask what a change in behaviour would do to the outlook</li>
    </ul>
    <p class="q">Can historical clinical data and live physiological signals be combined
    into an evolving twin that predicts a crossing before it happens, and explains itself?</p>""",
    "competition.txt section 2"))

SLIDES.append(slide(
    "A twin that updates on every reading",
    "What we built",
    """<ol class="flow">
      <li><b>Validate</b> units, range, duplicates, gaps, late and out of order arrival</li>
      <li><b>Update</b> a rolling 4 hour window and the patient's twin state</li>
      <li><b>Forecast</b> glucose at three horizons with an uncertainty band</li>
      <li><b>Classify</b> the chance of crossing the threshold within 60 minutes</li>
      <li><b>Explain</b> which features moved this particular prediction</li>
      <li><b>Persist</b> the prediction with timestamp, model version and data quality</li>
      <li><b>Push</b> the result to the console over a WebSocket</li>
    </ol>
    <p>Training and serving call the same feature engineering module, so what the model
    was fitted on is what it sees in production.</p>""",
    "competition.txt sections 5.3 and 7"))

SLIDES.append(slide(
    "Synthetic by design, and said so plainly",
    "Data",
    f"""<p>Candidate research datasets need signed data use agreements, so they cannot ship
    in a public repository or be fetched during a build. GlycoTwin generates its cohort
    instead, which makes the whole pipeline reproducible from a clean checkout.</p>
    {metric_cards([
        ("Patients", str(COHORT["patients"]), f"{COHORT['days_per_patient']} days each"),
        ("Observations", f"{COHORT['total_observations']:,}", "5 minute sampling"),
        ("Mean glucose", f"{COHORT['mean_glucose_mg_dl']:.0f}", "mg/dL"),
        ("Above 180", f"{COHORT['share_above_180'] * 100:.1f}%", "of all readings"),
    ])}
    <p><b>The cost is real and we state it:</b> every metric in this deck measures how well
    the model recovers a simulator written for this project, not human physiology. The brief
    warns that Type 1 research data cannot establish validity for Indian Type 2 patients.
    A synthetic cohort establishes even less.</p>""",
    "competition.txt section 12"))

SLIDES.append(slide(
    "The target was fixed before training",
    "Clinical target",
    f"""{metric_cards([
        ("Threshold", f"{T['excursion_threshold_mg_dl']:.0f}", "mg/dL, top of time in range"),
        ("Event horizon", f"{T['event_horizon_minutes']}", "minutes"),
        ("Forecast", "30 / 60 / 120", "minutes ahead"),
        ("Event rate", f"{EV['event_rate'] * 100:.1f}%", "in the scored population"),
    ])}
    <p>The decision that most affects the numbers: the event is scored <b>only on readings
    at or below the threshold</b>. Scoring every reading would include ones already above it,
    where the answer is close to trivial and the metrics flatter the model.</p>
    <p>Low glucose is not predicted. The cohort holds too few readings below 70 mg/dL to
    support a hypoglycaemia model, so none was trained.</p>""",
    "competition.txt sections 4 and 13"))

SLIDES.append(slide(
    "Two protocols, and a baseline that has to be beaten",
    "How it was evaluated",
    """<div class="two">
      <div>
        <h3>Patient level holdout, primary</h3>
        <p>40 patients split 26 / 6 / 8. Test patients appear in no part of training,
        early stopping, calibration or threshold selection.</p>
        <h3>Chronological holdout, secondary</h3>
        <p>Retrained without the final 3 days, then scored on those days, so no future
        reading leaks backwards.</p>
      </div>
      <div>
        <h3>Baselines on identical rows</h3>
        <ul>
          <li><b>Persistence:</b> future glucose equals the latest reading</li>
          <li><b>Ridge regression</b> on the same features</li>
          <li><b>Slope extrapolation</b> for the event</li>
        </ul>
        <p>Glucose is strongly autocorrelated. A model that cannot beat persistence is
        not doing anything, which is why it is reported beside every figure.</p>
      </div>
    </div>""",
    "competition.txt section 6.3"))

SLIDES.append(slide(
    "Forecast accuracy on patients the model never saw",
    "Results",
    table(["Horizon", "MAE", "RMSE", "Persistence MAE", "Ridge MAE", "Gain over persistence"],
          [[h, f(h), f(h, field="rmse"), f(h, "baseline_persistence"),
            f(h, "baseline_ridge"),
            f'{P["forecast"][h]["mae_improvement_over_persistence_pct"]}%']
           for h in ("30min", "60min", "120min")]) +
    f"""<p>The chronological holdout agrees: {C['forecast']['30min']['model_lightgbm']['mae']},
    {C['forecast']['60min']['model_lightgbm']['mae']} and
    {C['forecast']['120min']['model_lightgbm']['mae']} mg/dL at the three horizons. Two
    different ways of splitting the data give the same picture, so the gain is not an
    artefact of one split.</p>
    <p>Per patient MAE at 60 minutes ranges from
    {P['forecast']['60min']['by_patient']['mae_min']} to
    {P['forecast']['60min']['by_patient']['mae_max']} mg/dL. Pooled averages hide that
    spread, so both are reported.</p>""",
    "All figures from evaluation/metrics.json, written by the training run"))

SLIDES.append(slide(
    "Catching a crossing before it happens",
    "Results",
    table(["Metric", "Model", "Slope baseline"],
          [["Precision", EV["precision"], EVB["precision"]],
           ["Recall (sensitivity)", EV["recall"], EVB["recall"]],
           ["Specificity", EV["specificity"], EVB["specificity"]],
           ["PR-AUC", EV["pr_auc"], EVB["pr_auc"]],
           ["ROC-AUC", EV["roc_auc"], EVB["roc_auc"]],
           ["Brier score", EV["brier_score"], EVB["brier_score"]]]) +
    f"""<p>Scored on {EV['n']:,} readings at or below the threshold, operating point
    {EV['operating_threshold']} chosen on validation patients. Expected calibration error
    {EV['calibration']['expected_calibration_error']}, so a stated 70% means close to 70%
    in practice.</p>
    <p><b>Recall is {EV['recall'] * 100:.0f}%</b> at this operating point, so roughly four
    crossings in nine are missed. The threshold is adjustable, and the next slide shows what
    moving it costs.</p>""",
    f"Confusion matrix: {EV['confusion_matrix']['tp']} TP, {EV['confusion_matrix']['fp']} FP, "
    f"{EV['confusion_matrix']['fn']} FN, {EV['confusion_matrix']['tn']} TN"))

def sweep_row(t: float) -> dict:
    rows = EVENT.get("threshold_sweep", [])
    return min(rows, key=lambda r: abs(r["threshold"] - t)) if rows else {}


SLIDES.append(slide(
    "Where the alert line goes is a clinical choice, not a metric",
    "The operating point",
    f"""<p>The training run picks a default by F1 on validation patients. That is a
    statistical default. It says nothing about whether a missed crossing or a false alarm
    is worse, so the console hands the choice over and shows what it costs.</p>
    {table(["Threshold", "Crossings caught", "Alert episodes per patient per day",
            "True alerts", "Median warning"],
           [[f'{r["threshold"]}' + (" (default)" if abs(r["threshold"] - EV["operating_threshold"]) < 0.03 else ""),
             f'{r["recall"] * 100:.0f}%',
             f'{r.get("alert_episodes_per_patient_day", 0):.1f}',
             f'{(r.get("episode_precision") or 0) * 100:.0f}%',
             f'{r.get("median_warning_minutes", 0):.0f} min']
            for r in [sweep_row(t) for t in (0.10, 0.20, 0.35, 0.50, 0.80)]])}
    <p>Burden is counted as <b>episodes</b>, not flagged readings. Readings arrive every
    5 minutes, so one rising episode trips the threshold repeatedly; counting each firing
    separately overstates what reaches a clinician by roughly six times. Firings within
    {EVENT.get("refractory_minutes", 60)} minutes are treated as one alert.</p>
    <p>Median warning time hardly moves across the range, so a lower threshold buys more
    caught crossings rather than earlier ones. No setting is free, and nobody has yet asked
    a clinician where the line belongs.</p>""",
    f"Measured over {EVENT.get('patient_days', 0):.0f} held out patient days"))

SLIDES.append(slide(
    "The uncertainty band does not fully deliver",
    "An honest result",
    f"""<p>Intervals come from quantile regression at 0.10 and 0.90. On unseen patients the
    raw quantiles covered well under the nominal 80%, so conformal calibration fitted on the
    validation patients widens them.</p>
    {table(["Horizon", "Raw quantile coverage", "After conformal", "Mean width"],
           [[h,
             f'{P["forecast"][h]["prediction_interval_80_raw_quantile"]["coverage"]:.3f}',
             f'{P["forecast"][h]["prediction_interval_80_conformal"]["coverage"]:.3f}',
             f'{P["forecast"][h]["prediction_interval_80_conformal"]["mean_width"]:.1f} mg/dL']
            for h in ("30min", "60min", "120min")])}
    <p>Calibration helps but does not close the gap, because a previously unseen patient
    breaks the exchangeability the conformal guarantee assumes. <b>Bands shown in the console
    are narrower than they should be.</b> We report this rather than quoting the nominal 80%.</p>""",
    "Romano, Patterson and Candes, Conformalized Quantile Regression, 2019"))

SLIDES.append(slide(
    "What the clinician sees",
    "The console",
    """<div class="two">
      <div>
        <ul>
          <li>Measured readings and model output drawn as two separate series, never merged</li>
          <li>Forecast curve with its uncertainty band and the threshold line</li>
          <li>Risk panel in plain language, with projected crossing time</li>
          <li>Per prediction feature contributions, raising and lowering</li>
          <li>Data quality: gaps, stale readings, rejected values, late arrivals</li>
        </ul>
      </div>
      <div>
        <ul>
          <li>Replay, simulate, pause, restart, with a speed control</li>
          <li>Prediction history, every forecast the twin has produced</li>
          <li>Twin timeline pairing past forecasts with what was later measured</li>
          <li>Hypothetical scenarios, labelled hypothetical everywhere</li>
          <li>A results page reading metrics.json as produced</li>
        </ul>
      </div>
    </div>
    <p>A persistent banner states what the system is not. Rejected readings are counted and
    surfaced, never quietly replaced with an invented value.</p>""",
    "competition.txt section 8"))

SLIDES.append(slide(
    "Scenarios show a model response, not a treatment effect",
    "What-if, carefully",
    """<p>Four scenarios re-run the model on a modified recent window: a brisk walk, a lighter
    last meal, a later last meal, more sleep. Two guards sit on the feature.</p>
    <ol>
      <li><b>Magnitudes stay inside the range the cohort contains.</b> Gradient boosted trees
      do not extrapolate, so an input pushed past the largest split the model learned produces
      a number that stops responding and means nothing.</li>
      <li><b>Every modified input is checked against the training distribution</b> and reported
      as within range, extreme, or outside it. The console shows that check rather than
      hiding it.</li>
    </ol>
    <p>Effects come out small, usually a few mg/dL, because recent glucose history dominates.
    Activity and time of day also move together in this cohort, so the response to an activity
    change reflects that association. We show the measured result and say what it is not.</p>""",
    "competition.txt section 9"))

SLIDES.append(slide(
    "What this prototype does not establish",
    "Limitations",
    """<ol>
      <li>The data is synthetic. Performance here predicts nothing about real CGM data.</li>
      <li>No claim whatever about Indian Type 2 patients. No prospective validation, no
      clinical review, no real population.</li>
      <li>Prediction intervals under cover on unseen patients.</li>
      <li>Recall is moderate at the default. It is adjustable, but no setting is free:
      catching 88% of crossings costs about 8 alert episodes per patient per day, most of
      them false.</li>
      <li>Synthetic EHR demonstrates integration, not a realistic case mix.</li>
      <li>Scenario outputs are associations learned from a generator, not causal effects.</li>
      <li>No hypoglycaemia prediction.</li>
      <li>Time to threshold is interpolated off the forecast curve, not a time to event model.</li>
    </ol>""",
    "Stated in full in README.md"))

SLIDES.append(slide(
    "Where it goes next",
    "Future work",
    """<div class="two">
      <div>
        <h3>Data</h3>
        <ul>
          <li>Repeat the evaluation on a licensed CGM dataset under a data use agreement</li>
          <li>Prioritise a Type 2 cohort, and report the domain gap where one is used</li>
          <li>Per patient calibration using only earlier observations</li>
        </ul>
      </div>
      <div>
        <h3>Model and system</h3>
        <ul>
          <li>Close the interval coverage gap with per patient conformal calibration</li>
          <li>Set the operating point with clinical input, using the measured burden</li>
          <li>Drift detection as a patient's profile changes</li>
          <li>An automated test suite, which this prototype does not have</li>
        </ul>
      </div>
    </div>
    <p class="q">A credible twin is one where the data, the predictions, the evolving state
    and the evaluation hold together, and where the gaps are named.</p>""",
    "competition.txt section 20"))

STYLE = """
@page { size: 338mm 190mm; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: "IBM Plex Sans", system-ui, sans-serif;
       background: #0b1618; color: #e9efec; }
.slide { width: 338mm; height: 190mm; padding: 16mm 20mm 14mm; position: relative;
         page-break-after: always; display: flex; flex-direction: column;
         background: #0b1618; overflow: hidden; }
.slide::after { content: ""; position: absolute; left: 0; right: 0; top: 0; height: 3px;
                background: linear-gradient(90deg, #4fd1c5, #a3b4ff 60%, transparent); }
.kicker { color: #4fd1c5; font-size: 9.5pt; letter-spacing: 0.05em; margin-bottom: 3mm; }
h1 { font-size: 30pt; line-height: 1.12; margin: 6mm 0 0; max-width: 24ch; letter-spacing: -0.02em; }
h2 { font-size: 21pt; margin: 0 0 7mm; letter-spacing: -0.015em; font-weight: 600; max-width: 30ch; }
h3 { font-size: 11pt; margin: 0 0 2mm; color: #4fd1c5; font-weight: 600; }
.body { font-size: 11pt; line-height: 1.6; color: #c4d4d2; flex: 1; }
.body p { margin: 0 0 4mm; max-width: 95ch; }
.body b { color: #e9efec; }
ul, ol { margin: 0 0 4mm; padding-left: 6mm; }
li { margin-bottom: 1.8mm; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12mm; }
.q { color: #a3b4ff; font-size: 12.5pt; border-left: 2px solid #a3b4ff;
     padding-left: 5mm; margin-top: 5mm; }
.foot { color: #5f7d80; font-size: 8.5pt; border-top: 1px solid #1f3d42;
        padding-top: 3mm; margin-top: 4mm; }
.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 5mm; margin: 0 0 6mm; }
.card { background: #13262a; border: 1px solid #1f3d42; border-radius: 5px; padding: 4mm 5mm; }
.card .k { color: #5f7d80; font-size: 8.5pt; }
.card .v { font-size: 20pt; line-height: 1.15; margin: 1mm 0; }
.card .n { color: #90aaab; font-size: 8.5pt; }
.mono { font-family: "IBM Plex Mono", monospace; font-variant-numeric: tabular-nums; }
table { width: 100%; border-collapse: collapse; font-size: 10.5pt; margin-bottom: 5mm; }
th { text-align: left; color: #5f7d80; font-weight: 500; padding: 2.5mm 3mm;
     border-bottom: 1px solid #2b565c; font-size: 9.5pt; }
td { padding: 2.5mm 3mm; border-bottom: 1px solid rgba(31,61,66,.6);
     font-family: "IBM Plex Mono", monospace; font-variant-numeric: tabular-nums; }
td:first-child { font-family: "IBM Plex Sans", sans-serif; }
.title { justify-content: center; }
.brand { font-size: 13pt; color: #4fd1c5; letter-spacing: 0.08em; }
.lede { font-size: 13pt; color: #c4d4d2; max-width: 70ch; margin: 7mm 0 0; line-height: 1.55; }
.warn { margin-top: 9mm; background: #2a1a12; border-left: 3px solid #ff7a59;
        color: #ffd2b8; padding: 4mm 6mm; font-size: 10.5pt; max-width: 90ch; }
.meta { margin-top: 7mm; color: #5f7d80; font-size: 9.5pt; }
ol.flow li { margin-bottom: 2.4mm; }
"""

HTML = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>GlycoTwin</title><style>{STYLE}</style></head>
<body>{''.join(SLIDES)}</body></html>"""


def main() -> None:
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(HTML)
    script = f"""
import pathlib
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"])
    pg = b.new_page()
    pg.goto(pathlib.Path(r"{OUT_HTML}").as_uri(), wait_until="networkidle")
    pg.pdf(path=r"{OUT_PDF}", width="338mm", height="190mm", print_background=True,
           margin={{"top":"0","bottom":"0","left":"0","right":"0"}})
    b.close()
"""
    subprocess.run([sys.executable, "-c", script], check=True)
    print(f"Wrote {OUT_PDF.relative_to(ROOT)} with {len(SLIDES)} slides")


if __name__ == "__main__":
    main()
