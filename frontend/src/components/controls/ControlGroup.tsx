"use client";

import { type ReactNode } from "react";
import { C } from "@/lib/colors";
import { CONTROL, GROUP, TIER, type ControlTier } from "./controlTokens";

export function ControlGroup({
  label,
  tier,
  children,
  trailing,
  isLast = false,
  contextTint,
}: {
  label: string;
  tier: ControlTier;
  children: ReactNode;
  trailing?: ReactNode;
  isLast?: boolean;
  contextTint?: string;
}) {
  const t = TIER[tier];

  return (
    <div
      className="control-group flex items-stretch min-w-0"
      style={{
        height: t.height,
        borderBottom: isLast ? "none" : `1px solid ${GROUP.border}`,
        background: contextTint
          ? `linear-gradient(90deg, ${contextTint} 0%, ${GROUP.surface} 48%)`
          : GROUP.surface,
        fontFamily: CONTROL.font,
        transition: CONTROL.transition,
      }}
    >
      <div
        className="control-group-label flex shrink-0 items-center"
        style={{
          width: GROUP.labelWidth,
          paddingLeft: GROUP.labelPadX,
          paddingRight: GROUP.labelPadX,
          borderRight: `1px solid ${GROUP.border}`,
          background: GROUP.surfaceRaised,
        }}
      >
        <span
          style={{
            fontSize: t.labelSize,
            color: GROUP.labelColor,
            letterSpacing: GROUP.labelTrack,
            fontWeight: tier === "primary" ? 700 : 600,
            opacity: tier === "tertiary" ? 0.85 : 1,
          }}
        >
          {label}
        </span>
      </div>

      <div className="control-group-segments flex min-w-0 flex-1 items-stretch overflow-x-auto">
        {children}
      </div>

      {trailing && (
        <div
          className="control-group-rail flex shrink-0 items-center"
          style={{
            paddingLeft: GROUP.railPadX,
            paddingRight: GROUP.railPadX,
            borderLeft: `1px solid ${GROUP.border}`,
            background: GROUP.surfaceRaised,
            gap: 8,
          }}
        >
          {trailing}
        </div>
      )}
    </div>
  );
}

/** Subtle vertical divider between asset class groups */
export function ControlGroupDivider() {
  return (
    <div
      className="control-group-divider shrink-0 self-stretch"
      style={{
        width: 1,
        background: GROUP.borderMid,
        margin: "6px 0",
        opacity: 0.7,
      }}
    />
  );
}

/** Micro category label within a segmented group — not a large header */
export function ControlMicroLabel({ children }: { children: ReactNode }) {
  return (
    <span
      className="control-micro-label flex shrink-0 items-center self-center"
      style={{
        fontSize: 7,
        color: C.t4,
        letterSpacing: "0.14em",
        fontWeight: 600,
        paddingLeft: 10,
        paddingRight: 4,
        userSelect: "none",
      }}
    >
      {children}
    </span>
  );
}
