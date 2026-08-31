# 13 — Attu: Milvus GUI Setup & Usage

**Attu** is the official web UI for [Milvus](https://milvus.io/). In this project it runs as a **separate Docker container** — not part of `docker-compose.yaml`, not bundled with the Document Fragment APIs, and not related to SQLite.

Use Attu to browse the `fragments` collection, inspect chunk metadata, run vector search, and test filter expressions without writing Python.

---

## What Attu is (and is not)

| | Attu | Milvus | SQLite |
|---|------|--------|--------|
| **Type** | Web GUI (browser) | Vector database server | Embedded relational DB |
| **Container** | `attu` | `milvus-standalone` | (file inside `qa_api` mount) |
| **Image** | `zilliz/attu:v2.4` | `milvusdb/milvus:v2.4.4` | N/A |
| **Port** | `8000` (host) → `3000` (container) | `19530` | N/A |
| **Data** | None (UI only) | Vectors in `volumes/milvus/` | `src/rag/resources/sqlite.db` |
| **GUI tool** | Attu (this doc) | — | Navicat, DB Browser, etc. |

Attu connects **only to Milvus**. It does not show knowledge bases, agents, or chat history — those live in SQLite. See [06-database.md](./06-database.md).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Host (Windows + Docker Desktop)                                        │
│                                                                         │
│  Browser ──► http://localhost:8000 ──► ┌──────────────┐                 │
│                                         │    attu      │                 │
│                                         │ zilliz/attu  │                 │
│                                         │   :v2.4      │                 │
│                                         └──────┬───────┘                 │
│                                                │ MILVUS_URL               │
│                                                │ host.docker.internal:19530│
│                                                ▼                         │
│                                         ┌──────────────┐                 │
│  App containers (compose) ─────────────►│ milvus-      │                 │
│  Document API :12355                    │ standalone   │                 │
│  Embedding API :12356                   │ v2.4.4       │                 │
│  RAG / QA API :12357                    │ :19530       │                 │
│         MILVUS_URI                      └──────┬───────┘                 │
│         host.docker.internal:19530             │                         │
│                                                ▼                         │
│                                         volumes/milvus/                  │
│                                         (vector data on disk)            │
│                                                                         │
│  RAG API only ──► sqlite.db (metadata: Package, File, Agent, …)       │
│                   (not visible in Attu)                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

| Container | In compose? | Purpose |
|-----------|-------------|---------|
| `document_fragment-document_fragment_api-1` | Yes | Parse docs → insert vectors |
| `document_fragment-embedding_api-1` | Yes | Embeddings |
| `document_fragment-qa_api-1` | Yes | RAG Q&A, SQLite |
| `milvus-standalone` | No (manual `docker run`) | Vector storage |
| `attu` | No (manual `docker run`) | Milvus web UI |

**Total containers for a full dev stack:** 5 (3 app + Milvus + Attu).

---

## Installation (Windows)

Attu is **not** in `docker-compose.yaml`. Install once with `docker pull` and `docker run`.

### Pull image

```powershell
docker pull zilliz/attu:v2.4
```

Use **`v2.4`** to match Milvus **2.4.4** in this project. See [Troubleshooting](#troubleshooting) if pull fails.

### Run container

```powershell
docker run -d `
  --name attu `
  -p 8000:3000 `
  -e MILVUS_URL=host.docker.internal:19530 `
  zilliz/attu:v2.4
```

| Flag / env | Meaning |
|------------|---------|
| `-p 8000:3000` | Attu listens on port 3000 inside the container; open **http://localhost:8000** on the host |
| `-e MILVUS_URL=...` | Default Milvus address pre-filled in the UI |
| `host.docker.internal:19530` | From inside the Attu container, reach Milvus on the host (same pattern as app `.env`) |

**Prerequisite:** `milvus-standalone` must be running on port `19530` before Attu can connect. See [07-docker.md](./07-docker.md).

### Verify

```powershell
docker ps --filter name=attu
```

Expected:

```
NAMES   STATUS   PORTS                                         IMAGE
attu    Up ...   0.0.0.0:8000->3000/tcp   zilliz/attu:v2.4
```

Open http://localhost:8000 in a browser.

---

## Configuration

### Environment variables

| Variable | Value (this setup) | Description |
|----------|-------------------|-------------|
| `MILVUS_URL` | `host.docker.internal:19530` | Default Milvus gRPC address shown on connect screen |

Attu accepts `host:port` **without** `http://`. The app containers use `http://host.docker.internal:19530` in `.env` — both point at the same Milvus instance.

### Ports

| Where | Port |
|-------|------|
| Browser URL | `http://localhost:8000` |
| Container internal | `3000` |
| Milvus (target) | `19530` |

### Connection address in the UI

On first visit (or **Connect**), use:

```
host.docker.internal:19530
```

| From | Address |
|------|---------|
| Attu container → Milvus on host | `host.docker.internal:19530` |
| Host browser → Attu | `http://localhost:8000` |
| App containers → Milvus | `http://host.docker.internal:19530` (see [05-configuration.md](./05-configuration.md)) |

### This project's Milvus collection

| Setting | Value |
|---------|--------|
| Collection name | `fragments` |
| Config keys | `COLLECTION_NAME`, `MILVUS_COLLECTION` in `.env` / `app_config_pro.yaml` |

---

## Usage walkthrough

### 1. Connect to Milvus

1. Ensure `milvus-standalone` is up: `docker ps --filter name=milvus`
2. Open http://localhost:8000
3. Enter address: `host.docker.internal:19530`
4. Click **Connect**

You should see the database and collection list.

### 2. Browse collections

1. Open collection **`fragments`**
2. Review schema: scalar fields (`document_id`, `file_name`, `page_content`, …) and vector field `vector`

Field details and filter examples: [12-milvus-filter-expressions.md](./12-milvus-filter-expressions.md).

### 3. View data (Data tab)

1. Go to **Data**
2. Select output fields (e.g. `document_id`, `file_name`, `index`, `page_content`)
3. Optionally set a **filter expression**, e.g.:

   ```
   document_id == 'YOUR_FILE_MD5_HERE'
   ```

4. Run query — returns matching rows (metadata only, no vector ranking)

### 4. Vector search

1. Go to **Vector Search**
2. Choose the vector field (`vector`)
3. Provide a query vector (paste JSON array) or use Attu's text-to-vector helper if available
4. Set **Top K** (e.g. `10`)
5. Under **Advanced Filter**, narrow scope, e.g.:

   ```
   document_id in ['md5_a', 'md5_b']
   ```

This mirrors RAG `search()` with a `filter=` argument.

### 5. Advanced filter (scalar query)

Use the same boolean expression syntax as `pymilvus` — not SQL:

| Goal | Expression |
|------|------------|
| One file's chunks | `document_id == 'FILE_MD5'` |
| Filename pattern | `file_name LIKE '%report%'` |
| Content keyword | `page_content LIKE '%revenue%'` |
| Combined | `document_id == 'abc' and index < 5` |

Full syntax reference: [12-milvus-filter-expressions.md](./12-milvus-filter-expressions.md).

---

## Start / stop / logs

Attu is independent of `docker compose`:

```powershell
# Start (if container exists but stopped)
docker start attu

# Stop
docker stop attu

# Restart
docker restart attu

# Logs (follow)
docker logs -f attu

# Remove container (keeps image; re-run docker run to recreate)
docker stop attu
docker rm attu
```

Typical startup order:

```powershell
docker start milvus-standalone
docker compose up -d
docker start attu
```

---

## Troubleshooting

### Image pull fails

| Symptom | Things to try |
|---------|----------------|
| `Error response from daemon: pull access denied` | Use exact image `zilliz/attu:v2.4` (not `attu/attu`) |
| Timeout / network error | Check Docker Desktop network; retry; configure registry mirror if behind firewall |
| Wrong architecture | On Windows, Docker Desktop uses Linux images — `zilliz/attu` is multi-arch |

Offline alternative: on a machine with network access:

```powershell
docker pull zilliz/attu:v2.4
docker save zilliz/attu:v2.4 -o attu-v2.4.tar
# Copy tar to target machine, then:
docker load -i attu-v2.4.tar
```

### Cannot connect to Milvus

| Symptom | Fix |
|---------|-----|
| Connection refused | Start Milvus: `docker start milvus-standalone` |
| Wrong address | Use `host.docker.internal:19530` from Attu container on Windows |
| `localhost:19530` fails in Attu | `localhost` inside Attu container is the Attu container itself — use `host.docker.internal` |
| Milvus up but empty | Collection `fragments` is created when documents are indexed via Document API |

Check Milvus:

```powershell
docker logs milvus-standalone --tail 50
docker exec document_fragment-qa_api-1 python -c "from pymilvus import MilvusClient; print(MilvusClient('http://host.docker.internal:19530').list_collections())"
```

### Port 8000 already in use

```powershell
# Use another host port, e.g. 8001
docker run -d --name attu -p 8001:3000 -e MILVUS_URL=host.docker.internal:19530 zilliz/attu:v2.4
```

Then open http://localhost:8001.

### Version compatibility

| Component | Version in this project |
|-----------|-------------------------|
| Milvus | `milvusdb/milvus:v2.4.4` |
| Attu | `zilliz/attu:v2.4` |
| pymilvus | 2.4.x (in app image) |

Keep Attu on the **same major.minor** as Milvus (2.4). Using Attu 2.5+ against Milvus 2.4 may cause UI or API mismatches.

### Attu shows data but SQLite / Navicat differs

Expected. Attu shows **Milvus vectors only**. Knowledge base names, file upload status, and agents are in **SQLite** (`sqlite.db`). Use Navicat or DB Browser for SQLite metadata — see [06-database.md](./06-database.md).

Deleting a file via the Knowledge API removes SQLite rows; Milvus chunks may remain until collection delete or re-index.

---

## Relationship to other tools

```
┌──────────────────┬─────────────────────┬──────────────────────────────┐
│ Tool             │ Database            │ Use for                      │
├──────────────────┼─────────────────────┼──────────────────────────────┤
│ Attu             │ Milvus              │ Vectors, search, filters     │
│ Navicat / SQLite │ sqlite.db           │ Packages, files, agents, chat│
│ Swagger          │ HTTP APIs           │ Upload, Q&A, embeddings      │
│ pymilvus / CLI   │ Milvus              │ Scripted queries (doc 15)    │
└──────────────────┴─────────────────────┴──────────────────────────────┘
```

---

## Related docs

| Doc | Topic |
|-----|--------|
| [06-database.md](./06-database.md) | Milvus vs SQLite roles |
| [07-docker.md](./07-docker.md) | All containers, Milvus start command |
| [12-milvus-filter-expressions.md](./12-milvus-filter-expressions.md) | Filter syntax, Python examples, Attu quick steps |
| [05-configuration.md](./05-configuration.md) | `MILVUS_URI`, `COLLECTION_NAME` |
| [14-milvus-introduction.md](./14-milvus-introduction.md) | Milvus concepts, schema, pipeline |
| [15-milvus-cli-and-plain-usage.md](./15-milvus-cli-and-plain-usage.md) | Terminal alternatives: pymilvus, REST, milvus-cli |

## External links

- [Attu quick start (Milvus docs)](https://milvus.io/docs/quickstart_with_attu.md)
- [Attu GitHub](https://github.com/zilliztech/attu)
- [Milvus 2.4 release notes](https://milvus.io/docs/release_notes.md)
