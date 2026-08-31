# 15 — Milvus CLI & Plain Usage (Beyond Attu)

Practical ways to inspect and query Milvus **without the Attu browser UI** — for users who expect a **mysql/psql-style SQL CLI** or **Navicat-style** terminal access.

**Milvus version in this project:** `milvusdb/milvus:v2.4.4`  
**Collection:** `fragments`  
**Connection:** `http://localhost:19530` (host) · `http://host.docker.internal:19530` (app containers)

---

## The short answer: there is no SQL CLI for Milvus

Milvus is a **vector database**, not a relational one. You **cannot** run:

```sql
SELECT file_name, page_content FROM fragments WHERE document_id = 'abc123';
```

That syntax does not exist in Milvus.

| What you might expect | What Milvus actually offers |
|-----------------------|----------------------------|
| `mysql`, `psql`, Navicat SQL window | **Boolean filter expressions** — e.g. `document_id == 'abc123'` |
| `SELECT … FROM … WHERE …` | **`query(filter=…)`** — metadata-only row lookup |
| `ORDER BY similarity` | **`search(data=[vector], filter=…)`** — needs an embedding vector |
| Tables | **Collections** (schema fixed at create time) |

Filter syntax is documented in [12-milvus-filter-expressions.md](./12-milvus-filter-expressions.md).  
Milvus concepts and pipeline: [14-milvus-introduction.md](./14-milvus-introduction.md).  
GUI alternative: [13-attu.md](./13-attu.md).

**For catalog metadata** (packages, files, agents, chat) use **SQLite** — that *does* support real SQL. See [06-database.md](./06-database.md).

---

## Closest alternatives (ranked for this project)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Want SQL-like terminal access to Milvus?                               │
│                                                                         │
│  1. docker exec + pymilvus one-liners   ← best: already in app image   │
│  2. docker exec -it … python            ← interactive REPL              │
│  3. Attu browser UI                     ← doc 13                       │
│  4. curl REST API v2                    ← automation, no Python        │
│  5. milvus-cli (pip install)            ← optional; extra install       │
│                                                                         │
│  For real SQL on metadata → sqlite.db via Navicat / python -c           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

```powershell
# Milvus must be running
docker start milvus-standalone
docker ps --filter name=milvus

# App container (pymilvus pre-installed)
docker ps --filter name=qa_api
# Expected name: document_fragment-qa_api-1
```

Health check (metrics port, not the client port):

```powershell
curl http://localhost:9091/healthz
```

---

## Method 1 — pymilvus one-liners (recommended)

The `document_fragment:mupdf-3` image already includes **pymilvus 2.4.x**. Use `document_fragment-qa_api-1` as a ready-made Milvus client shell.

### List collections

```powershell
docker exec document_fragment-qa_api-1 python -c "
from pymilvus import MilvusClient
c = MilvusClient('http://host.docker.internal:19530')
print(c.list_collections())
"
```

Expected after indexing: `['fragments']`. Empty `[]` means Milvus is up but no documents indexed yet.
If `[]` appears unexpectedly after a reboot or container recreate, first verify that Milvus is still mounted to the original persistent path rather than a new empty volume.

### Count rows (approximate vs exact)

```powershell
# Fast estimate (may lag right after insert)
docker exec document_fragment-qa_api-1 python -c "
from pymilvus import MilvusClient
c = MilvusClient('http://host.docker.internal:19530')
print(c.get_collection_stats('fragments'))
"

# Exact count of loaded entities (slower, scans data)
docker exec document_fragment-qa_api-1 python -c "
from pymilvus import MilvusClient
c = MilvusClient('http://host.docker.internal:19530')
print(c.query('fragments', filter=\"document_id != ''\", output_fields=['count(*)']))
"
```

### Query rows by document_id (metadata only — no vector ranking)

Replace `YOUR_FILE_MD5` with a real `document_id` from SQLite `File.file_id` or from Attu.

