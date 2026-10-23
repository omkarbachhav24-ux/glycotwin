"use client";

/*
  The alert threshold, and what moving it costs.

  The training run picks a default by F1 on validation patients. That is a
  statistical default, not a clinical judgement about whether a missed
  crossing or a false alarm is worse, so the choice belongs to whoever is
  reading the alerts. Every figure here was measured on held out patients.

  Burden is shown as alert episodes rather than flagged readings. Readings
  arrive every 5 minutes, so one rising episode trips the threshold repeatedly;
  counting each firing separately overstates what a clinician would see.
*/

import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { OperatingPoint as OP, SweepRow } from "@/lib/types";

function nearest(sweep: SweepRow[], threshold: number): SweepRow | null {
  if (!sweep.length) return null;
  return sweep.reduce((best, row) =>
    Math.abs(row.threshold - threshold) < Math.abs(best.threshold - threshold) ? row : best);
}

function TradeTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload as SweepRow;
  return (
    <div style={{
      background: "#0b1618", border: "1px solid #2b565c", borderRadius: 4,
      padding: "9px 12px", fontSize: 13,
    }}>
      <div className="mono" style={{ color: "#90aaab", marginBottom: 4 }}>
        Threshold {r.threshold.toFixed(2)}
      </div>
      <div style={{ color: "#4fd1c5" }}>
        Catches <span className="mono">{(r.recall * 100).toFixed(0)}%</span> of crossings
      </div>
      <div style={{ color: "#ff7a59" }}>
        <span className="mono">{r.alert_episodes_per_patient_day.toFixed(1)}</span> alerts
        per patient per day
      </div>
    </div>
  );
}

export default function OperatingPointPanel({
  data, pending, onChange,
}: {
  data: OP | null;
  pending: boolean;
  onChange: (threshold: number) => void;
}) {
  if (!data) return <p className="empty">Loading the measured trade.</p>;
  const row = nearest(data.sweep, data.threshold);
  const isDefault = Math.abs(data.threshold - data.default_threshold) < 0.005;

  return (
    <div className="op-grid">
      <div>
        <div className="readout-row" style={{ marginBottom: 14 }}>
          <div>
            <div className="readout-label">Alert threshold</div>
            <div className="readout-value mono" style={{ fontSize: 44 }}>
              {data.threshold.toFixed(2)}
            </div>
          </div>
          {row && (
            <>
              <div>
                <div className="readout-label">Crossings caught</div>
                <div className="readout-small mono">{(row.recall * 100).toFixed(0)}%</div>
              </div>
              <div>
                <div className="readout-label">Alerts per patient per day</div>
                <div className="readout-small mono" style={{ color: "var(--alert)" }}>
                  {row.alert_episodes_per_patient_day.toFixed(1)}
                </div>
              </div>
            </>
          )}
        </div>

        <label htmlFor="threshold-slider" style={{ color: "var(--faint)", fontSize: 13 }}>
          Move the line
        </label>
        <input
          id="threshold-slider"
          className="slider"
          type="range"
          min={0.05}
          max={0.95}
          step={0.05}
          value={data.threshold}
          disabled={pending}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        <div className="btn-row" style={{ marginTop: 10 }}>
          <button
            className="btn"
            onClick={() => onChange(data.default_threshold)}
            disabled={pending || isDefault}
          >
            Back to the default ({data.default_threshold.toFixed(2)})
          </button>
          {isDefault && <span style={{ color: "var(--faint)", fontSize: 12.5 }}>In use</span>}
        </div>

        {row && (
          <div className="metric-strip">
            <div>
              <div className="k">True alerts</div>
              <div className="v mono">
                {row.episode_precision === null
                  ? "--" : `${(row.episode_precision * 100).toFixed(0)}%`}
              </div>
            </div>
            <div>
              <div className="k">Median warning</div>
              <div className="v mono">
                {row.median_warning_minutes === null
                  ? "--" : `${row.median_warning_minutes} min`}
              </div>
            </div>
            <div>
              <div className="k">Missed per day</div>
              <div className="v mono">{row.missed_per_patient_day.toFixed(1)}</div>
            </div>
            <div>
              <div className="k">Specificity</div>
              <div className="v mono">{row.specificity.toFixed(3)}</div>
            </div>
          </div>
        )}

        <p className="footnote">
          {data.selection_note} Moving this line changes which predictions are flagged and
          how the risk band reads. It does not change the probability the model produced,
          and it does not retrain anything.
        </p>
      </div>

      <div>
        <div style={{ color: "var(--faint)", fontSize: 12.5, marginBottom: 6 }}>
          Crossings caught against alerts raised, on held out patients
        </div>
        <ResponsiveContainer width="100%" height={230}>
          <LineChart data={data.sweep} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="#1f3d42" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="threshold"
              tick={{ fill: "#5f7d80", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "#1f3d42" }}
              tickFormatter={(v: number) => v.toFixed(2)}
              interval={1}
            />
            <YAxis
              yAxisId="left"
              tick={{ fill: "#5f7d80", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={54}
              domain={[0, 1]}
              tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fill: "#5f7d80", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={30}
            />
            <Tooltip content={<TradeTooltip />} />
            <ReferenceLine
              yAxisId="left"
              x={data.threshold}
              stroke="#e9efec"
              strokeDasharray="4 3"
            />
            <Line
              yAxisId="left"
              dataKey="recall"
              stroke="#4fd1c5"
              strokeWidth={2}
              dot={false}
              name="Crossings caught"
              isAnimationActive={false}
            />
            <Line
              yAxisId="right"
              dataKey="alert_episodes_per_patient_day"
              stroke="#ff7a59"
              strokeWidth={2}
              dot={false}
              name="Alerts per patient per day"
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
        <div className="legend-row">
          <span><i style={{ background: "#4fd1c5" }} /> Crossings caught, left axis</span>
          <span><i style={{ background: "#ff7a59" }} /> Alerts per patient per day, right axis</span>
        </div>
        <p className="footnote">
          Repeated firings inside one rising episode are counted once, using a{" "}
          {data.refractory_minutes ?? 60} minute window, over{" "}
          {data.evaluation_patient_days ?? "the held out"} patient days.
        </p>
      </div>
    </div>
  );
}
