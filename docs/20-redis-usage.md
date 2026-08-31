# 20 — Redis Usage

Where this project **references and uses Redis** — code locations, intended roles, and what actually runs in the default deployment.

Related: [05-configuration.md](./05-configuration.md), [08-known-limitations.md](./08-known-limitations.md), [18-configuration-files-summary.md](./18-configuration-files-summary.md).

---

## Summary

Redis is **optional** and **not deployed** in the default `docker-compose.yaml` stack. The project references Redis in **three code locations**, but only one async pipeline was ever intended — and that pipeline is **inactive** in normal use.

| # | Location | Purpose | Status |
|---|----------|---------|--------|
| 1 | `src/tasks/main.py` | Celery **broker** (`CELERY_BROKER=redis`) | Active code, not deployed |
| 2 | `src/tasks/main.py` + `src/api/services/word.py` | **Result cache** in hash `document_fragment_result` | Active code, not used |
| 3 | `src/rag/controllers/qa.py` | OCR chat **dedup** (`ocr_chat:{task_id}`) | **Commented out** — does not run |

**What does *not* use Redis:** Milvus, embedding API, main RAG/QA flow (except commented OCR dedup), and default **sync** document processing.

---

## Three places in code — what “works” means

### Place 1 & 2: Same async Word-processing pipeline

These are **not two independent features**. They are two parts of one optional flow:

1. **Broker** — Celery enqueues `process_word` via Redis when `CELERY_BROKER` is set.
2. **Result store** — The Celery worker writes parsed fragments to Redis; `get_async_result()` would read them back.

```python
# src/tasks/main.py
CELERY_BROKER = os.environ.get("CELERY_BROKER", None)

if CELERY_BROKER:
    app = Celery("document_fragment_tasks", broker=CELERY_BROKER)

    @app.task(bind=True)
    def process_word(self, content: bytes):
        fragments = process_word_core(content)
        fragments = [fragment.to_json() for fragment in fragments]
        redis_client.hset("document_fragment_result", get_hash_code(content), json.dumps(fragments))
```

```python
# src/api/services/word.py
def process_word(..., sync, ...):
    if sync:
        resp = tasks.process_word_core(file_content)
        ...
    else:
        tasks.process_word.delay(file_content)  # async path
        resp = get_hash_code(file_content)

def get_async_result(hash_code: str):
    result = redis_client.hget("document_fragment_result", hash_code)
    ...
```

### Place 3: Commented OCR chat dedup

`src/rag/controllers/qa.py` contains commented code that would use `redis.asyncio` to deduplicate OCR chat requests (`ocr_chat:{task_id}` keys with TTL). **This code is disabled** and never runs.

---

## Why nothing runs in the default setup

Even though places 1 and 2 are real (non-commented) code, the async Redis path is **effectively dead**:

| Gap | Detail |
|-----|--------|
| No Redis in compose | `docker-compose.yaml` has no Redis service |
| No Celery worker | No worker container to consume tasks |
| All callers use sync | e.g. `src/api/controllers/word.py` calls `process_word(..., True, ...)` |
| `get_async_result` unwired | No controller or route calls it |
| Missing import bug | `word.py` uses `redis_client` in `get_async_result()` but does not import it — would crash if invoked |

**Bottom line:** One location is explicitly disabled (OCR dedup). Two locations are live code for async Celery, but that whole feature is **unfinished and unused** in the default deployment.

---

## Configuration

### Environment (`.env`)

```env
CELERY_BROKER='redis'
```

When set, Celery uses the string `redis` as the broker URL. Redis must be reachable separately; compose does not start it.

### Redis client config

**File:** `src/utils/redis/redis_config.yaml`

```yaml
redis_config:
  host: "192.168.14.76"
  port: 36379
  database: 13
```

**Client wrapper:** `src/utils/redis/redis_client.py`  
**Singleton:** `src/utils/redis/__init__.py` → `client = RedisClient("utils/redis/redis_config.yaml")`

`RedisClient` wraps `redis.StrictRedis` with:

- `hset(name, key, val)`
- `hget(name, key)`
- `hdel(name, key)`
- `hgetall(name, key=None)`

### Redis hash key used by async Word processing

| Key | Type | Field | Value |
|-----|------|-------|-------|
| `document_fragment_result` | Hash | content hash (`get_hash_code(content)`) | JSON array of fragment objects |

---

## Code map

```
src/
├── utils/redis/
│   ├── __init__.py              # exports client singleton
│   ├── redis_client.py          # RedisClient wrapper
│   └── redis_config.yaml        # host, port, database
├── tasks/main.py                # Celery app + hset on async task complete
├── api/services/word.py         # async enqueue + get_async_result (hget)
└── rag/controllers/qa.py        # commented redis.asyncio OCR dedup
```

---

## What would be needed to enable async processing

1. Run Redis (add to compose or external instance).
2. Point `CELERY_BROKER` at a full URL (e.g. `redis://host:6379/0`), not just the string `redis`.
3. Add a Celery worker service to compose.
4. Expose an API endpoint that calls `get_async_result(hash_code)`.
5. Fix the missing `redis_client` import in `src/api/services/word.py`.
6. Call `process_word(..., sync=False, ...)` from at least one route when async is desired.

Until then, use **sync endpoints only** (`/word/sync`, `/pdf/sync`, etc.) — they do not use Redis.

---

## Related docs

- [08-known-limitations.md](./08-known-limitations.md) — Celery/Redis listed as unavailable
- [18-configuration-files-summary.md](./18-configuration-files-summary.md) — Redis config file reference
- [03-structure.md](./03-structure.md) — `tasks/` and `utils/` layout
