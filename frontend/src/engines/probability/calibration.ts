// ─────────────────────────────────────────────────────────────────────────────
// PROBABILITY CALIBRATION PRIMITIVES
//
// Financial probabilities are routinely overconfident: a raw model that prints
// "BULL 99%" is statistically indefensible in a fat-tailed, non-stationary,
// regime-unstable market. This module provides the standard calibration toolkit
// used to map raw scores onto realistic, frequency-consistent probabilities:
//
//   • Platt scaling      — parametric logistic recalibration (sigmoid fit)
//   • Isotonic regression — non-parametric monotone fit via Pool-Adjacent-Violators
//   • Bayesian shrinkage  — Beta-Binomial pull toward the empirical base rate
//   • Wilson interval     — small-sample confidence bounds on a proportion
//
// Everything is deterministic and dependency-free.
// ─────────────────────────────────────────────────────────────────────────────

export interface Sample {
  /** Predicted probability in (0,1). */
  p: number;
  /** Realized binary outcome (0 or 1). */
  y: number;
}

const EPS = 1e-6;

export function clamp01(x: number): number {
  if (Number.isNaN(x)) return 0.5;
  return Math.max(EPS, Math.min(1 - EPS, x));
}

export function logit(p: number): number {
  const c = clamp01(p);
  return Math.log(c / (1 - c));
}

export function sigmoid(z: number): number {
  if (z >= 0) {
    const e = Math.exp(-z);
    return 1 / (1 + e);
  }
  const e = Math.exp(z);
  return e / (1 + e);
}

// ── PLATT SCALING ─────────────────────────────────────────────────────────────
// Fits P(y=1) = sigmoid(A * f + B) where f is the raw score (here we use the
// logit of the raw probability so the transform is well-behaved). Implements
// Platt's regularized Newton iteration with Lin et al. (2007) target smoothing
// to avoid overfitting on small / separable samples.

export interface PlattParams {
  A: number;
  B: number;
}

export function fitPlatt(samples: Sample[]): PlattParams {
  const n = samples.length;
  if (n < 8) return { A: 1, B: 0 };

  let prior1 = 0;
  for (const s of samples) prior1 += s.y;
  const prior0 = n - prior1;
  if (prior1 === 0 || prior0 === 0) return { A: 1, B: 0 };

  // Lin et al. target smoothing.
  const hiTarget = (prior1 + 1) / (prior1 + 2);
  const loTarget = 1 / (prior0 + 2);

  const f = samples.map((s) => logit(s.p));
  const t = samples.map((s) => (s.y > 0 ? hiTarget : loTarget));

  // Numerically stable softplus: log(1 + e^x).
  const softplus = (x: number): number =>
    x > 0 ? x + Math.log1p(Math.exp(-x)) : Math.log1p(Math.exp(x));

  // Negative log-likelihood under the smoothed targets, using the SAME sign
  // convention as the gradient/Hessian below: P(y=1) = sigmoid(A*f + B).
  //   NLL_i = t_i·softplus(-z_i) + (1 - t_i)·softplus(z_i),  z_i = A·f_i + B
  const objective = (A: number, B: number): number => {
    let fval = 0;
    for (let i = 0; i < n; i++) {
      const z = f[i] * A + B;
      fval += t[i] * softplus(-z) + (1 - t[i]) * softplus(z);
    }
    return fval;
  };

  let A = 0;
  let B = Math.log((prior0 + 1) / (prior1 + 1));
  const maxIter = 100;
  const minStep = 1e-10;
  const sigma = 1e-12;

  for (let it = 0; it < maxIter; it++) {
    let h11 = sigma;
    let h22 = sigma;
    let h21 = 0;
    let g1 = 0;
    let g2 = 0;

    for (let i = 0; i < n; i++) {
      const fApB = f[i] * A + B;
      let p: number; // P(y=1)
      let q: number; // P(y=0)
      if (fApB >= 0) {
        const e = Math.exp(-fApB);
        p = 1 / (1 + e);
        q = e / (1 + e);
      } else {
        const e = Math.exp(fApB);
        p = e / (1 + e);
        q = 1 / (1 + e);
      }
      const d2 = p * q;
      h11 += f[i] * f[i] * d2;
      h22 += d2;
      h21 += f[i] * d2;
      const d1 = p - t[i];
      g1 += f[i] * d1;
      g2 += d1;
    }

    if (Math.abs(g1) < 1e-5 && Math.abs(g2) < 1e-5) break;

    const det = h11 * h22 - h21 * h21;
    if (Math.abs(det) < 1e-12) break;
    const dA = -(h22 * g1 - h21 * g2) / det;
    const dB = -(-h21 * g1 + h11 * g2) / det;
    const gd = g1 * dA + g2 * dB;

    let stepScale = 1;
    let improved = false;
    const baseErr = objective(A, B);
    while (stepScale >= minStep) {
      const newErr = objective(A + stepScale * dA, B + stepScale * dB);
      if (newErr < baseErr + 1e-4 * stepScale * gd) {
        A += stepScale * dA;
        B += stepScale * dB;
        improved = true;
        break;
      }
      stepScale /= 2;
    }
    if (!improved || Math.abs(gd) < 1e-7) break;
  }

  return { A, B };
}

