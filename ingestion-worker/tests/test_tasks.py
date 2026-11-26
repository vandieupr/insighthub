"""Tests cho ARQ task ingest_document — retry semantics."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from arq import Retry

from worker import tasks


def _run(coro):
    return asyncio.run(coro)


def test_success_returns_chunk_count():
    with (
        patch.object(tasks, "process_document", return_value=7) as proc,
        patch.object(tasks, "_update_status") as upd,
    ):
        result = _run(tasks.ingest_document({"job_try": 1}, 1, "a.md", b"x"))

    assert result == 7
    proc.assert_called_once_with(1, "a.md", b"x")
    upd.assert_not_called()


@pytest.mark.parametrize("job_try", [1, 2])
def test_failure_before_last_try_raises_retry_and_keeps_status(job_try):
    with (
        patch.object(tasks, "process_document", side_effect=RuntimeError("embed 503")),
        patch.object(tasks, "_update_status") as upd,
        pytest.raises(Retry) as exc_info,
    ):
        _run(tasks.ingest_document({"job_try": job_try}, 1, "a.md", b"x"))

    # Backoff tăng dần theo số lần thử (ARQ lưu defer theo ms)
    assert exc_info.value.defer_score == tasks.RETRY_BASE_DELAY_S * job_try * 1000
    upd.assert_not_called()  # chưa được đánh dấu failed khi còn lượt retry


def test_failure_on_last_try_marks_failed_and_reraises():
    with (
        patch.object(tasks, "process_document", side_effect=RuntimeError("embed 503")),
        patch.object(tasks, "_update_status") as upd,
        pytest.raises(RuntimeError, match="embed 503"),
    ):
        _run(tasks.ingest_document({"job_try": tasks.MAX_TRIES}, 1, "a.md", b"x"))

    upd.assert_called_once_with(1, "failed")


def test_worker_settings_use_same_max_tries():
    with patch("arq.connections.RedisSettings.from_dsn", return_value=MagicMock()):
        from worker.settings import WorkerSettings

    assert WorkerSettings.max_tries == tasks.MAX_TRIES
    assert WorkerSettings.retry_jobs is True
