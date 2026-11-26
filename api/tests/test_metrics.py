"""Tests cho /metrics — queue depth đọc trực tiếp từ Redis (ZCARD arq:queue)."""

import re
from unittest.mock import AsyncMock

from redis.exceptions import ConnectionError as RedisConnectionError


def _queue_depth(body: str) -> float:
    m = re.search(r"^insighthub_ingestion_queue_depth (\S+)$", body, re.MULTILINE)
    assert m, "metric insighthub_ingestion_queue_depth không có trong /metrics"
    return float(m.group(1))


def test_metrics_queue_depth_reads_redis(client):
    c, _, arq_pool = client
    arq_pool.zcard = AsyncMock(return_value=4)

    res = c.get("/metrics")

    assert res.status_code == 200
    arq_pool.zcard.assert_awaited_once_with("arq:queue")
    assert _queue_depth(res.text) == 4


def test_upload_does_not_touch_queue_depth(client):
    """Upload chỉ enqueue; gauge chỉ thay đổi khi /metrics đọc lại Redis."""
    c, mock_conn, arq_pool = client
    arq_pool.zcard = AsyncMock(return_value=0)
    c.get("/metrics")
    mock_conn.execute.return_value.fetchone.return_value = (1,)

    c.post("/documents", files={"file": ("a.md", b"# hi", "text/markdown")})

    assert _queue_depth(c.get("/metrics").text) == 0


def test_metrics_survives_redis_error(client):
    c, _, arq_pool = client
    arq_pool.zcard = AsyncMock(side_effect=RedisConnectionError("down"))

    res = c.get("/metrics")

    assert res.status_code == 200
    assert "insighthub_ingestion_queue_depth" in res.text