```powershell
docker exec document_fragment-qa_api-1 python -c "
from pymilvus import MilvusClient
c = MilvusClient('http://host.docker.internal:19530')
rows = c.query(
    'fragments',
    filter=\"document_id == 'YOUR_FILE_MD5'\",
    output_fields=['id', 'file_name', 'index', 'type'],
    limit=10,
)
for r in rows:
    print(r)
"
```

### Peek at chunk text

```powershell
docker exec document_fragment-qa_api-1 python -c "
from pymilvus import MilvusClient
c = MilvusClient('http://host.docker.internal:19530')
rows = c.query(
    'fragments',
    filter=\"document_id == 'YOUR_FILE_MD5'\",
    output_fields=['index', 'page_content'],
    limit=3,
)
for r in rows:
    print('--- chunk', r['index'], '---')
    print(r['page_content'][:200])
"
```

### List unique indexed files (like `/knowledge_manage/get`)

```powershell
docker exec document_fragment-qa_api-1 python -c "
from pymilvus import MilvusClient
c = MilvusClient('http://host.docker.internal:19530')
rows = c.query('fragments', filter=\"document_id != ''\", output_fields=['document_id','file_name'], limit=16384)
seen = {}
for r in rows:
    seen[r['document_id']] = r.get('file_name','')
for md5, name in seen.items():
    print(md5, name)
print('Unique files:', len(seen))
"
```

### Vector search (needs embedding)

Search requires a query **vector**. Get one from the Embedding API, then search Milvus — same pattern as RAG code in `src/rag/services/qa.py`.

```powershell
docker exec document_fragment-qa_api-1 python -c "
import requests
from pymilvus import MilvusClient

question = 'your question here'
emb = requests.post('http://embedding_api:5006/v1/embeddings', json={'input': [question]}).json()
vec = emb['data'][0]['embedding']

c = MilvusClient('http://host.docker.internal:19530')
hits = c.search(
    'fragments',
    data=[vec],
    filter=\"document_id == 'YOUR_FILE_MD5'\",
    limit=5,
    output_fields=['file_name', 'page_content', 'document_id'],
)
for h in hits[0]:
    print('distance:', h['distance'])
    print(h['entity'].get('page_content','')[:150])
    print('---')
"
```

From the **host** (not inside Docker), use `http://localhost:12356` for the Embedding API instead of `http://embedding_api:5006`.

### Run from host Python (optional)

If pymilvus is installed locally:

```powershell
python -c "from pymilvus import MilvusClient; print(MilvusClient('http://localhost:19530').list_collections())"
```

---

## Method 2 — Interactive Python as “CLI”

For exploratory sessions (closest feel to an interactive SQL shell):

```powershell
docker exec -it document_fragment-qa_api-1 python
```

```python
from pymilvus import MilvusClient
c = MilvusClient("http://host.docker.internal:19530")

c.list_collections()
c.get_collection_stats("fragments")

c.query(
    "fragments",
    filter="document_id != ''",
    output_fields=["document_id", "file_name"],
    limit=5,
)

# exit with Ctrl+D or exit()
```

Tip: paste filter expressions from [12-milvus-filter-expressions.md](./12-milvus-filter-expressions.md) — same syntax as Attu and application code.

---

## Method 3 — Milvus REST API v2 (curl)

Milvus standalone exposes **HTTP REST** on port **19530** (same port as gRPC). This project's app code uses pymilvus (gRPC), but REST works for quick checks from PowerShell without Python.

**Auth:** default standalone install in this project has **no authentication**. If you enabled auth, add `-H "Authorization: Bearer root:Milvus"`.

Base URL: `http://localhost:19530`

### List collections

```powershell
curl -X POST "http://localhost:19530/v2/vectordb/collections/list" `
  -H "Content-Type: application/json" `
  -d "{}"
```

### Collection row count (estimate)

