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
            executor = _RetryExecutor(
                func=func,
                max_attempts=max_attempts,
                exceptions=exceptions,
                delay=delay,
                backoff=backoff,
                max_delay=max_delay,
                jitter=jitter,
                logger=logger,
                raise_on_final=raise_on_final,
            )
            return executor.run(*args, **kwargs)

        return _wrapped

    return _decorator


class _RetryExecutor:
    """Helper class to execute retry logic and keep complexity low."""

    def __init__(
        self,
        func: Callable[..., Any],
        max_attempts: int,
        exceptions: Tuple[Type[BaseException], ...],
        delay: float,
        backoff: float,
        max_delay: Optional[float],
        jitter: float,
        logger: Optional[logging.Logger],
        raise_on_final: bool,
    ):
        self.func = func
        self.max_attempts = max_attempts
        self.exceptions = exceptions
        self.delay = delay
        self.backoff = backoff
        self.max_delay = max_delay
        self.jitter = jitter
        self.logger = logger
        self.raise_on_final = raise_on_final

    def run(self, *args, **kwargs) -> Any:
        attempt = 0
        cur_delay = float(self.delay)
        last_exc: Optional[BaseException] = None

        while attempt < self.max_attempts:
            try:
                return self.func(*args, **kwargs)
            except self.exceptions as exc:
                last_exc = exc
                attempt += 1
                self._log_attempt(exc, attempt)

                if attempt >= self.max_attempts:
                    break

                time.sleep(self._get_sleep_time(cur_delay))
                cur_delay = self._update_delay(cur_delay)

        if last_exc is not None and self.raise_on_final:
            raise last_exc
        return None

    def _get_sleep_time(self, current_delay: float) -> float:
        if self.jitter and self.jitter > 0.0:
            max_ms = int(self.jitter * 1000)
            return current_delay + (secrets.randbelow(max_ms + 1) / 1000.0)
        return current_delay

    def _update_delay(self, current_delay: float) -> float:
        new_delay = current_delay * float(self.backoff)
        if self.max_delay is not None:
            return min(new_delay, float(self.max_delay))
        return new_delay

    def _log_attempt(self, exc: BaseException, attempt: int):
        if self.logger:
            self.logger.warning(
                "Retrying %s (attempt %d/%d) after exception: %s",
                getattr(self.func, "__name__", str(self.func)),
                attempt,
                self.max_attempts,
                exc,
            )
