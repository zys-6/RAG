# 28 - Remote GPU `embedding_api` Deployment and Rerank Redirection

This document records the successful July 21, 2026 operation that moved the heavy `embedding_api` workload onto a separate GPU server and redirected the main RAG server to use it remotely.

The purpose was to make embeddings and rerank use GPU, while the main `document_fragment` application remained on a machine with no GPU.

---

## Final architecture

Two machines are involved:

### `192.168.1.227`

This is the main `document_fragment` application server.

It runs:

- `document_fragment_api`
- `qa_api`
- the original `embedding_api` service in Docker
- Milvus

Important limitation:

- this machine has **no GPU**

### `192.168.1.100`

This is the GPU server.

It was used to run a new CUDA-enabled `embedding_api` image and expose the same service endpoints remotely.

It provides:

- `/embeddings`
- `/rerank`

using GPU acceleration.

---

## Why this architecture was necessary

At first, there was a question whether the CUDA image built on `192.168.1.100` could simply be deployed on `192.168.1.227` and somehow use `192.168.1.100`'s GPU.

That is not how Docker works.

Rules:

1. A container uses the GPU of the machine where it runs.
2. A container running on `192.168.1.227` cannot use the GPU of `192.168.1.100`.
3. If `192.168.1.227` has no GPU, GPU rerank must run as a remote service on `192.168.1.100`.

So the correct design is:

1. run CUDA `embedding_api` on `192.168.1.100`
2. point `192.168.1.227` to the remote endpoints with `EMBEDDING_URL` and `RERANK_URL`

---

## What was validated first

Before changing the live RAG server config, the new image was validated on `192.168.1.100`.

### 1. GPU visibility inside the image

Tested by running the image directly with GPU enabled:

```bash
docker run --rm --gpus all -it <image-id> python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"
```

Successful result:

- `True 4`

Meaning:

- PyTorch could see CUDA
- the image could see all 4 GPUs on the host

### 2. Initial startup blockers

During validation, these issues were found:

1. `/models/text2vec-base-multilingual` was missing on the GPU machine
2. `embedding.api` could not import if the mounted `/src` tree was incomplete

These were not CUDA failures. They were missing runtime assets.

---

## Runtime assets required by `embedding_api`

The service does not need only the CUDA image. It also needs:

1. the model directory mounted as `/models`
2. the application code mounted as `/src`

On the main server `192.168.1.227`, the real mounts of the running service were discovered from Docker:

```bash
docker inspect document_fragment-embedding_api-1 --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

Result:

```text
/home/zhuque/zhuque_backend/setup/document_fragment/models -> /models
/home/zhuque/zhuque_backend/setup/document_fragment/src -> /src
```

These two host paths were treated as the reference runtime layout.

---

## Model directories copied to the GPU server

On `192.168.1.227`, the required model folders were confirmed:

```text
reranker
text2vec-base-multilingual
```

These were archived and copied to `192.168.1.100`.

### Pack on `192.168.1.227`

```bash
cd /home/zhuque/zhuque_backend/setup/document_fragment/models
tar -czf /tmp/embedding-models.tar.gz text2vec-base-multilingual reranker
```

### Copy to `192.168.1.100`

```bash
scp /tmp/embedding-models.tar.gz root@192.168.1.100:/tmp/
```

### Extract on `192.168.1.100`

```bash
mkdir -p /home/zhuque/zhuque_backend/setup/document_fragment/models
tar -xzf /tmp/embedding-models.tar.gz -C /home/zhuque/zhuque_backend/setup/document_fragment/models
```

After extraction, the GPU machine had:

```text
/home/zhuque/zhuque_backend/setup/document_fragment/models/reranker
/home/zhuque/zhuque_backend/setup/document_fragment/models/text2vec-base-multilingual
```

---

## Source tree required by the GPU service

The GPU machine also needed the code tree:

```text
/home/zhuque/zhuque_backend/setup/document_fragment/src
```

This path was verified to contain the expected package:

```text
src/embedding/api.py
src/embedding/__init__.py
```

Without this, the service would fail with:

```text
ModuleNotFoundError: No module named 'embedding'
```

---

## Correct container test command on `192.168.1.100`

After models and source were present, the validated one-line startup command was:

```bash
docker run --rm --gpus all -p 15006:5006 -v /home/zhuque/zhuque_backend/setup/document_fragment/models:/models -v /home/zhuque/zhuque_backend/setup/document_fragment/src:/src -w /src -it <image-id> uvicorn embedding.api:app --host 0.0.0.0 --port 5006
```

Notes:

1. `15006:5006` was used instead of `5006:5006` to avoid clashing with any existing local service
2. `-w /src` matches the project's usual runtime layout
3. a one-line command was more reliable than line continuations during manual shell testing

Successful runtime log included:

```text
Use pytorch device: cuda
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:5006
```

This was the key proof that the service was actually using CUDA.

---

## Endpoint validation on the GPU server

The remote test service was exposed on:

```text
http://127.0.0.1:15006
```

### 1. Swagger / docs

```bash
curl http://127.0.0.1:15006/docs
```

Result:

- Swagger HTML returned successfully

### 2. Embeddings endpoint

```bash
curl -X POST 'http://127.0.0.1:15006/embeddings' \
  -H 'Content-Type: application/json' \
  -d '{"input":["Java"]}'
