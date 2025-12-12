"""Reusable retry decorator utilities.

Provide a small, well-documented `retry` decorator that supports:
- configurable max attempts
- exponential backoff (multiplier)
- optional jitter
- optional max delay cap
- configurable exception tuple to catch
- optional logger for observability

This implementation has no external dependencies.
"""

from __future__ import annotations

import functools
import logging
import secrets
import time
from typing import Any, Callable, Optional, Tuple, Type


def retry(
    max_attempts: int = 3,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: Optional[float] = None,
    jitter: float = 0.0,
    logger: Optional[logging.Logger] = None,
    raise_on_final: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Return a decorator that retries the wrapped callable on exceptions.

    Args:
        max_attempts: Number of attempts (including the first call).
        exceptions: Tuple of exception types that should trigger a retry.
        delay: Initial delay in seconds between attempts.
        backoff: Multiplier applied to the delay after each failed attempt.
        max_delay: Optional cap for the backoff delay.
        jitter: Optional additional random jitter (seconds) added to each sleep.
        logger: Optional logger used to emit retry warnings.
        raise_on_final: If True, re-raise the final exception when attempts are exhausted.

    Returns:
        A decorator which can be applied to functions or methods.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    def _decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            cur_delay = float(delay)
            last_exc: Optional[BaseException] = None

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    attempt += 1
                    if logger:
                        logger.warning(
                            "Retrying %s (attempt %d/%d) after exception: %s",
                            getattr(func, "__name__", str(func)),
                            attempt,
                            max_attempts,
                            exc,
                        )

                    if attempt >= max_attempts:
                        break

                    sleep_for = cur_delay
                    if jitter and jitter > 0.0:
                        max_ms = int(jitter * 1000)
                        # secrets.randbelow(n) returns int in range(0, n)
                        # pass max_ms + 1 to include max_ms itself
                        sleep_for += secrets.randbelow(max_ms + 1) / 1000.0

                    time.sleep(sleep_for)

                    cur_delay = cur_delay * float(backoff)
                    if max_delay is not None:
                        cur_delay = min(cur_delay, float(max_delay))

            # Exhausted attempts
            if last_exc is not None and raise_on_final:
                raise last_exc

            return None

        return _wrapped

    return _decorator
