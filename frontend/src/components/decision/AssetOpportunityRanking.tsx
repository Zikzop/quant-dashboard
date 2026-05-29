"use client";

import { C } from "@/lib/colors";
import { T, TRACK } from "@/lib/tokens";
import type { OpportunityRankingState } from "@/engines/types";
import { useTimeframeStore } from "@/state/stores/useTimeframeStore";

export default function AssetOpportunityRanking({ ranking }: { ranking: OpportunityRankingState }) {
  const setAsset = useTimeframeStore((s) => s.setActiveAsset);
  const activeAsset = useTimeframeStore((s) => s.activeAsset);

  return (
    <div
      style={{
        background: C.surface,
        border: `1px solid ${C.border}`,
        fontFamily: "'IBM Plex Sans', sans-serif",
      }}
    >
      <div
        className="flex items-center justify-between px-3"
        style={{ height: 28, borderBottom: `1px solid ${C.border}`, background: C.bg }}
      >
        <span style={{ fontSize: T.nano, color: C.t2, letterSpacing: TRACK.label, fontWeight: 700 }}>
          ASSET OPPORTUNITY RANKING
        </span>
        {ranking.best && (
          <span style={{ fontSize: T.pico, color: C.bullish, letterSpacing: "0.08em", fontWeight: 600 }}>
            FOCUS · {ranking.best.assetId}
          </span>
        )}
      </div>

      <div className="divide-y" style={{ borderColor: C.border }}>
        {ranking.ranked.map((entry) => {
          const isActive = entry.assetId === activeAsset;
          const rankColor = entry.rank === 1 ? C.bullish : entry.rank === 2 ? C.cyan : C.t2;
          return (
            <button
              key={entry.assetId}
              onClick={() => setAsset(entry.assetId)}
              className="w-full text-left px-3 py-2 transition-colors"
              style={{
                background: isActive ? C.surface2 : "transparent",
                borderLeft: isActive ? `2px solid ${C.cyan}` : "2px solid transparent",
                cursor: "pointer",
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <span
                  style={{
                    fontSize: T.micro,
                    fontWeight: 800,
                    color: rankColor,
                    fontFamily: "'IBM Plex Mono', monospace",
                    width: 18,
                  }}
                >
                  {entry.rank}
                </span>
                <span style={{ fontSize: T.base, fontWeight: 700, color: C.t1, letterSpacing: "0.04em" }}>
                  {entry.assetId}
                </span>
                <span style={{ fontSize: T.pico, color: entry.actionable ? C.bullish : C.t3, marginLeft: "auto" }}>
                  {entry.actionable ? "ACTIONABLE" : "PASS"}
                </span>
              </div>
              <div className="flex items-center gap-3 pl-5">
                <MiniStat label="EDGE" value={`${(entry.edgeScore * 100).toFixed(0)}`} />
                <MiniStat label="ALIGN" value={`${(entry.alignmentScore * 100).toFixed(0)}`} />
                <MiniStat label="UNC" value={`${(entry.uncertaintyScore * 100).toFixed(0)}`} warn={entry.uncertaintyScore > 0.6} />
                <MiniStat label="SCORE" value={`${(entry.compositeScore * 100).toFixed(0)}`} accent={rankColor} />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function MiniStat({
  label,
  value,
  warn,
  accent,
}: {
  label: string;
  value: string;
  warn?: boolean;
  accent?: string;
}) {
  return (
    <div className="flex items-baseline gap-1">
      <span style={{ fontSize: T.pico, color: C.t3 }}>{label}</span>
      <span
        style={{
          fontSize: T.nano,
          fontFamily: "'IBM Plex Mono', monospace",
          fontWeight: 600,
          color: accent ?? (warn ? C.warning : C.t2),
        }}
      >
        {value}
      </span>
    </div>
  );
}
