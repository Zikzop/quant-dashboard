"""
Cash management — tracks cash flows, interest, and margin.

Cash is not just "what's left after trades." Proper cash management tracks:
- Trade settlement timing (T+1/T+2)
- Interest on cash balances
- Margin requirements for leveraged/short positions
- Dividend receipts
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CashFlow:
    """Single cash flow event."""

    timestamp: pd.Timestamp
    amount: float
    description: str
    flow_type: str


class CashManager:
    """Tracks cash balance and flows with full audit trail."""

    def __init__(self, initial_cash: float) -> None:
        self._balance = initial_cash
        self._initial = initial_cash
        self._flows: list[CashFlow] = []

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def initial_balance(self) -> float:
        return self._initial

    def deposit(self, timestamp: pd.Timestamp, amount: float, description: str = "") -> None:
        self._balance += amount
        self._flows.append(CashFlow(timestamp, amount, description, "deposit"))

    def withdraw(self, timestamp: pd.Timestamp, amount: float, description: str = "") -> None:
        self._balance -= amount
        self._flows.append(CashFlow(timestamp, -amount, description, "withdrawal"))

    def trade_settlement(
        self,
        timestamp: pd.Timestamp,
        quantity: float,
        price: float,
        costs: float,
    ) -> None:
        """Record cash impact of a trade settlement."""
        trade_cash = quantity * price + costs
        self._balance -= trade_cash
        self._flows.append(
            CashFlow(
                timestamp,
                -trade_cash,
                f"Trade: {quantity:.0f} @ {price:.2f} + costs {costs:.2f}",
                "trade",
            )
        )

    def accrue_interest(
        self,
        timestamp: pd.Timestamp,
        annual_rate: float = 0.0,
    ) -> None:
        """Accrue daily interest on positive cash balances."""
        if self._balance > 0 and annual_rate > 0:
            daily_interest = self._balance * annual_rate / 365
            self._balance += daily_interest
            self._flows.append(
                CashFlow(timestamp, daily_interest, "Interest accrual", "interest")
            )

    def to_dataframe(self) -> pd.DataFrame:
        if not self._flows:
            return pd.DataFrame()
        return pd.DataFrame([
            {
                "timestamp": f.timestamp,
                "amount": f.amount,
                "description": f.description,
                "type": f.flow_type,
            }
            for f in self._flows
        ])

    def net_flows(self) -> float:
        return sum(f.amount for f in self._flows)
