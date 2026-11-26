"""
InsightHub — Ingestion Worker Tasks (ARQ)

Nhận job từ Redis queue, gọi process_document() trong thread pool
để không block event loop của ARQ.

Retry: ARQ chỉ retry khi task raise `arq.Retry` (hoặc job bị cancel) —
exception thường sẽ kết thúc job ngay. Vì vậy task tự bắt lỗi và raise
Retry với backoff tăng dần; chỉ đánh dấu 'failed' ở lần thử cuối.
"""

import asyncio
import logging

from arq import Retry

from app.services.ingestion import _update_status, process_document

logger = logging.getLogger("insighthub.worker")

MAX_TRIES = 3
RETRY_BASE_DELAY_S = 10  # backoff: 10s, 20s, ...


async def ingest_document(
    ctx: dict,
    document_id: int,
    filename: str,
    content: bytes,
) -> int:
    """ARQ task: chunk + embed + store một tài liệu.

    process_document() dùng psycopg sync pool — chạy trong executor
    để tránh block event loop ARQ.
    """
    job_try: int = ctx.get("job_try", 1)
    logger.info(
        "Worker nhận job document_id=%d filename=%s try=%d/%d",
        document_id,
        filename,
        job_try,
        MAX_TRIES,
    )

    loop = asyncio.get_running_loop()
    try:
        chunk_count: int = await loop.run_in_executor(
            None, process_document, document_id, filename, content
        )
    except Exception as exc:
        if job_try < MAX_TRIES:
            delay = RETRY_BASE_DELAY_S * job_try
            logger.warning(
                "Document %d lỗi lần %d/%d, retry sau %ds: %s",
                document_id,
                job_try,
                MAX_TRIES,
                delay,
                exc,
            )
            raise Retry(defer=delay) from exc
        logger.exception("Document %d thất bại sau %d lần", document_id, job_try)
        await loop.run_in_executor(None, _update_status, document_id, "failed")
        raise

    logger.info("Document %d xử lý xong: %d chunks", document_id, chunk_count)
    return chunk_count
