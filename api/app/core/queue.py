"""
InsightHub API — ARQ job queue

Module-level singleton pattern: pool được khởi tạo trong lifespan của FastAPI,
sau đó các router lấy qua get_arq_pool().
"""

import logging

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from arq.constants import default_queue_name
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.metrics import ingestion_queue_depth

logger = logging.getLogger("insighthub.queue")

_arq_pool: ArqRedis | None = None


async def open_arq_pool() -> None:
    global _arq_pool
    settings = get_settings()
    _arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    logger.info("ARQ Redis pool opened: %s", settings.redis_url)


def get_arq_pool() -> ArqRedis | None:
    return _arq_pool


async def refresh_queue_depth() -> None:
    """Đặt gauge queue depth = số job trong sorted set của ARQ.

    ARQ giữ job trong `arq:queue` tới khi xong (kể cả đang chạy hoặc chờ retry),
    nên ZCARD = pending + in-progress. Đọc thẳng từ Redis thay vì inc/dec ở
    hai process khác nhau (API và worker có registry Prometheus riêng → lệch).
    Lỗi Redis không được làm hỏng /metrics.
    """
    pool = get_arq_pool()
    if pool is None:
        return
    try:
        ingestion_queue_depth.set(await pool.zcard(default_queue_name))
    except RedisError as exc:
        logger.warning("Không đọc được queue depth từ Redis: %s", exc)


async def close_arq_pool() -> None:
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.aclose()
        _arq_pool = None
        logger.info("ARQ Redis pool closed")
