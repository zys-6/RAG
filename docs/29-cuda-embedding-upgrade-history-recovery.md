# 29 - CUDA `embedding_api` Upgrade History and Recovery Notes

This note preserves the earlier July 9, 2026 CUDA upgrade attempt for `embedding_api`, so the same migration can be repeated later without depending on raw Codex session archives.

It complements [28-remote-gpu-embedding-api-deployment.md](./28-remote-gpu-embedding-api-deployment.md):

- `28` records the final successful remote GPU deployment on July 21, 2026
- this document records the earlier upgrade history, failed assumptions, code/config changes, and recovery lessons that led to that final pattern

---

## Why this note exists

The old migration history contained several details that are operationally important but easy to lose:

- what was first assumed incorrectly
- what image strategy was tried on Windows
- why the first CUDA-base build failed
- which source/config files were revised to support remote embedding and rerank
- what parts of the system needed to stay mounted at runtime

Those details are useful when repeating the same upgrade on a new machine.

---

## Historical objective

The goal was:

1. move `embedding_api` and rerank onto a GPU-capable host
2. keep the main RAG application on another host
3. make the main application call remote `/embeddings` and `/rerank`
4. avoid breaking the existing Dockerized application layout

The main machines in that history were:

- `192.168.1.227`: current application host, running `embedding_api` but with no GPU
- `192.168.1.100`: GPU-capable peer machine intended to host CUDA embedding/rerank

---

## The first important conclusion

The correct target was **not**:

- “run the container on `192.168.1.227` and somehow use the GPU from `192.168.1.100`”

The correct model was:

- run the CUDA `embedding_api` container on the GPU machine itself
- expose it remotely
- point the app host to the remote endpoints

This is the same conclusion later captured in [28-remote-gpu-embedding-api-deployment.md](./28-remote-gpu-embedding-api-deployment.md).

---

## How the CUDA upgrade was actually made

This is the clearest reconstruction of the real upgrade path.

### Stage 1 - Try a dedicated CUDA-base build on Windows

The first idea was:

1. create a special CUDA embedding image
2. build it on the Windows Lenovo machine
3. test that image there

The attempted base was:

```dockerfile
FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime
```

The intended build command was:

```bash
docker build -f Dockerfile.embedding -t embedding_api:cuda12.1 .
```

This stage did **not** finish successfully.

Why it failed:

- the build could not fetch the CUDA base image metadata
- Docker was going through a mirror/proxy path
- the local proxy endpoint `127.0.0.1:7890` was not usable

So the first stage ended as:

- **attempted**
- **not validated**
- **not usable as the final recovery method**

### Stage 2 - Stop treating the problem as "just pull a CUDA base image"

After the Windows build failure, the strategy changed.

The important realization was:

- the deployment problem was bigger than the Dockerfile base line
- even with a good image, the service still needs the project `src/` tree and model directories at runtime
- the main application host did not have a GPU anyway

So the migration shifted from:

- "build CUDA image on Windows and prove it there"

to:

- "run the embedding service on the actual GPU machine and preserve the original runtime layout"

### Stage 3 - Use a wrapper image instead of a fresh heavy CUDA-base rebuild

The recovered `Dockerfile.embedding` approach became:

```dockerfile
FROM document_fragment:mupdf-3

ENV PYTHONUNBUFFERED=1

WORKDIR /src

# Offline build wrapper for the embedding service.
# Reuses the already-loaded local `document_fragment:mupdf-3` image,
# then mounts the live source code and model weights at runtime.
CMD ["uvicorn", "embedding.api:app", "--host", "0.0.0.0", "--port", "5006"]
```

This means the practical "CUDA upgrade" was **not**:

- rebuild the whole stack from a brand-new public CUDA base and bake all code/models into it

It was:

- keep the existing project image strategy
- preserve runtime mounts
- run the service on a host where GPU is actually available

### Stage 4 - Make the Python service CUDA-capable where it mattered

The real code-side CUDA upgrade happened in `src/embedding/api.py`.

The reranker path was upgraded so it:

1. detects whether CUDA is available
2. moves the reranker model to CUDA when available
3. moves tokenized inputs to the same device
4. moves output back to CPU for JSON serialization

The critical pattern was:

