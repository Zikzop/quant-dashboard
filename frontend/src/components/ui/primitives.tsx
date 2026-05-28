"use client";

import { C } from "@/lib/colors";
import { T, TRACK, PANEL } from "@/lib/tokens";
import { type ReactNode } from "react";

// ─────────────────────────────────────────────────────────────────────────────
// PANEL — Bloomberg-style container with header label
// ─────────────────────────────────────────────────────────────────────────────

export function Panel({
  label,
  tag,
  accent,
  children,
  className = "",
  noPad,
}: {
  label: string;
  tag?: string;
  accent?: string;
  children: ReactNode;
  className?: string;
  noPad?: boolean;
}) {
  return (
    <div
      className={`flex flex-col ${className}`}
      style={{
        background: C.bg,
        border: `1px solid ${C.border}`,
        borderTop: `2px solid ${accent ?? C.border}`,
        fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
      }}
    >
      <div
        className="flex items-center justify-between"
        style={{
          borderBottom: `1px solid ${C.border}`,
          background: C.surface,
          padding: `${PANEL.headerPadY}px ${PANEL.headerPadX}px`,
        }}
      >
        <span
          style={{
            fontSize: T.micro,
            color: accent ?? C.t2,
            letterSpacing: TRACK.label,
            fontWeight: 700,
          }}
        >
          {label}
        </span>
        {tag && (
          <span
            style={{
              fontSize: T.nano,
              color: C.t3,
              letterSpacing: "0.12em",
              background: C.bg,
              border: `1px solid ${C.border}`,
              padding: "1px 6px",
            }}
          >
            {tag}
          </span>
        )}
      </div>
      <div
        style={{ flex: 1, padding: noPad ? 0 : `${PANEL.padY}px ${PANEL.padX}px` }}
      >
        {children}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// STAT ROW — key/value pair for dense data display
// ─────────────────────────────────────────────────────────────────────────────

export function StatRow({
  label,
  value,
  accent,
  sub,
  mono = true,
}: {
  label: string;
  value: string;
  accent?: string;
  sub?: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between py-[3px]">
      <span style={{ fontSize: T.sm, color: C.t2, letterSpacing: "0.04em" }}>
        {label}
      </span>
      <div className="flex items-baseline gap-1">
        {sub && <span style={{ fontSize: T.nano, color: C.t3 }}>{sub}</span>}
        <span
          style={{
            fontSize: T.base,
            fontFamily: mono ? "'IBM Plex Mono', monospace" : "inherit",
            fontWeight: 600,
            color: accent ?? C.t1,
            letterSpacing: TRACK.value,
          }}
        >
          {value}
        </span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// STAT CELL — compact metric box
// ─────────────────────────────────────────────────────────────────────────────

export function StatCell({
  label,
  value,
  accent,
  large,
}: {
  label: string;
  value: string;
  accent?: string;
  large?: boolean;
}) {
  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        padding: "7px 9px",
      }}
    >
      <div style={{ fontSize: T.nano, color: C.t3, letterSpacing: "0.12em", marginBottom: 3 }}>
        {label}
      </div>
      <div
        style={{
          fontSize: large ? T.xl : T.md,
          fontFamily: "'IBM Plex Mono', monospace",
          fontWeight: 700,
          color: accent ?? C.t1,
          letterSpacing: TRACK.display,
        }}
      >
        {value}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PROGRESS BAR — horizontal fill bar with label
// ─────────────────────────────────────────────────────────────────────────────

export function ProgressBar({
  label,
  value,
  color,
  max = 1,
}: {
  label: string;
  value: number;
  color: string;
  max?: number;
}) {
  const pct = Math.max(0, Math.min(1, value / max));
  return (
    <div className="flex items-center gap-2">
      <span
        style={{
          fontSize: T.micro,
          color: C.t2,
          width: 76,
          letterSpacing: "0.04em",
          flexShrink: 0,
        }}
      >
        {label}
      </span>
      <div className="flex-1 h-[4px]" style={{ background: C.border }}>
        <div
          className="h-full transition-all duration-300"
          style={{ width: `${pct * 100}%`, background: color }}
        />
      </div>
      <span
        style={{
          fontSize: T.sm,
          fontFamily: "'IBM Plex Mono', monospace",
          fontWeight: 600,
          color: C.t1,
          width: 38,
          textAlign: "right",
        }}
      >
        {(pct * 100).toFixed(0)}%
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PROXIMITY BAR — critical threshold indicator (for prop firm death widget)
// ─────────────────────────────────────────────────────────────────────────────

export function ProximityBar({
  label,
  consumed,
  total,
  color,
  dangerZone = 0.8,
}: {
  label: string;
  consumed: number;
  total: number;
  color: string;
  dangerZone?: number;
}) {
  const pct = total > 0 ? consumed / total : 0;
  const inDanger = pct >= dangerZone;
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <span style={{ fontSize: T.micro, color: C.t2, letterSpacing: "0.04em" }}>{label}</span>
        <span
          style={{
            fontSize: T.sm,
            fontFamily: "'IBM Plex Mono', monospace",
            fontWeight: 700,
            color: inDanger ? C.critical : color,
          }}
        >
          {(pct * 100).toFixed(1)}%
        </span>
      </div>
      <div className="w-full h-[6px] relative" style={{ background: C.surface2 }}>
        <div
          className="absolute top-0 left-0 h-full transition-all duration-500"
          style={{
            width: `${Math.min(100, pct * 100)}%`,
            background: inDanger ? C.critical : color,
          }}
        />
        <div
          className="absolute top-0 h-full w-px"
          style={{
            left: `${dangerZone * 100}%`,
            background: C.danger,
            opacity: 0.6,
          }}
        />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// STATUS BADGE — colored inline status indicator
// ─────────────────────────────────────────────────────────────────────────────

export function StatusBadge({
  label,
  color,
  pulse,
}: {
  label: string;
  color: string;
  pulse?: boolean;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="relative flex items-center justify-center" style={{ width: 8, height: 8 }}>
        {pulse && (
          <div
            className="absolute w-2 h-2 rounded-full animate-ping"
            style={{ background: color, opacity: 0.4 }}
          />
        )}
        <div className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
      </div>
      <span style={{ fontSize: T.micro, color, letterSpacing: "0.1em", fontWeight: 700 }}>
        {label}
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// KILL SWITCH — toggle-style indicator
// ─────────────────────────────────────────────────────────────────────────────

export function KillSwitch({
  label,
  active,
  triggered,
}: {
  label: string;
  active: boolean;
  triggered: boolean;
}) {
  const color = triggered ? C.critical : active ? C.safe : C.t3;
  const statusText = triggered ? "TRIGGERED" : active ? "ARMED" : "OFF";
  return (
    <div
      className="flex items-center justify-between"
      style={{
        background: triggered ? "rgba(220,38,38,0.08)" : C.surface,
        border: `1px solid ${triggered ? C.critical : C.border}`,
        padding: "5px 8px",
      }}
    >
      <span style={{ fontSize: T.micro, color: C.t2, letterSpacing: "0.06em" }}>{label}</span>
      <StatusBadge label={statusText} color={color} pulse={triggered} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// DIVIDER
// ─────────────────────────────────────────────────────────────────────────────

export function Divider({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 my-2">
      <div className="flex-1 h-px" style={{ background: C.border }} />
      {label && (
        <span style={{ fontSize: T.nano, color: C.t3, letterSpacing: TRACK.label }}>{label}</span>
      )}
      <div className="flex-1 h-px" style={{ background: C.border }} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MINI TABLE — compact tabular data
// ─────────────────────────────────────────────────────────────────────────────

export function MiniTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: Array<{ cells: Array<{ value: string; accent?: string }>; highlight?: boolean }>;
}) {
  return (
    <table className="w-full border-collapse" style={{ fontSize: T.sm }}>
      <thead>
        <tr>
          {headers.map((h) => (
            <th
              key={h}
              className="text-left py-1 px-1"
              style={{
                color: C.t3,
                fontSize: T.nano,
                letterSpacing: "0.12em",
                borderBottom: `1px solid ${C.border}`,
                fontWeight: 600,
              }}
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr
            key={i}
            style={{
              background: row.highlight ? "rgba(239,68,68,0.05)" : "transparent",
              borderBottom: `1px solid ${C.border}`,
            }}
          >
            {row.cells.map((cell, j) => (
              <td
                key={j}
                className="py-1 px-1"
                style={{
                  fontFamily: "'IBM Plex Mono', monospace",
                  color: cell.accent ?? C.t1,
                  fontWeight: 500,
                }}
              >
                {cell.value}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SPARKLINE — tiny inline chart
// ─────────────────────────────────────────────────────────────────────────────

export function Sparkline({
  data,
  width = 80,
  height = 20,
  color,
}: {
  data: number[];
  width?: number;
  height?: number;
  color: string;
}) {
  if (!data.length) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((v - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.2}
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ALERT STRIP — warning/danger alert bar
// ─────────────────────────────────────────────────────────────────────────────

export function AlertStrip({
  text,
  severity,
}: {
  text: string;
  severity: "info" | "warning" | "danger" | "critical";
}) {
  const colorMap = {
    info: C.cyan,
    warning: C.warning,
    danger: C.danger,
    critical: C.critical,
  };
  const bgMap = {
    info: "rgba(6,182,212,0.06)",
    warning: "rgba(245,158,11,0.06)",
    danger: "rgba(239,68,68,0.06)",
    critical: "rgba(220,38,38,0.1)",
  };
  const col = colorMap[severity];
  return (
    <div
      className="flex items-center gap-2 px-2 py-1"
      style={{
        background: bgMap[severity],
        borderLeft: `2px solid ${col}`,
      }}
    >
      <span style={{ fontSize: T.micro, color: col, letterSpacing: "0.06em", fontWeight: 700 }}>
        {text}
      </span>
    </div>
  );
}
