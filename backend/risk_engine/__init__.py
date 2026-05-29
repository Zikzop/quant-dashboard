"""
Phase 6 — Institutional risk engine.

Portfolio-aware, regime-aware, execution-aware risk infrastructure.
NOT retail stop-loss logic. NOT simple volatility controls.

This engine monitors exposure, drawdown, tail risk, correlation stability,
and concentration in real time. It enforces governance limits with staged
degradation and kill-switch escalation — preserving capital through
regime shifts rather than maximizing short-term Sharpe.

WARNING: All risk models are approximations. VaR underestimates tail risk.
Correlations break down in crises. Stress scenarios are incomplete by
construction. The risk engine reduces — but cannot eliminate — the
probability of catastrophic loss.
"""