```python
rerank_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
...
reranker_model = AutoModelForSequenceClassification.from_pretrained(...).to(rerank_device)
...
inputs = {key: value.to(rerank_device) for key, value in inputs.items()}
scores = reranker_model(**inputs, return_dict=True).logits.view(-1, ).float().cpu()
```

This was necessary because:

- embedding already auto-selected device via `text2vec`
- rerank needed explicit device placement

### Stage 5 - Make the app configurable enough to call remote GPU embedding

To finish the upgrade, the application had to be taught to call a remote embedding/rerank service.

That required:

1. environment override support in `src/rag/configs/__init__.py`
2. passing `EMBEDDING_URL` and `RERANK_URL` through compose/env
3. updating examples/docs away from assuming only `embedding_api:5006`

Without this, even a working GPU-side embedding service would not be used by the main app.

### Stage 6 - Run the upgraded service on the actual GPU machine

The final successful path was:

1. prepare the GPU host `192.168.1.100`
2. ensure it has:
   - `models/text2vec-base-multilingual`
   - `models/reranker`
   - the project `src/` tree
3. start the service there with GPU enabled
4. validate `/embeddings` and `/rerank`
5. point the main app host `192.168.1.227` to the remote GPU endpoints

So the finished upgrade was:

- **service logic upgraded for CUDA**
- **deployment architecture changed to remote GPU hosting**
- **config changed so the main app uses the remote GPU service**

### Short truth

If someone asks, "How was the CUDA upgrade made?", the shortest accurate answer is:

1. the first Windows CUDA-base image attempt failed during image pull
2. the approach changed to a wrapper-image plus runtime-mount strategy
3. rerank code in `src/embedding/api.py` was made CUDA-aware
4. app config was changed so embedding/rerank endpoints could point to a remote GPU host
5. the upgraded `embedding_api` was finally run and validated on `192.168.1.100`

That is the real historical sequence.

---

## Early image strategy that was attempted

An early attempt was to build a CUDA-specific embedding image on the Windows Lenovo machine using:

```dockerfile
FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime
```

That build failed before the image could even be created.

Observed failure pattern:

- Docker tried to resolve `pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime`
- the request went through `docker.mirrors.ustc.edu.cn`
- the machine also tried to use a dead local proxy at `127.0.0.1:7890`
- the result was metadata-fetch failure, not a Python or CUDA runtime failure

Practical meaning:

- the first failure was **registry/proxy/network related**
- it did **not** prove CUDA was impossible
- it only proved the Windows build path could not currently pull that base image

---

## Recovery in image strategy

The later practical recovery was to stop depending on a new remote CUDA base pull and instead use a thin wrapper image:

```dockerfile
FROM document_fragment:mupdf-3

ENV PYTHONUNBUFFERED=1

WORKDIR /src

# Offline build wrapper for the embedding service.
# Reuses the already-loaded local `document_fragment:mupdf-3` image,
# then mounts the live source code and model weights at runtime.
CMD ["uvicorn", "embedding.api:app", "--host", "0.0.0.0", "--port", "5006"]
```

Why this mattered:

1. it reused the already available local image
2. it avoided failing on external CUDA-base image pulls
3. it kept source code and model weights as runtime mounts instead of baking them into the image

This is a key recovery lesson:

- if the environment is offline, mirrored, or proxy-broken, prefer a wrapper around an existing local image over a fresh heavyweight CUDA base pull

---

## Source changes that were part of the migration history

The old upgrade thread included several important code/config changes. These are the parts worth preserving conceptually when repeating the migration.

### 1. Make rerank use CUDA when available

`src/embedding/api.py` was changed so rerank explicitly follows the active Torch device:

- compute `rerank_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")`
- move reranker model to that device
- move tokenizer tensors to that device
- move logits back to CPU before returning JSON

Practical meaning:

- embedding already auto-selected device through `text2vec`
- rerank needed explicit `.to(rerank_device)` handling

### 2. Allow app config to be overridden by environment

`src/rag/configs/__init__.py` was changed so keys from `app_config_pro.yaml` can be overridden from environment variables.

Practical meaning:

- deployment-specific URLs like `EMBEDDING_URL` and `RERANK_URL` no longer had to be hardcoded only in YAML
- the same app code could be pointed at a remote GPU service through environment at runtime

