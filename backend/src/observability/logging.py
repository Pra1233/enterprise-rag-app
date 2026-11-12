"""Structured (JSON-line) logging, additive to — not a replacement for — the
plain-text logging.basicConfig already set up in src/api/main.py. Opt into
this where logs are shipped to an aggregator that expects JSON lines.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any


class StructuredFormatter(logging.Formatter):
    """Formats each log record as a single JSON line, with correlation IDs
    (request_id/conversation_id/tenant_id) included when present on the record.

    Never includes raw document content or API keys — only whatever the
    caller explicitly attaches via `extra={...}` plus the exception traceback.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "conversation_id", "tenant_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_structured_logging(level: str = "INFO") -> None:
    """Opt-in structured logging for the whole process. Call this instead of
    (not in addition to) logging.basicConfig when JSON-line logs are needed.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