```powershell
curl -X POST "http://localhost:19530/v2/vectordb/collections/get_stats" `
  -H "Content-Type: application/json" `
  -d "{\"collectionName\": \"fragments\"}"
```

### Query by filter (metadata)

```powershell
curl -X POST "http://localhost:19530/v2/vectordb/entities/query" `
  -H "Content-Type: application/json" `
  -d "{\"collectionName\": \"fragments\", \"filter\": \"document_id != ''\", \"outputFields\": [\"document_id\", \"file_name\", \"index\"], \"limit\": 5}"
```

Filter one file:

```powershell
curl -X POST "http://localhost:19530/v2/vectordb/entities/query" `
  -H "Content-Type: application/json" `
  -d "{\"collectionName\": \"fragments\", \"filter\": \"document_id == 'YOUR_FILE_MD5'\", \"outputFields\": [\"file_name\", \"page_content\"], \"limit\": 3}"
```

### Vector search (REST)

You must supply the full embedding array in JSON. For ad-hoc search, pymilvus + Embedding API (Method 1) is usually easier.

```powershell
# Minimal shape — replace data with a real 768-dim vector from Embedding API
curl -X POST "http://localhost:19530/v2/vectordb/entities/search" `
  -H "Content-Type: application/json" `
  -d "{\"collectionName\": \"fragments\", \"annsField\": \"vector\", \"data\": [[0.1, 0.2]], \"filter\": \"document_id == 'YOUR_FILE_MD5'\", \"limit\": 3, \"outputFields\": [\"page_content\", \"file_name\"]}"
```

