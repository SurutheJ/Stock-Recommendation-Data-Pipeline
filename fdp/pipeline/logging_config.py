"""Structured (JSON) logging so every pipeline run can be correlated by
`run_id` across stages -- the kind of operational visibility a real data
platform needs to spot process issues and regressions after the fact.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_CORRELATION_FIELDS = ("run_id", "ticker", "stage", "status", "duration_ms")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _CORRELATION_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload)


def get_logger(name: str = "fdp") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
