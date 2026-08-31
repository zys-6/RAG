# 31 - Offline GPU `vLLM` Pattern

This document captures the recommended deployment pattern for bringing up a new inner-network GPU host when the target machine cannot access the internet.

It is written for the `10.42.*` environment and especially the `10.42.0.125`-style host shape:

- Ubuntu host
- RTX 4090 class GPU
- NVIDIA driver installed on the host
- application/runtime artifacts prepared elsewhere and copied in

This document is a deployment playbook.

It is different from:

- [30-separate-network-rag-gpu-stack-validation.md](./30-separate-network-rag-gpu-stack-validation.md), which records what was validated on July 23, 2026
- [28-remote-gpu-embedding-api-deployment.md](./28-remote-gpu-embedding-api-deployment.md), which records the earlier remote CUDA `embedding_api` deployment pattern
- [21-software-recovery.md](./21-software-recovery.md), which explains generic repo and artifact recovery on a new machine

---

## Core rule

For an offline GPU host, split the system into two layers:

1. **host-specific layer**
   - Ubuntu
   - kernel
   - NVIDIA driver
   - Docker / NVIDIA Container Toolkit if containers are used

2. **portable layer**
   - Python environment
   - `vLLM`
   - application code
   - model files
   - Docker image tarballs

Do not treat the full machine image as the default migration artifact.

Even when two machines both use RTX 4090 GPUs, the host layer still needs to be validated per machine.

---

## Recommended strategy

### Best strategy for multiple same-GPU inner-network machines

Use:

1. an **offline APT source** for Ubuntu and the NVIDIA driver
2. a **containerized app runtime** for `vLLM`
3. **model files** copied separately

Why:

- the driver remains machine-managed and repairable
- the app runtime becomes portable and repeatable
- rollout to a second or third machine stays consistent

### Best strategy for one machine with lower setup overhead

Use:

1. an **offline driver package bundle** or offline APT source
2. a **Python venv plus offline wheelhouse**
3. copied **models** and **app code**

Why:

- this is simpler to get running quickly
- it avoids forcing Docker if the immediate goal is only a single host

---

## What "install the driver on the target" actually means

It does **not** mean the target machine downloads packages from the internet.

It means:

1. prepare the driver packages on an internet-connected Ubuntu machine
2. transfer them into the inner network
3. run the install while logged into the target host

This matters because the NVIDIA driver is tied to:

- the target kernel
- DKMS/module build state
- Secure Boot state if enabled
- the target machine's actual runtime environment

So the driver should be installed on the target host itself, even if all packages are brought in offline.

---

## Recommended offline driver pattern

### Preferred pattern: local offline APT source

This is the best operational choice if more than one target machine will exist.

Workflow:

1. On an internet-connected Ubuntu machine, choose the exact NVIDIA driver version for the target OS.
2. Download the `.deb` packages and their dependencies.
3. Build a local package folder or small APT repository.
4. Copy that repository into the inner network.
5. Point each target machine at that offline source.
6. Install the driver through normal package management on the target.

Why this is preferred:

- dependencies stay manageable
- reinstall and rollback are cleaner
- additional same-OS machines can reuse the same source

### Acceptable fallback: raw `.deb` bundle

This is acceptable for one machine if you already know the full dependency set.

Workflow:

1. Download the required `.deb` packages on a connected machine.
2. Copy them to the target.
3. Install locally on the target.

This is less robust than a proper offline APT source because dependency closure is easier to get wrong.

### Not preferred: `.run` installer

The NVIDIA `.run` installer can work offline, but it is not the default recommendation here.

Reasons:

- weaker package-manager integration
- more fragile upgrades
- more friction with kernel updates
- harder long-term maintenance

---

## Recommended app-runtime pattern

### Preferred for repeatable rollout: Docker image plus models

Use:

- `docker save` / `docker load` for the runtime image
- separate bind mounts or copied directories for `models/`
- separate config files for environment-specific URLs and secrets

This is the closest match to the already-validated `embedding_api` GPU-host pattern in this repo.

### Acceptable for a single host: `venv` plus wheelhouse

Use:

- Python `venv`
- offline wheel directory
- copied app code
- copied models

This is easier to inspect manually, but less standardized than a container image.

---

## Migration recommendation for this repo

For the `10.42.*` environment, the recommended split is:

1. **Host**
   - install Ubuntu on the target machine
   - install the NVIDIA driver on the target from offline packages
   - install Docker and NVIDIA Container Toolkit if using the container path

2. **Runtime**
   - move prebuilt image tarballs or offline Python wheels into the inner network
   - copy `src/`, `models/`, and deployment config
   - keep model files outside the image when practical

3. **Validation**
   - validate `nvidia-smi`
   - validate GPU visibility from the container or Python runtime
   - validate local API endpoints before pointing other services at them

---

## Example host validation sequence

On the target machine:

```bash
lsb_release -a
uname -r
lspci | grep -i nvidia
nvidia-smi
```

If using Python `venv`:

```bash
python3 --version
python3 -m venv ~/vllm-venv
source ~/vllm-venv/bin/activate
python -m pip install --upgrade pip
```

If using Docker:

```bash
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

The final service should only be started after these checks pass.

---

## `vLLM` note

For normal `vLLM` usage, `nvcc` is not the deciding requirement.

The critical requirements are usually:

- a working NVIDIA driver
- CUDA-compatible PyTorch wheels
- a matching Python environment
- local model availability if the target cannot download at runtime

Missing `nvcc` does not block a prebuilt-wheel `vLLM` deployment by itself.

---

## What to copy, and what not to copy

### Copy

- Docker image tarballs
- offline Python wheels
- `src/`
- `models/`
- deployment config files
- documented startup commands

### Do not rely on copying alone

- the running kernel state
- the installed NVIDIA driver state
- bootloader assumptions
- machine-specific network naming
- host-specific Docker/NVIDIA runtime registration

---

## Why full-system cloning is not the default

A raw disk or full-system clone sounds convenient, but it is not the default recommendation unless the two machines are nearly identical beyond just the GPU.

Common failure points:

- boot mismatch
- kernel/module mismatch
- NIC renaming
- UUID or storage-path differences
- stale machine-specific configuration

The safer pattern is:

1. rebuild the host layer cleanly
2. restore the portable runtime layer
3. validate locally

---

## Practical recommendation summary

If you are preparing **multiple** same-class offline GPU hosts:

- prefer **offline APT repo + Docker image + separate models**

If you are preparing **one** host quickly:

- prefer **offline driver packages + Python venv/wheels + separate models**

In both cases:

- install the NVIDIA driver on the target host itself
- move the rest as portable artifacts
