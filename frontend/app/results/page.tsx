"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Panel } from "@/components/Panels";

/*
  Every number on this page is read from evaluation/metrics.json, written by
  ml/train.py on the last run. Nothing is typed in by hand.
  competition.txt section 14 asks for evidence, not targets.
*/

interface Metrics { [key: string]: any }

function Forecast({ block }: { block: Metrics }) {
  const horizons = Object.keys(block.forecast ?? {});
  return (
    <table>
      <thead>
        <tr>
          <th>Horizon</th>
          <th>MAE</th>
          <th>RMSE</th>
          <th>Persistence MAE</th>
          <th>Ridge MAE</th>
          <th>Better than persistence</th>
          <th>80% interval covers</th>
        </tr>
      </thead>
      <tbody>
        {horizons.map((h) => {
          const e = block.forecast[h];
          return (
            <tr key={h}>
              <td className="mono">{h}</td>
              <td className="mono">{e.model_lightgbm.mae}</td>
              <td className="mono">{e.model_lightgbm.rmse}</td>
              <td className="mono" style={{ color: "var(--faint)" }}>
                {e.baseline_persistence.mae}
              </td>
              <td className="mono" style={{ color: "var(--faint)" }}>
                {e.baseline_ridge.mae}
              </td>
              <td className="mono" style={{ color: "var(--observed)" }}>
                {e.mae_improvement_over_persistence_pct}%
              </td>
              <td className="mono">
                {(e.prediction_interval_80_conformal.coverage * 100).toFixed(1)}%
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Event({ block }: { block: Metrics }) {
  const m = block.event?.model_lightgbm_calibrated;
  const b = block.event?.baseline_slope_extrapolation;
  if (!m) return <p className="empty">No event metrics in this split.</p>;
  const rows: [string, string | number, string | number][] = [
    ["Precision", m.precision, b?.precision ?? "--"],
    ["Recall (sensitivity)", m.recall, b?.recall ?? "--"],
    ["Specificity", m.specificity, b?.specificity ?? "--"],
    ["F1", m.f1, b?.f1 ?? "--"],
    ["PR-AUC", m.pr_auc, b?.pr_auc ?? "--"],
    ["ROC-AUC", m.roc_auc, b?.roc_auc ?? "--"],
    ["Brier score", m.brier_score, b?.brier_score ?? "--"],
    ["Calibration error", m.calibration.expected_calibration_error, "--"],
  ];
  return (
    <>
      <div className="metric-strip" style={{ marginTop: 0, borderTop: "none", paddingTop: 0 }}>
        <div><div className="k">Scored rows</div><div className="v mono">{m.n.toLocaleString()}</div></div>
        <div><div className="k">Event rate</div><div className="v mono">{(m.event_rate * 100).toFixed(1)}%</div></div>
        <div><div className="k">Operating threshold</div><div className="v mono">{m.operating_threshold}</div></div>
      </div>
      <table style={{ marginTop: 16 }}>
        <thead>
          <tr><th>Metric</th><th>Model</th><th>Slope baseline</th></tr>
        </thead>
        <tbody>
          {rows.map(([k, v, bv]) => (
            <tr key={k}>
              <td>{k}</td>
              <td className="mono">{v}</td>
              <td className="mono" style={{ color: "var(--faint)" }}>{bv}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="footnote">
        Confusion matrix at the operating threshold: {m.confusion_matrix.tp} true positives,{" "}
        {m.confusion_matrix.fp} false positives, {m.confusion_matrix.fn} missed events,{" "}
        {m.confusion_matrix.tn} true negatives.
      </p>
    </>
  );
}

function Calibration({ bins }: { bins: Metrics[] }) {
  return (
    <table>
      <thead>
        <tr><th>Predicted probability</th><th>Observed rate</th><th>Readings</th></tr>
      </thead>
      <tbody>
        {bins.map((b) => (
          <tr key={`${b.bin_lower}-${b.bin_upper}`}>
            <td className="mono">{b.bin_lower.toFixed(1)} to {b.bin_upper.toFixed(1)}</td>
            <td className="mono">{(b.observed_rate * 100).toFixed(1)}%</td>
            <td className="mono" style={{ color: "var(--faint)" }}>{b.n.toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function Results() {
  const [m, setM] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.metrics().then(setM).catch(() => setError(
      "No evaluation results available. Run python -m ml.train, then reload."));
  }, []);

  if (error) {
    return (
      <main className="shell">
        <header className="masthead">
          <div className="wordmark"><h1>Model results</h1></div>
          <Link href="/">Back to console</Link>
        </header>
        <ul className="warn-list" style={{ marginTop: 20 }}><li>{error}</li></ul>
      </main>
    );
  }
  if (!m) {
    return (
      <main className="shell">
        <p className="empty" style={{ marginTop: 40 }}>Loading results.</p>
      </main>
    );
  }

  const primary = m.primary_patient_holdout;
  const chrono = m.secondary_chronological_holdout;
  const target = m.clinical_target;

  return (
    <main className="shell">
      <header className="masthead">
        <div className="wordmark">
          <h1>Model results</h1>
          <span>Measured on held out data, written by the training run</span>
        </div>
        <div className="masthead-right">
          <span className="status-pill mono">{m.model_version}</span>
          <Link href="/">Back to console</Link>
        </div>
      </header>

      <div style={{ marginTop: 22 }}>
        <Panel title="What the model predicts" note="Fixed before training">
          <div className="metric-strip" style={{ marginTop: 0, borderTop: "none", paddingTop: 0 }}>
            <div>
              <div className="k">Excursion threshold</div>
              <div className="v mono">{target.excursion_threshold_mg_dl} mg/dL</div>
            </div>
            <div>
              <div className="k">Event horizon</div>
              <div className="v mono">{target.event_horizon_minutes} min</div>
            </div>
            <div>
              <div className="k">Forecast horizons</div>
              <div className="v mono">{target.forecast_horizons_minutes.join(", ")} min</div>
            </div>
            <div>
              <div className="k">Features</div>
              <div className="v mono">{m.n_features}</div>
            </div>
            <div>
              <div className="k">Observations</div>
              <div className="v mono">{m.data.observations.toLocaleString()}</div>
            </div>
          </div>
          <p style={{ marginTop: 14, marginBottom: 0 }}>
            The event is scored only on {target.event_scored_population}, so the task is
            predicting a crossing rather than restating a reading that is already high.
          </p>
          <p className="footnote">{m.evaluation_protocol}</p>
        </Panel>
      </div>

      <div style={{ marginTop: 20 }}>
        <Panel
          title="Forecast accuracy, unseen patients"
          note={`Test patients: ${primary.patients.join(", ")}`}
        >
          <Forecast block={primary} />
          <p className="footnote">
            Intervals are quantile regression widened by conformal calibration on the
            validation patients. Coverage lands below the nominal 80% on patients the model
            has never seen, which is the honest result and is noted as a limitation in the
            README.
          </p>
        </Panel>
      </div>

      <div className="grid-2">
        <Panel title="Excursion detection, unseen patients" note="At the chosen operating point">
          <Event block={primary} />
        </Panel>
        <Panel title="Probability calibration" note="Predicted against observed, test patients">
          <Calibration bins={primary.event.model_lightgbm_calibrated.calibration.bins} />
          <p className="footnote">
            Expected calibration error{" "}
            {primary.event.model_lightgbm_calibrated.calibration.expected_calibration_error}.
            Lower means the stated probability matches how often the event happened.
          </p>
        </Panel>
      </div>

      <div style={{ marginTop: 20 }}>
        <Panel
          title="Chronological holdout"
          note={`Final days of the training patients, cut at ${new Date(chrono.cutoff_timestamp).toLocaleDateString()}`}
        >
          <Forecast block={chrono} />
          <p className="footnote">
            A second protocol on the same pipeline, retrained without the held out days so
            no future reading leaks in. Results agree with the patient level split, which
            suggests the gain is not an artefact of one way of splitting.
          </p>
        </Panel>
      </div>

      <div className="grid-2">
        <Panel title="Per patient spread, 60 minutes" note="Pooled averages hide variation">
          <table>
            <thead><tr><th>Patient</th><th>MAE</th><th>RMSE</th><th>Readings</th></tr></thead>
            <tbody>
              {primary.forecast["60min"].by_patient.per_patient.map((p: Metrics) => (
                <tr key={p.patient_id}>
                  <td className="mono">{p.patient_id}</td>
                  <td className="mono">{p.mae}</td>
                  <td className="mono">{p.rmse}</td>
                  <td className="mono" style={{ color: "var(--faint)" }}>{p.n.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel title="Most used features" note="Split gain, 60 minute forecaster">
          <table>
            <thead><tr><th>Feature</th><th>Importance</th></tr></thead>
            <tbody>
              {m.feature_importance_60min_gain.slice(0, 12).map((f: Metrics) => (
                <tr key={f.feature}>
                  <td>{f.feature.replace(/_/g, " ")}</td>
                  <td className="mono" style={{ color: "var(--faint)" }}>{f.importance}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>

      <div style={{ marginTop: 20 }}>
        <Panel title="Error by glucose band, 60 minutes" note="Where the model is weakest">
          <table>
            <thead><tr><th>Glucose at prediction time</th><th>MAE</th><th>RMSE</th><th>Readings</th></tr></thead>
            <tbody>
              {Object.entries(primary.forecast["60min"].by_glucose_range).map(
                ([band, v]: [string, any]) => (
                  <tr key={band}>
                    <td>{band.replace(/_/g, " ")} mg/dL</td>
                    <td className="mono">{v.mae ?? "--"}</td>
                    <td className="mono">{v.rmse ?? "--"}</td>
                    <td className="mono" style={{ color: "var(--faint)" }}>
                      {v.n?.toLocaleString() ?? 0}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
          <p className="footnote">
            Error is broadly flat across the three bands, so the model is not markedly
            worse in the range where an excursion is being decided. Trained{" "}
            {new Date(m.trained_at).toLocaleString()} on a fully synthetic cohort, which
            bounds what any of these numbers can mean.
          </p>
        </Panel>
      </div>
    </main>
  );
}
