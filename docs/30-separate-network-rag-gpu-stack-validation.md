# 30 - Separate-Network RAG and GPU Stack Validation (`10.42.*`)

This document records the successful July 23, 2026 validation of a second deployment in the `10.42.*` network.

It is **not** the same deployment as the older `192.168.1.*` environment.

The purpose was:

1. keep the existing `192.168.1.*` deployment unchanged
2. build a separate CUDA embedding host in the `10.42.*` network
3. reproduce the RAG-side stack in that same network
4. point the local RAG-side services to the local-network GPU endpoints first

---

## Naming

`Parallel test` is understandable in conversation, but it is not the best technical name for this task.

Why:

1. the `10.42.*` and `192.168.1.*` environments are on separate internal networks
2. the new stack is not sharing live traffic with the old one
3. the work was mainly **reproduction, validation, and pointing**, not parallel serving of the same production path

Better names:

- separate-network validation
- separate-network reproduction
- secondary environment bring-up
- isolated GPU/RAG stack validation

This document uses:

- **separate-network RAG and GPU stack validation**

To keep the docs clear, this document intentionally avoids the phrase:

- `parallel test`

because that phrase suggests two environments serving the same role side-by-side, which was not the actual deployment model here.

---

## Final architecture in `10.42.*`

Two roles exist in this new network:

### `10.42.0.125`

This machine was validated as:

- GPU host
- `embedding_api` host
- local Milvus host
- temporary RAG-side host for `document_fragment_api` and `qa_api`

Services confirmed on this machine:

- `embedding_api_gpu` on `15006`
- `document_fragment_api` on `12355`
- `qa_api` on `12357`
- Milvus on `19530`

Important limitation:

- this network still has **no LLM endpoint**

So:

- embedding and rerank can be validated
- Milvus-backed retrieval flows can be validated
- full LLM-backed QA is still incomplete until an LLM endpoint exists in `10.42.*`

---

## What was successfully completed

### 1. CUDA host validation

The machine initially failed `nvidia-smi` because it was booted into the wrong kernel.

The working kernel was:

```text
6.17.0-40-generic
```

After booting that kernel:

- `nvidia-smi` worked
- Docker GPU passthrough worked
- `docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi` succeeded

---

### 2. Runtime assets were recovered locally

The following were recovered on `10.42.0.125`:

- full `document_fragment` tree
- `models/text2vec-base-multilingual`
- `models/reranker`
- `embedding_api_cuda12.1.tar`
- `milvus.tar`
- `standalone_embed.sh`

This mattered because the service is not recoverable from image alone.

It depends on:

- image
- mounted `models/`
- mounted `src/`
- correct working directory

The CUDA wrapper image was saved from a machine where it already existed as:

```bash
docker save -o embedding_api_cuda12.1.tar embedding_api:cuda12.1
```

Before validating the service on `10.42.0.125`, the recovered image tarballs had to be loaded into Docker:

```bash
docker load -i embedding_api_cuda12.1.tar
docker load -i milvus.tar
```

This makes the image names available locally so later commands like
`docker run ... embedding_api:cuda12.1 ...` can actually start.

---

### 3. GPU embedding service was validated first with direct `docker run`

The working runtime pattern was:

```bash
docker run --rm --gpus all -p 15006:5006 -v /home/jj/document_fragment/models:/models -v /home/jj/document_fragment/src:/src -w /src -it embedding_api:cuda12.1 uvicorn embedding.api:app --host 0.0.0.0 --port 5006
```

Successful proof included:

- startup log showed `Use pytorch device: cuda`
- `/docs` responded
- `/embeddings` returned vectors
- `/rerank` returned scores

This direct `docker run` path remained the fallback method for isolated manual recovery.

---

### 4. The GPU service was then made persistent

On `10.42.0.125`, persistence was successfully achieved with:

```yaml
services:
  embedding_api:
    image: embedding_api:cuda12.1
    container_name: embedding_api_gpu
    restart: unless-stopped
    gpus: all
    ports:
      - "15006:5006"
    volumes:
      - ./models:/models
      - ./src:/src
    environment:
      - EMBEDDING_MODEL_PATH=/models/text2vec-base-multilingual
      - RERANKER_MODEL_PATH=/models/reranker
    working_dir: /src
    command: uvicorn embedding.api:app --host 0.0.0.0 --port 5006
```

Validation:

- `docker compose up -d` succeeded
- container restart succeeded
- `/docs`, `/embeddings`, and `/rerank` still worked after restart

---

### 5. RAG-side services were pointed to the local-network GPU endpoint

The intended active values were:

```text
EMBEDDING_URL=http://10.42.0.125:15006/embeddings
RERANK_URL=http://10.42.0.125:15006/rerank
```

These had to be applied carefully because:

