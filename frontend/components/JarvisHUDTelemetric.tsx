"use client";

import React, { useState, useEffect } from "react";
import type { PatientSummary, Prediction } from "@/lib/types";

interface JarvisHUDTelemetricProps {
  prediction: Prediction | null;
  patient: PatientSummary | null;
  streaming: boolean;
  activeOrgan?: string | null;
  onTriggerDiagnosis?: () => void;
  onVoiceScan?: () => void;
}

export default function JarvisHUDTelemetric({
  prediction,
  patient,
  streaming,
  activeOrgan,
}: JarvisHUDTelemetricProps) {
  const [pulseBeat, setPulseBeat] = useState(72);
  const [neuromorphicLoad, setNeuromorphicLoad] = useState(94.2);
  const [audioScanning, setAudioScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState(100);

  // Dynamic heart rate and neural processor simulation
  useEffect(() => {
    const interval = setInterval(() => {
      setPulseBeat(Math.floor(68 + Math.random() * 8));
      setNeuromorphicLoad(+(92 + Math.random() * 6).toFixed(1));
    }, 2200);
    return () => clearInterval(interval);
  }, []);

  const triggerDeepScan = () => {
    setAudioScanning(true);
    setScanProgress(0);
    const step = setInterval(() => {
      setScanProgress((prev) => {
        if (prev >= 100) {
          clearInterval(step);
          setAudioScanning(false);
          return 100;
        }
        return prev + 20;
      });
    }, 250);
  };

  const curr = prediction?.current_glucose ?? patient?.baseline_fasting_glucose ?? 135;
  const prob = prediction ? Math.round(prediction.excursion_probability * 100) : 18;
  const riskClass = prob > 50 ? "critical" : prob > 25 ? "warning" : "nominal";

  return (
    <div className="jarvis-hud-overlay">
      {/* 1. TOP TELEMETRY RIBBON */}
      <div className="hud-top-ribbon">
        <div className="hud-metric-pill">
          <span className="hud-tag">STATUS</span>
          <span className="hud-val hud-glow-cyan">
            {streaming ? "LIVE TELEMETRY FEED" : "STANDBY / CACHED"}
          </span>
        </div>

        <div className="hud-metric-pill">
          <span className="hud-tag">NEURAL LOAD</span>
          <span className="hud-val mono">{neuromorphicLoad}%</span>
        </div>

        <div className="hud-metric-pill">
          <span className="hud-tag">VASCULAR BPM</span>
          <span className="hud-val mono" style={{ color: "#ff3366" }}>
            ♥ {pulseBeat}
          </span>
        </div>

        <div className="hud-metric-pill">
          <span className="hud-tag">ACTIVE NODE</span>
          <span className="hud-val hud-glow-amber">
            {activeOrgan ? activeOrgan.toUpperCase() : "PANCREAS / ISLETS"}
          </span>
        </div>
      </div>

      {/* 2. LATERAL BIO-METRIC HUD BRACKETS */}
      <div className="hud-lateral-left">
        <div className="hud-reticle-box">
          <div className="hud-box-title">ENDOCRINE CORE // B-CELL</div>
          <div className="hud-stat-line">
            <span>INSULIN SENSITIVITY:</span>
            <span className="mono" style={{ color: "var(--forecast)" }}>0.82 U/h</span>
          </div>
          <div className="hud-stat-line">
            <span>GLUCOSE VELOCITY:</span>
            <span className="mono" style={{ color: curr > 160 ? "var(--alert)" : "var(--observed)" }}>
              {prediction?.trend?.rate_mg_dl_per_min !== null
                ? `${prediction?.trend?.rate_mg_dl_per_min?.toFixed(2)} mg/dL/m`
                : "+0.15 mg/dL/m"}
            </span>
          </div>
          <div className="hud-bar-container">
            <div
              className="hud-bar-fill"
              style={{
                width: `${Math.min(100, (curr / 240) * 100)}%`,
                background: curr > 180 ? "var(--alert)" : "var(--observed)",
              }}
            />
          </div>
        </div>

        {/* Diagnostic Command Trigger */}
        <button
          className="btn tiny hud-scan-btn"
          onClick={triggerDeepScan}
          disabled={audioScanning}
          style={{ width: "100%", marginTop: 8 }}
        >
          {audioScanning ? `SCANNING MATRIX ${scanProgress}%` : "⚡ RUN JARVIS BIO-SCAN"}
        </button>
      </div>

      <div className="hud-lateral-right">
        <div className="hud-reticle-box">
          <div className="hud-box-title">EXCURSION TRAJECTORY</div>
          <div className="hud-hero-stat">
            <span className="hud-hero-num mono" style={{ color: prob > 40 ? "var(--alert)" : "var(--observed)" }}>
              {prob}%
            </span>
            <span className="hud-hero-sub">P(&gt;180 in 60m)</span>
          </div>
          <div className="hud-risk-indicator">
            <span className={`hud-badge ${riskClass}`}>
              RISK: {prediction?.risk_band?.toUpperCase() ?? "NOMINAL"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
