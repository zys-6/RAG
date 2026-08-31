# 27 - Ollama `qwen2.5:14b` Switch Validation

This note records a successful validation on July 20, 2026 for switching the project LLM backend from the existing Dockerized vLLM service to host Ollama using model `qwen2.5:14b`.

The goal of this validation was not to replace embeddings or rerank. It was only to prove that the chat/completions path required by the RAG project can be served by Ollama.

---

## Result

Validation succeeded.

The following was confirmed:

- the old vLLM service was running inside Docker container `zhuque3`
- `vllm` was not installed in the host Python environment
- `vllm` was installed inside the Docker container
- host Ollama was running
- model `qwen2.5:14b` existed locally in Ollama
- Ollama responded correctly on both:
  - `/api/generate`
  - `/v1/chat/completions`

That means this project can switch its main LLM endpoint to Ollama by configuration, without changing the Python LLM call sites.

---

## Environment Observations

### Old vLLM location

Host check:

```bash
python3 -m pip show vllm
```

Result:

- package not found on host

Docker check:

```bash
docker exec -it zhuque3 bash
python -m pip show vllm
```

Result:

- `vllm` installed in container
- verified version: `0.5.5`

Conclusion:

- vLLM belonged to the Docker container, not the host Python environment

### Ollama location

Host check:

```bash
ollama list
```

Result included:

- `qwen2.5:14b`

Conclusion:

- Ollama and the target model were available on the host

---

## GPU Safety Before Switching

Before switching, both vLLM and Ollama were occupying GPU memory at the same time.

That is not a safe long-term serving pattern for this machine because GPU memory was already nearly full.

Recommended stop command for the old vLLM container:

```bash
docker stop zhuque3
```

Verification:

```bash
nvidia-smi
```

Expected result after stop:

- the large `/bin/python` processes belonging to vLLM disappear
- only Ollama and normal desktop processes remain

This stop/start workflow is reversible:

```bash
docker start zhuque3
```

---

## Successful Ollama Tests

### 1. Native Ollama generate API

Successful command:

```bash
curl http://127.0.0.1:11434/api/generate -d '{"model":"qwen2.5:14b","prompt":"Say only:ok","stream":false}'
```

Successful result characteristics:

- response JSON returned
- `"model":"qwen2.5:14b"`
- `"response":"ok"`
- `"done":true`

This proves:

- Ollama is healthy
- the model is usable
- inference works locally

### 2. OpenAI-compatible chat completions API

Successful command:

```bash
curl http://127.0.0.1:11434/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"qwen2.5:14b","messages":[{"role":"user","content":"Say only: ok"}],"stream":false}'
```

Successful result characteristics:

- valid JSON returned
- `"object":"chat.completion"`
- `"model":"qwen2.5:14b"`
- assistant response content returned normally

This is the key proof for this project, because the Python code uses an OpenAI-compatible client.

---

## Why This Project Can Switch By Config

The project does not call vLLM-specific Python APIs directly.

It uses OpenAI-compatible HTTP clients, for example:

- `src/rag/services/qa.py`
- `src/rag/utils/request_llm.py`
- `src/rag/domain/chat_request.py`

These paths build `openai.AsyncClient(...)` with:

- `API_BASE_URL`
- `API_KEY`
- `MODEL_NAME`

So as long as the backend provides a compatible `/v1/chat/completions` API, the application code does not need a logic change.

---

## Important Config Source

For this repo, the effective Python runtime config is read from:

`src/rag/configs/app_config_pro.yaml`

Loader:

```python
# src/rag/configs/__init__.py
app_config = read_app_config()
```

This matters because Docker `.env` values are not the only config source in this repo.

When switching LLM backends, do not assume that editing `.env` alone is enough.

---

## Recommended Ollama Config

To use host Ollama with `qwen2.5:14b`, set the LLM config in `src/rag/configs/app_config_pro.yaml` like this:

```yaml
MODEL_NAME: "qwen2.5:14b"
API_KEY: "ollama"
API_BASE_URL: "http://host.docker.internal:11434/v1/"

MODEL_NAME2: "qwen2.5:14b"
API_KEY2: "ollama"
API_BASE_URL2: "http://host.docker.internal:11434/v1/"
```

Leave these unchanged for the first switch:

- `EMBEDDING_URL`
- `RERANK_URL`
- `MILVUS_URI`
- `MILVUS_COLLECTION`

That keeps the migration small:

- chat LLM switched to Ollama
- embeddings and rerank stay on the current path

---

## Practical Switching Sequence

Recommended sequence:

1. Stop the old vLLM container:

```bash
docker stop zhuque3
```

2. Verify Ollama model works:

```bash
curl http://127.0.0.1:11434/api/generate -d '{"model":"qwen2.5:14b","prompt":"Say only:ok","stream":false}'
```

3. Verify OpenAI-compatible endpoint works:

```bash
curl http://127.0.0.1:11434/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"qwen2.5:14b","messages":[{"role":"user","content":"Say only: ok"}],"stream":false}'
```

4. Update `src/rag/configs/app_config_pro.yaml`

5. Restart the relevant project service, usually `qa_api`

6. Test `/qa/qa`

---

## Rollback

Rollback is simple if the vLLM container was only stopped, not deleted.

Restart:

```bash
docker start zhuque3
```

Then restore the previous values in `src/rag/configs/app_config_pro.yaml`.

Recommended backup before switching:

```bash
docker inspect zhuque3 > zhuque3.inspect.json
cp src/rag/configs/app_config_pro.yaml src/rag/configs/app_config_pro.yaml.bak
```

---

## What This Validation Does Not Prove

This validation proves the chat endpoint works.

It does not by itself prove:

- embedding compatibility with Ollama
- rerank compatibility with Ollama
- production throughput relative to vLLM
- long-context performance equivalence
- concurrency equivalence under load

Those should be treated as separate validation tasks.

---

## Short Conclusion

On July 20, 2026, Ollama with model `qwen2.5:14b` was successfully validated on the host machine for this project's OpenAI-compatible chat path.

The project can switch its LLM backend from Dockerized vLLM to host Ollama by configuration, as long as:

- the old GPU-heavy vLLM service is stopped first
- `src/rag/configs/app_config_pro.yaml` is updated
- embeddings and rerank remain unchanged for the first migration step
