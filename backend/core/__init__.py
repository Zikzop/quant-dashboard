"""
Cross-cutting infrastructure shared by every layer of the research platform.

Nothing in `core` knows about market data, engines, or HTTP. It provides the
deterministic, dependency-light primitives (config, logging, metrics,
reliability) that higher layers compose. This keeps research code free of
infrastructure concerns and makes the platform testable in isolation.
"""

from core.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
