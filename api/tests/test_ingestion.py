"""Tests cho ingestion service — process_document pipeline."""

from unittest.mock import MagicMock, patch


def test_extract_text_txt():
    from app.services.ingestion import extract_text

    result = extract_text("hello.txt", b"Hello World")
    assert "Hello World" in result


def test_extract_text_md():
    from app.services.ingestion import extract_text

    result = extract_text("readme.md", b"# Title\nContent here")
    assert "Title" in result


def test_extract_text_unsupported_raises():
    from app.services.ingestion import extract_text
    import pytest

    with pytest.raises(ValueError, match="Định dạng không hỗ trợ"):
        extract_text("file.docx", b"binary data")


def test_process_document_empty_text():
    """process_document với file rỗng → chunk_count=0, status='ready'."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)

    with (
        patch("app.core.db.get_pool") as mock_pool,
        patch("app.services.ingestion.embed", return_value=[]),
        patch("app.services.ingestion.chunk_text", return_value=[]),
    ):
        mock_pool.return_value.connection.return_value = mock_conn

        from app.services.ingestion import process_document

        result = process_document(1, "empty.txt", b"")
        assert result == 0


def _run_process_document(mock_conn):
    with (
        patch("app.core.db.get_pool") as mock_pool,
        patch("app.services.ingestion.chunk_text", return_value=["c1", "c2"]),
        patch("app.services.ingestion.embed", return_value=[[0.1], [0.2]]),
    ):
        mock_pool.return_value.connection.return_value = mock_conn

        from app.services.ingestion import process_document

        return process_document(42, "doc.txt", b"c1 c2")


def test_process_document_is_idempotent():
    """Chạy lại cùng document → khoá row, xoá chunk cũ rồi mới insert (1 transaction)."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)

    for _ in range(2):  # mô phỏng ARQ chạy lại job
        mock_conn.reset_mock()
        assert _run_process_document(mock_conn) == 2

        sqls = [c.args[0].strip() for c in mock_conn.execute.call_args_list]
        assert sqls[0] == "SELECT id FROM documents WHERE id = %s FOR UPDATE"
        assert sqls[1].startswith("DELETE FROM chunks WHERE document_id")
        assert mock_conn.execute.call_args_list[0].args[1] == (42,)
        assert mock_conn.execute.call_args_list[1].args[1] == (42,)
        assert sum(s.startswith("INSERT INTO chunks") for s in sqls) == 2
        assert sqls[-1].startswith("UPDATE documents SET status = 'ready'")
        mock_conn.transaction.assert_called_once()
