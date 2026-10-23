"use client";

/*
  Observed glucose and model forecast, drawn as two separate series.

  competition.txt section 8 is explicit that measured readings and model output
  must be plotted separately, so the observed trace stops at the latest reading
  and the forecast starts there, in its own colour, with its uncertainty band.
*/

import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Observation, Prediction } from "@/lib/types";

interface Point {
  t: number;
  label: string;
  observed?: number;
  forecast?: number;
  band?: [number, number];
}

function clockLabel(iso: string | number): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

export function buildSeries(observations: Observation[], prediction: Prediction | null): Point[] {
  const points: Point[] = observations.map((o) => ({
    t: new Date(o.timestamp).getTime(),
    label: clockLabel(o.timestamp),
    observed: o.glucose_mg_dl,
  }));

  if (prediction && points.length) {
    const anchor = points[points.length - 1];
    // The forecast line starts from the latest measurement so the two series
    // join visually without the observed trace being extended by the model.
    anchor.forecast = anchor.observed;
    anchor.band = [anchor.observed as number, anchor.observed as number];
    for (const f of prediction.forecast) {
      points.push({
        t: new Date(f.target_timestamp).getTime(),
        label: clockLabel(f.target_timestamp),
        forecast: f.point_mg_dl,
        band: [f.lower_mg_dl, f.upper_mg_dl],
      });
    }
  }
  return points;
}

function TooltipBody({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as Point;
  return (
    <div
      style={{
        background: "#ffffff",
        border: "1px solid #cbd5e1",
        borderRadius: 10,
        padding: "10px 14px",
        fontSize: 13,
        boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05)",
      }}
    >
      <div className="mono" style={{ color: "#64748b", marginBottom: 4, fontWeight: 500 }}>{label}</div>
      {row.observed !== undefined && (
        <div style={{ color: "#0284c7", fontWeight: 600 }}>
          Measured <span className="mono">{row.observed.toFixed(1)}</span> mg/dL
        </div>
      )}
      {row.forecast !== undefined && (
        <div style={{ color: "#38bdf8", fontWeight: 500 }}>
          Forecast <span className="mono">{row.forecast.toFixed(1)}</span> mg/dL
        </div>
      )}
      {row.band && row.band[0] !== row.band[1] && (
        <div style={{ color: "#94a3b8", fontSize: 12 }}>
          Interval <span className="mono">{row.band[0].toFixed(0)}</span> to{" "}
          <span className="mono">{row.band[1].toFixed(0)}</span>
        </div>
      )}
    </div>
  );
}

export default function GlucoseChart({
  data,
  threshold,
  height = 320,
}: {
  data: Point[];
  threshold: number;
  height?: number;
}) {
  if (!data.length) {
    return <p className="empty">Waiting for the first readings to arrive.</p>;
  }
  const values = data.flatMap((d) => [
    d.observed, d.forecast, d.band?.[0], d.band?.[1],
  ].filter((v): v is number => typeof v === "number"));
  const lo = Math.floor((Math.min(...values, threshold) - 15) / 20) * 20;
  const hi = Math.ceil((Math.max(...values, threshold) + 15) / 20) * 20;
  const ticks: number[] = [];
  for (let v = lo; v <= hi; v += 20) ticks.push(v);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 10, right: 16, bottom: 0, left: 4 }}>
        <CartesianGrid stroke="rgba(56, 189, 248, 0.12)" strokeDasharray="2 4" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fill: "#64748b", fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: "rgba(56, 189, 248, 0.2)" }}
          minTickGap={36}
        />
        <YAxis
          domain={[lo, hi]}
          ticks={ticks}
          tick={{ fill: "#64748b", fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={64}
          tickFormatter={(v: number) => `${v}`}
          label={{
            value: "mg/dL", angle: -90, position: "left",
            fill: "#64748b", fontSize: 11, offset: -18,
          }}
        />
        <Tooltip content={<TooltipBody />} />
        <Legend
          wrapperStyle={{ fontSize: 12.5, color: "#94a3b8", paddingTop: 6 }}
          iconType="plainline"
          iconSize={16}
        />
        <ReferenceLine
          y={threshold}
          stroke="#f59e0b"
          strokeDasharray="5 4"
          label={{
            value: `Excursion threshold ${threshold}`,
            fill: "#f59e0b", fontSize: 11, position: "insideTopLeft",
          }}
        />
        <Area
          dataKey="band"
          stroke="none"
          fill="#38bdf8"
          fillOpacity={0.16}
          name="Forecast interval (80%)"
          isAnimationActive={false}
          connectNulls
        />
        <Line
          dataKey="observed"
          stroke="#00f0ff"
          strokeWidth={2.5}
          dot={false}
          name="Measured glucose"
          isAnimationActive={false}
          connectNulls={false}
        />
        <Line
          dataKey="forecast"
          stroke="#38bdf8"
          strokeWidth={2.5}
          strokeDasharray="5 3"
          dot={{ r: 3, fill: "#38bdf8" }}
          name="Model forecast"
          isAnimationActive={false}
          connectNulls
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
