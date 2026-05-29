"""
Structured logging with request-ID propagation.

Why this design
---------------
* Institutional systems need machine-parseable logs (one JSON object per line)
  so latency, fit durations, and cache behaviour can be aggregated downstream
  (Loki/ELK/Datadog) without regex scraping.
* Every log line carries the ``request_id`` of the in-flight request via a
  ``ContextVar``, so a single trade-research request can be reconstructed end
  to end across the data, feature, and regime layers.
* ``structlog`` is used when present (best-in-class structured logging) but the
  module degrades gracefully to the stdlib + ``python-json-logger`` (already a
  dependency) so the platform never hard-fails on a missing optional package.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_CONFIGURED = False

try:  # pragma: no cover - exercised implicitly by import environment
    import structlog

    _HAS_STRUCTLOG = True
except Exception:  # pragma: no cover
    structlog = None  # type: ignore[assignment]
    _HAS_STRUCTLOG = False


def set_request_id(request_id: str | None = None) -> str:
    """Bind a request id to the current context, generating one if absent."""
    rid = request_id or uuid.uuid4().hex[:16]
    _request_id_ctx.set(rid)
    return rid


def get_request_id() -> str | None:
    return _request_id_ctx.get()


def clear_request_id() -> None:
    _request_id_ctx.set(None)


def _inject_request_id(_logger: Any, _method: str, event_dict: dict) -> dict:
    rid = _request_id_ctx.get()
    if rid is not None:
        event_dict.setdefault("request_id", rid)
    return event_dict


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Idempotently configure process-wide structured logging."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)

    if _HAS_STRUCTLOG:
        renderer = (
            structlog.processors.JSONRenderer()
            if json_output
            else structlog.dev.ConsoleRenderer()
        )
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                _inject_request_id,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                renderer,
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        handler = logging.StreamHandler(sys.stdout)
        if json_output:
            try:
                try:
                    from pythonjsonlogger import json as jsonlogger  # new path
                except Exception:
                    from pythonjsonlogger import jsonlogger  # legacy path

                handler.setFormatter(
                    jsonlogger.JsonFormatter(
                        "%(asctime)s %(levelname)s %(name)s %(message)s",
                        rename_fields={"asctime": "timestamp", "levelname": "level"},
                    )
                )
            except Exception:
                handler.setFormatter(
                    logging.Formatter(
                        "%(asctime)s %(levelname)s %(name)s %(message)s"
                    )
                )
        root = logging.getLogger()
        root.handlers = [handler]
        root.setLevel(log_level)

    _CONFIGURED = True


class _StdlibStructAdapter:
    """Minimal structlog-like façade over stdlib logging.

    Accepts ``logger.info("event", key=value, ...)`` and folds the kwargs plus
    the active request id into the message so downstream JSON parsing works
    even without structlog installed.
    """

    def __init__(self, name: str) -> None:
        self._log = logging.getLogger(name)

    def _emit(self, _levelno: int, _event: str, **kwargs: Any) -> None:
        rid = _request_id_ctx.get()
        if rid is not None:
            kwargs.setdefault("request_id", rid)
        if kwargs:
            self._log.log(_levelno, _event, extra={"context": kwargs})
        else:
            self._log.log(_levelno, _event)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.DEBUG, event, **kwargs)

    def info(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.ERROR, event, **kwargs)

    def exception(self, event: str, **kwargs: Any) -> None:
        self._log.exception(event, extra={"context": kwargs} if kwargs else None)


def get_logger(name: str = "quant") -> Any:
    """Return a structured logger bound to ``name``."""
    if _HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return _StdlibStructAdapter(name)
