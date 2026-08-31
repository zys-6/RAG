# 16 — Milvus Code Locations

Where this project **connects to and operates Milvus** in application code — file paths, operations, and how they fit the RAG pipeline.

Use this as a quick reminder when debugging indexing, search, or knowledge-base admin. For Milvus concepts and GUI/CLI usage, see [14-milvus-introduction.md](./14-milvus-introduction.md), [13-attu.md](./13-attu.md), and [15-milvus-cli-and-plain-usage.md](./15-milvus-cli-and-plain-usage.md).

---

## Summary

| Layer | File | Milvus operations |
|-------|------|-------------------|
| **Config** | `src/rag/configs/app_config_pro.yaml` | `MILVUS_URI`, `MILVUS_COLLECTION` |
| **Write (indexing)** | `src/api/services/utils.py` | `create_collection`, `insert`, `query`, `refresh_load` |
| **Read (RAG search)** | `src/rag/services/qa.py` | `search`, `query` |
| **Knowledge admin** | `src/rag/services/knowledge.py` | `query`, `drop_collection` |
| **API routes** | `src/rag/controllers/knowledge_mange.py` | Exposes delete/list Milvus endpoints |
| **Document parsers** | `src/api/services/pdf.py`, `word.py`, `caj.py` | Trigger indexing via `@insert_fragments_into_milvus` |

**Client library:** `pymilvus.MilvusClient` (v2.4.x)

**Collection name:** `fragments` (`MILVUS_COLLECTION` / `COLLECTION_NAME`)

**Default URI:** `http://host.docker.internal:19530` (from app containers)

---

## Configuration

```yaml
# src/rag/configs/app_config_pro.yaml
MILVUS_COLLECTION : 'fragments'
MILVUS_URI : 'http://host.docker.internal:19530'
```

Dev override: `src/rag/configs/app_config_dev.yaml`

Connection keys are also documented in [05-configuration.md](./05-configuration.md).

---

## 1. Client setup & indexing — Document API

**File:** `src/api/services/utils.py`

Creates the shared `milvus_client` used by Document API indexing and Knowledge API reads.

| Symbol | Role |
|--------|------|
| `milvus_client` | Module-level `MilvusClient(MILVUS_URI)` |
| `insert_fragments_into_milvus` | Decorator: embed chunks → insert into Milvus |
| `get_vectors()` | Calls Embedding API; vectors are **not** stored by Milvus client directly |

**Milvus calls in the decorator:**

1. `has_collection` / `create_collection` — create `fragments` on first upload
2. `query` — skip duplicate uploads (`document_id == md5`)
3. `insert` — write chunk rows (vector + metadata)
4. `refresh_load` — reload collection after insert

**Indexed fields per row:** `id`, `vector`, `page_content`, `pages`, `coordinates`, `outline`, `document_id`, `package_id`, `parent_id`, `num_tokens`, `index`, `file_name`, `type`

### Who triggers indexing

| File | Function | Notes |
|------|----------|-------|
| `src/api/services/pdf.py` | `process_pdf` | `@insert_fragments_into_milvus` |
| `src/api/services/word.py` | `process_word` | `@insert_fragments_into_milvus` |
| `src/api/services/caj.py` | `process_caj` | Converts CAJ → PDF, then calls `process_pdf` |

After Milvus insert, fragment JSON is also saved to `src/api/static/fragment/{md5}.json` for citations.

---

## 2. RAG retrieval — QA API

**File:** `src/rag/services/qa.py`

Separate module-level `milvus_client = MilvusClient(MILVUS_URI)`.

| Function | Milvus API | Purpose |
|----------|------------|---------|
| `search(text, filter, limit)` | `milvus_client.search()` | Vector similarity search (question → nearest chunks) |
| `query(filter)` | `milvus_client.query()` | Metadata-only lookup (no ranking) |
| `search_with_same_outline(text, _filter)` | `search` + `query` | Retrieve hits, then expand to sibling chunks under same outline |

**RAG entry points** (call `search_with_same_outline`):

- ~line 637 — general QA flow
- ~line 1012 — filtered QA (by `document_id` / package files)

Filter syntax used here matches [12-milvus-filter-expressions.md](./12-milvus-filter-expressions.md).

---

## 3. Knowledge management — Knowledge API

**File:** `src/rag/services/knowledge.py`

Imports shared client: `from api.services.utils import milvus_client`

| Function | Milvus API | Purpose |
|----------|------------|---------|
| `knowledge_recommend()` | `query` | Read chunk text for package files → LLM recommendations |
| `update_maybe_question()` | `query` | Same pattern for suggested questions |
| `delete_milvus()` | `drop_collection` | Wipe entire `fragments` collection |
| `get_milvus_file()` | `query` (limit 16384) | List `document_id` → `file_name` map |

**HTTP routes:** `src/rag/controllers/knowledge_mange.py`

| Method | Path | Handler |
|--------|------|---------|
| `DELETE` | `/knowledge_manage/delete` | `delete_milvus()` — clear Milvus collection |
| `GET` | `/knowledge_manage/get` | `get_milvus_file()` — list indexed files in Milvus |

**Note:** `DELETE /knowledge_manage/file/delete` removes SQLite metadata only; Milvus vectors may remain until re-index or full collection delete.

---

## 4. Data flow

```
Upload PDF / Word / CAJ
        │
        ▼
Document API parsers (pdf.py, word.py, caj.py)
        │
        ▼
@insert_fragments_into_milvus (utils.py)
        ├─► Embedding API  →  vectors
        └─► Milvus insert  →  collection "fragments"
                                    │
User question ──► QA API (qa.py) ───┤
        ├─► Embedding API
        ├─► Milvus search + query
        └─► LLM answer with retrieved chunks

Knowledge API (knowledge.py) ──► Milvus query / drop_collection
```

---

## 5. Legacy / backup files (not primary paths)

These files also contain Milvus code but appear to be older or backup copies:

| File | Notes |
|------|-------|
| `src/rag/services.py` | Standalone `search` / `query`; likely superseded by `qa.py` |
| `src/rag/services/qa_bak.py` | Backup of `qa.py` |

When tracing active behavior, prefer **`utils.py`**, **`qa.py`**, and **`knowledge.py`**.

---

## 6. Milvus vs SQLite

| Store | Role | Code location |
|-------|------|---------------|
| **Milvus** | Vector chunks for semantic search | Files listed above |
| **SQLite** | Packages, files, agents, chat history | `src/rag/mappers/`, `src/rag/utils/sqlite/` |

Milvus runs as a **separate Docker container** (`milvus-standalone`), not in `docker-compose.yaml`. See [06-database.md](./06-database.md) and [07-docker.md](./07-docker.md).

---

## Related docs

| Doc | Topic |
|-----|--------|
| [06-database.md](./06-database.md) | Milvus vs SQLite, ports, disk paths |
| [11-knowledge-chunking.md](./11-knowledge-chunking.md) | What each Milvus row represents |
| [12-milvus-filter-expressions.md](./12-milvus-filter-expressions.md) | Filter syntax in `search` / `query` |
| [13-attu.md](./13-attu.md) | Browse Milvus in the browser |
| [14-milvus-introduction.md](./14-milvus-introduction.md) | Milvus concepts and quick start |
| [15-milvus-cli-and-plain-usage.md](./15-milvus-cli-and-plain-usage.md) | Terminal / pymilvus one-liners |
