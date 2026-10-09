"""JSON-line structured logging with request ID context and secret redaction."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from backend.app.config.env import SecretRedactionFilter, Settings

# Context variable for request ID propagated across coroutines
request_id_ctx: ContextVar[str | None] = ContextVar("request_id_ctx", default=None)


class JSONLineFormatter(logging.Formatter):
    """Formatter outputting single-line JSON with UTC ISO timestamp and request_id."""

    def format(self, record: logging.LogRecord) -> str:
        # Generate UTC timestamp in ISO 8601 format
        created_dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        ts_str = created_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        req_id = getattr(record, "request_id", None)
        if req_id is None:
            req_id = request_id_ctx.get()

        log_payload: dict[str, Any] = {
            "ts": ts_str,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": req_id,
        }

        # Include exception text if formatted by SecretRedactionFilter
        if record.exc_text:
            log_payload["exception"] = record.exc_text

        return json.dumps(log_payload)


def configure_logging(settings: Settings) -> None:
    """Configure root logging to stdout using JSONLineFormatter and SecretRedactionFilter."""
    root_logger = logging.getLogger()
    level_name = settings.log_level.upper()
    level = getattr(logging, level_name, logging.INFO)
    root_logger.setLevel(level)

    # Remove existing handlers
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONLineFormatter())

    # Attach existing SecretRedactionFilter
    redaction_filter = SecretRedactionFilter.from_settings(settings)
    handler.addFilter(redaction_filter)

    root_logger.addHandler(handler)
