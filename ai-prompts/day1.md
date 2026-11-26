# Day 1 AI Prompts — InsightHub: Review & Fix refactor v1

> Tài liệu chứng minh AI-augmented workflow.
> Mỗi prompt ghi rõ: mục đích, prompt thật đã gõ, agent làm gì, và tôi review / điều chỉnh gì.

**Bối cảnh:** repo fork về đã có sẵn bản refactor v0 → v1 (ARQ worker, Redis, API trả 202).
Phần việc của tôi trong Day 1: dùng Claude Code để **hiểu, review và sửa** bản v1 đó,
kiểm chứng bằng test thật thay vì tin vào code/tài liệu có sẵn.

**Tool:** Claude Code (Opus 5.5) trong VS Code — **Ngày:** 2026-11-26 — **Nhánh:** `day1-fixes`

---

## Prompt 1 — Khởi tạo CLAUDE.md

**Prompt**:
```
/init
```

**Agent output (tóm tắt)**:
- Repo đã có CLAUDE.md → agent đối chiếu với code thật và đề xuất cải tiến thay vì viết mới.
- Phát hiện CLAUDE.md cũ sai/thiếu: compose thực tế có 9 service (thêm `litellm`, profile
  `monitoring`, `ollama`), thiếu provider `LLM_PROVIDER=litellm`, số test bot sai (44 → 51),
  thiếu hoàn toàn Day 3 (Terraform/Helm/CI) và Day 4 (observability/chaos).
- Ghi lại điều chỉ thấy khi đọc nhiều file: worker image **copy `api/app`** → sửa
  `api/app/services` phải rebuild cả api lẫn worker.

**Review & điều chỉnh**:
- Giữ ràng buộc ≤ 200 dòng (verify-day-1 kiểm tra) → cắt bảng version MCP, gộp lệnh.
- Sau khi fix code (Prompt 4), cập nhật lại phần retry / queue depth cho khớp code mới.

---

## Prompt 2 — Review tài liệu Day 1

**Prompt**:
```
review day1_reame
```

**Agent output (tóm tắt)** — agent đối chiếu `DAY_01_README.md` với code, script và source ARQ:
- **Sai nghiêm trọng:** README ghi "retry 3 lần exponential backoff", nhưng ARQ chỉ retry khi
  task `raise arq.Retry`; `tasks.py` raise exception thường → **không retry lần nào**.
- `/health` không tồn tại (chỉ có `/healthz`, `/readyz`); smoke test v1 là 7/7 chứ không 6/6;
  "Option B — stash v1" không làm được vì v1 đã commit.
- `verify-day-1.sh` bước pytest dùng `grep "passed"` → "2 failed, 6 passed" vẫn PASS.

**Review & điều chỉnh**:
- Tôi báo cho agent đây là **bài tập về nhà**. Agent chỉ ra fork đã chứa sẵn solution và prompt
  log của người khác → tôi chọn **"chỉ giải thích solution" trước**, chưa cho sửa code,
  để tự hiểu luồng v0 → v1 (queue, 202, `run_in_executor`, idempotency) trước khi fix.

---

## Prompt 3 — Lập danh sách cần fix

**Prompt**:
```
các phần cần fix
```

**Agent output (tóm tắt)** — 6 mục xếp theo mức độ, kèm code đề xuất:

| # | Vấn đề | Mức |
|---|---|---|
| 1 | Retry không hoạt động | Cao |
| 2 | `process_document` chưa idempotent → chạy lại job bị trùng chunk | Cao |
| 3 | Gauge `queue_depth`: API `inc()`, worker `dec()` ở 2 process khác registry → lệch | TB |
| 4 | Nội dung file (≤10MB) đi qua Redis | Thấp |
| 5 | Tài liệu sai (README, CLAUDE.md) | TB |
| 6 | Script chấm PASS cả khi test fail | TB |

**Review & điều chỉnh**:
- Mục 4 là thay đổi thiết kế (cần shared storage ở compose + Helm + Terraform) → **hoãn**,
  ghi thành "known limitation" trong tài liệu.

