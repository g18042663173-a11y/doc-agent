from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def deterministic_parsed_at(path: Path) -> str:
    """Use source mtime as the stable audit timestamp required by reproducible parsing."""
    seconds, nanoseconds = divmod(path.stat().st_mtime_ns, 1_000_000_000)
    value = datetime.fromtimestamp(seconds, timezone.utc).replace(microsecond=nanoseconds // 1_000)
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")
