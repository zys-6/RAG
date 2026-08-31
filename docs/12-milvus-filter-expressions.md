# 12 — Milvus Filter Expression Usage

How **filter expressions** work in this project’s Milvus collection `fragments` — syntax, operators, where they are used, and how to run them outside Python.

---

## What a filter expression is

Milvus filter expressions are **boolean predicates** (true/false conditions) used to narrow results. They look **SQL-like** but are **not full SQL** — there is no `SELECT … FROM …`.

| API method | Needs vector? | Filter role |
|------------|---------------|-------------|
| `query()` | No | Return rows matching metadata only |
| `search()` | Yes | Vector similarity **+** metadata filter |

Official reference: [Milvus boolean expression rules](https://milvus.io/docs/boolean.md)

---

## Collection and filterable fields

| Setting | Value |
|---------|--------|
| Collection | `fragments` (`MILVUS_COLLECTION` / `COLLECTION_NAME`) |
| Milvus URI | `http://host.docker.internal:19530` (from containers) |
| Client | `pymilvus.MilvusClient` |

Fields written at insert time (from Document API):

| Field | Type (approx.) | Filter example |
|-------|----------------|----------------|
| `id` | VARCHAR (PK) | `id == 'chunk-uuid'` |
| `document_id` | VARCHAR | `document_id == 'md5hash'` |
| `file_name` | VARCHAR | `file_name LIKE '%report%'` |
| `package_id` | VARCHAR | `package_id == 'fragments'` |
| `parent_id` | VARCHAR | `parent_id == 'section-id'` |
| `type` | VARCHAR | `type == 'paragraph'` |
| `index` | INT | `index >= 0 and index < 10` |
| `num_tokens` | INT | `num_tokens == 0` |
| `page_content` | VARCHAR | `page_content LIKE '%keyword%'` |
| `vector` | FLOAT_VECTOR | Used in `search()`, not in scalar filters |

Other stored fields (`pages`, `coordinates`, `outline`) exist but are less commonly filtered in this codebase.

---

## Operators used in this project

| Operator | Meaning | Example in repo |
|----------|---------|-----------------|
| `==` | Equal | `document_id == 'abc123'` |
| `in` | Value in list | `document_id in ['id1', 'id2']` |
| `LIKE` | Pattern match (`%` wildcard) | `page_content LIKE '% %'` |
| `and` / `or` | Combine conditions | `document_id == 'x' and type == 'title'` |
| `>=`, `<`, etc. | Numeric compare | `index >= 0` |

**String quoting:** use single quotes for string literals: `'md5hash'`, not `"md5hash"`.

**`in` list format:** Python generates lists like `['file_id_1', 'file_id_2']` — keep the same shape when writing filters manually.

---

## Where filters are used in code

### 1. Duplicate check on upload (Document API)

File: `src/api/services/utils.py`

```python
milvus_client.query(
    COLLECTION_NAME,
    filter="document_id == '{}'".format(md5)
)
```

If any row exists for that MD5, upload is rejected as duplicate.

---

### 2. Knowledge Q&A — scope to package files (RAG API)

File: `src/rag/services/qa.py`

```python
_filter = "document_id in {}".format(
    [_file.file_id for _file in File.get_by(package_id=package_id)]
)
relevant_documents = await search_with_same_outline(question, _filter)
```

Typical filter:

```
document_id in ['751899b1955ed632c4821e9b14f19038', 'ff90ff6d2fd3a04291f173656ed18de8']
```

Used with `search()` — embed question, return top similar chunks **within** those documents only (default limit 30 in the knowledge agent flow).

---

### 3. Knowledge recommend — load chunks by file list

File: `src/rag/services/knowledge.py`

```python
filter = f"document_id in {file_ids}"
result = milvus_client.query(COLLECTION_NAME, filter=filter, output_fields=output_fields)
```

Metadata-only query (no vector ranking).

---

### 4. Outline expansion — LIKE on content

File: `src/rag/services.py`

```python
like_docs = await search(text, filter="page_content LIKE '% %'", limit=3)
```

Combines vector search with a content pattern filter.

---

### 5. List all indexed files (no filter)

File: `src/rag/services/knowledge.py` → `GET /knowledge_manage/get`

```python
client.query(collection_name=COLLECTION_NAME, limit=16384)
```

No filter — returns up to 16384 entities; deduplicates by `document_id` → `file_name`.

---

## Python usage patterns

### Query (metadata only)

```python
from pymilvus import MilvusClient

client = MilvusClient("http://host.docker.internal:19530")

# One document
rows = client.query(
    "fragments",
    filter="document_id == 'YOUR_MD5_HERE'",
    output_fields=["id", "file_name", "page_content", "index"],
    limit=100,
)

# Multiple documents
rows = client.query(
    "fragments",
    filter="document_id in ['md5_a', 'md5_b']",
    output_fields=["document_id", "file_name"],
)
```

### Search (vector + filter)

```python
import requests
from pymilvus import MilvusClient

client = MilvusClient("http://host.docker.internal:19530")

# Get query embedding from Embedding API (port 12356)
resp = requests.post(
    "http://localhost:12356/v1/embeddings",
    json={"input": ["your question here"]},
)
query_vector = resp.json()["data"][0]["embedding"]

results = client.search(
    "fragments",
    data=[query_vector],
    filter="document_id in ['YOUR_MD5']",
    limit=10,
    output_fields=["page_content", "file_name", "document_id", "pages"],
)
```

### From a running container

```powershell
docker exec document_fragment-qa_api-1 python -c "
from pymilvus import MilvusClient
c = MilvusClient('http://host.docker.internal:19530')
print(c.list_collections())
print(c.query('fragments', filter=\"document_id != ''\", limit=3, output_fields=['document_id','file_name']))
"
```

---

## Attu GUI (no Python required)

Attu is installed as container `attu`:

| Item | Value |
|------|--------|
| Web UI | http://localhost:8000 |
| Milvus address | `host.docker.internal:19530` |
| Collection | `fragments` |

Steps:

1. Open http://localhost:8000
2. Connect to `host.docker.internal:19530`
3. Open collection **fragments**
4. **Data** tab — browse rows; optional scalar filter
5. **Vector Search** tab — enter/query vector → **Advanced Filter** → e.g. `document_id == 'md5hash'`

Attu builds the same boolean expression syntax as Python `filter=`.

---

## Common recipes

| Goal | Filter expression |
|------|-------------------|
| All chunks of one file | `document_id == 'FILE_MD5'` |
| Chunks in a knowledge package | `document_id in ['md5_1', 'md5_2', ...]` |
| Filename contains text | `file_name LIKE '%annual%'` |
| Content contains keyword | `page_content LIKE '%revenue%'` |
| First N chunks by index | `document_id == 'MD5' and index < 5` |
| Non-empty documents | `document_id != ''` |

Combine with `and` / `or`:

```
document_id == 'abc123' and file_name LIKE '%.pdf%'
document_id in ['a', 'b'] or package_id == 'fragments'
```

---

## `query()` vs `search()`

```
                    ┌─────────────────────────────────────┐
  User question ──► │  Embed text → query vector          │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │  search(vector, filter, limit)      │
                    │  → ranked by similarity             │
                    └─────────────────────────────────────┘

                    ┌─────────────────────────────────────┐
  Admin / ingest ──►│  query(filter, output_fields)       │
                    │  → all matching rows, no ranking    │
                    └─────────────────────────────────────┘
```

| Use case | Method |
|----------|--------|
| RAG retrieval | `search()` |
| Duplicate check, list chunks, recommend sampling | `query()` |
| List unique files (`/knowledge_manage/get`) | `query()` with `limit` only |

---

## Pitfalls

1. **Not SQL** — `SELECT * FROM fragments WHERE …` will not work; use `MilvusClient.query` / `search` or Attu.
2. **Quote strings** — `document_id == abc` fails; use `document_id == 'abc'`.
3. **`in` syntax** — must be a list: `document_id in ['a','b']`, not `document_id in ('a','b')`.
4. **Empty filter on search** — allowed; searches entire collection (can be slow/large).
5. **Delete file vs vectors** — `DELETE /knowledge_manage/file/delete` removes SQLite metadata; Milvus vectors may remain until re-index or `DELETE /knowledge_manage/delete` (drops whole collection).
6. **Config** — filters hit collection `fragments`; URI must match running Milvus (`app_config_pro.yaml` and `.env`).

---

## Related docs

| Doc | Topic |
|-----|--------|
| [06-database.md](./06-database.md) | Milvus deployment and storage |
| [11-knowledge-chunking.md](./11-knowledge-chunking.md) | What each Milvus row represents |
| [05-configuration.md](./05-configuration.md) | `MILVUS_URI`, connection checks |
| [13-attu.md](./13-attu.md) | Attu GUI for filters without Python |
| [14-milvus-introduction.md](./14-milvus-introduction.md) | Milvus concepts and quick start |
| [15-milvus-cli-and-plain-usage.md](./15-milvus-cli-and-plain-usage.md) | pymilvus one-liners, REST curl, milvus-cli |

## External links

- [Milvus boolean expressions](https://milvus.io/docs/boolean.md)
- [Attu quick start](https://milvus.io/docs/quickstart_with_attu.md)
- [pymilvus MilvusClient](https://milvus.io/api-reference/pymilvus/v2.4.x/MilvusClient/Client/MilvusClient.md)
