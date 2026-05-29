"use client";

import { useMemo } from "react";
import type { DecisionState } from "@/engines/types";
import type { MTFAlignment } from "@/types/market";
import { C } from "@/lib/colors";

export interface ControlContext {
  /** Subtle background tint for the entire control layer */
  layerTint?: string;
  /** Left accent stripe color */
  accentStripe?: string;
  /** Context label shown in the asset rail */
  contextLabel?: string;
  contextColor?: string;
}

export function useControlContext(
  decision: DecisionState | null,
  alignment: MTFAlignment,
): ControlContext {
  return useMemo(() => {
    if (!decision) {
      if (alignment.state === "ALIGNED") {
        return {
          layerTint: "rgba(34,197,94,0.018)",
          accentStripe: C.safe,
        };
      }
      return {};
    }

    const isCrisis =
      decision.structuralRegime === "CRISIS" ||
      decision.riskState === "CRISIS" ||
      decision.headline.some((h) => h.toLowerCase().includes("crisis"));

    const highUncertainty =
      decision.uncertaintyLevel === "HIGH" || decision.uncertaintyLevel === "EXTREME";

    const aligned =
      decision.alignmentState === "ALIGNED" && alignment.state === "ALIGNED";

    if (isCrisis) {
      return {
        layerTint: "rgba(239,68,68,0.035)",
        accentStripe: C.danger,
        contextLabel: "CRISIS",
        contextColor: C.danger,
      };
    }

    if (decision.alignmentState === "CONFLICT" || alignment.state === "CONFLICT") {
      return {
        layerTint: "rgba(239,68,68,0.02)",
        accentStripe: C.danger,
        contextLabel: "MTF CONFLICT",
        contextColor: C.danger,
      };
    }

    if (highUncertainty) {
      return {
        layerTint: "rgba(245,158,11,0.025)",
        accentStripe: C.warning,
        contextLabel: "UNCERTAIN",
        contextColor: C.warning,
      };
    }

    if (aligned && decision.confidence >= 0.6) {
      return {
        layerTint: "rgba(34,197,94,0.022)",
        accentStripe: C.safe,
        contextLabel: "ALIGNED",
        contextColor: C.safe,
      };
    }

    if (alignment.state === "PARTIAL") {
      return {
        layerTint: "rgba(245,158,11,0.015)",
        accentStripe: C.warning,
      };
    }

    return {};
  }, [decision, alignment]);
}
