"""
Backtest engine — event-driven, execution-aware, portfolio-realistic simulation.

This is the central orchestrator. It:
1. Converts market data into MarketEvents
2. Runs alpha models to produce SignalEvents
3. Passes signals through the portfolio engine for order generation
4. Simulates execution via the fill simulator
5. Updates portfolio state and PnL
6. Records everything in the trade ledger and equity curve
7. Produces a comprehensive backtest report

CORRECTNESS > SPEED. No premature optimization.

WARNING: All backtest results are optimistic estimates of live performance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from backtesting.accounting.equity_curve import EquityCurveBuilder
from backtesting.accounting.trade_ledger import TradeLedger
from backtesting.event_engine.event_loop import EventLoop
from backtesting.event_engine.event_types import EventType
from backtesting.event_engine.events import (
    Event,
    FillEvent,
    MarketEvent,
    OrderEvent,
    PortfolioUpdateEvent,
    RiskUpdateEvent,
    SignalEvent,
)
from backtesting.execution.fill_simulator import FillSimulator, MarketSnapshot
from backtesting.portfolio.portfolio_engine import PortfolioEngine
from backtesting.reports.backtest_report import BACKTEST_WARNINGS, BacktestReport
from backtesting.reports.execution_diagnostics import compute_execution_diagnostics
from backtesting.reports.risk_report import compute_risk_report
from backtesting.reports.tearsheet import Tearsheet, generate_tearsheet
from backtesting.simulation_config import SimulationConfig

logger = logging.getLogger(__name__)


@dataclass
class AlphaAdapter:
    """
    Adapts an alpha model from the alpha engine to produce SignalEvents.

    The alpha engine produces AlphaSeriesOutput; this adapter converts
    those outputs into SignalEvents for each timestamp and symbol.
    """

    alpha_name: str
    alpha_model: Any
    symbols: list[str] = field(default_factory=list)


class BacktestEngine:
    """
    Institutional event-driven backtesting engine.

    Flow:
        for each bar:
            emit MarketEvent for each symbol
            run alpha models -> SignalEvents
            portfolio engine: Signal -> Order (with constraints)
            fill simulator: Order -> Fill (with execution realism)
            portfolio engine: Fill -> PortfolioUpdate + RiskUpdate
            record PnL, ledger, equity
    """

    def __init__(
        self,
        config: SimulationConfig | None = None,
    ) -> None:
        self._config = config or SimulationConfig()
        rng_seed = self._config.random_seed
        self._rng = np.random.default_rng(rng_seed) if rng_seed is not None else np.random.default_rng()

        self._portfolio = PortfolioEngine(self._config)
        self._fill_sim = FillSimulator(
            config=self._config.execution,
            rng=self._rng,
        )
        self._event_loop = EventLoop()
        self._ledger = TradeLedger()
        self._equity_builder = EquityCurveBuilder()

        self._alpha_adapters: list[AlphaAdapter] = []
        self._constraint_violations = 0
        self._event_stats: dict[str, int] = {}

        self._register_handlers()

    def _register_handlers(self) -> None:
        self._event_loop.register(EventType.MARKET, self._on_market)
        self._event_loop.register(EventType.SIGNAL, self._on_signal)
        self._event_loop.register(EventType.ORDER, self._on_order)
        self._event_loop.register(EventType.FILL, self._on_fill)
        self._event_loop.register(EventType.RISK_UPDATE, self._on_risk_update)

    def register_alpha(self, adapter: AlphaAdapter) -> None:
        self._alpha_adapters.append(adapter)

    def _on_market(self, event: Event) -> list[Event] | None:
        assert isinstance(event, MarketEvent)
        self._portfolio.on_market(event)
        return None

    def _on_signal(self, event: Event) -> list[Event] | None:
        assert isinstance(event, SignalEvent)
        return self._portfolio.on_signal(event)

    def _on_order(self, event: Event) -> list[Event] | None:
        assert isinstance(event, OrderEvent)
        snapshot = self._portfolio.get_snapshot(event.symbol)
        if snapshot is None:
            logger.warning("No snapshot for %s, skipping order", event.symbol)
            return None
        fill = self._fill_sim.simulate_fill(event, snapshot)
        return [fill]

    def _on_fill(self, event: Event) -> list[Event] | None:
        assert isinstance(event, FillEvent)
        self._ledger.record_fill(event)
        return self._portfolio.on_fill(event)

    def _on_risk_update(self, event: Event) -> list[Event] | None:
        assert isinstance(event, RiskUpdateEvent)
        if event.constraint_violations:
            self._constraint_violations += len(event.constraint_violations)
            for v in event.constraint_violations:
                logger.warning("Constraint violation: %s", v)
        return None

    def run(
        self,
        market_data: dict[str, pd.DataFrame],
        alpha_signals: dict[str, pd.DataFrame] | None = None,
    ) -> BacktestReport:
        """
        Run the backtest.

        market_data : dict[symbol, DataFrame]
            OHLCV data keyed by symbol. Index must be DatetimeIndex.
            Columns: open, high, low, close, volume (and optionally bid, ask).

        alpha_signals : dict[symbol, DataFrame] or None
            Pre-computed alpha signals. Each DataFrame must have
            'alpha_score' and 'confidence' columns with DatetimeIndex.
            If None, alpha adapters are used (not yet implemented for
            series-level alpha — use pre-computed signals).
        """
        all_dates = set()
        for df in market_data.values():
            all_dates.update(df.index.tolist())
        sorted_dates = sorted(all_dates)

        self._precompute_volatilities(market_data)

        logger.info(
            "Starting backtest: %d symbols, %d dates",
            len(market_data),
            len(sorted_dates),
        )

        for date in sorted_dates:
            for symbol, df in market_data.items():
                if date not in df.index:
                    continue

                row = df.loc[date]
                market_event = MarketEvent(
                    timestamp=pd.Timestamp(date),
                    symbol=symbol,
                    open=float(row.get("open", row.get("Open", 0))),
                    high=float(row.get("high", row.get("High", 0))),
                    low=float(row.get("low", row.get("Low", 0))),
                    close=float(row.get("close", row.get("Close", 0))),
                    volume=float(row.get("volume", row.get("Volume", 0))),
                    bid=float(row["bid"]) if "bid" in row.index else None,
                    ask=float(row["ask"]) if "ask" in row.index else None,
                )
                self._event_loop.submit(market_event)

            if alpha_signals:
                for symbol, sig_df in alpha_signals.items():
                    if date not in sig_df.index:
                        continue
                    sig_row = sig_df.loc[date]
                    signal = SignalEvent(
                        timestamp=pd.Timestamp(date),
                        symbol=symbol,
                        alpha_name=str(sig_row.get("alpha_name", "composite")),
                        alpha_score=float(sig_row["alpha_score"]),
                        confidence=float(sig_row["confidence"]),
                    )
                    self._event_loop.submit(signal)

            self._event_stats = self._event_loop.run()

            self._portfolio.record_period_pnl(pd.Timestamp(date))
            self._equity_builder.record(
                pd.Timestamp(date),
                self._portfolio.state.portfolio_value,
            )

        return self._build_report(sorted_dates)

    def _precompute_volatilities(self, market_data: dict[str, pd.DataFrame]) -> None:
        """Pre-compute rolling volatilities for each symbol."""
        for symbol, df in market_data.items():
            close_col = "close" if "close" in df.columns else "Close"
            if close_col in df.columns:
                returns = df[close_col].pct_change().dropna()
                if len(returns) > 20:
                    vol = float(returns.rolling(20).std().iloc[-1] * np.sqrt(252))
                    self._portfolio.update_volatility(symbol, max(vol, 0.01))

    def _build_report(self, sorted_dates: list) -> BacktestReport:
        """Build comprehensive backtest report from accumulated state."""
        state = self._portfolio.state
        equity_analysis = self._equity_builder.analyze()

        exec_summary = self._portfolio.execution_report.summary()
        cost_drag = self._portfolio.pnl_engine.cost_drag()

        n_days = len(sorted_dates)
        turnover_ann = self._portfolio.turnover_engine.annualized_turnover(
            state.portfolio_value, n_days
        )

        warnings = list(BACKTEST_WARNINGS)
        if turnover_ann > 10:
            warnings.append(
                f"Annualized turnover is {turnover_ann:.1f}x — "
                f"transaction costs will dominate returns"
            )
        if equity_analysis.max_drawdown < -0.30:
            warnings.append(
                f"Max drawdown {equity_analysis.max_drawdown:.1%} — "
                f"strategy may not survive in practice"
            )

        return BacktestReport(
            strategy_name="backtest",
            start_date=pd.Timestamp(sorted_dates[0]),
            end_date=pd.Timestamp(sorted_dates[-1]),
            initial_capital=state.initial_capital,
            final_capital=state.portfolio_value,
            equity_analysis=equity_analysis,
            execution_summary=exec_summary,
            cost_attribution=cost_drag,
            turnover_annualized=turnover_ann,
            n_trades=self._ledger.n_trades,
            event_stats=self._event_stats,
            config_summary={
                "slippage_model": "VolatilityScaledSlippage",
                "spread_model": "VolatilityAdjustedSpread",
                "impact_model": "SquareRootImpact",
                "sizer": "VolatilityTargetSizer",
                "max_leverage": str(self._config.portfolio.max_gross_leverage),
                "target_vol": str(self._config.portfolio.target_volatility),
            },
            warnings=tuple(warnings),
        )

    def generate_tearsheet(self, strategy_name: str = "backtest") -> Tearsheet:
        """Generate a full tearsheet after running the backtest."""
        returns = self._equity_builder.returns()
        report = self._build_report(
            list(self._equity_builder.to_series().index)
        )
        risk = compute_risk_report(
            returns,
            constraint_violation_count=self._constraint_violations,
        )
        exec_diag = compute_execution_diagnostics(
            self._portfolio.execution_report,
            self._portfolio.state.portfolio_value,
        )

        return generate_tearsheet(
            strategy_name=strategy_name,
            backtest_report=report,
            risk_report=risk,
            execution_diagnostics=exec_diag,
            equity_builder=self._equity_builder,
        )

    @property
    def ledger(self) -> TradeLedger:
        return self._ledger

    @property
    def equity_builder(self) -> EquityCurveBuilder:
        return self._equity_builder

    @property
    def portfolio(self) -> PortfolioEngine:
        return self._portfolio