1. config existed in both `.env` and `app_config_pro.yaml`
2. the code now allows environment variables to override YAML
3. `docker compose restart` does not apply changed env values
4. containers had to be recreated with `--force-recreate`

Key lesson:

- after changing `.env`, use:

```bash
docker compose up -d --force-recreate document_fragment_api qa_api
```

not only `docker compose restart`.

---

### 6. Milvus had to be started with the project-specific script contract

A plain manual Milvus startup was attempted first, but it was not the right startup contract for this repo.

The correct higher-signal path was the saved Linux script:

```bash
bash standalone_embed.sh start
```

Why:

1. it sets `ETCD_USE_EMBED=true`
2. it generates and mounts `embedEtcd.yaml`
3. it mounts `user.yaml`
4. it exposes `2379`, `19530`, and `9091`
5. it follows the original Milvus startup model used by this project

This was the correct recovery path after the simpler `milvus run standalone` attempt proved insufficient.

---

## Main failures encountered, and what they actually meant

### Failure 1 - `host.docker.internal` Milvus assumption

Old config still pointed to:

```text
http://host.docker.internal:19530
```

On this Linux host, that was the wrong address from inside containers.

Practical fix:

- set `.env` to:

```text
MILVUS_URI='http://172.17.0.1:19530'
MILVUS_URL='http://172.17.0.1:19530'
```

Meaning:

- Linux container-to-host addressing is not the same as the earlier Windows-style assumption

Why `172.17.0.1` worked:

1. on a typical Linux Docker host, the default bridge network is `172.17.0.0/16`
2. containers on that bridge often receive addresses like `172.17.0.x`
3. the host-side bridge interface is commonly `172.17.0.1`
4. Milvus was published on the host at port `19530`
5. the application containers needed a route from container space back to the host-published Milvus port

So the effective path was:

```text
container -> 172.17.0.1:19530 -> host port 19530 -> Milvus container
```

Why not `localhost`:

- inside a container, `localhost` means the container itself, not the host

Why not `host.docker.internal`:

- that old assumption came from Docker Desktop style setups
- on this Linux host, it was not the working route for this stack

If this must be rechecked later on another Linux machine, verify with:

```bash
ip addr show docker0
docker network inspect bridge
```

and confirm the bridge gateway visible to containers.

---

### Failure 2 - stale container environment after `.env` edits

After `.env` was changed, the services still used old values.

Root cause:

- `docker compose restart` restarts existing containers
- it does not rebuild the container environment from the new `.env`

Practical fix:

```bash
docker compose up -d --force-recreate document_fragment_api qa_api
```

Meaning:

- env changes require container recreation

---

### Failure 3 - the app image was missing

`document_fragment_api` and `qa_api` initially failed because:

```text
document_fragment:mupdf-3
```

was not present locally.

Practical recovery:

```bash
docker tag embedding_api:cuda12.1 document_fragment:mupdf-3
```

This worked because:

- `embedding_api:cuda12.1` was a thin wrapper on top of the original app image
- live `src/` and `models/` were mounted anyway

---

### Failure 4 - shell input damage

A large amount of noise came from commands being split across lines in the middle of:

- URLs
- file paths
- header values
- heredoc terminators
- shell redirections

Meaning:

- many apparent failures were shell formatting mistakes, not stack failures

This is worth calling out because it consumed a large part of the recovery time.

---

## Final validated state on `10.42.0.125`

At the end of the operation:

- `embedding_api_gpu` was persistent and reachable on `15006`
- `document_fragment_api` responded on `12355`
- `qa_api` responded on `12357`
- local Milvus was running
- the stack was pointed to the local GPU endpoints:
  - `http://10.42.0.125:15006/embeddings`
  - `http://10.42.0.125:15006/rerank`

This means the separate `10.42.*` deployment was successfully reproduced and pointed.

---

## What is finished vs not finished

### Finished

- GPU host setup
- CUDA embedding service validation
- persistent embedding service deployment
- local Milvus startup
- RAG-side service pointing to local-network embedding/rerank
- RAG-side API startup

### Not finished

- full LLM-backed QA validation
- any cutover involving the unrelated `192.168.1.*` network
- consolidation of old and new config comments in YAML

The missing LLM is a functional limitation, not a GPU or pointing failure.

---

## Recommended next steps

1. Keep `10.42.*` and `192.168.1.*` as separate deployments.
2. Treat `10.42.*` as a validated isolated retrieval/embedding environment until an LLM endpoint exists there.
3. On `192.168.1.100`, prefer the already-working `docker run -d --restart unless-stopped` pattern rather than forcing Compose if its Compose schema rejects `gpus:`.
4. Clean `app_config_pro.yaml` so only the intended active values remain.

---

## Short conclusion

This task is better described as a:

- **separate-network validation**

not a:

- **parallel test**

because the new stack was isolated, reproduced, validated, and pointed within its own network, rather than serving the same live traffic in parallel with the old deployment.
