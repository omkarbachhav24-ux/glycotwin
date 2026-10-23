"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, wsUrl } from "./api";
import type {
  Observation, Prediction, PredictionRow, StreamStatus, TwinSnapshot,
} from "./types";

const MAX_POINTS = 220;   // about 18 hours at 5 minute sampling

interface TwinLive {
  snapshot: TwinSnapshot | null;
  observations: Observation[];
  prediction: Prediction | null;
  predictions: PredictionRow[];
  outcomes: Record<string, number | string | null>[];
  stream: StreamStatus | null;
  connected: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  setStream: (s: StreamStatus) => void;
}

export function useTwin(patientId: string | null): TwinLive {
  const [snapshot, setSnapshot] = useState<TwinSnapshot | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [predictions, setPredictions] = useState<PredictionRow[]>([]);
  const [outcomes, setOutcomes] = useState<Record<string, number | string | null>[]>([]);
  const [stream, setStream] = useState<StreamStatus | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socket = useRef<WebSocket | null>(null);
  const dirty = useRef(false);

  const refresh = useCallback(async () => {
    if (!patientId) return;
    try {
      const [snap, obs, preds, outs] = await Promise.all([
        api.twin(patientId),
        api.observations(patientId, 8),
        api.predictions(patientId, 60),
        api.outcomes(patientId, 80),
      ]);
      setSnapshot(snap);
      setObservations(obs);
      setPrediction(snap.latest_prediction);
      setPredictions(preds);
      setOutcomes(outs);
      setStream(snap.stream);
      setError(null);
    } catch (e) {
      setError(
        e instanceof Error
          ? `Cannot reach the API. Start the backend, then reload. (${e.message})`
          : "Cannot reach the API.",
      );
    }
  }, [patientId]);

  useEffect(() => {
    setSnapshot(null);
    setObservations([]);
    setPrediction(null);
    setPredictions([]);
    setOutcomes([]);
    void refresh();
  }, [patientId, refresh]);

  // Live updates. Each accepted event appends one observation and replaces the
  // current prediction, so the console reflects the twin without polling.
  useEffect(() => {
    if (!patientId) return;
    let closed = false;
    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl(patientId));
    } catch {
      return;
    }
    socket.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => { if (!closed) setConnected(false); };
    ws.onerror = () => setConnected(false);
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data as string);
      if (msg.type === "snapshot") {
        setStream(msg.snapshot.stream);
        return;
      }
      if (msg.type === "stream_error") {
        setError(`Stream stopped: ${msg.message}`);
        setStream(msg.status);
        return;
      }
      if (msg.type === "stream_complete") {
        setStream(msg.status);
        void refresh();
        return;
      }
      if (msg.type !== "twin_update") return;

      setStream(msg.status);
      if (msg.data_quality) {
        setSnapshot((prev) => (prev ? { ...prev, data_quality: msg.data_quality, trend: msg.trend } : prev));
      }
      if (msg.accepted && msg.observation?.glucose_mg_dl != null) {
        setObservations((prev) => {
          const next = [...prev, {
            timestamp: msg.observation.timestamp,
            glucose_mg_dl: msg.observation.glucose_mg_dl,
            heart_rate_bpm: msg.observation.heart_rate_bpm ?? null,
            steps_last_5_min: msg.observation.steps_last_5_min ?? null,
            minutes_since_meal: msg.observation.minutes_since_meal ?? null,
            data_source: msg.observation.data_source ?? "simulated",
          } as Observation];
          return next.slice(-MAX_POINTS);
        });
      }
      if (msg.prediction) {
        setPrediction(msg.prediction);
        setPredictions((prev) => [{
          generated_at: msg.prediction.generated_at,
          observation_timestamp: msg.prediction.observation_timestamp,
          model_version: msg.prediction.model_version,
          current_glucose: msg.prediction.current_glucose,
          forecast: Object.fromEntries(msg.prediction.forecast.map((f: any) => [
            String(f.horizon_minutes),
            { point: f.point_mg_dl, lower: f.lower_mg_dl, upper: f.upper_mg_dl },
          ])),
          excursion_probability: msg.prediction.excursion_probability,
          excursion_predicted: msg.prediction.excursion_predicted,
          time_to_threshold_minutes: msg.prediction.time_to_threshold_minutes,
          risk_band: msg.prediction.risk_band,
          data_quality_status: msg.prediction.data_quality?.status ?? null,
        } as PredictionRow, ...prev].slice(0, 80));
      }
      dirty.current = true;
    };

    return () => {
      closed = true;
      ws.close();
      socket.current = null;
    };
  }, [patientId, refresh]);

  // The twin timeline needs forecasts paired with later measurements, which the
  // server computes. Refresh it on a slow cadence while a stream is running
  // rather than on every event.
  useEffect(() => {
    if (!patientId) return;
    const id = setInterval(() => {
      if (!dirty.current) return;
      dirty.current = false;
      api.outcomes(patientId, 80).then(setOutcomes).catch(() => undefined);
    }, 6000);
    return () => clearInterval(id);
  }, [patientId]);

  return {
    snapshot, observations, prediction, predictions, outcomes, stream,
    connected, error, refresh, setStream,
  };
}
