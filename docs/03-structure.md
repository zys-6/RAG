# 03 — Project Structure

## Top-level layout

```
setup/
├── document_fragment/              # Main application
│   ├── docker-compose.yaml
│   ├── .env
│   ├── models/                     # ML weights (mounted to /models)
│   ├── docs/                       # This documentation
│   └── src/                        # All Python source (mounted to /src)
├── volumes/milvus/                 # Milvus persistent data
├── embedEtcd.yaml                  # Milvus etcd config
├── user.yaml                       # Milvus override config
├── standalone_embed.sh             # Milvus startup (Linux)
├── document_fragment-mupdf-3.tar   # App Docker image export
├── milvus.tar                      # Milvus image export
└── voice/                          # Incomplete voice module (not deployed)
```

## Inside `src/` — the three APIs

```
src/
├── api/                    # ★ Document API (port 12355)
├── embedding/              # ★ Embedding API (port 12356)
├── rag/                    # ★ RAG / QA API (port 12357)
├── document_fragment/      # Shared document parsing library
├── layout_analysis/        # PDF layout, tables (modified pdfplumber)
├── tasks/                  # Celery async tasks (optional, needs Redis)
├── doc2docx/               # Word .doc → .docx conversion
└── utils/                  # Redis helpers, etc.
```

## Document API — `src/api/`

```
api/
├── main.py                 # FastAPI entry (root_path=/api/v1)
├── controllers/
│   ├── pdf.py              # /pdf/sync
│   ├── word.py             # /word/sync, /word/doc2docx
│   ├── ocr.py              # /ocr/sync
│   ├── caj.py              # /caj/sync/caj
│   ├── zip.py              # /zip/sync, FTP upload
│   └── manage.py           # /manage/list, update, delete
├── services/
│   ├── pdf.py, word.py, ocr.py, caj.py, zip.py
│   ├── utils.py            # Milvus insert, HTTP helpers
│   └── cajparser.py
└── static/
    └── fragment/           # Parsed fragment JSON output
```

## Embedding API — `src/embedding/`

```
embedding/
├── api.py                  # POST /embeddings, POST /rerank
└── static/                 # Swagger UI assets
```

## RAG / QA API — `src/rag/`

```
rag/
├── api.py                  # FastAPI entry, mounts routers
├── controllers/            # HTTP routes
│   ├── qa.py               # Chat, agents, reports
│   ├── knowledge_mange.py  # Knowledge base CRUD (note typo: mange)
│   ├── agent_manage.py
│   ├── api_manage.py       # Dynamic API tool config
│   └── user_config_manage.py
├── services/               # Business logic
│   ├── qa.py               # Large: RAG pipeline, LLM streaming
│   ├── knowledge.py
│   ├── agent.py
│   └── api_manage.py
├── mappers/                # SQLite ORM models
│   ├── knowledge.py        # Package, File
│   ├── agent.py
│   ├── task.py             # Dialogue
│   ├── user_config.py
│   └── sqlite_mappers.py   # Generic SQLite CRUD
├── configs/
│   ├── app_config_pro.yaml # Production runtime config
│   ├── app_config_dev.yaml
│   ├── prompt_config.yaml  # LLM prompt templates
│   └── api_config.json     # Tool/API definitions
├── utils/
│   ├── request_llm.py      # LLM client calls
│   └── sqlite/
│       └── sqlite_client.py
└── resources/
    └── sqlite.db           # SQLite database file
```

## Shared libraries

| Module | Purpose |
|--------|---------|
| `document_fragment/document/` | PDF/Word document models, fragment objects |
| `layout_analysis/` | Table detection, modified pdfplumber |
| `tasks/main.py` | Celery PDF/Word processing (optional) |

## Layer pattern (RAG service)

```
HTTP Request
    → controllers/     (routes, validation)
    → services/        (business logic)
    → mappers/         (SQLite)
    → utils/           (Milvus, LLM, helpers)
```

Document API is flatter: `controllers/` → `services/` → libraries + Milvus.

## Models directory

```
models/
├── text2vec-base-multilingual/   # Embedding model
├── reranker/                     # Reranker model
├── table_detection/              # Table detect
├── table_recognition/            # Table OCR
└── .paddleocr/                   # PaddleOCR weights
```

Mounted into containers at `/models`.

## Naming map (avoid confusion)

| You see… | It is… |
|----------|--------|
| Folder `document_fragment/` | Whole project |
| Folder `src/document_fragment/` | Parsing library only |
| Image `document_fragment:mupdf-3` | Docker runtime |
| Service `document_fragment_api` | Document API container |
| Service `qa_api` | RAG API container |

## Known structural issues

- Typos: `knowledge_mange.py`, `moudle.json`
- Backup files in tree: `qa_bak.py`, `*_bk.yaml`
- Cross-imports: `api/services/utils.py` imports `rag.configs`
- Milvus startup separate from compose
- No `requirements.txt` (deps baked into image)

These reflect an evolved internal codebase, not greenfield design.
