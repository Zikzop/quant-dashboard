"use client";

import { useEffect, useCallback } from "react";
import { C } from "@/lib/colors";
import { T, TRACK, CHROME } from "@/lib/tokens";
import { useMarketStore } from "@/state/stores/useMarketStore";
import type { WorkspaceId } from "@/types/market";

const WORKSPACES: Array<{ id: WorkspaceId; label: string; key: string; accent: string }> = [
  { id: "chart", label: "CHART", key: "1", accent: C.t1 },
  { id: "risk", label: "RISK", key: "2", accent: C.danger },
  { id: "market", label: "MARKET", key: "3", accent: C.cyan },
  { id: "execution", label: "EXECUTION", key: "4", accent: C.blue },
  { id: "alpha", label: "ALPHA", key: "5", accent: C.purple },
  { id: "portfolio", label: "PORTFOLIO", key: "6", accent: C.amber },
  { id: "terminal", label: "TERMINAL", key: "7", accent: C.bullish },
];

export default function WorkspaceNav() {
  const active = useMarketStore((s) => s.activeWorkspace);
  const setActive = useMarketStore((s) => s.setActiveWorkspace);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (!e.altKey) return;

      const ws = WORKSPACES.find((w) => w.key === e.key);
      if (ws) {
        e.preventDefault();
        setActive(ws.id);
      }
    },
    [setActive]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div
      className="flex items-stretch"
      style={{
        background: C.bg,
        borderBottom: `1px solid ${C.border}`,
        height: CHROME.nav,
        fontFamily: "'IBM Plex Mono', monospace",
      }}
    >
      {WORKSPACES.map((ws) => {
        const isActive = active === ws.id;
        return (
          <button
            key={ws.id}
            onClick={() => setActive(ws.id)}
            className="relative flex items-center gap-1.5 px-3.5 transition-colors"
            style={{
              background: isActive ? C.surface2 : "transparent",
              borderRight: `1px solid ${C.border}`,
              borderBottom: isActive ? `2px solid ${ws.accent}` : "2px solid transparent",
              color: isActive ? ws.accent : C.t2,
              fontSize: T.micro,
              letterSpacing: TRACK.label,
              fontWeight: isActive ? 700 : 500,
              cursor: "pointer",
            }}
          >
            <span
              style={{
                fontSize: T.pico,
                color: C.t4,
                opacity: 0.6,
              }}
            >
              ⌥{ws.key}
            </span>
            {ws.label}
          </button>
        );
      })}
      <div className="flex-1" />
      <div
        className="flex items-center px-3.5 gap-2"
        style={{ fontSize: T.nano, color: C.t3, letterSpacing: "0.08em" }}
      >
        <span>⌥1-7 SWITCH</span>
      </div>
    </div>
  );
}
