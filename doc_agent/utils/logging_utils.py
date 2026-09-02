from __future__ import annotations

import json
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from doc_agent.config import get_settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("method", "path", "status_code", "duration_ms", "request_id", "client"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_json_logging(log_dir: str | Path | None = None, level: str | None = None) -> None:
    settings = get_settings()
    active_level = getattr(logging, (level or settings.log_level).upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(active_level)

    if not any(getattr(handler, "_doc_agent_json", False) for handler in root.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(JsonFormatter())
        stream_handler._doc_agent_json = True  # type: ignore[attr-defined]
        root.addHandler(stream_handler)

    active_log_dir = Path(log_dir) if log_dir else settings.log_dir
    active_log_dir.mkdir(parents=True, exist_ok=True)
    log_path = active_log_dir / "app.log"
    if not any(getattr(handler, "_doc_agent_file", None) == str(log_path) for handler in root.handlers):
        file_handler = TimedRotatingFileHandler(log_path, when="midnight", backupCount=30, encoding="utf-8")
        file_handler.setFormatter(JsonFormatter())
        file_handler._doc_agent_file = str(log_path)  # type: ignore[attr-defined]
        root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    configure_json_logging()
    return logging.getLogger(name)
