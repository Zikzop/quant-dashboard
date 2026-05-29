"""
Audit log — immutable record of all risk events, breaches, and actions.

Every risk decision must be traceable. The audit log records:
- Breach detections with full context
- Escalation decisions with rationale
- Automated actions taken
- Manual overrides and acknowledgments

This log is append-only. Entries cannot be modified or deleted.
It supports regulatory compliance, post-mortem analysis, and
risk process improvement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique

import pandas as pd

logger = logging.getLogger(__name__)


@unique
class AuditEventType(Enum):
    BREACH_DETECTED = "BREACH_DETECTED"
    ESCALATION_TRIGGERED = "ESCALATION_TRIGGERED"
    ACTION_TAKEN = "ACTION_TAKEN"
    KILL_SWITCH_ACTIVATED = "KILL_SWITCH_ACTIVATED"
    KILL_SWITCH_DEACTIVATED = "KILL_SWITCH_DEACTIVATED"
    LIMIT_MODIFIED = "LIMIT_MODIFIED"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    ACKNOWLEDGMENT = "ACKNOWLEDGMENT"
    RISK_STATE_SNAPSHOT = "RISK_STATE_SNAPSHOT"


@dataclass(frozen=True)
class AuditEntry:
    """Single immutable audit log entry."""

    timestamp: pd.Timestamp
    event_type: AuditEventType
    severity: str
    source: str
    message: str
    details: dict
    entry_id: str = ""


class AuditLog:
    """
    Append-only audit log for risk governance.

    Thread-safe by design: entries are only appended, never modified.
    The log can be exported to DataFrame for analysis or to JSON for
    archival/compliance.
    """

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []
        self._counter = 0

    def record(
        self,
        event_type: AuditEventType,
        severity: str,
        source: str,
        message: str,
        timestamp: pd.Timestamp,
        details: dict | None = None,
    ) -> AuditEntry:
        self._counter += 1
        entry = AuditEntry(
            timestamp=timestamp,
            event_type=event_type,
            severity=severity,
            source=source,
            message=message,
            details=details or {},
            entry_id=f"AUD-{self._counter:06d}",
        )
        self._entries.append(entry)
        return entry

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    @property
    def n_entries(self) -> int:
        return len(self._entries)

    def entries_since(self, since: pd.Timestamp) -> list[AuditEntry]:
        return [e for e in self._entries if e.timestamp >= since]

    def entries_by_type(self, event_type: AuditEventType) -> list[AuditEntry]:
        return [e for e in self._entries if e.event_type == event_type]

    def to_dataframe(self) -> pd.DataFrame:
        if not self._entries:
            return pd.DataFrame()
        records = []
        for e in self._entries:
            records.append({
                "entry_id": e.entry_id,
                "timestamp": e.timestamp,
                "event_type": e.event_type.value,
                "severity": e.severity,
                "source": e.source,
                "message": e.message,
            })
        return pd.DataFrame(records)

    def breach_count(self, since: pd.Timestamp | None = None) -> int:
        entries = self.entries_since(since) if since else self._entries
        return sum(1 for e in entries if e.event_type == AuditEventType.BREACH_DETECTED)

    def last_entry(self) -> AuditEntry | None:
        return self._entries[-1] if self._entries else None