```

Result:

- embedding vectors returned successfully

### 3. Rerank endpoint

At first, the request body was wrong and failed because the endpoint expects:

- `query`
- `texts`

not:

- `input`

The corrected request was:

```bash
curl -X POST 'http://127.0.0.1:15006/rerank' \
  -H 'Content-Type: application/json' \
  -d '{"query":"Java","texts":["hello world","java document","python note"]}'
```

Result:

- rerank scores returned successfully

That proved:

1. the service was live
2. reranker model was loaded
3. the service contract was usable remotely

---

## Why `nvidia-smi` did not obviously move during rerank

Rerank requests were very short, often under one second.

Because of that:

- `watch -n 1 nvidia-smi` could easily miss the transient GPU activity

This does **not** invalidate the result.

The stronger evidence was:

1. startup log explicitly said CUDA was used
2. endpoints returned valid embedding and rerank results
3. the service only started cleanly after the CUDA image plus model mounts were correct

If a more visible GPU proof is needed later, use:

```bash
nvidia-smi dmon -s u
```

or a looped rerank workload.

---

## Config changes made on `192.168.1.227`

The main RAG application reads runtime config from:

```text
src/rag/configs/app_config_pro.yaml
```

On `192.168.1.227`, the file was backed up:

```bash
cp src/rag/configs/app_config_pro.yaml src/rag/configs/app_config_pro.yaml.bak-2026-07-21
```

Then the embedding and rerank URLs were changed to point to the GPU server:

```yaml
EMBEDDING_URL: "http://192.168.1.100:15006/embeddings"
RERANK_URL: "http://192.168.1.100:15006/rerank"
```

These were verified with:

```bash
grep -E 'EMBEDDING_URL|RERANK_URL' src/rag/configs/app_config_pro.yaml
```

---

## Service restart on `192.168.1.227`

Only `qa_api` needed restart after the config change:

```bash
docker compose restart qa_api
```

or equivalently:

```bash
docker restart document_fragment-qa_api-1
```

Logs were then checked to ensure no startup/import error.

---

## Final successful state

At the end of this operation:

### On `192.168.1.100`

- CUDA-enabled `embedding_api` was running
- `/embeddings` worked
- `/rerank` worked
- startup explicitly reported CUDA usage

### On `192.168.1.227`

- `qa_api` config was updated to use the remote GPU service
- restart succeeded
- end-to-end remote embedding/rerank redirection succeeded

This means the main RAG application now uses the GPU server for embedding and rerank, while the main application host still has no GPU.

---

## Common mistakes encountered during the operation

These were all encountered and resolved during the real procedure:

1. wrong image/tag typing when using `docker run`
2. typo in `torch.cuda.is_available()`
3. wrong `uvicorn` flag (`-port` instead of `--port`)
4. broken shell continuation producing `docker: invalid reference format`
5. missing `/models/text2vec-base-multilingual`
6. missing or incomplete `/src` tree causing `No module named 'embedding'`
7. wrong request body for `/rerank` (`input` instead of `query` + `texts`)

These are worth checking first if the operation is repeated on another machine.

---

## Rollback

If the main server needs to return to its previous config:

### Restore config on `192.168.1.227`

```bash
cp src/rag/configs/app_config_pro.yaml.bak-2026-07-21 src/rag/configs/app_config_pro.yaml
docker compose restart qa_api
```

### Stop the remote GPU test service on `192.168.1.100`

Stop the foreground `docker run` process with `Ctrl+C`, or stop the container if it is detached.

---

## Short conclusion

On July 21, 2026, the project successfully moved `embedding_api` workloads to a remote GPU server.

The final pattern was:

1. run CUDA `embedding_api` on `192.168.1.100`
2. keep `document_fragment_api`, `qa_api`, and Milvus on `192.168.1.227`
3. redirect `EMBEDDING_URL` and `RERANK_URL` on `192.168.1.227` to the GPU server

This achieved the real goal:

- embeddings and rerank now use GPU
- the main RAG server does not need a GPU of its own
