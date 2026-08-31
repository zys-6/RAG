# Document Fragment Platform 鈥?Documentation Index

Enterprise document processing and RAG (Retrieval-Augmented Generation) backend. One codebase, three FastAPI services, one Docker image.

## Documents

| # | Document | Description |
|---|----------|-------------|
| 1 | [01-overview.md](./01-overview.md) | What the project is, goals, architecture globe view |
| 2 | [02-startup.md](./02-startup.md) | Prerequisites, install images, start/stop services |
| 3 | [03-structure.md](./03-structure.md) | Folder layout, modules, naming map |
| 4 | [04-functions.md](./04-functions.md) | APIs, features, data flows |
| 5 | [05-configuration.md](./05-configuration.md) | `.env`, YAML configs, external dependencies |
| 6 | [06-database.md](./06-database.md) | SQLite tables, Milvus, storage locations |
| 7 | [07-docker.md](./07-docker.md) | Images vs containers, tar load, compose |
| 8 | [08-known-limitations.md](./08-known-limitations.md) | **Features blocked/unavailable and why** |
| 9 | [09-storage-breakdown.md](./09-storage-breakdown.md) | **Why the repo is ~38 GB despite ~47k lines of code** |
| 10 | [10-cleanup-recommendations.md](./10-cleanup-recommendations.md) | **What can be safely deleted (tiered checklist + scripts)** |
| 11 | [11-knowledge-chunking.md](./11-knowledge-chunking.md) | **Knowledge feature: chunking, splitting, sliding windows** |
| 12 | [12-milvus-filter-expressions.md](./12-milvus-filter-expressions.md) | **Milvus filter expressions: syntax, usage, Attu, examples** |
| 13 | [13-attu.md](./13-attu.md) | **Attu: Milvus GUI 鈥?install, connect, browse, search, troubleshoot** |
| 14 | [14-milvus-introduction.md](./14-milvus-introduction.md) | **Milvus intro: structure, operations, tools, pipeline, quick start** |
| 15 | [15-milvus-cli-and-plain-usage.md](./15-milvus-cli-and-plain-usage.md) | **Milvus CLI & plain usage: pymilvus, REST, milvus-cli 鈥?not SQL** |
| 16 | [16-milvus-code-locations.md](./16-milvus-code-locations.md) | **Milvus in code: source files, operations, and data flow** |
| 17 | [17-text2vec-embedding-model.md](./17-text2vec-embedding-model.md) | **Text2Vec embedding model: location, runtime, CPU/GPU, pipeline** |
| 18 | [18-configuration-files-summary.md](./18-configuration-files-summary.md) | **All configuration files: what they do, who reads them, when to edit** |
| 19 | [19-knowledge-improvement-recommendations.md](./19-knowledge-improvement-recommendations.md) | **Project overview & Knowledge improvement recommendations (model, code, design, priorities)** |
| 20 | [20-redis-usage.md](./20-redis-usage.md) | **Redis in code: three locations, async Celery pipeline, what runs vs. what doesn't** |
| 21 | [21-software-recovery.md](./21-software-recovery.md) | **Recover software on a new machine: git clone + Docker tars + models + config** |
| 22 | [22-retrieval-eval.md](./22-retrieval-eval.md) | **Retrieval eval harness, qa.py pipeline fix, golden set, test commands** |
| 23 | [23-dev-1gpu-prod-4gpu-migration.md](./23-dev-1gpu-prod-4gpu-migration.md) | **Windows 1-GPU development vs CentOS 4-GPU deployment: what to validate where** |
| 24 | [24-retrieval-pipeline-internals.md](./24-retrieval-pipeline-internals.md) | **Retrieval pipeline internals: index vs query, vector, parent_id, rerank** |
| 25 | [25-deploy-code-updates.md](./25-deploy-code-updates.md) | **Deploy code updates to production Docker: git pull, restart, config caveats** |
| 26 | [26-merge-prod-code-into-local.md](./26-merge-prod-code-into-local.md) | **Merge production code into local dev: git merge-file, branch merge, conflict resolution** |
| 27 | [27-ollama-qwen2.5-14b-switch-validation.md](./27-ollama-qwen2.5-14b-switch-validation.md) | **Validated host Ollama `qwen2.5:14b` as an OpenAI-compatible LLM backend and recorded the switch/rollback steps** |
| 28 | [28-remote-gpu-embedding-api-deployment.md](./28-remote-gpu-embedding-api-deployment.md) | **Moved `embedding_api` to a remote GPU server, validated CUDA embeddings/rerank, and redirected the main RAG server to use it** |
| 30 | [30-separate-network-rag-gpu-stack-validation.md](./30-separate-network-rag-gpu-stack-validation.md) | **Validated a separate `10.42.*` GPU+RAG stack, recovered Milvus/runtime contracts, and pointed local RAG services to local-network embedding/rerank** |
| 31 | [31-offline-gpu-vllm-pattern.md](./31-offline-gpu-vllm-pattern.md) | **Recommended offline deployment pattern for inner-network GPU hosts: host-specific NVIDIA driver handling plus portable `vLLM` runtime artifacts** |
| 32 | [32-offline-gpu-migration-runbook.md](./32-offline-gpu-migration-runbook.md) | **Single-file migration checklist: copy list, checksums, target restore commands, and final validation for offline GPU hosts** |
| 33 | [33-10.42.0.125-vllm-compose-qa-validation.md](./33-10.42.0.125-vllm-compose-qa-validation.md) | **Records the exact July 29, 2026 working recipe for host `vLLM` plus Compose-managed backend services on `10.42.0.125`** |
| 34 | [34-compatibility-baseline.md](./34-compatibility-baseline.md) | **Stage 1 refactor baseline: freeze current service entrypoints, routes, response envelopes, config keys, and `10.42.0.125` deployment assumptions** |
| 35 | [35-rebuild-plan.md](./35-rebuild-plan.md) | **Companion execution plan for `34`: phased rebuild checklist, status tracking, guardrails, and deferred framework evaluation** |
| 36 | [36-jj-rdp-vm-notes.md](./36-jj-rdp-vm-notes.md) | **Operational notes from the August 6, 2026 `jj` workstation rehearsal: XRDP user separation, libvirt access, and offline Ubuntu VM validation constraints** |
| 37 | [37-qwen3-awq-multi-gpu-concurrency-notes.md](./37-qwen3-awq-multi-gpu-concurrency-notes.md) | **Troubleshooting note for running `Qwen3-14B-AWQ` and `Qwen3-32B-AWQ` concurrently on a 4-GPU host: port-vs-GPU confusion, `--gpus all` limits, tensor parallel setup, and the final working 32B command** |

## Quick reference

| Service | Port | Swagger |
|---------|------|---------|
| Document API | 12355 | http://localhost:12355/docs |
| Embedding API | 12356 | http://localhost:12356/docs |
| RAG / QA API | 12357 | http://localhost:12357/docs |
| Milvus | 19530 | (gRPC/HTTP, no Swagger) |
| Attu (Milvus GUI) | 8000 | http://localhost:8000 |

## Project root layout

```
setup/
鈹溾攢鈹€ document_fragment/     鈫?main project (code + compose)
鈹溾攢鈹€ volumes/milvus/        鈫?Milvus data
鈹溾攢鈹€ document_fragment-mupdf-3.tar
鈹溾攢鈹€ milvus.tar
鈹斺攢鈹€ standalone_embed.sh    鈫?Milvus start script (Linux)
```