---

## Prompt 4 — Fix theo vòng lặp, test lại toàn bộ

**Prompt**:
```
tiến hành fix từng phần, review code, test -> commit

=> lập lại quy trình trên đến khi hoàn thành thì test lại toàn bộ
```

**Agent output (tóm tắt)**:
- Tạo nhánh `day1-fixes`; chạy test trong container Python 3.12 (khớp Dockerfile, máy local là
  3.14 không cài được deps đã pin). Baseline trước khi sửa: api 8/8, bot 51/51.
- Trước khi sửa mục 1, **đọc source ARQ 0.26.3** để xác nhận: chỉ `Retry`/`CancelledError`
  mới retry, exception khác → `finish = True`.
- Mỗi phần: sửa → ruff → test → review diff → commit (Conventional Commits).

| Commit | Nội dung |
|---|---|
| `a6e125b` | `raise Retry(defer=10s × job_try)`, chỉ set `failed` ở lần cuối; `MAX_TRIES` dùng chung |
| `3823076` | DELETE chunk cũ + INSERT trong cùng transaction |
| `303c16b` | `queue_depth` = `ZCARD arq:queue` mỗi lần scrape, giữ tên metric (Day 4 dùng) |
| `c419eb6` | Sửa DAY_01_README + CLAUDE.md |
| `0012927` | verify-day-1 dựa vào exit code pytest, chạy thêm test worker |
| `70e51ce` | Khoá row `documents` (`FOR UPDATE`) — xem bên dưới |

**Review & điều chỉnh** (phần quan trọng nhất — review code AI như review junior):
- **Test tích hợp bắt được lỗi mà unit test bỏ sót.** Enqueue 2 job cùng document → 2 job
  chạy **song song** (`max_jobs=10`) → còn **2 chunk** thay vì 1. Nguyên nhân: READ COMMITTED,
  DELETE của job sau dùng snapshot trước khi job trước commit. Unit test chỉ thử chạy lại
  *tuần tự*. Fix: `SELECT ... FOR UPDATE` trên row `documents` → 3 job song song còn 1 chunk.
- Ruff 0.17 bật nhiều rule mặc định, code cũ có sẵn 95 lỗi → quy tắc: **code mới không thêm lỗi**,
  không sửa lan sang code không liên quan.
- Smoke test chạy bằng Git Bash trên Windows FAIL 2 check — **không phải lỗi code**: `python3`
  là stub Microsoft Store, và `curl -d` gửi tiếng Việt bị lỗi encoding (đã chứng minh bằng
  request ASCII chạy được). Chạy lại trong container Linux → PASS.

**Kết quả test toàn bộ (trên stack 5 service thật):**
- Unit test: **68/68** (api 12, worker 5, bot 51 — thêm 9 test mới).
- Retry: PDF hỏng → thử 1 → 10s → thử 2 → 20s → thử 3 → `failed`.
- Queue depth: 0 → 2 (dừng worker, upload 2 file) → 0 (bật lại worker).
- Idempotency: 3 job song song cùng document → 1 chunk.
- `smoke-test.sh` **7/7**, `verify-day-1.sh` **12/12**.

---

## Bài học

1. **Không tin comment/tài liệu — đọc source thư viện.** Cả code lẫn README đều nói "ARQ tự retry
   exponential backoff"; 1 lần đọc `arq/worker.py` cho thấy điều đó sai.
2. **Unit test với mock không đủ cho bài toán đồng thời.** Lỗi race condition chỉ lộ ra khi
   chạy trên Postgres thật với nhiều job song song.
3. **Bắt agent làm theo vòng lặp nhỏ** (fix → review → test → commit) giúp mỗi commit dễ review
   và khi test tích hợp phát hiện lỗi thì biết ngay commit nào cần bổ sung.
4. **Còn lại (chưa xử lý):** khi job vượt `job_timeout`, ARQ huỷ coroutine nhưng thread chạy
   `process_document` vẫn tiếp tục; file vẫn đi qua Redis (mục 4).