export function applyPlatt(p: number, params: PlattParams): number {
  return clamp01(sigmoid(params.A * logit(p) + params.B));
}

// ── ISOTONIC REGRESSION (Pool Adjacent Violators) ──────────────────────────────
// Produces a non-decreasing step function mapping predicted prob → observed
// frequency. This is the gold-standard non-parametric calibration map.

export interface IsotonicModel {
  /** Sorted breakpoints of predicted probability. */
  x: number[];
  /** Calibrated value at each breakpoint. */
  y: number[];
}

export function fitIsotonic(samples: Sample[]): IsotonicModel | null {
  if (samples.length < 8) return null;
  const sorted = [...samples].sort((a, b) => a.p - b.p);

  // Each block: weighted mean of outcomes.
  const blocks: Array<{ sum: number; w: number; x: number }> = [];
  for (const s of sorted) {
    blocks.push({ sum: s.y, w: 1, x: s.p });
    // Merge while monotonicity is violated.
    while (
      blocks.length > 1 &&
      blocks[blocks.length - 2].sum / blocks[blocks.length - 2].w >
        blocks[blocks.length - 1].sum / blocks[blocks.length - 1].w
    ) {
      const b = blocks.pop()!;
      const a = blocks.pop()!;
      blocks.push({ sum: a.sum + b.sum, w: a.w + b.w, x: a.x });
    }
  }

  const x: number[] = [];
  const y: number[] = [];
  // Re-expand block means against their max x for breakpoints.
  let cursor = 0;
  for (const b of blocks) {
    const mean = b.sum / b.w;
    // The block spans w consecutive sorted samples starting at `cursor`.
    const endX = sorted[Math.min(cursor + b.w - 1, sorted.length - 1)].p;
    x.push(endX);
    y.push(mean);
    cursor += b.w;
  }
  return { x, y };
}

export function applyIsotonic(p: number, model: IsotonicModel): number {
  const { x, y } = model;
  if (x.length === 0) return clamp01(p);
  if (p <= x[0]) return clamp01(y[0]);
  if (p >= x[x.length - 1]) return clamp01(y[y.length - 1]);
  // Linear interpolation between breakpoints for a smooth map.
  for (let i = 1; i < x.length; i++) {
    if (p <= x[i]) {
      const t = (p - x[i - 1]) / (x[i] - x[i - 1] || 1);
      return clamp01(y[i - 1] + t * (y[i] - y[i - 1]));
    }
  }
  return clamp01(y[y.length - 1]);
}

// ── BAYESIAN SHRINKAGE (Beta-Binomial) ──────────────────────────────────────────
// Posterior mean of a Beta(α,β) prior centered on `priorMean` with pseudo-count
// `strength`, updated by an observation equivalent to `evidenceN` trials at rate
// `p`. Pulls extreme probabilities toward the base rate when evidence is thin.

export function bayesianShrink(
  p: number,
  priorMean: number,
  strength: number,
  evidenceN: number,
): number {
  const c = clamp01(p);
  const alpha0 = priorMean * strength;
  const beta0 = (1 - priorMean) * strength;
  const successes = c * evidenceN;
  const failures = (1 - c) * evidenceN;
  return clamp01((alpha0 + successes) / (alpha0 + beta0 + evidenceN));
}

// ── WILSON SCORE INTERVAL ──────────────────────────────────────────────────────

export function wilsonInterval(
  p: number,
  n: number,
  z = 1.96,
): { lower: number; upper: number } {
  const c = clamp01(p);
  const nn = Math.max(1, n);
  const z2 = z * z;
  const denom = 1 + z2 / nn;
  const center = c + z2 / (2 * nn);
  const margin =
    z * Math.sqrt((c * (1 - c)) / nn + z2 / (4 * nn * nn));
  return {
    lower: clamp01((center - margin) / denom),
    upper: clamp01((center + margin) / denom),
  };
}

// ── SCORING ──────────────────────────────────────────────────────────────────

export function brierScore(samples: Sample[], map: (p: number) => number): number {
  if (!samples.length) return 0;
  let s = 0;
  for (const sm of samples) {
    const d = map(sm.p) - sm.y;
    s += d * d;
  }
  return s / samples.length;
}

export function reliabilityBins(
  samples: Sample[],
  map: (p: number) => number,
  bins = 5,
): Array<{ predicted: number; observed: number; n: number }> {
  const acc: Array<{ pSum: number; ySum: number; n: number }> = Array.from(
    { length: bins },
    () => ({ pSum: 0, ySum: 0, n: 0 }),
  );
  for (const s of samples) {
    const cp = clamp01(map(s.p));
    const bi = Math.min(bins - 1, Math.floor(cp * bins));
    acc[bi].pSum += cp;
    acc[bi].ySum += s.y;
    acc[bi].n += 1;
  }
  return acc
    .filter((b) => b.n > 0)
    .map((b) => ({
      predicted: b.pSum / b.n,
      observed: b.ySum / b.n,
      n: b.n,
    }));
}
