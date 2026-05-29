"use client";

import { type ReactNode } from "react";
import { C } from "@/lib/colors";
import { T, TRACK, PANEL } from "@/lib/tokens";

// ─────────────────────────────────────────────────────────────────────────────
// COLLAPSIBLE — progressive-disclosure container for the analytics layer.
//
// Header always renders (so the section's existence + a one-line summary stay
// scannable); the body mounts only when expanded to keep the DOM light and the
// visual field calm.
// ─────────────────────────────────────────────────────────────────────────────

export function Collapsible({
  label,
  accent,
  open,
  onToggle,
  summary,
  tag,
  children,
}: {
  label: string;
  accent?: string;
  open: boolean;
  onToggle: () => void;
  /** Compact one-line summary shown when collapsed. */
  summary?: ReactNode;
  tag?: string;
  children: ReactNode;
}) {
  return (
    <div
      className="flex flex-col"
      style={{
        background: C.bg,
        border: `1px solid ${C.border}`,
        borderLeft: `2px solid ${open ? accent ?? C.borderMid : C.border}`,
        fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
      }}
    >
      <button
        onClick={onToggle}
        className="flex items-center justify-between w-full text-left transition-colors"
        style={{
          background: C.surface,
          padding: `${PANEL.headerPadY}px ${PANEL.headerPadX}px`,
          cursor: "pointer",
        }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            style={{
              fontSize: T.micro,
              color: open ? accent ?? C.t1 : C.t2,
              transition: "transform 0.15s",
              transform: open ? "rotate(90deg)" : "rotate(0deg)",
              display: "inline-block",
              width: 8,
            }}
          >
            ▸
          </span>
          <span
            style={{
              fontSize: T.micro,
              color: open ? accent ?? C.t1 : C.t2,
              letterSpacing: TRACK.label,
              fontWeight: 700,
              whiteSpace: "nowrap",
            }}
          >
            {label}
          </span>
          {!open && summary && (
            <span
              className="truncate"
              style={{ fontSize: T.nano, color: C.t3, letterSpacing: "0.04em", marginLeft: 4 }}
            >
              {summary}
            </span>
          )}
        </div>
        {tag && (
          <span
            style={{
              fontSize: T.nano,
              color: C.t3,
              letterSpacing: "0.1em",
              border: `1px solid ${C.border}`,
              padding: "1px 6px",
              flexShrink: 0,
            }}
          >
            {tag}
          </span>
        )}
      </button>
      {open && (
        <div style={{ padding: `${PANEL.padY}px ${PANEL.padX}px` }}>{children}</div>
      )}
    </div>
  );
}
