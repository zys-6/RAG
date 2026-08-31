# 22 — Retrieval Evaluation & Pipeline Fix

Last updated: **2026-07-01**

How to **test knowledge retrieval** (fragment + vector search accuracy), what was wrong in the production pipeline, what was fixed in `qa.py`, and all commands to run eval and end-to-end Q&A.

**Related docs:** [11-knowledge-chunking.md](./11-knowledge-chunking.md), [19-knowledge-improvement-recommendations.md](./19-knowledge-improvement-recommendations.md), [13-attu.md](./13-attu.md), [17-text2vec-embedding-model.md](./17-text2vec-embedding-model.md), [24-retrieval-pipeline-internals.md](./24-retrieval-pipeline-internals.md) (theory & data flow)

---

## Why this document exists

The project had **no automated retrieval tests** and a **critical bug** in `search_with_same_outline()` that hurt knowledge Q&A more than embedding model choice. This doc records:

1. How to measure retrieval (global + direct views)
2. What changed in production code
3. Commands to deploy, test, and interpret results

---

## Files changed vs added

### Production (affects live Q&A)

| File | Change |
|------|--------|
| `src/rag/services/qa.py` | **Only runtime file modified** — retrieval pipeline fix |

After editing `qa.py`, restart the QA container:

```powershell
docker compose restart qa_api
```

`docker-compose` mounts `./src` into `qa_api`, so code changes apply on restart (no image rebuild).

### Tooling (test only)

| Path | Purpose |
|------|---------|
| `eval/retrieval_golden.json` | Golden questions + expected chunk (`document_id`, `gold_fragment_index`) |
| `eval/report.json` | Generated metrics (optional; safe to gitignore) |
| `scripts/eval_retrieval.py` | Eval runner — mirrors `qa.py` retrieval logic |

---

## The problem (before fix)

### Bug 1 — Vector hits discarded

Old `search_with_same_outline()`:

```
vector search top-30
  → REPLACE with ALL sibling text under matched headings (200–500+ chunks)
  → vector order and relevance lost
```

Example: J2EE thesis query returned **555** chunks instead of 30.

### Bug 2 — Rerank model present but not wired

| Component | Before fix |
|-----------|------------|
| Reranker model `models/reranker/` | ✅ Present |
| Embedding API `POST /rerank` (port 12356) | ✅ Working |
| `rerank_documents()` in `qa.py` | ✅ Implemented |
| `with_rerank=True` on `search_with_same_outline()` | ⚠️ **Dead parameter — never called rerank** |
| `knowledge_agent` retrieval path | ❌ **No rerank** |

The reranker was **installed but unplugged** from knowledge retrieval.

### Bug 3 — Package filter missing on sibling expansion

Sibling `query()` did not always apply the package `_filter`, risking cross-package leakage when filters failed.

### Symptom in eval (before)

| Case | Issue |
|------|-------|
| `j2ee-keywords` | Gold chunk at **rank 16** (title chunks above keywords line) |
| `outline` mode | **272–553** `retrieved_count` per query |
| LLM context | Hundreds of fragments merged into ~10k-char prompt |

---

## The fix (current pipeline)

Target flow (now implemented in `search_with_same_outline()`):

```
Question
  → vector search top-30 (package filter)
  → expand siblings via parent_id (MERGE, don't replace)
  → dedupe by fragment id
  → apply package filter on sibling query
  → cap rerank pool to 50 (vector hits stay first)
  → rerank via Embedding API /rerank
  → return top 8 for LLM + citations
```

### New / changed symbols in `qa.py`

| Symbol | Role |
|--------|------|
| `RERANK_POOL_MAX = 50` | Max chunks sent to CPU reranker |
| `merge_documents()` | Merge vector hits + siblings, dedupe |
| `cap_for_rerank()` | Truncate pool before rerank (speed) |
| `search_with_same_outline(..., with_rerank=True, top_k=8)` | Now actually reranks and caps output |

### Call sites (unchanged — automatically improved)

| Function | Route |
|----------|-------|
| `knowledge_agent_stream()` | `POST /qa/agent/knowledge_agent` |
| `qa_stream()` (intent `文档`) | `POST /qa/qa` |

---

## Eval results (after fix)

Golden set: 5 cases in `eval/retrieval_golden.json` (J2EE thesis, MBSE paper, OMG SysML RFP, cross-corpus).

