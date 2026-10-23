"use client";

import type { StreamStatus } from "@/lib/types";

const SPEEDS = [1, 2, 5, 10];

export default function StreamControls({
  stream, speed, onSpeed, onStart, onPause, onRestart, busy,
}: {
  stream: StreamStatus | null;
  speed: number;
  onSpeed: (s: number) => void;
  onStart: (mode: "replay" | "simulate") => void;
  onPause: () => void;
  onRestart: () => void;
  busy: boolean;
}) {
  const running = stream?.running ?? false;
  const progress = stream && stream.total_points
    ? Math.round((stream.cursor_index / stream.total_points) * 100)
    : 0;

  return (
    <>
      <div className="btn-row">
        <button
          className="btn"
          onClick={() => onStart("replay")}
          disabled={busy}
          aria-pressed={running && stream?.mode === "replay"}
        >
          Replay recorded data
        </button>
        <button
          className="btn"
          onClick={() => onStart("simulate")}
          disabled={busy}
          aria-pressed={running && stream?.mode === "simulate"}
        >
          Simulate live sensor
        </button>
        <button className="btn" onClick={onPause} disabled={busy || !running}>
          Pause
        </button>
        <button className="btn" onClick={onRestart} disabled={busy}>
          Restart from the beginning
        </button>
      </div>

      <div className="btn-row" style={{ marginTop: 14 }}>
        <span style={{ color: "var(--faint)", fontSize: 13 }}>Speed</span>
        {SPEEDS.map((s) => (
          <button
            key={s}
            className="btn"
            onClick={() => onSpeed(s)}
            aria-pressed={speed === s}
            style={{ padding: "6px 12px" }}
          >
            <span className="mono">{s}x</span>
          </button>
        ))}
      </div>

      <div className="metric-strip">
        <div>
          <div className="k">Mode</div>
          <div className="v" style={{ fontSize: 14, textTransform: "capitalize" }}>
            {stream?.mode ?? "idle"}
          </div>
        </div>
        <div>
          <div className="k">Position</div>
          <div className="v mono">
            {stream?.cursor_index ?? 0} / {stream?.total_points ?? 0}
          </div>
        </div>
        <div>
          <div className="k">Through series</div>
          <div className="v mono">{progress}%</div>
        </div>
      </div>
      <p className="footnote">
        Replay sends the recorded synthetic series in timestamp order, defects included.
        Simulate adds noise and injects the occasional invalid, missing or late reading so
        validation and the data quality panel can be seen working.
      </p>
    </>
  );
}
