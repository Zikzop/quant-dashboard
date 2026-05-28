"""
Walk-forward splitting with purge/embargo (purged-CV preparation).

Why purge + embargo
-------------------
In financial ML, features at time t use look-back windows and labels look
forward, so naive train/test adjacency leaks information across the boundary.
Purging removes training observations whose label window overlaps the test set;
the embargo additionally drops a buffer of training observations immediately
after the test set. This module produces the index splits; the metric layer
consumes them. (López de Prado, *Advances in Financial Machine Learning*, ch.7.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np


@dataclass(frozen=True)
class Fold:
    fold_id: int
    train_idx: np.ndarray
    test_idx: np.ndarray


@dataclass(frozen=True)
class WalkForwardSplitter:
    train_size: int
    test_size: int
    step: int | None = None       # defaults to test_size (non-overlapping OOS)
    expanding: bool = True         # expanding vs rolling train window
    purge: int = 0                 # bars dropped from train tail adjacent to test
    embargo: int = 0               # bars after test excluded from later... (recorded)

    def split(self, n: int) -> Iterator[Fold]:
        if self.train_size <= 0 or self.test_size <= 0:
            raise ValueError("train_size and test_size must be positive")
        step = self.step or self.test_size
        fold_id = 0
        train_start = 0
        test_start = self.train_size
        while test_start + self.test_size <= n:
            test_end = test_start + self.test_size
            train_lo = 0 if self.expanding else train_start
            train_hi = max(train_lo, test_start - self.purge)
            train_idx = np.arange(train_lo, train_hi)
            test_idx = np.arange(test_start, test_end)
            if train_idx.size > 0:
                yield Fold(fold_id=fold_id, train_idx=train_idx, test_idx=test_idx)
                fold_id += 1
            train_start += step
            test_start += step

    def n_folds(self, n: int) -> int:
        return sum(1 for _ in self.split(n))