| Mode | Recall@5 | MRR | Notes |
|------|----------|-----|-------|
| `vector` | 80% | 0.58 | Baseline embedding only |
| `outline` | 80% | 0.58 | Merge only, no rerank |
| `rerank` | 100% | 0.90 | Vector + rerank |
| **`pipeline`** | **100%** | **0.90** | **Production path** |

Notable: `j2ee-keywords` gold rank **1** (was 16). `retrieved_count` **5–8** per query (was 200–553).

---

## Folder layout

```
document_fragment/
├── eval/
│   ├── retrieval_golden.json    ← edit to add test cases
│   └── report.json              ← generated (--report)
├── scripts/
│   └── eval_retrieval.py        ← eval runner
└── src/rag/services/
    └── qa.py                    ← production retrieval
```

---

## Golden set format

Each case in `eval/retrieval_golden.json`:

```json
{
  "id": "j2ee-keywords",
  "enabled": true,
  "question": "这篇J2EE电子政务论文的关键词有哪些？",
  "document_ids": ["8960b697c1d4e61d1750c0d3ba04f5dd"],
  "gold_document_id": "8960b697c1d4e61d1750c0d3ba04f5dd",
  "gold_fragment_index": 6,
  "gold_text_contains": "关键词",
  "category": "prose"
}
```

| Field | How to find |
|-------|-------------|
| `document_ids` | File MD5 — Attu, `GET /knowledge_manage/file/list`, or `src/api/static/fragment/{md5}.json` |
| `gold_fragment_index` | `index` field in fragment JSON |
| `enabled` | `false` = skipped; use `--include-disabled` to run drafts |

---

## Package ID & search scope

When you call `knowledge_agent`, `retrieval/search`, or scope a golden case, **`package_id` = which knowledge library (知识库) to search**. It is not the document MD5 and not chosen by you at search time — it is assigned when the library is created.

### How `package_id` is generated

| Source | Format | Example |
|--------|--------|---------|
| **Create package** (`POST /knowledge_manage/package/create`) | `package-` + UUID | `package-8b1a8997-579b-5856-941c-183461a3fde7` |
| **Public library** (seeded on first DB init) | Fixed id | `package-00000000000000000000000000000000` (公共知识库) |

Generation in code (`src/rag/mappers/knowledge.py`):

```python
id: str = Field(default_factory=lambda: 'package-' + create_uuid())
# create_uuid() → uuid5(NAMESPACE_DNS, uuid1() + random())
```

You **do not** invent a id when searching. Flow:

```
POST /package/create  →  response includes id  →  use that as package_id
POST /file/upload     →  files linked to that package_id in SQLite
POST /retrieval/search →  package_id limits Milvus to those files' MD5s
```

### `package_id` vs `file_id` (document MD5)

| ID | Meaning | Generated how |
|----|---------|----------------|
| `package_id` | Knowledge library | Server UUID on package create |
| `file_id` | One document in a library | **MD5** of file bytes at upload/index |

Milvus stores vectors for **all** indexed docs. `package_id` filters to the file list in SQLite `File` for that package:

```
package_id → File.get_by(package_id=…) → document_id in [md5, md5, …] → Milvus search
```

### Search scope options (`retrieval/search`)

| Request body | Search scope |
|--------------|----------------|
| `package_id` set | All files in that library (normal) |
| `document_ids` set | Only those MD5s (manual / eval golden set) |
| Neither set | **Entire** Milvus `fragments` collection (dev only — cross-library) |

For production-like tests, always set `package_id` or `document_ids`.

### How to list existing `package_id` values

Swagger: `GET /knowledge_manage/package/list?user_id=...`

```powershell
docker exec document_fragment-qa_api-1 python -c "from rag.mappers.knowledge import Package; [print(p.id, p.name) for p in Package.get_by()]"
```

Files in one package:

```powershell
docker exec document_fragment-qa_api-1 python -c "from rag.mappers.knowledge import File; [print(f.file_id, f.file_name) for f in File.get_by(package_id='YOUR_PACKAGE_ID')]"
```

---

## Eval modes

