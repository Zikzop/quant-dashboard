// ─────────────────────────────────────────────────────────────────────────────
// DESIGN TOKENS — single source of truth for institutional visual hierarchy.
//
// The terminal aesthetic stays intact (dense, mono, tracked uppercase labels).
// These tokens exist so typography, spacing and chrome heights stay consistent
// across the workstation instead of being hand-tuned per component.
// ─────────────────────────────────────────────────────────────────────────────

// Typography scale (px). Tiers map to information hierarchy, not arbitrary sizes.
//   PRIMARY  → asset, regime, signal, risk state   (display / xl / lg / md)
//   MEDIUM   → volatility, ADX, confidence, dir     (base / sm)
//   SECONDARY→ diagnostics, supporting stats, labels (micro / nano / pico)
export const T = {
  pico: 8, // micro diagnostics, transition probabilities, suppression reasons
  nano: 9, // section labels, chips, table headers, secondary labels
  micro: 10, // panel titles, tab labels, dense stat labels
  sm: 11, // stat-row labels, secondary numeric values
  base: 12, // medium numeric values
  md: 13, // primary metric values, active asset, chart title
  lg: 16, // medium overlay headlines (exec / alpha)
  xl: 18, // surface-level headlines (vol surface, entry quality)
  xxl: 21, // hero headline (regime engine)
} as const;

// Letter-spacing presets for the tracked-uppercase terminal look.
export const TRACK = {
  label: "0.16em", // uppercase tracked section/metric labels
  labelTight: "0.1em",
  value: "0.02em", // numeric values
  display: "-0.01em", // large display headlines
} as const;

// Chrome bar heights — institutional vertical rhythm (~+30% over the
// previously compressed values for breathing room without retail spacing).
export const CHROME = {
  topbar: 42, // was 32
  strip: 26, // was 22
  nav: 34, // was 28
  selector: 32, // was 26
} as const;

// Spacing scale (px) — standardized paddings / gaps / vertical rhythm.
export const SP = {
  xs: 2,
  sm: 4,
  md: 6,
  lg: 8,
  xl: 12,
  xxl: 16,
} as const;

// Canonical panel chrome spacing (used by the Panel primitive + bespoke panels).
export const PANEL = {
  padX: 12,
  padY: 10,
  headerPadX: 12,
  headerPadY: 7,
} as const;
