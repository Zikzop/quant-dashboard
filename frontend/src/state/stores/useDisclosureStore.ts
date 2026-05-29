import { create } from "zustand";

// Progressive-disclosure state for the institutional information hierarchy.
//   Level 1 (primary)   — always visible.
//   Level 2 (analytics) — collapsible panels, expanded on demand.
//   Level 3 (research)  — hidden by default behind an explicit toggle.

export type AnalyticsPanelId =
  | "probability"
  | "volatility"
  | "structure"
  | "transition"
  | "historical"
  | "execution"
  | "correlation"
  | "risk";

interface DisclosureStore {
  expanded: Record<AnalyticsPanelId, boolean>;
  researchVisible: boolean;
  togglePanel: (id: AnalyticsPanelId) => void;
  setPanel: (id: AnalyticsPanelId, open: boolean) => void;
  expandAll: () => void;
  collapseAll: () => void;
  toggleResearch: () => void;
}

// Default: the two highest-value analytics panels open, the rest collapsed.
const DEFAULT_EXPANDED: Record<AnalyticsPanelId, boolean> = {
  probability: true,
  transition: true,
  volatility: false,
  structure: false,
  historical: false,
  execution: false,
  correlation: false,
  risk: false,
};

export const useDisclosureStore = create<DisclosureStore>((set) => ({
  expanded: { ...DEFAULT_EXPANDED },
  researchVisible: false,
  togglePanel: (id) =>
    set((s) => ({ expanded: { ...s.expanded, [id]: !s.expanded[id] } })),
  setPanel: (id, open) =>
    set((s) => ({ expanded: { ...s.expanded, [id]: open } })),
  expandAll: () =>
    set((s) => ({
      expanded: Object.fromEntries(
        Object.keys(s.expanded).map((k) => [k, true]),
      ) as Record<AnalyticsPanelId, boolean>,
    })),
  collapseAll: () =>
    set((s) => ({
      expanded: Object.fromEntries(
        Object.keys(s.expanded).map((k) => [k, false]),
      ) as Record<AnalyticsPanelId, boolean>,
    })),
  toggleResearch: () => set((s) => ({ researchVisible: !s.researchVisible })),
}));