Official reference: [Milvus RESTful API v2.4.x](https://milvus.io/api-reference/restful/v2.4.x/About.md)

---

## Method 4 — milvus-cli (optional separate install)

**milvus-cli** is Milvus's official interactive terminal tool. It is **not SQL** — it uses subcommands and prompts (`connect`, `list collections`, `query`, `search`).

| Item | Value |
|------|--------|
| Recommended version for Milvus 2.4.x | **milvus-cli 1.0.1** |
| Install | `pip install milvus-cli==1.0.1` |
| Launch | `milvus_cli` |

**Not included** in the project's Docker image. Install on the host (or a throwaway venv) if you want a dedicated Milvus shell.

```powershell
pip install milvus-cli==1.0.1
milvus_cli
```

Inside the CLI:

```
milvus_cli > connect -uri http://127.0.0.1:19530
milvus_cli > list collections
milvus_cli > show collection -c fragments
milvus_cli > query
# prompts: collection name → fragments
#          filter expression → document_id == 'YOUR_FILE_MD5'
#          output fields → document_id, file_name, page_content
milvus_cli > search
# prompts for vector data (CSV or pasted array) — use Embedding API output
```

**Note:** `zilliz-cli` on PyPI targets **Zilliz Cloud** management, not local Milvus SQL. For self-hosted Milvus 2.4, use **milvus-cli** or pymilvus.

Docs: [Milvus CLI overview (2.4.x)](https://milvus.io/docs/v2.4.x/cli_overview.md)

---

## Comparison table

| Tool | Milvus? | SQL? | Interactive? | In this project? | Best for |
|------|---------|------|--------------|------------------|----------|
| **Attu** | Yes | No (boolean filters) | Browser GUI | Yes — container `attu` | Browse rows, test filters, paste vectors |
| **pymilvus one-liners** | Yes | No | One-shot commands | Yes — `qa_api` image | Scripts, CI checks, copy-paste debugging |
| **Python REPL** | Yes | No | Yes (Python) | Yes — `docker exec -it … python` | Exploratory queries, prototyping |
| **REST API (curl)** | Yes | No (JSON body) | One-shot HTTP | Milvus port 19530 | Health checks, non-Python automation |
| **milvus-cli** | Yes | No (CLI prompts) | Yes (terminal) | No — pip install separately | Dedicated Milvus admin shell |
| **Navicat / sqlite3** | **No** — SQLite only | **Yes** | GUI / CLI | Yes — `sqlite.db` | Packages, files, agents, chat history |

### Mental mapping: SQL habit → Milvus equivalent

| SQL habit | Milvus equivalent |
|-----------|-------------------|
| `SHOW TABLES` | `client.list_collections()` or `list collections` (milvus-cli) |
| `SELECT COUNT(*) FROM t` | `query(..., output_fields=['count(*)'])` |
| `SELECT col FROM t WHERE id = 'x'` | `query('fragments', filter="document_id == 'x'", output_fields=[...])` |
| `SELECT … ORDER BY similarity(?)` | `search('fragments', data=[vector], filter=..., limit=N)` |
| `DESCRIBE t` | `client.describe_collection('fragments')` or Attu schema tab |

---

## When to use each

| Your goal | Use this |
|-----------|----------|
| Quick “is Milvus up? any collections?” | `curl` list collections **or** pymilvus one-liner |
| Browse chunk text and metadata visually | **Attu** — [13-attu.md](./13-attu.md) |
| Filter by `document_id`, count chunks, debug ingest | **pymilvus** one-liners from `qa_api` container |
| Prototype filters before putting them in code | **Python REPL** or Attu |
| Automate from shell scripts without Python | **REST API** curl |
| Prefer a persistent Milvus-only terminal session | **milvus-cli** (after pip install) |
| List knowledge bases, file registry, agents | **SQLite** — Navicat, DBeaver, or `sqlite3` |
| RAG semantic retrieval | Application APIs or `search()` with Embedding API |

---

## SQLite side-by-side (real SQL)

Milvus stores **vectors**; SQLite stores **catalog**. For Navicat/SQL-CLI users, both are often needed:

```powershell
# Real SQL on metadata (not Milvus)
docker exec document_fragment-qa_api-1 python -c "
import sqlite3
c = sqlite3.connect('/src/rag/resources/sqlite.db')
for row in c.execute('SELECT file_id, file_name, package_id FROM File WHERE is_delete=0 LIMIT 10'):
    print(row)
"
```

Use `file_id` from SQLite as `document_id` in Milvus filters.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Connection refused` | `docker start milvus-standalone` |
| Empty `list_collections()` | Normal before first document upload; if unexpected after restart, verify Milvus still mounts the original persistent data path instead of a fresh empty volume |
| `document_id == 'x'` returns nothing | Confirm MD5 exists in SQLite `File.file_id`; check Attu |
| Search fails / wrong dimension | Embedding model dimension must match collection; re-create collection if model changed |
| `host.docker.internal` fails from host Python | Use `http://localhost:19530` on the host |
| REST returns auth error | Add header `Authorization: Bearer root:Milvus` if auth enabled |

More Attu-specific issues: [13-attu.md](./13-attu.md).

---

## Related docs

| Doc | Topic |
|-----|--------|
| [12-milvus-filter-expressions.md](./12-milvus-filter-expressions.md) | Filter syntax, `query` vs `search`, Python patterns |
| [13-attu.md](./13-attu.md) | Attu GUI — install, connect, browse, vector search |
| [14-milvus-introduction.md](./14-milvus-introduction.md) | Milvus concepts, schema, pipeline, quick start |
| [06-database.md](./06-database.md) | Milvus vs SQLite roles, ports, backup |

## External links

- [pymilvus MilvusClient (2.4.x)](https://milvus.io/api-reference/pymilvus/v2.4.x/MilvusClient/Client/MilvusClient.md)
- [Milvus boolean expressions](https://milvus.io/docs/boolean.md)
- [Milvus RESTful API v2.4.x](https://milvus.io/api-reference/restful/v2.4.x/About.md)
- [Milvus CLI (2.4.x)](https://milvus.io/docs/v2.4.x/cli_overview.md)
