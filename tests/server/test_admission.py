"""Tests for Request Admission Controller and memory ceiling supervision."""

from __future__ import annotations

import asyncio
from unittest.mock import patch
import pytest

from excel_intel.server.admission import (
    AdmissionController,
    AdmissionRejectedError,
    get_current_working_set_bytes,
    get_current_working_set_mb,
)


def test_working_set_telemetry() -> None:
    """Verifies process working set RSS query returns non-zero positive numbers."""
    rss_bytes = get_current_working_set_bytes()
    rss_mb = get_current_working_set_mb()
    assert rss_bytes > 0
    assert rss_mb > 0.0
    assert abs(rss_mb - (rss_bytes / (1024.0 * 1024.0))) < 0.001


@pytest.mark.asyncio
async def test_admission_controller_semaphore_bounded() -> None:
    """Verifies AdmissionController bounds concurrent operations to configured limit."""
    controller = AdmissionController(
        concurrency_limit=1,
        throttle_threshold_mb=180.0,
        hard_limit_mb=250.0,
    )
    assert controller.available_slots == 1
    assert controller.active_parsing_jobs == 0

    execution_order = []

    async def worker(worker_id: int, delay: float):
        async with controller.acquire(f"worker_{worker_id}"):
            assert controller.active_parsing_jobs == 1
            assert controller.available_slots == 0
            execution_order.append(f"start_{worker_id}")
            await asyncio.sleep(delay)
            execution_order.append(f"end_{worker_id}")

    # Launch two workers concurrently with limit 1
    await asyncio.gather(worker(1, 0.05), worker(2, 0.02))

    # Second worker should have waited for first worker to complete
    assert execution_order == ["start_1", "end_1", "start_2", "end_2"]
    assert controller.active_parsing_jobs == 0
    assert controller.available_slots == 1


@pytest.mark.asyncio
async def test_admission_controller_preflight_rejection() -> None:
    """Verifies AdmissionRejectedError is raised when working set exceeds throttle threshold."""
    controller = AdmissionController(
        concurrency_limit=1,
        throttle_threshold_mb=100.0,
        hard_limit_mb=250.0,
    )

    with patch("excel_intel.server.admission.get_current_working_set_mb", return_value=120.0):
        with pytest.raises(AdmissionRejectedError) as exc_info:
            async with controller.acquire("heavy_sheet_inspection"):
                pass

        assert exc_info.value.exit_code == 429
        assert "exceeds admission threshold" in str(exc_info.value)
        assert controller.active_parsing_jobs == 0
        assert controller.available_slots == 1


@pytest.mark.asyncio
async def test_admission_controller_post_acquisition_recheck() -> None:
    """Verifies that if memory rises while queued, the post-acquisition re-check rejects and releases the slot."""
    controller = AdmissionController(
        concurrency_limit=1,
        throttle_threshold_mb=100.0,
        hard_limit_mb=250.0,
    )

    # Sequence of RSS readings:
    # 1. Worker 1 preflight (50 MB)
    # 2. Worker 1 post-acquisition (50 MB)
    # 3. Worker 2 preflight before queueing (50 MB) -> passes queue entrance
    # 4. Worker 2 post-acquisition after worker 1 finishes (110 MB) -> triggers rejection!
    rss_values = [50.0, 50.0, 50.0, 110.0]

    def mock_rss():
        if rss_values:
            return rss_values.pop(0)
        return 110.0

    worker1_finished = False
    worker2_rejected = False

    async def worker_1():
        nonlocal worker1_finished
        async with controller.acquire("worker_1"):
            await asyncio.sleep(0.05)
            worker1_finished = True

    async def worker_2():
        nonlocal worker2_rejected
        await asyncio.sleep(0.01)  # Ensure worker 1 acquires semaphore first
        try:
            async with controller.acquire("worker_2"):
                pass
        except AdmissionRejectedError as e:
            assert e.exit_code == 429
            assert e.context.get("phase") == "post_acquisition"
            worker2_rejected = True

    with patch("excel_intel.server.admission.get_current_working_set_mb", side_effect=mock_rss):
        await asyncio.gather(worker_1(), worker_2())

    assert worker1_finished is True
    assert worker2_rejected is True
    # Invariant: slot must be released cleanly
    assert controller.active_parsing_jobs == 0
    assert controller.available_slots == 1
