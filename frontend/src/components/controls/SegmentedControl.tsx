"use client";

import { type ReactNode, useState } from "react";
import { CONTROL, TIER, type ControlTier } from "./controlTokens";

export function SegmentedControl({
  label,
  isActive,
  onClick,
  tier,
  accentColor,
  indicator,
  title,
  className = "",
}: {
  label: ReactNode;
  isActive: boolean;
  onClick: () => void;
  tier: ControlTier;
  accentColor?: string;
  indicator?: ReactNode;
  title?: string;
  className?: string;
}) {
  const t = TIER[tier];
  const accent = accentColor ?? "#06b6d4";
  const [hovered, setHovered] = useState(false);

  const bg = isActive ? t.activeBg : hovered ? t.hoverBg : "transparent";

  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`control-segment relative flex shrink-0 items-center h-full ${className}`}
      style={{
        paddingLeft: t.segmentPadX,
        paddingRight: t.segmentPadX,
        gap: tier === "primary" ? 6 : 5,
        background: bg,
        color: isActive ? t.activeColor : t.inactiveColor,
        fontSize: isActive ? t.activeSize : t.inactiveSize,
        fontWeight: isActive ? t.activeWeight : t.inactiveWeight,
        letterSpacing: isActive ? "0.08em" : "0.06em",
        cursor: "pointer",
        borderRight: `1px solid rgba(28,28,32,0.8)`,
        transition: CONTROL.transition,
        opacity: isActive ? 1 : hovered ? 0.92 : 0.78,
        textShadow: isActive ? `0 0 12px ${accent}22` : "none",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {indicator}
      <span className="relative z-[1]">{label}</span>

      {/* Active underline with glow */}
      <span
        className="control-segment-underline absolute bottom-0 left-0 right-0 pointer-events-none"
        style={{
          height: t.underlineHeight,
          background: accent,
          opacity: isActive ? 1 : hovered ? 0.35 : 0,
          transform: isActive ? "scaleX(1)" : hovered ? "scaleX(0.65)" : "scaleX(0)",
          transformOrigin: "center",
          boxShadow: isActive ? `0 0 ${t.glowSpread}px ${accent}66, 0 1px 0 ${accent}` : "none",
          transition: CONTROL.underlineTransition,
        }}
      />

      {/* Active background tint overlay */}
      {isActive && (
        <span
          className="control-segment-glow absolute inset-0 pointer-events-none"
          style={{
            background: `linear-gradient(180deg, ${accent}08 0%, transparent 70%)`,
            transition: CONTROL.transition,
          }}
        />
      )}
    </button>
  );
}
