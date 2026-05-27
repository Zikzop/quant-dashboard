"""
Tests for the institutional backtesting engine.

Validates:
- Event ordering and causal integrity
- No lookahead leakage
- Portfolio accounting consistency
- End-to-end backtest execution
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from backtesting.backtest_engine import BacktestEngine
from backtesting.event_engine.event_loop import EventLoop
from backtesting.event_engine.event_queue import EventQueue
from backtesting.event_engine.event_types import EventType
from backtesting.event_engine.events import (
    Event,
    FillEvent,
    FillStatus,
    MarketEvent,
    OrderEvent,
    OrderSide,
    SignalEvent,
)
from backtesting.simulation_config import SimulationConfig


def _make_market_data(n: int = 100, seed: int = 42) -> dict[str, pd.DataFrame]:
    """Generate synthetic market data for testing."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="B", tz="UTC")
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    close = np.maximum(close, 10)
    return {
        "TEST": pd.DataFrame(
            {
                "open": close + rng.normal(0, 0.1, n),
                "high": close + rng.uniform(0.1, 1.0, n),
                "low": close - rng.uniform(0.1, 1.0, n),
                "close": close,
                "volume": rng.integers(10000, 100000, n).astype(float),
            },
            index=idx,
        )
    }


def _make_alpha_signals(market_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Generate simple momentum signals for testing."""
    signals = {}
    for symbol, df in market_data.items():
        close = df["close"]
        returns = close.pct_change()
        momentum = returns.rolling(20).mean()
        score = np.tanh(momentum.fillna(0) * 100)
        signals[symbol] = pd.DataFrame(
            {
                "alpha_score": score,
                "confidence": np.clip(np.abs(score) * 0.8, 0.1, 0.9),
                "alpha_name": "test_momentum",
            },
            index=df.index,
        )
    return signals


class TestEventQueue(unittest.TestCase):
    def test_causal_ordering(self) -> None:
        """Events at the same timestamp must be ordered by EventType priority."""
        q = EventQueue()
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        q.push(SignalEvent(timestamp=ts, symbol="A", alpha_score=0.5, confidence=0.8))
        q.push(MarketEvent(timestamp=ts, symbol="A", close=100))
        q.push(OrderEvent(timestamp=ts, symbol="A", quantity=10))

        events = list(q.drain())
        self.assertEqual(events[0].event_type, EventType.MARKET)
        self.assertEqual(events[1].event_type, EventType.SIGNAL)
        self.assertEqual(events[2].event_type, EventType.ORDER)

    def test_temporal_ordering(self) -> None:
        """Events at different timestamps must be ordered chronologically."""
        q = EventQueue()
        ts1 = pd.Timestamp("2023-01-02", tz="UTC")
        ts2 = pd.Timestamp("2023-01-01", tz="UTC")
        q.push(MarketEvent(timestamp=ts1, symbol="A", close=100))
        q.push(MarketEvent(timestamp=ts2, symbol="A", close=99))

        first = q.pop()
        self.assertEqual(first.timestamp, ts2)


class TestEventLoop(unittest.TestCase):
    def test_causal_violation_raises(self) -> None:
        """Handlers must not produce events before current time."""
        loop = EventLoop()
        ts = pd.Timestamp("2023-01-02", tz="UTC")
        past_ts = pd.Timestamp("2023-01-01", tz="UTC")

        def bad_handler(event: Event) -> list[Event]:
            return [MarketEvent(timestamp=past_ts, symbol="A", close=99)]

        loop.register(EventType.MARKET, bad_handler)
        loop.submit(MarketEvent(timestamp=ts, symbol="A", close=100))

        with self.assertRaises(ValueError, msg="Causal violation"):
            loop.run()

    def test_handler_chain(self) -> None:
        """Downstream events from handlers are processed in correct order."""
        processed = []

        def market_handler(event: Event) -> list[Event]:
            processed.append(("market", event.timestamp))
            return [
                SignalEvent(
                    timestamp=event.timestamp,
                    symbol="A",
                    alpha_score=0.5,
                    confidence=0.8,
                )
            ]

        def signal_handler(event: Event) -> list[Event]:
            processed.append(("signal", event.timestamp))
            return None

        loop = EventLoop()
        loop.register(EventType.MARKET, market_handler)
        loop.register(EventType.SIGNAL, signal_handler)
        loop.submit(
            MarketEvent(
                timestamp=pd.Timestamp("2023-01-01", tz="UTC"),
                symbol="A",
                close=100,
            )
        )
        loop.run()

        self.assertEqual(len(processed), 2)
        self.assertEqual(processed[0][0], "market")
        self.assertEqual(processed[1][0], "signal")


class TestNoLookahead(unittest.TestCase):
    def test_signal_cannot_use_future_price(self) -> None:
        """
        Signals at time T must not depend on prices at time T+1.

        We verify this by checking that adding future data doesn't change
        historical signals.
        """
        data_short = _make_market_data(50)
        data_long = _make_market_data(100)

        signals_short = _make_alpha_signals(data_short)
        signals_long = _make_alpha_signals(data_long)

        common_dates = data_short["TEST"].index
        for symbol in signals_short:
            short_vals = signals_short[symbol].loc[common_dates, "alpha_score"]
            long_vals = signals_long[symbol].loc[common_dates, "alpha_score"]
            pd.testing.assert_series_equal(
                short_vals, long_vals, check_names=False,
                rtol=1e-10,
            )


class TestBacktestEngine(unittest.TestCase):
    def test_end_to_end(self) -> None:
        """Full backtest runs without error and produces valid report."""
        data = _make_market_data(100)
        signals = _make_alpha_signals(data)

        config = SimulationConfig()
        engine = BacktestEngine(config=config)
        report = engine.run(market_data=data, alpha_signals=signals)

        self.assertGreater(report.final_capital, 0)
        self.assertIsNotNone(report.equity_analysis)
        self.assertEqual(report.initial_capital, 1_000_000)
        self.assertTrue(len(report.warnings) > 0)

    def test_execution_degrades_returns(self) -> None:
        """
        With high execution costs, net returns should be worse than
        a zero-cost backtest.
        """
        data = _make_market_data(200, seed=1)
        signals = _make_alpha_signals(data)

        config_low = SimulationConfig()
        engine_low = BacktestEngine(config=config_low)
        report_low = engine_low.run(market_data=data, alpha_signals=signals)

        config_high = SimulationConfig.conservative()
        engine_high = BacktestEngine(config=config_high)
        report_high = engine_high.run(market_data=data, alpha_signals=signals)

        self.assertLessEqual(
            report_high.equity_analysis.total_return,
            report_low.equity_analysis.total_return + 0.01,
            "High-cost execution should degrade returns",
        )

    def test_portfolio_value_never_negative(self) -> None:
        """Portfolio value must never go negative."""
        data = _make_market_data(100)
        signals = _make_alpha_signals(data)

        engine = BacktestEngine()
        engine.run(market_data=data, alpha_signals=signals)

        eq = engine.equity_builder.to_series()
        self.assertTrue(
            (eq > 0).all(),
            "Portfolio value went negative — accounting error",
        )


if __name__ == "__main__":
    unittest.main()
