# 37 - Qwen3 AWQ Multi-GPU Concurrency Notes

This note records the August 14, 2026 troubleshooting sequence for running `Qwen3-14B-AWQ` and `Qwen3-32B-AWQ` at the same time on a 4-GPU host.

It is intentionally narrower than the migration runbook. Its purpose is to preserve the exact failure pattern and the working launch shape for a multi-GPU workstation where one model should span two GPUs and another model should stay isolated on a different GPU.

---

## 1. Problem Summary

Goal:

- run `Qwen3-14B-AWQ` and `Qwen3-32B-AWQ` concurrently
- keep them on different GPU allocations
- expose them on different HTTP ports

Initial assumption that did **not** solve the problem:

- changing `32B` from host port `8000` to `8001`

Why that was not enough:

- host port selection affects HTTP routing only
- it does not affect CUDA device visibility or model placement

Starting point that triggered the investigation:

- the original `32B` launcher used:

```bash
docker run --rm --runtime nvidia --gpus all \
  --name vllm-qwen3-32b-awq \
  -p 8000:8000 \
  --ipc=host \
  -v /home/jj/models/Qwen3-32B-AWQ:/models/Qwen3-32B-AWQ \
  vllm/vllm-openai:latest \
  /models/Qwen3-32B-AWQ \
  --gpu-memory-utilization 0.95 \
  --max-model-len 4096
```

- the user wanted `14B` and `32B` online at the same time
- the first attempted change was only to move `32B` from `8000` to `8001`

---

## 2. First Failure Mode: Port Changed, GPU Still Wrong

Observed behavior:

- `32B` was changed to a different host port
- startup still reported low free memory on `cuda:0`
- startup failed before the server came up

Root cause:

- no explicit GPU selection was applied
- the process still tried to allocate on the first visible GPU
- another model already occupied most of that GPU

Practical rule:

- if `CUDA_VISIBLE_DEVICES` or Docker `--gpus "device=..."` is not set, the first visible GPU is typically used first
- changing `-p 8001:8000` does not move the workload to another GPU

Example of the insufficient change:

```bash
docker run --rm --runtime nvidia --gpus all \
  --name vllm-qwen3-32b-awq \
  -p 8001:8000 \
  --ipc=host \
  -v /home/jj/models/Qwen3-32B-AWQ:/models/Qwen3-32B-AWQ \
  vllm/vllm-openai:latest \
  /models/Qwen3-32B-AWQ \
  --gpu-memory-utilization 0.95 \
  --max-model-len 4096
```

Representative symptom:

- startup still complained about low free memory on `cuda:0`
- this showed the model was still trying to allocate on the first visible GPU rather than on an isolated pair of GPUs

---

## 3. Second Failure Mode: `--gpus all` Still Failed

Observed behavior:

- the container was started with `--gpus all`
- startup still failed

Root cause:

- `--gpus all` exposes multiple GPUs to the container
- it does **not** automatically shard one model across them
- `Qwen3-32B-AWQ` still behaved like a single-placement workload until tensor parallelism was explicitly enabled

Practical rule:

- `--gpus all` means "all GPUs are visible"
- `--tensor-parallel-size 2` means "split this model across two GPUs"

Representative test that still failed:

```bash
docker run --rm --runtime nvidia --gpus all \
  --name vllm-qwen3-32b-awq \
  -p 8001:8000 \
  --ipc=host \
  -v /home/jj/models/Qwen3-32B-AWQ:/models/Qwen3-32B-AWQ \
  vllm/vllm-openai:latest \
  /models/Qwen3-32B-AWQ \
  --gpu-memory-utilization 0.95 \
  --max-model-len 4096
```

Why this matters operationally:

- seeing multiple GPUs in `nvidia-smi` is not enough
- the `32B` model still needs explicit multi-GPU sharding instructions
- otherwise it behaves like a first-visible-GPU launch with extra unused visible devices

---

## 4. Third Failure Mode: 2-GPU Tensor Parallelism Started, Then Crashed

Observed behavior after moving `32B` to two explicit GPUs and adding tensor parallelism:

- logs showed `Worker_TP0` and `Worker_TP1`
- startup advanced much farther than before
- failures occurred during warmup and CUDA graph capture
- representative errors included:
  - `torch_call_dispatcher(... c_marlin_gemm_default ...)`
  - `Engine core initialization failed`
  - later, a more explicit `CUDA error: out of memory`

