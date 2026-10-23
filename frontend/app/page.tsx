"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import GlucoseChart, { buildSeries } from "@/components/GlucoseChart";
import StreamControls from "@/components/StreamControls";
import {
  DataQualityPanel, ExplanationPanel, Panel, PatientOverview, PredictionHistory,
  RiskPanel, ScenarioPanel, TwinTimeline,
} from "@/components/Panels";
import { api } from "@/lib/api";
import OperatingPointPanel from "@/components/OperatingPoint";
import type { TwinView } from "@/components/TwinFigure";
import type { CounterfactualResult, OperatingPoint, PatientSummary } from "@/lib/types";
import { useTwin } from "@/lib/useTwin";

// The 3D view is client only and the heaviest thing on the page, so it loads
// after the clinical content rather than blocking it.
const TwinFigure = dynamic(() => import("@/components/TwinFigure"), {
  ssr: false,
  loading: () => (
    <div style={{ height: 420, display: "grid", placeItems: "center", color: "var(--faint)" }}>
      Loading twin view
    </div>
  ),
});

export default function Dashboard() {
  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [patientId, setPatientId] = useState<string | null>(null);
  const [speed, setSpeed] = useState(5);
  const [busy, setBusy] = useState(false);
  const [scenario, setScenario] = useState<CounterfactualResult | null>(null);
  const [pendingScenario, setPendingScenario] = useState<string | null>(null);
  const [operating, setOperating] = useState<OperatingPoint | null>(null);
  const [operatingBusy, setOperatingBusy] = useState(false);
  const [twinView, setTwinView] = useState<TwinView>("real_3d");

  const twin = useTwin(patientId);

  useEffect(() => {
    api.patients()
      .then((list) => {
        setPatients(list);
        setPatientId((current) => current ?? list[0]?.patient_id ?? null);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => { setScenario(null); }, [patientId]);

  useEffect(() => {
    api.operatingPoint().then(setOperating).catch(() => undefined);
  }, []);

  async function changeThreshold(threshold: number) {
    setOperatingBusy(true);
    try {
      await api.setOperatingPoint(threshold);
      const [next] = await Promise.all([api.operatingPoint(), twin.refresh()]);
      setOperating(next);
    } catch {
      // Leave the panel on its last good value rather than clearing it.
    } finally {
      setOperatingBusy(false);
    }
  }

  const threshold = twin.snapshot?.model.excursion_threshold_mg_dl ?? 180;
  const series = useMemo(
    () => buildSeries(twin.observations, twin.prediction),
    [twin.observations, twin.prediction],
  );

  const running = twin.stream?.running ?? false;
  const mode = twin.stream?.mode ?? "idle";
  const band = twin.prediction?.risk_band ?? "unknown";

  async function start(streamMode: "replay" | "simulate", restart = false) {
    if (!patientId) return;
    setBusy(true);
    try {
      twin.setStream(await api.startStream(patientId, streamMode, speed, restart));
    } finally {
      setBusy(false);
    }
  }

  async function pause() {
    if (!patientId) return;
    setBusy(true);
    try {
      twin.setStream(await api.pauseStream(patientId));
      await twin.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function runScenario(name: string) {
    if (!patientId) return;
    setPendingScenario(name);
    try {
      setScenario(await api.counterfactual(patientId, name, 1));
    } catch {
      setScenario(null);
    } finally {
      setPendingScenario(null);
    }
  }

  const sourceWord =
    mode === "replay" ? "Replayed recording"
      : mode === "simulate" ? "Simulated sensor"
        : "Primed history";

  return (
    <main className="shell">
      <header className="masthead">
        <div className="wordmark">
          <h1 style={{ color: "#0f172a", letterSpacing: "-0.03em" }}>
            GlycoTwin <span style={{ color: "var(--observed)", fontWeight: 500 }}>Apex</span>
          </h1>
          <span style={{ color: "var(--muted)", fontSize: 13, fontWeight: 500 }}>
            Precision Metabolic Digital Twin Console
          </span>
        </div>
        <div className="masthead-right">
          <span className="status-pill">
            <span
              className={`dot ${running ? "live pulsing" : twin.connected ? "live" : "warn"}`}
            />
            {running ? `${sourceWord}, ${speed}x` : twin.connected ? "Connected, idle" : "Offline"}
          </span>
          <label>
            <span style={{ position: "absolute", left: -9999 }}>Patient</span>
            <select
              value={patientId ?? ""}
              onChange={(e) => setPatientId(e.target.value)}
            >
              {patients.map((p) => (
                <option key={p.patient_id} value={p.patient_id}>
                  {p.patient_id}, HbA1c {p.hba1c_percent}%
                </option>
              ))}
            </select>
          </label>
          <Link href="/results">Model results</Link>
        </div>
      </header>

      {twin.error && (
        <ul className="warn-list" style={{ marginTop: 18 }}>
          <li>{twin.error}</li>
        </ul>
      )}

      <div className="hero">
        <section className="panel">
          <div className="panel-head">
            <h2>Patient 3D Twin</h2>
            <span className="note" style={{ color: "var(--observed)", fontWeight: 600 }}>
              Live Endocrine Telemetry
            </span>
          </div>
          <div className="jarvis-hud-container">
            <TwinFigure riskBand={band} streaming={running} />
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Glucose trajectory</h2>
            <span className="note">
              Measured readings and model forecast are plotted separately
            </span>
          </div>
          <div className="panel-body">
            <div className="readout-row" style={{ marginBottom: 18 }}>
              <div>
                <div className="readout-label">Latest measured glucose</div>
                <div className="readout-value mono">
                  {twin.prediction?.current_glucose?.toFixed(0)
                    ?? twin.snapshot?.latest_glucose?.toFixed(0) ?? "--"}
                  <span className="readout-unit">mg/dL</span>
                </div>
              </div>
              {twin.prediction?.forecast.map((f) => (
                <div key={f.horizon_minutes}>
                  <div className="readout-label">Forecast {f.horizon_minutes} min</div>
                  <div className="readout-small mono" style={{ color: "var(--forecast)" }}>
                    {f.point_mg_dl.toFixed(0)}
                    <span style={{ color: "var(--faint)", fontSize: 13, marginLeft: 6 }}>
                      {f.lower_mg_dl.toFixed(0)} to {f.upper_mg_dl.toFixed(0)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <GlucoseChart data={series} threshold={threshold} />
          </div>
        </section>
      </div>

      <div className="grid-2">
        <Panel title="Excursion risk" note={`Chance of crossing ${threshold} mg/dL within 60 minutes`}>
          <RiskPanel prediction={twin.prediction} />
        </Panel>
        <Panel title="What moved this prediction" note="Per prediction feature contributions">
          <ExplanationPanel contributors={twin.prediction?.contributors ?? []} />
        </Panel>
      </div>

      <div style={{ marginTop: 20 }}>
        <Panel
          title="Alert threshold"
          note="Measured on held out patients, not a default to accept blindly"
        >
          <OperatingPointPanel
            data={operating}
            pending={operatingBusy}
            onChange={changeThreshold}
          />
        </Panel>
      </div>

      <div className="grid-2">
        <Panel title="Stream controls" note="Replay, simulate, pause, restart">
          <StreamControls
            stream={twin.stream}
            speed={speed}
            onSpeed={setSpeed}
            onStart={(m) => start(m)}
            onPause={pause}
            onRestart={() => start(mode === "simulate" ? "simulate" : "replay", true)}
            busy={busy || !patientId}
          />
        </Panel>
        <Panel title="Data quality" note="Missing, stale, invalid and late readings">
          {twin.snapshot ? (
            <DataQualityPanel quality={twin.snapshot.data_quality} streamMode={sourceWord} />
          ) : (
            <p className="empty">Connecting to the twin.</p>
          )}
        </Panel>
      </div>

      <div className="grid-2">
        <Panel title="Hypothetical scenarios" note="Model response to changed inputs">
          <ScenarioPanel
            result={scenario}
            pending={pendingScenario}
            onRun={runScenario}
            disabled={!patientId}
          />
        </Panel>
        <Panel title="Patient overview" note="Synthetic EHR on record">
          {twin.snapshot ? (
            <PatientOverview
              profile={twin.snapshot.profile}
              trend={twin.snapshot.trend}
              rolling={twin.snapshot.rolling_glucose}
              historyPoints={twin.snapshot.history_points}
              modelVersion={twin.snapshot.model.version}
            />
          ) : (
            <p className="empty">Connecting to the twin.</p>
          )}
        </Panel>
      </div>

      <div className="grid-2">
        <Panel title="Prediction history" note="Every forecast this twin has produced">
          <PredictionHistory rows={twin.predictions} />
        </Panel>
        <Panel title="Twin timeline" note="Past forecasts against what was measured">
          <TwinTimeline rows={twin.outcomes} />
        </Panel>
      </div>
    </main>
  );
}