| Mode | What it tests | LLM required? |
|------|---------------|---------------|
| `vector` | Milvus embedding search only | No |
| `outline` | Vector + sibling merge (no rerank) | No |
| `rerank` | Vector top-30 + rerank | No |
| `pipeline` | Merge + rerank + top-8 (**production**) | No |
| `all` | All four modes | No |

Metrics: **Recall@5/10/30**, **MRR**, per-case **gold_rank** and **top_hits** (`--verbose`).

---

## Commands

All commands assume project root:

```powershell
cd D:\setup\setup\document_fragment
```

### Start services

```powershell
docker start milvus-standalone
docker compose up -d
docker compose restart qa_api    # after qa.py changes
```

### Pipeline eval (~1–2 min for 5 cases)

Use `PYTHONUNBUFFERED=1` so progress prints immediately (rerank on CPU is slow).

```powershell
docker run --rm -e PYTHONUNBUFFERED=1 -v "${PWD}:/work" `
  -e MILVUS_URI=http://host.docker.internal:19530 `
  -e EMBEDDING_URL=http://host.docker.internal:12356/embeddings `
  -e RERANK_URL=http://host.docker.internal:12356/rerank `
  --add-host=host.docker.internal:host-gateway `
  document_fragment:mupdf-3 `
  python /work/scripts/eval_retrieval.py --mode pipeline --verbose
```

### Save report

```powershell
docker run --rm -e PYTHONUNBUFFERED=1 -v "${PWD}:/work" `
  -e MILVUS_URI=http://host.docker.internal:19530 `
  -e EMBEDDING_URL=http://host.docker.internal:12356/embeddings `
  -e RERANK_URL=http://host.docker.internal:12356/rerank `
  --add-host=host.docker.internal:host-gateway `
  document_fragment:mupdf-3 `
  python /work/scripts/eval_retrieval.py --mode all --verbose --report /work/eval/report.json
```

### Fast vector-only sanity check (~seconds)

```powershell
docker run --rm -e PYTHONUNBUFFERED=1 -v "${PWD}:/work" `
  -e MILVUS_URI=http://host.docker.internal:19530 `
  -e EMBEDDING_URL=http://host.docker.internal:12356/embeddings `
  --add-host=host.docker.internal:host-gateway `
  document_fragment:mupdf-3 `
  python /work/scripts/eval_retrieval.py --mode vector --verbose
