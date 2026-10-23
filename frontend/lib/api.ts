import type {
  CounterfactualResult, Observation, OperatingPoint, PatientSummary, PredictionRow,
  StreamStatus, TwinSnapshot,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} on ${path}`);
  return res.json() as Promise<T>;
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} on ${path}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} on ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  patients: () => get<PatientSummary[]>("/api/patients"),
  twin: (id: string) => get<TwinSnapshot>(`/api/patients/${id}/twin`),
  observations: (id: string, hours = 6) =>
    get<Observation[]>(`/api/patients/${id}/observations?hours=${hours}`),
  predictions: (id: string, limit = 40) =>
    get<PredictionRow[]>(`/api/patients/${id}/predictions?limit=${limit}`),
  outcomes: (id: string, limit = 60) =>
    get<Record<string, number | string | null>[]>(
      `/api/patients/${id}/prediction-outcomes?limit=${limit}`),
  startStream: (id: string, mode: "replay" | "simulate", speed: number, restart: boolean) =>
    post<StreamStatus>(`/api/patients/${id}/stream`, { mode, speed, restart }),
  pauseStream: (id: string) => post<StreamStatus>(`/api/patients/${id}/stream/pause`),
  counterfactual: (id: string, scenario: string, magnitude: number) =>
    post<CounterfactualResult>(`/api/patients/${id}/counterfactual`, { scenario, magnitude }),
  operatingPoint: () => get<OperatingPoint>("/api/operating-point"),
  setOperatingPoint: (threshold: number) =>
    put<{ threshold: number; twins_recomputed: number }>("/api/operating-point", { threshold }),
  metrics: () => get<Record<string, any>>("/api/metrics"),
  cohort: () => get<Record<string, any>>("/api/cohort-summary"),
};

export function wsUrl(patientId: string): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/ws/${patientId}`;
}
