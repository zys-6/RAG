# 06 — Database & Storage

This project uses **two databases** plus **file storage**.

## Overview

| Store | Type | Purpose | Location |
|-------|------|---------|----------|
| **Milvus** | Vector DB | Document chunk embeddings, semantic search | `setup/volumes/milvus/` |
| **SQLite** | Relational (embedded) | Knowledge bases, agents, chat history | `src/rag/resources/sqlite.db` |
| **Static files** | JSON / uploads | Parsed fragments, temp files | `src/api/static/` |

```
SQLite  →  "what exists?" (catalog, metadata)
Milvus  →  "what matches semantically?" (vectors)
Files   →  raw fragment JSON, uploads
```

---

## Milvus (vector database)

### Role

- Stores **embedding vectors** for document fragments
- Powers similarity search in RAG pipeline
- Collection name: **`fragments`** (configurable via `COLLECTION_NAME`)

### Deployment

- **Container:** `milvus-standalone`
- **Image:** `milvusdb/milvus:v2.4.4`
- **Port:** `19530` (client), `9091` (metrics/health)
- **Not** defined in `docker-compose.yaml` — started separately

### Data on disk

```
setup/volumes/milvus/
├── data/
├── etcd/
├── rdb_data/
└── rdb_data_meta_kv/
```

Mounted as `/var/lib/milvus` in the Milvus container.

### Used by

| Service | Operation |
|---------|-----------|
| Document API | Insert vectors after parsing |
| RAG API | Search similar chunks for Q&A |
| Embedding API | Env may reference Milvus URI |

### Connection string

- From host: `http://localhost:19530`
- From app containers (Windows): `http://host.docker.internal:19530`
- Config keys: `MILVUS_URI`, `MILVUS_COLLECTION` in yaml

---

## SQLite (metadata database)

### Role

Embedded **file-based** database — no separate server to install or run.

- Opened automatically by Python when RAG API starts
- Uses Python stdlib `sqlite3` (included in Docker image)

### File location

```
document_fragment/src/rag/resources/sqlite.db
```

Inside container: `/src/rag/resources/sqlite.db`

Because `./src` is volume-mounted, the file lives on your **host disk** and persists across container restarts.

### Tables

#### `Package` — knowledge bases

| Column | Description |
|--------|-------------|
| id | Primary key (`package-...`) |
| name | Knowledge base name |
| type | `public` / `group` / `person` |
| user_id, group_id | Ownership |
| description | Text description |
| knowledge_recommend | Recommended items (JSON text) |
| create_time, is_delete | Audit / soft delete |

#### `File` — files in a knowledge base

| Column | Description |
|--------|-------------|
| id, file_id | Identifiers |
| file_name, file_path, file_size, file_type | File info |
| package_id | Parent knowledge base |
| user_id | Owner |
| read, write, share | Permission flags |
| status | e.g. upload, success, failed |
| create_time, is_delete | Audit |

#### `Agent` — custom AI agents

| Column | Description |
|--------|-------------|
| id | Primary key (`agent-...`) |
| agent_name, agent_prompt, agent_example | Agent definition |
| description, agent_type, icon | Metadata |
| agent_temperature | LLM temperature |
| create_time, is_delete | Audit |

#### `Dialogue` — chat / task history

| Column | Description |
|--------|-------------|
| id | Primary key (`dialogue-...`) |
| query, llm_text | Question and answer |
| llm_sql, llm_data | Structured agent outputs |
| user_id, type, status | Session metadata |
| think_pattern, think_time, api_name, maybe_query | Extended fields |
| create_time, modify_time | Timestamps |

#### `UserConfig` — user JSON templates

| Column | Description |
|--------|-------------|
| id, user_id | Identifiers |
| config_name, config_json | Saved template |
| create_time, modify_time | Timestamps |

### Logical foreign-key relationships

The current SQLite schema is **application-enforced**, not database-enforced:

- There are **no explicit SQLite `FOREIGN KEY` constraints** in the mapper-generated tables.
- Relationships are maintained by Python code and naming conventions.

Useful mental model:

| Child table.column | Parent table.column | Meaning |
|--------------------|---------------------|---------|
| `File.package_id` | `Package.id` | A file belongs to one knowledge base |
| `File.user_id` | external client/user identity | Owner of the uploaded file |
| `Dialogue.user_id` | external client/user identity | Who started the chat/task |
| `UserConfig.user_id` | external client/user identity | Who owns the saved template |

Notes:

- `File.id` is the SQLite row identifier for file metadata.
- `File.file_id` is a separate business identifier, typically the file MD5, and is used as Milvus `document_id`.
- `Package.id` scopes retrieval indirectly: `Package.id` -> `File.package_id` -> `File.file_id` -> Milvus `document_id`.

### Code mapping

| Table | Python mapper |
|-------|---------------|
| Package, File | `rag/mappers/knowledge.py` |
| Agent | `rag/mappers/agent.py` |
| Dialogue | `rag/mappers/task.py` |
| UserConfig | `rag/mappers/user_config.py` |

Generic CRUD: `rag/mappers/sqlite_mappers.py`

### Used by

**RAG / QA API only** — Document API and Embedding API do not use SQLite.

---

## Static file storage

### Fragment JSON

```
src/api/static/fragment/*.json
```

Output of document parsing — referenced in RAG responses as citations.

### Temp uploads

```
src/static/tmp/
```

Temporary processing files from historical uploads.

---

## Data relationships

```
Package (SQLite)
    └── File (SQLite, via File.package_id -> Package.id)
                         └── File.file_id -> Milvus document_id
                         ──→ triggers Document API processing
                              └── fragments → Milvus (vectors)
                              └── fragment JSON (static files)

Agent (SQLite) ──→ used in /agent/stream chat

Dialogue (SQLite, carries user_id from client) ──→ stores each Q&A session

UserConfig (SQLite, carries user_id from client) ──→ stores per-user JSON templates
```

---

## Backup & migration

| Data | What to copy |
|------|--------------|
| Milvus vectors | Entire `volumes/milvus/` folder |
| SQLite metadata | `src/rag/resources/sqlite.db` |
| Models | `document_fragment/models/` |
| Fragment files | `src/api/static/fragment/` |

Stop containers before copying Milvus data for consistency.

---

## Query SQLite locally (optional)

```powershell
docker exec -it document_fragment-qa_api-1 python -c "
import sqlite3
c = sqlite3.connect('/src/rag/resources/sqlite.db')
for row in c.execute('SELECT id, agent_name FROM Agent LIMIT 5'):
    print(row)
"
```

Or copy `sqlite.db` out and open with [DB Browser for SQLite](https://sqlitebrowser.org/).