```

### Host Python (optional)

```powershell
pip install pymilvus requests pyyaml
python scripts/eval_retrieval.py --mode pipeline --verbose
```

### Direct retrieval API (no LLM) — recommended for dev

**There is no LLM in this path.** It uses the same code as `knowledge_agent` retrieval (`search_with_same_outline`).

Swagger: http://localhost:12357/docs → `POST /knowledge_manage/retrieval/search`

| Field | Required | Description |
|-------|----------|-------------|
| `query` | yes | Your search sentence |
| `package_id` | one of | Scope to all files in a knowledge package |
| `document_ids` | one of | Scope to specific file MD5 list |
| `mode` | no | `vector` \| `outline` \| `pipeline` (default `pipeline`) |
| `limit` | no | Vector search limit (default 30) |
| `top_k` | no | Results after rerank (default 8) |

Example body:

```json
{
  "query": "这篇J2EE电子政务论文的关键词有哪些？",
  "package_id": "package-8b1a8997-579b-5856-941c-183461a3fde7",
  "mode": "pipeline"
}
```

PowerShell:

```powershell
$body = @{
  query = "你的搜索句子"
  package_id = "package-8b1a8997-579b-5856-941c-183461a3fde7"
  mode = "pipeline"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:12357/knowledge_manage/retrieval/search" `
  -Method POST -ContentType "application/json; charset=utf-8" -Body $body
```

Response `data.hits[]` includes `rank`, `file_name`, `index`, `page_content` — no streamed answer.

After adding this endpoint, restart QA API:

```powershell
docker compose restart qa_api
```

**Other no-LLM options (already existed):**

| Tool | What it does |
|------|----------------|
| `POST /embeddings` (port 12356) | Embed text only — does **not** search Milvus |
| `POST /rerank` (port 12356) | Rerank texts you supply — does **not** search |
| Attu (port 8000) | Manual Milvus vector search in GUI |
| `scripts/eval_retrieval.py` | Batch golden-set metrics |

### End-to-end knowledge agent (needs LLM)

Swagger: http://localhost:12357/docs → `POST /qa/agent/knowledge_agent`

Example body (J2EE package):

```json
{
  "package_id": "package-8b1a8997-579b-5856-941c-183461a3fde7",
  "task_id": "test-001",
  "query": "这篇J2EE电子政务论文的关键词有哪些？",
  "history": [],
  "thing_pattern": false,
  "user_id": "eb02ba91-6e58-4433-aa7e-1bac12d942c2"
}
```

Check retrieval in logs:

```powershell
docker logs document_fragment-qa_api-1 --tail 50
```

Expect: `merged docs len:`, `rerank pool capped:`, ~8 chunks to LLM.

### Find package_id / file_id

```powershell
docker exec document_fragment-qa_api-1 python -c "from rag.mappers.knowledge import Package, File; [print(p.id, p.name) for p in Package.get_by()[:10]]"
docker exec document_fragment-qa_api-1 python -c "from rag.mappers.knowledge import File; [print(f.file_id, f.file_name) for f in File.get_by(package_id='YOUR_PACKAGE_ID')]"
```

---

## Global view vs direct view

| View | Tool | What you see |
|------|------|--------------|
| **Global** | `eval_retrieval.py` summary table | Recall@k, MRR across all cases |
| **Global** | `--report eval/report.json` | Full JSON for dashboards / diffs |
| **Direct** | `--verbose` top_hits | Rank, file, fragment index, text preview per query |
| **Direct** | Attu (http://localhost:8000) | Browse Milvus rows, manual vector search |
| **Direct** | `src/api/static/fragment/{md5}.json` | Raw chunks after parse |
| **Direct** | `knowledge_agent` `references` in SSE | What production sends to LLM |

---

## Interpreting output

| Signal | Good | Investigate |
|--------|------|-------------|
| `pipeline` Recall@5 | ≥ 80% on your golden set | Embedding model, chunking, or bad gold labels |
| `gold_rank` | 1–3 | Rerank or query wording |
| `retrieved_count` | 5–8 | If >> 8, `top_k` or rerank path broken |
| `rerank pool capped: N -> 50` | Normal for large docs | N > 50 expected on long PDFs |
| `vector` OK, `pipeline` bad | Rerank or merge logic | |
| All modes miss | Wrong `document_id` / not indexed | Attu + fragment JSON |

---

## Still open (not fixed in this work)

| Item | Impact |
|------|--------|
| Tiny title-only chunks dominate raw vector search | `vector` mode still 80% Recall@5 |
| Long fragments (>256 tokens) = one weak embedding | Index-time chunking |
| No chunk overlap | Cross-boundary answers |
| LLM at `API_BASE` unreachable | Blocks full Q&A, not retrieval eval |
| Delete file leaves orphan Milvus vectors | Data integrity |
| `qa.py` monolithic (~2700 lines) | Maintainability |

See [19-knowledge-improvement-recommendations.md](./19-knowledge-improvement-recommendations.md) for full priority list.

---

## Quick reference

| Goal | Command / location |
|------|-------------------|
| Deploy retrieval fix | `docker compose restart qa_api` |
| Test production retrieval | `eval_retrieval.py --mode pipeline` |
| **Ad-hoc query in Swagger (no LLM)** | `POST /knowledge_manage/retrieval/search` |
| Add test case | Edit `eval/retrieval_golden.json` |
| Production retrieval code | `qa.py` → `search_with_same_outline()` |
| Rerank API | http://localhost:12356/docs → `/rerank` |
| Knowledge Q&A API | http://localhost:12357/docs → `/qa/agent/knowledge_agent` |

---

## One-page mental model

```
                    ┌─────────────────────────────────────┐
                    │  eval/retrieval_golden.json         │
                    │  (questions + gold chunk labels)    │
                    └─────────────────┬───────────────────┘
                                      │
                    scripts/eval_retrieval.py
                    (vector | outline | rerank | pipeline)
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
        Embedding API            Milvus                 report.json
        :12356 /embeddings      fragments              + console metrics
              :12356 /rerank

Production path (qa.py):
  knowledge_agent → search_with_same_outline → top 8 → LLM stream
```

**Short answer:** Test retrieval with `eval/` + `scripts/eval_retrieval.py`. Production fix is only in `qa.py` — merge siblings instead of replacing vector hits, wire existing rerank, cap to top 8.