What that meant:

- the model was no longer failing because of wrong GPU selection
- it was failing because startup warmup still needed more memory headroom

Practical rule:

- once tensor parallel workers appear, GPU placement is likely correct
- at that point, failures during `Capturing CUDA graphs` are usually startup headroom problems rather than basic device-selection problems

First explicit 2-GPU command:

```bash
docker run --rm --runtime nvidia --gpus '"device=1,2"' \
  --name vllm-qwen3-32b-awq \
  -p 8001:8000 \
  --ipc=host \
  -v /home/jj/models/Qwen3-32B-AWQ:/models/Qwen3-32B-AWQ \
  vllm/vllm-openai:latest \
  /models/Qwen3-32B-AWQ \
  --tensor-parallel-size 2 \
  --gpu-memory-utilization 0.95 \
  --max-model-len 4096
```

What changed in the logs:

- `Worker_TP0` and `Worker_TP1` appeared
- startup reached model warmup and graph capture
- failure moved from "wrong card" behavior to runtime warmup behavior

That was an important diagnostic improvement:

- before this point, the model was not placed correctly
- after this point, the model was placed correctly but still did not have enough startup headroom

---

## 5. Working Fix

The configuration that came up successfully was:

- pin `Qwen3-32B-AWQ` to GPUs `1,2`
- use `--tensor-parallel-size 2`
- lower startup pressure with:
  - `--gpu-memory-utilization 0.85`
  - `--max-model-len 2048`
- expose the 32B server on host port `8001`

Intermediate attempt that still failed:

```bash
docker run --rm --runtime nvidia --gpus '"device=1,2"' \
  --name vllm-qwen3-32b-awq \
  -p 8001:8000 \
  --ipc=host \
  -v /home/jj/models/Qwen3-32B-AWQ:/models/Qwen3-32B-AWQ \
  vllm/vllm-openai:latest \
  /models/Qwen3-32B-AWQ \
  --tensor-parallel-size 2 \
  --gpu-memory-utilization 0.95 \
  --max-model-len 4096 \
  --enforce-eager
```

Observed result:

- the launch progressed farther
- logs still showed CUDA graph capture activity
- startup eventually failed with explicit `CUDA error: out of memory`

Why the final change worked:

- lowering memory utilization from `0.95` to `0.85` created meaningful VRAM headroom
- lowering context from `4096` to `2048` reduced cache and warmup pressure
- together, those changes allowed startup and graph capture to finish

Working launch:

```bash
docker run --rm --runtime nvidia --gpus '"device=1,2"' \
  --name vllm-qwen3-32b-awq \
  -p 8001:8000 \
  --ipc=host \
  -v /home/jj/models/Qwen3-32B-AWQ:/models/Qwen3-32B-AWQ \
  vllm/vllm-openai:latest \
  /models/Qwen3-32B-AWQ \
  --tensor-parallel-size 2 \
  --gpu-memory-utilization 0.85 \
  --max-model-len 2048 \
  --enforce-eager
```

Successful outcome:

- server reached `Application startup complete`
- route list included `/v1/chat/completions`
- test request to `http://127.0.0.1:8001/v1/chat/completions` returned HTTP `200`

Useful fallback ladder if a future image tag regresses:

1. `--gpu-memory-utilization 0.95 --max-model-len 4096`
2. `--gpu-memory-utilization 0.95 --max-model-len 4096 --enforce-eager`
3. `--gpu-memory-utilization 0.85 --max-model-len 2048 --enforce-eager`
4. if still needed, try `--gpu-memory-utilization 0.80 --max-model-len 1024`

---

## 6. Recommended Companion Placement For 14B

If `32B` uses GPUs `1,2`, keep `14B` on a different GPU such as `0` or `3`.

Example:

```bash
docker run --rm --runtime nvidia --gpus '"device=0"' \
  --name vllm-qwen3-14b-awq \
  -p 8000:8000 \
  --ipc=host \
  -v /home/jj/models/Qwen3-14B-AWQ:/models/Qwen3-14B-AWQ \
  vllm/vllm-openai:latest \
  /models/Qwen3-14B-AWQ \
  --gpu-memory-utilization 0.65 \
  --max-model-len 8192
```

