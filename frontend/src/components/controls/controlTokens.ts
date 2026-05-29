import { C } from "@/lib/colors";
import { T, TRACK, CHROME } from "@/lib/tokens";

export type ControlTier = "primary" | "secondary" | "tertiary";

export const CONTROL = {
  font: "'IBM Plex Mono', monospace",
  transition: "color 80ms ease, background 80ms ease, box-shadow 120ms ease, border-color 80ms ease, opacity 80ms ease",
  underlineTransition: "transform 120ms ease, opacity 120ms ease, box-shadow 120ms ease",
} as const;

export const TIER = {
  primary: {
    height: CHROME.selector + 4,
    labelSize: T.nano,
    activeSize: T.md,
    inactiveSize: T.sm,
    activeWeight: 800,
    inactiveWeight: 500,
    activeColor: C.t1,
    inactiveColor: C.t3,
    activeBg: "rgba(255,255,255,0.04)",
    hoverBg: "rgba(255,255,255,0.02)",
    segmentPadX: 14,
    segmentGap: 0,
    underlineHeight: 3,
    glowSpread: 8,
  },
  secondary: {
    height: CHROME.selector,
    labelSize: T.nano,
    activeSize: T.sm,
    inactiveSize: T.micro,
    activeWeight: 700,
    inactiveWeight: 500,
    activeColor: C.t1,
    inactiveColor: C.t3,
    activeBg: "rgba(255,255,255,0.035)",
    hoverBg: "rgba(255,255,255,0.018)",
    segmentPadX: 12,
    segmentGap: 0,
    underlineHeight: 2,
    glowSpread: 6,
  },
  tertiary: {
    height: CHROME.selector - 2,
    labelSize: T.pico,
    activeSize: T.micro,
    inactiveSize: T.nano,
    activeWeight: 700,
    inactiveWeight: 500,
    activeColor: C.t2,
    inactiveColor: C.t4,
    activeBg: "rgba(255,255,255,0.025)",
    hoverBg: "rgba(255,255,255,0.012)",
    segmentPadX: 10,
    segmentGap: 0,
    underlineHeight: 2,
    glowSpread: 4,
  },
} as const;

export const GROUP = {
  labelWidth: 52,
  labelPadX: 10,
  railPadX: 12,
  border: C.border,
  borderMid: C.borderMid,
  surface: C.surface,
  surfaceRaised: "#0e0e11",
  labelColor: C.t3,
  labelTrack: TRACK.label,
} as const;

export const CLASS_COLORS: Record<string, string> = {
  crypto: C.cyan,
  future: C.purple,
  index: C.blue,
  fx: C.warning,
  commodity: C.amber,
  equity_index: C.purple,
  macro: C.warning,
};

export const TF_ROLE_COLORS: Record<string, string> = {
  EXECUTION: C.cyan,
  TACTICAL: C.blue,
  STRATEGIC: C.purple,
};