### 3. Pass remote embedding/rerank URLs through compose

`docker-compose.yaml` and `.env.example` were changed so these variables propagate consistently:

- `EMBEDDING_URL`
- `RERANK_URL`

They were passed into:

- `document_fragment_api`
- `embedding_api`
- `qa_api`

Practical meaning:

- all relevant services could agree on the remote embedding/rerank location

### 4. Replace internal-only `embedding_api:5006` assumptions in docs/examples

Docs and example config values were updated away from assuming only:

```text
http://embedding_api:5006
```

and toward the remote-host model:

```text
http://192.168.1.100:5006/embeddings
http://192.168.1.100:5006/rerank
```

Practical meaning:

- the project shifted from “same Docker network only” toward “remote GPU service is valid”

---

## Runtime assumptions discovered during the old upgrade

The CUDA image/service was not enough by itself.

The embedding service also required:

1. `/models/text2vec-base-multilingual`
2. `/models/reranker`
3. the application source tree mounted at `/src`
4. working directory set to `/src`

Without these, failures looked like:

- missing model path
- `ModuleNotFoundError: No module named 'embedding'`

This is one of the most important recovery facts:

- the service is image + runtime mounts, not image alone

---

## Durable replay procedure

If this upgrade must be replayed again on another machine, use this order:

1. Confirm the main app host has no usable GPU and the target remote host does.
2. Do not assume a container can use a GPU from another machine.
3. Prefer the existing local-image wrapper strategy if fresh CUDA base pulls are unreliable.
4. Ensure the GPU host has:
   - `models/text2vec-base-multilingual`
   - `models/reranker`
   - project `src/`
5. Start the embedding service on the GPU host with GPU access enabled.
6. Verify inside-container CUDA visibility first.
7. Verify `/embeddings` and `/rerank` directly on the GPU host.
8. Point `EMBEDDING_URL` and `RERANK_URL` on the main host to the remote GPU host.
9. Restart only the services that need the new config, usually `qa_api` and any service that directly calls embedding/rerank.

For the validated runtime command and endpoint checks, use [28-remote-gpu-embedding-api-deployment.md](./28-remote-gpu-embedding-api-deployment.md).

---

## What failed historically, and what it meant

### Failed assumption

- “maybe the app host container can use the GPU from the other machine”

Meaning:

- wrong deployment model

### Failed build

- `docker build -f Dockerfile.embedding -t embedding_api:cuda12.1 .`
- failed while fetching `pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime`

Meaning:

- registry/proxy issue, not proof that CUDA serving design was invalid

### Missing runtime assets

- missing models
- missing/incomplete `/src`

Meaning:

- container runtime layout must match the original service layout

---

## Most important recovery lessons

1. The real architecture is **remote GPU service**, not remote GPU borrowing.
2. The first blocker may be network/proxy/image-pull related, not CUDA related.
3. `Dockerfile.embedding` is best treated as a thin wrapper when the base image already exists locally.
4. Rerank needed explicit CUDA device handling in `src/embedding/api.py`.
5. Environment override support is critical for deployment portability.
6. The service is not recoverable from image alone; the mounted `models/` and `src/` trees are part of the runtime contract.

---

## Search commands for the raw history

If the old Codex session archive must be searched again:

Quick index:

```bash
rg -n "embedding_api|Dockerfile.embedding|cuda12.1|CUDA base|GPU server" /home/z/.codex/history.jsonl
```

Full session archive:

```bash
rg -n "embedding_api|Dockerfile.embedding|cuda12.1|CUDA base|GPU server" /home/z/.codex/sessions
```

Specific session file from the July 9 upgrade thread:

```bash
less /home/z/.codex/sessions/2026/07/09/rollout-2026-07-09T14-30-06-019f4591-b9f8-7761-9e13-95a794758454.jsonl
```

---

## Short conclusion

The old CUDA-upgrade history shows that the final successful migration was not a single clean deployment step.

It was a sequence of corrections:

1. stop assuming cross-machine GPU sharing
2. stop treating the problem as “just build a CUDA image”
3. preserve the runtime mount contract
4. make rerank explicitly CUDA-aware
5. make embedding/rerank endpoints deployment-configurable
6. run the service on the GPU host and call it remotely

That is the durable recovery pattern to reuse next time.
