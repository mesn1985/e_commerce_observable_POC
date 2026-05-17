"""
Structured JSON logging shared across all services.
"""

import json
import logging
import sys
from datetime import datetime, timezone

_SKIP_ATTRS = {
    "args", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "module", "msecs", "message",
    "msg", "name", "pathname", "process", "processName", "relativeCreated",
    "stack_info", "thread", "threadName", "taskName",
}


class JSONFormatter(logging.Formatter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        ts = (
            datetime.fromtimestamp(record.created, tz=timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%S.")
            + f"{int(record.msecs):03d}Z"
        )
        entry = {
            "timestamp": ts,
            "level": record.levelname,
            "service_name": self.service_name,
            "event_name": getattr(record, "event", record.getMessage()),
            "correlation_id": getattr(record, "correlation_id", ""),
        }
        # Merge any extra fields supplied via extra={...}
        for key, value in record.__dict__.items():
            if key in _SKIP_ATTRS or key.startswith("_"):
                continue

            mapped_key = {
                "event": "event_name",
                "service": "service_name",
                "error": "error_message",
                "status": "status_text",
            }.get(key, key)

            if mapped_key not in entry:
                entry[mapped_key] = value

        if record.exc_info:
            entry["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(entry)


def setup_logging(service_name: str) -> logging.Logger:
    """Configure and return a JSON structured logger for the given service."""
    logger = logging.getLogger(service_name)
    # Avoid adding duplicate handlers when module is reloaded
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter(service_name))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
