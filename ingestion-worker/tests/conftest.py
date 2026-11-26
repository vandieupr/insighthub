"""Cho phép import cả `worker.*` lẫn `app.*` (code chung copy từ api/ trong Docker image)."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for p in (_ROOT / "api", _ROOT / "ingestion-worker"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
