"""
Experiment tracker for research reproducibility.

Persists experiment metadata, parameters, and metrics to JSONL for
audit trails and replication.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExperimentTrackerConfig:
    storage_dir: Path | None = None
    auto_flush: bool = True


@dataclass
class ExperimentRecord:
    experiment_id: str
    dataset_version: str
    features_used: list[str]
    parameters: dict[str, Any]
    metrics: dict[str, Any]
    timestamp: str
    notes: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperimentTracker:
    """
    Track and persist quantitative research experiments.

    Each record includes dataset version, features, parameters, and metrics
    for full reproducibility auditing.
    """

    def __init__(self, config: ExperimentTrackerConfig | None = None) -> None:
        cfg = config or ExperimentTrackerConfig()
        if cfg.storage_dir is None:
            backend_root = Path(__file__).resolve().parent.parent
            self._storage_dir = backend_root / "data" / "experiments"
        else:
            self._storage_dir = Path(cfg.storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._storage_dir / "experiments.jsonl"
        self._auto_flush = cfg.auto_flush

    def create_experiment(
        self,
        *,
        dataset_version: str,
        features_used: list[str],
        parameters: dict[str, Any],
        metrics: dict[str, Any],
        notes: str = "",
        tags: list[str] | None = None,
        experiment_id: str | None = None,
    ) -> ExperimentRecord:
        """
        Create and optionally persist a new experiment record.

        Parameters
        ----------
        dataset_version : str
            Identifier for data snapshot (e.g. ``GC=F_1d_features_20240527``).
        features_used : list[str]
            Feature column names used in the experiment.
        parameters : dict
            Hyperparameters, window sizes, thresholds, etc.
        metrics : dict
            Out-of-sample metrics (Sharpe, drawdown, p-values, etc.).
        """
        record = ExperimentRecord(
            experiment_id=experiment_id or str(uuid.uuid4()),
            dataset_version=dataset_version,
            features_used=list(features_used),
            parameters=dict(parameters),
            metrics=dict(metrics),
            timestamp=datetime.now(timezone.utc).isoformat(),
            notes=notes,
            tags=list(tags or []),
        )

        if self._auto_flush:
            self.save(record)

        logger.info("Created experiment %s", record.experiment_id)
        return record

    def save(self, record: ExperimentRecord) -> Path:
        """Append experiment record to JSONL log."""
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), default=str) + "\n")
        logger.info("Saved experiment %s to %s", record.experiment_id, self._log_path)
        return self._log_path

    def load_all(self) -> list[ExperimentRecord]:
        """Load all experiment records from JSONL log."""
        if not self._log_path.exists():
            return []

        records: list[ExperimentRecord] = []
        with self._log_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                records.append(ExperimentRecord(**data))
        return records

    def get_by_id(self, experiment_id: str) -> ExperimentRecord | None:
        """Retrieve a single experiment by ID."""
        for record in self.load_all():
            if record.experiment_id == experiment_id:
                return record
        return None

    def list_by_tag(self, tag: str) -> list[ExperimentRecord]:
        """Filter experiments containing a specific tag."""
        return [r for r in self.load_all() if tag in r.tags]