The key operational rule is isolation:

- do not let `14B` share the same GPUs that `32B` needs for tensor parallel startup

Example split used for this troubleshooting pattern:

- `32B` on GPUs `1,2`
- `14B` on GPU `0`
- GPU `3` left free for headroom or later reuse

---

## 7. Step-By-Step Replay

This section is the compact replay order for the August 14, 2026 troubleshooting sequence.

### A. Confirm the currently exposed model IDs

For `14B`:

```bash
curl http://127.0.0.1:8000/v1/models
```

For `32B` after it starts:

```bash
curl http://127.0.0.1:8001/v1/models
```

### B. Check which containers are already running

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
```

### C. Check current GPU pressure before starting `32B`

```bash
nvidia-smi
```

Why this matters:

- if one of the intended `32B` GPUs is already heavily loaded, even the final working command may still fail

### D. Start `14B` on an isolated single GPU

```bash
docker run --rm --runtime nvidia --gpus '"device=0"' \
  --name vllm-qwen3-14b-awq \
  -p 8000:8000 \
  --ipc=host \
  -v /home/jj/models/Qwen3-14B-AWQ:/models/Qwen3-14B-AWQ \
  vllm/vllm-openai:latest \
  /models/Qwen3-14B-AWQ \
  --gpu-memory-utilization 0.65 \
  --max-model-len 8192
```

### E. Start `32B` on two different GPUs

Use the final working command:

```bash
docker run --rm --runtime nvidia --gpus '"device=1,2"' \
  --name vllm-qwen3-32b-awq \
  -p 8001:8000 \
  --ipc=host \
  -v /home/jj/models/Qwen3-32B-AWQ:/models/Qwen3-32B-AWQ \
  vllm/vllm-openai:latest \
  /models/Qwen3-32B-AWQ \
  --tensor-parallel-size 2 \
  --gpu-memory-utilization 0.85 \
  --max-model-len 2048 \
  --enforce-eager
```

### F. Watch for the success signature

Representative good signs:

- `Graph capturing finished`
- `Starting vLLM API server`
- `Application startup complete`

### G. Validate the `32B` endpoint with a direct request

```bash
curl http://127.0.0.1:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "/models/Qwen3-32B-AWQ",
    "messages": [
      {"role": "user", "content": "hello"}
    ]
  }'
```

### H. Validate the `14B` endpoint with a direct request

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "/models/Qwen3-14B-AWQ",
    "messages": [
      {"role": "user", "content": "hello"}
    ]
  }'
```

### I. Re-check live GPU/container state after both launches

```bash
nvidia-smi
docker ps
```

---

## 8. Validation Commands

Check that `32B` is serving:

```bash
curl http://127.0.0.1:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "/models/Qwen3-32B-AWQ",
    "messages": [
      {"role": "user", "content": "hello"}
    ]
  }'
```

Check that `14B` is serving:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "/models/Qwen3-14B-AWQ",
    "messages": [
      {"role": "user", "content": "hello"}
    ]
  }'
```

Check live GPU/container state:

```bash
nvidia-smi
docker ps
```

---

## 9. Cleanup And Relaunch Commands

If a prior failed attempt left a container name occupied or a stopped container behind, clear it before retrying:

```bash
docker ps -a --filter name=vllm-qwen3-32b-awq
docker rm -f vllm-qwen3-32b-awq
```

Likewise for `14B`:

```bash
docker ps -a --filter name=vllm-qwen3-14b-awq
docker rm -f vllm-qwen3-14b-awq
```

If the next attempt should reuse different GPUs, change both:

- Docker device list in `--gpus '"device=...'"'`
- `14B` placement so it does not collide with `32B`

---

## 10. Practical Conclusions

- port changes do not change GPU placement
- `--gpus all` is visibility only, not model parallelism
- multi-GPU `32B` requires explicit tensor parallelism
- once startup reaches CUDA graph capture, later failure is often memory-headroom related
- on this host, `Qwen3-32B-AWQ` succeeded after reducing startup pressure to `0.85` utilization and `2048` context

If a later image tag changes behavior again, re-test with:

1. explicit `device=...` placement
2. explicit `--tensor-parallel-size`
3. lower `--gpu-memory-utilization`
4. lower `--max-model-len`
