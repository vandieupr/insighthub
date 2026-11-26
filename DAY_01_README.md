# DAY 01 — AI Coding Agent Refactor
## Hướng dẫn Mentor: Demo & Lab Step-by-Step

> **Đối tượng:** Trainer / Mentor hướng dẫn học viên  
> **Thời lượng:** 2.5 giờ (150 phút)  
> **Ngày:** Day 1 trong Module 7 — AI-Native DevOps  
> **Branch học viên làm việc:** `day1-refactor`

---

## Mục lục

1. [Tổng quan & Mục tiêu](#1-tổng-quan--mục-tiêu)
2. [Chuẩn bị trước buổi (Mentor Checklist)](#2-chuẩn-bị-trước-buổi-mentor-checklist)

> Các bước lab chi tiết (Bước 0–5, troubleshooting, homework): [`docs/lab-guides/Day1-AI-Coding-Agents.md`](docs/lab-guides/Day1-AI-Coding-Agents.md).

---

## 1. Tổng quan & Mục tiêu

### Bức tranh lớn

Day 1 là điểm khởi đầu — học viên nhận InsightHub **v0** (3 service, ingest đồng bộ) và chuyển thành **v1** (5 service, async queue). Đây không phải bài "refactor code đẹp hơn" — đây là bài học về **cách làm việc với AI agent như một kỹ sư senior**.

Điểm cốt lõi cần học viên hiểu cuối buổi:
> **AI tăng tốc, không thay thế phán đoán kỹ thuật. Review code AI sinh như review một junior.**

### V0 → V1: thay đổi kiến trúc

| Chiều | v0 (trước Day 1) | v1 (sau refactor) |
|---|---|---|
| Số service | 3 (web, api, postgres) | 5 (+redis, +ingestion-worker) |
| Upload flow | Sync trong API request | 202 ngay → enqueue → worker xử lý nền |
| Queue | Không có | Redis + ARQ |
| Retry | Không | Tối đa 3 lần thử, backoff 10s → 20s qua `raise Retry(defer=...)` |
| Idempotency | — | Chạy lại job thay thế chunk cũ (DELETE + INSERT cùng transaction) |
| Metrics | Không | `ingestion_queue_depth` Gauge = `ZCARD arq:queue` mỗi lần scrape |
| Scalability | API và ingest dùng chung resource | Worker scale độc lập |

**Lưu ý kỹ thuật cho mentor:**

- ARQ **chỉ retry khi task raise `arq.Retry`** (hoặc job bị cancel). Exception thường kết thúc job ngay — `max_tries` không có tác dụng. Đây là lỗi AI agent hay sinh ra, dùng làm ví dụ review.
- Giới hạn đã biết của v1: API gửi **nguyên nội dung file** (≤ 10MB) qua Redis. Cải tiến: lưu file vào shared storage (volume / S3) và chỉ enqueue đường dẫn.

### Mục tiêu học viên đạt được cuối Day 1

| # | Mục tiêu | Verify |
|---|---|---|
| 1 | Phân biệt IDE-first / CLI-first / Cloud agent | Trả lời quiz |
| 2 | Vận hành Claude Code: CLAUDE.md, task refactor | Demo live |
| 3 | Refactor InsightHub v0 → v1 (5 service, async) | `verify-day-1.sh` PASS |
| 4 | Viết Constraint-first prompt 4-part | `ai-prompts/day1.md` |
| 5 | Review plan AI trước khi cho thực thi | Documented trong prompt log |

### Artifacts học viên nộp

```
1. CLAUDE.md                  — 6 section (verify cần ≥ 5 heading `## `), ≤ 200 dòng
2. ingestion-worker/          — Dockerfile + worker/tasks.py + worker/settings.py + requirements.txt
3. docker-compose.yml         — 5 service (thêm redis, ingestion-worker)
4. api/app/core/queue.py      — ARQ pool singleton
5. api/app/routers/documents.py — trả 202, enqueue thay vì sync call
6. api/tests/                 — test_documents.py, test_ingestion.py pass
7. ai-prompts/day1.md         — ≥ 3 prompts với giải thích, mỗi prompt dưới heading `## Prompt ...`
                                (verify-day-1.sh đếm đúng pattern này)
8. PR trên GitHub             — title: [Day 1] Refactor ingestion async + Redis queue
```

---

## 2. Chuẩn bị trước buổi (Mentor Checklist)

### 2.1. Kiểm tra environment demo của mentor

```bash
# Claude Code CLI
claude --version
# Đăng nhập: chạy `claude` rồi gõ /login (tài khoản Claude),
# hoặc export ANTHROPIC_API_KEY=... nếu dùng API key

# Docker
docker --version          # ≥ 24
docker compose version    # ≥ 2.x

# Python (cho pytest demo)
python3 --version         # ≥ 3.11
pip install pytest ruff   # nếu chưa có

# Node.js (cho web service)
node --version            # ≥ 20

# Verify InsightHub chạy được (trước khi demo)
docker compose up --build -d
bash scripts/smoke-test.sh   # v1 (main): PASS 7/7 — v0 (commit 10ea69a): PASS 6/6
```

### 2.2. Chuẩn bị "v0 state" để demo refactor

Mentor cần có một bản InsightHub v0 sạch (chưa refactor) để demo trực tiếp trước lớp. Các cách:

**Option A — Tạo branch v0 riêng:**

```bash
git checkout 10ea69a      # commit khởi tạo v0
git checkout -b day1-demo-start
# Đây là trạng thái v0 — 3 service, sync ingest
```

**Option B — Worktree v0 song song với v1 (mở 2 cửa sổ để so sánh):**

```bash
git worktree add ../insighthub-v0 10ea69a
# ../insighthub-v0 = v0, thư mục hiện tại = v1 (solution)
# Dọn sau buổi: git worktree remove ../insighthub-v0
```

**Lưu ý:** Solution v1 đã nằm sẵn trên `main`. Demo từ v0 và không chia sẻ link nhánh solution cho học viên trước buổi học.

### 2.3. Chuẩn bị tình huống "vibe-coding" để phản ví dụ

Chuẩn bị sẵn 1 đoạn code AI sinh sai để demo lý do cần review plan trước. Ví dụ:

- Agent đặt `max_tries=3` rồi tin là "ARQ tự retry với exponential backoff", trong khi task raise exception thường → **không retry lần nào**. Cách đúng: `raise Retry(defer=...)` khi còn lượt.
- Agent tự `pickle.dumps()` bytes trước khi enqueue — **thừa**, vì ARQ đã serialize job args (mặc định bằng pickle).
- Agent `inc()` gauge ở API và `dec()` ở worker — hai process có registry Prometheus riêng nên số liệu lệch.

### 2.4. Setup sample documents

```bash
ls sample-docs/
# phải có ít nhất 1 file .md hoặc .pdf để demo upload
# so-tay-van-hanh.md đã có trong repo
```

### 2.5. Verify API key hoạt động

```bash
# API sống (KHÔNG kiểm tra key): /healthz, DB sẵn sàng: /readyz
curl -s http://localhost:8000/healthz

# Kiểm tra key LLM thật sự hoạt động (Gemini mặc định):
# câu trả lời KHÔNG được bắt đầu bằng "[Chế độ fallback"
ANS=$(curl -sf -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"question":"Tài liệu nói gì?"}')
if ! echo "$ANS" | grep -q '"answer"'; then echo "❌ /chat lỗi"
elif echo "$ANS" | grep -q "Chế độ fallback"; then echo "❌ Đang chạy fallback — kiểm tra GEMINI_API_KEY trong .env"
else echo "✅ LLM key OK"; fi

# Test upload + chat flow (smoke test)
bash scripts/smoke-test.sh
```