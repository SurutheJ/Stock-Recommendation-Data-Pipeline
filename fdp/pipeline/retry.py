"""A small retry-with-backoff decorator for transient acquisition failures
against a live data source (network hiccups, rate limits). The fixture
client never raises transiently, so this only matters in `--mode live`.
"""

from __future__ import annotations

import functools
import time
from typing import Callable, TypeVar

T = TypeVar("T")


def retry_with_backoff(max_attempts: int = 3, base_delay_seconds: float = 0.5) -> Callable:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001 - deliberately broad, re-raised below
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        time.sleep(base_delay_seconds * (2**attempt))
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator
