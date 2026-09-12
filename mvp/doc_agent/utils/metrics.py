from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock


@dataclass
class AppMetrics:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_requests: int = 0
    active_requests: int = 0
    error_requests: int = 0
    total_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    by_status: dict[str, int] = field(default_factory=dict)
    by_path: dict[str, int] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def begin_request(self) -> None:
        with self._lock:
            self.active_requests += 1

    def finish_request(self, path: str, status_code: int, duration_ms: float) -> None:
        status_key = str(status_code)
        with self._lock:
            self.active_requests = max(self.active_requests - 1, 0)
            self.total_requests += 1
            self.total_duration_ms += duration_ms
            self.max_duration_ms = max(self.max_duration_ms, duration_ms)
            self.by_status[status_key] = self.by_status.get(status_key, 0) + 1
            self.by_path[path] = self.by_path.get(path, 0) + 1
            if status_code >= 500:
                self.error_requests += 1

    def snapshot(self) -> dict:
        with self._lock:
            average = self.total_duration_ms / self.total_requests if self.total_requests else 0.0
            return {
                "started_at": self.started_at.isoformat(),
                "total_requests": self.total_requests,
                "active_requests": self.active_requests,
                "error_requests": self.error_requests,
                "average_duration_ms": round(average, 2),
                "max_duration_ms": round(self.max_duration_ms, 2),
                "by_status": dict(self.by_status),
                "by_path": dict(self.by_path),
            }


app_metrics = AppMetrics()
