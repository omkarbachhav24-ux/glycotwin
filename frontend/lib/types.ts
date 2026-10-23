export interface PatientSummary {
  patient_id: string;
  age: number;
  sex: string;
  bmi: number;
  hba1c_percent: number;
  years_since_diagnosis: number;
  medication_category: string;
  comorbidities: string;
  baseline_fasting_glucose: number;
  data_source: string;
}

export interface HorizonForecast {
  horizon_minutes: number;
  point_mg_dl: number;
  lower_mg_dl: number;
  upper_mg_dl: number;
  target_timestamp: string;
}

export interface Contributor {
  feature: string;
  label: string;
  value: number | null;
  contribution: number;
  direction: "raises" | "lowers";
}

export interface DataQuality {
  status: "ok" | "stale" | "unusable" | "insufficient_history";
  minutes_since_last_observation: number | null;
  history_points: number;
  missing_signals: string[];
  warnings: string[];
  rejected_last_hour: number;
}

export interface Prediction {
  generated_at: string;
  observation_timestamp: string;
  model_version: string;
  current_glucose: number;
  forecast: HorizonForecast[];
  excursion_probability: number | null;
  excursion_predicted: boolean;
  time_to_threshold_minutes: number | null;
  risk_band: "high" | "moderate" | "low" | "above_threshold" | "unknown";
  excursion_threshold_mg_dl: number;
  contributors: Contributor[];
  explanation: string;
  data_quality: DataQuality;
  scenario: string;
}

export interface Trend {
  direction: "rising" | "falling" | "stable" | "unknown";
  rate_mg_dl_per_min: number | null;
  change_30min: number | null;
}

export interface StreamStatus {
  patient_id: string;
  mode: "idle" | "replay" | "simulate";
  running: boolean;
  speed: number;
  cursor_index: number;
  total_points: number;
  last_event_timestamp: string | null;
}

export interface TwinSnapshot {
  patient_id: string;
  profile: PatientSummary;
  latest_observation: Record<string, unknown> | null;
  latest_glucose: number | null;
  rolling_glucose: Record<string, number>;
  trend: Trend;
  data_quality: DataQuality;
  latest_prediction: Prediction | null;
  updated_at: string | null;
  history_points: number;
  stream: StreamStatus;
  model: {
    version: string;
    trained_at: string;
    excursion_threshold_mg_dl: number;
    operating_threshold: number;
    horizons_minutes: number[];
    event_horizon_minutes: number;
  };
}

export interface Observation {
  timestamp: string;
  glucose_mg_dl: number;
  heart_rate_bpm: number | null;
  steps_last_5_min: number | null;
  minutes_since_meal: number | null;
  data_source: string;
}

export interface PredictionRow {
  generated_at: string;
  observation_timestamp: string;
  model_version: string;
  current_glucose: number;
  forecast: Record<string, { point: number; lower: number; upper: number }>;
  excursion_probability: number | null;
  excursion_predicted: boolean;
  time_to_threshold_minutes: number | null;
  risk_band: string;
  data_quality_status: string | null;
}

export interface InputChange {
  feature: string;
  label: string;
  before: number;
  after: number;
  training_p01_p99: [number, number];
  status: "within_range" | "extreme_but_observed" | "outside_training_range";
}

export interface CounterfactualResult {
  patient_id: string;
  scenario: string;
  scenario_label: string;
  magnitude: number;
  description: string;
  baseline: Prediction;
  alternative: Prediction;
  difference: {
    horizon_minutes: number;
    baseline_mg_dl: number;
    scenario_mg_dl: number;
    difference_mg_dl: number;
  }[];
  input_changes: InputChange[];
  probability_change: number | null;
  caveats: string[];
  disclaimer: string;
}

export interface SweepRow {
  threshold: number;
  precision: number;
  recall: number;
  specificity: number;
  f1: number;
  alerts_per_patient_day: number;
  missed_per_patient_day: number;
  alert_episodes_per_patient_day: number;
  episode_precision: number | null;
  median_warning_minutes: number | null;
}

export interface OperatingPoint {
  threshold: number;
  default_threshold: number;
  selection_note: string;
  refractory_minutes: number | null;
  evaluation_patient_days: number | null;
  sweep: SweepRow[];
}
