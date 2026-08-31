# Document Fragment / RAG Platform

Backend for document ingestion, fragmentation, vector search, and RAG Q&A.

## Services (Docker Compose)

| Service | Port | Role |
|---------|------|------|
| `document_fragment_api` | 12355 | Document parsing / fragmentation |
| `embedding_api` | 12356 | Embeddings + reranking |
| `qa_api` | 12357 | RAG / Q&A |

## Quick start

**New machine / disaster recovery:** follow [docs/21-software-recovery.md](docs/21-software-recovery.md) (git pull + Docker tars + models + config).

Daily startup on an already-configured machine: [docs/02-startup.md](docs/02-startup.md).

Short version:

1. `git clone https://gitee.com/zys123321/rag.git`
2. `docker load` both `.tar` images (not in Git — copy from backup)
3. Copy `models/` and create `.env` + `app_config_pro.yaml` from `.example` files
4. Start Milvus, then `docker compose up -d`

## Documentation

See [docs/README.md](docs/README.md) for the full guide (startup, configuration, Milvus, API reference, [retrieval eval](docs/22-retrieval-eval.md)).
