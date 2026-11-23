"""Request admission controller and process memory supervisor.

Enforces ADR-001 (bounded memory ceiling) via:
1. Application-level asyncio.Semaphore(1) for heavy workbook operations.
2. Preflight working-set RSS queries before admitting resource-intensive tasks.
3. Tracking active concurrent parsing jobs.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator, Optional

from excel_intel.exceptions import PlatformError


class AdmissionRejectedError(PlatformError):
    """Raised when request admission is denied due to memory pressure or saturated capacity."""

    exit_code: int = 429
    category: str = "ERR_ADMISSION_REJECTED"


def get_current_working_set_bytes() -> int:
    """Returns the process working set memory in bytes.

    Attempts to query the Rust memory_guard via PyO3 first;
    falls back to psutil or standard OS libraries if unavailable.
    """
    try:
        from excel_intel._rs import py_get_process_working_set_bytes

        return int(py_get_process_working_set_bytes())
    except (ImportError, AttributeError):
        pass

    try:
        import psutil

        return int(psutil.Process(os.getpid()).memory_info().rss)
    except Exception:
        # Minimal conservative fallback if psutil fails
        return 50 * 1024 * 1024


def get_current_working_set_mb() -> float:
    """Returns current process working set memory in MiB."""
    return get_current_working_set_bytes() / (1024.0 * 1024.0)


class AdmissionController:
    """Supervises concurrency and memory budget for the FastAPI application."""

    def __init__(
        self,
        concurrency_limit: int = 1,
        throttle_threshold_mb: float = 180.0,
        hard_limit_mb: float = 250.0,
    ) -> None:
        self._concurrency_limit = concurrency_limit
        self._throttle_threshold_mb = throttle_threshold_mb
        self._hard_limit_mb = hard_limit_mb
        self._semaphore = asyncio.Semaphore(concurrency_limit)
        self._active_jobs: int = 0
        self._lock = asyncio.Lock()

    @property
    def concurrency_limit(self) -> int:
        return self._concurrency_limit

    @property
    def active_parsing_jobs(self) -> int:
        return self._active_jobs

    @property
    def available_slots(self) -> int:
        return max(0, self._concurrency_limit - self._active_jobs)

    def is_memory_within_limit(self) -> bool:
        """Returns True if current RSS is below hard ceiling."""
        return get_current_working_set_mb() < self._hard_limit_mb

    def can_admit_workload(self) -> bool:
        """Returns True if current RSS is below the preflight throttle threshold."""
        return get_current_working_set_mb() < self._throttle_threshold_mb

    @asynccontextmanager
    async def acquire(self, task_name: str = "parsing") -> AsyncGenerator[None, None]:
        """Acquires admission for a heavy task or raises AdmissionRejectedError.

        Performs:
        1. Preflight memory check against throttle threshold before queueing.
        2. Async semaphore acquisition.
        3. Post-acquisition memory re-check immediately upon obtaining the slot.
        4. Active job counter maintenance wrapped in try...finally.
        """
        # Preflight memory check
        pre_mb = get_current_working_set_mb()
        if pre_mb >= self._throttle_threshold_mb:
            raise AdmissionRejectedError(
                f"Request throttled: current process RSS ({pre_mb:.1f} MiB) "
                f"exceeds admission threshold ({self._throttle_threshold_mb:.1f} MiB).",
                context={
                    "current_rss_mb": pre_mb,
                    "threshold_mb": self._throttle_threshold_mb,
                    "task": task_name,
                    "phase": "preflight",
                },
                exit_code=429,
            )

        # 1. Acquire admission semaphore
        await self._semaphore.acquire()

        # 2. Re-check memory immediately AFTER acquiring the slot
        post_mb = get_current_working_set_mb()
        if post_mb >= self._throttle_threshold_mb:
            self._semaphore.release()
            raise AdmissionRejectedError(
                f"Request throttled: process RSS ({post_mb:.1f} MiB) "
                f"exceeds admission threshold ({self._throttle_threshold_mb:.1f} MiB) upon slot acquisition.",
                context={
                    "current_rss_mb": post_mb,
                    "threshold_mb": self._throttle_threshold_mb,
                    "task": task_name,
                    "phase": "post_acquisition",
                },
                exit_code=429,
            )

        async with self._lock:
            self._active_jobs += 1

        try:
            yield
        finally:
            async with self._lock:
                self._active_jobs = max(0, self._active_jobs - 1)
            self._semaphore.release()
