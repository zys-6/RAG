# 32 - Offline GPU Migration Runbook

This checklist turns the July 28, 2026 working state into a single migration document for a new inner-network GPU host.

It assumes the source machine already proved these artifacts:

- NVIDIA driver `580.173.02`
- working `vllm/vllm-openai:latest` (later seen as `vllm 0.26.0` on `192.168.1.100`; tag is not pinned)
- working CUDA embedding image `embedding_api:cuda12.1`
- exported Docker image tarballs under `~/offline-gpu-notes/`
- exported offline package bundles under `~/offline-pkgs/`
- or a target-matching local offline APT repository tarball such as `~/offline-repo-noble-gpu-min.tar`
- local models under `~/models/`

Use this as the practical flow:

1. copy
2. checksum
3. restore on target
4. validate on target

---

## 1. Copy List

Copy these from the source GPU host.

### How to use each copied artifact

Use this mapping when restoring on the target:

| Artifact type | Examples | How it is used on the target |
| --- | --- | --- |
| Docker image tarballs | `embedding_api_cuda12.1.tar`, `milvus.tar`, `vllm-openai-latest-working.tar` | Load with `docker load -i ...`, then use the resulting local images for container startup and validation |
| Runtime notes | `host-baseline.txt`, `runtime-summary.txt`, `final-migration-inventory.txt`, `qwen3-14b-awq-download.txt` | Reference only; not installed |
| Launch scripts | `run-vllm-qwen3-14b-awq.sh`, `run-vllm-qwen3-32b-awq.sh` | Execute directly to start validated vLLM containers |
| Model directories | `~/models/Qwen3-14B-AWQ/`, `~/models/Qwen3-32B-AWQ/` | Copy as directories, then mount into containers with `-v ...:/models/...`; not installed as packages |
| Optional cache artifact | `uv-cache.tar.gz` | Optional inspection or reuse only; not part of the core host install path |
| Repo tarballs | `offline-repo-noble-gpu-min.tar`, `offline-repo-noble-gpu-repair.tar` | Extract under `/opt`, register as a local APT source, then install with `apt` |
| Raw offline package bundles | `~/offline-pkgs/docker/`, `~/offline-pkgs/nvidia-driver-580/`, `~/offline-pkgs/nvidia-container-toolkit/`, `~/offline-pkgs/host-support-expanded/` | Fallback/manual path using `dpkg -i`; prefer the local APT repo tarball when available |
| Ops tool bundle | `~/offline-pkgs/ops-tools/` | Optional convenience tools; install after the core host path succeeds |
| Checksum manifests | `~/offline-pkgs/checksums/`, `*.sha256` | Verification only with `sha256sum -c`; not installed |

### A. Docker image tarballs

- `~/offline-gpu-notes/embedding_api_cuda12.1.tar`
- `~/offline-gpu-notes/milvus.tar`
- `~/offline-gpu-notes/vllm-openai-latest-working.tar`

### B. Runtime notes and launch scripts

- `~/offline-gpu-notes/host-baseline.txt`
- `~/offline-gpu-notes/runtime-summary.txt`
- `~/offline-gpu-notes/final-migration-inventory.txt`
- `~/offline-gpu-notes/qwen3-32b-awq-download.txt` if present
- `~/offline-gpu-notes/qwen3-14b-awq-download.txt`
- `~/offline-gpu-notes/scripts/run-vllm-qwen3-32b-awq.sh`
- `~/offline-gpu-notes/scripts/run-vllm-qwen3-14b-awq.sh`

### C. Model directories

- `~/models/Qwen3-32B-AWQ/`
- `~/models/Qwen3-14B-AWQ/`

### D. Optional cache artifact

- `~/offline-gpu-notes/uv-cache.tar.gz`

This is useful for inspection and possible reuse, but it is not the core migration artifact if the container path is used.

### E. Offline package bundles

Copy these directories from the source GPU host:

- `~/offline-pkgs/docker/`
- `~/offline-pkgs/nvidia-driver-580/`
- `~/offline-pkgs/nvidia-container-toolkit/`
- `~/offline-pkgs/ops-tools/`
- `~/offline-pkgs/host-support/`
- `~/offline-pkgs/host-support-expanded/`
- `~/offline-pkgs/checksums/`

Preferred alternative for new hosts:

- `~/offline-repo-noble-gpu-min.tar`
- `~/offline-repo-noble-gpu-min.tar.sha256`

If first-time SSH access is also needed on the target, refresh that repo tar after adding:

- `openssh-server`
- `openssh-client`
- `openssh-sftp-server`

These are small compared with the model and image artifacts, but they are what make a totally offline host install practical.

As of August 10, 2026, keep both repo histories:

- Path A: `offline-repo-noble-gpu-min.tar` for clean VM validation on Ubuntu 24.04 Noble
- Path B: `offline-repo-noble-gpu-repair.tar` for real-host recovery when the target already has a broken package graph

---

## 2. Checksum Commands

Run these on the source machine before transfer.

Create a checksum folder:

```bash
mkdir -p ~/offline-gpu-notes/checksums
```

### A. Docker tarballs

```bash
sha256sum ~/offline-gpu-notes/embedding_api_cuda12.1.tar > ~/offline-gpu-notes/checksums/embedding_api_cuda12.1.tar.sha256
sha256sum ~/offline-gpu-notes/milvus.tar > ~/offline-gpu-notes/checksums/milvus.tar.sha256
sha256sum ~/offline-gpu-notes/vllm-openai-latest-working.tar > ~/offline-gpu-notes/checksums/vllm-openai-latest-working.tar.sha256
```

### B. Optional cache tarball

```bash
sha256sum ~/offline-gpu-notes/uv-cache.tar.gz > ~/offline-gpu-notes/checksums/uv-cache.tar.gz.sha256
```

### C. Model directory manifests

```bash
find ~/models/Qwen3-32B-AWQ -type f -print0 | sort -z | xargs -0 sha256sum > ~/offline-gpu-notes/checksums/Qwen3-32B-AWQ.files.sha256
find ~/models/Qwen3-14B-AWQ -type f -print0 | sort -z | xargs -0 sha256sum > ~/offline-gpu-notes/checksums/Qwen3-14B-AWQ.files.sha256
```

### D. Script checksums

```bash
sha256sum ~/offline-gpu-notes/scripts/run-vllm-qwen3-32b-awq.sh > ~/offline-gpu-notes/checksums/run-vllm-qwen3-32b-awq.sh.sha256
sha256sum ~/offline-gpu-notes/scripts/run-vllm-qwen3-14b-awq.sh > ~/offline-gpu-notes/checksums/run-vllm-qwen3-14b-awq.sh.sha256
```

### E. Offline package bundle manifests

These were created during the July 28, 2026 preparation session:

- `~/offline-pkgs/checksums/docker.files.sha256`
- `~/offline-pkgs/checksums/nvidia-driver-580.files.sha256`
- `~/offline-pkgs/checksums/nvidia-container-toolkit.files.sha256`
- `~/offline-pkgs/checksums/ops-tools.files.sha256`
- `~/offline-pkgs/checksums/host-support.files.sha256`
- `~/offline-pkgs/checksums/host-support-expanded.files.sha256`

If using the local offline APT repository tarball instead of raw bundle directories:

```bash
sha256sum ~/offline-repo-noble-gpu-min.tar > ~/offline-repo-noble-gpu-min.tar.sha256
```

After transfer, rerun the same `sha256sum -c` checks on the target.

Examples:

```bash
sha256sum -c ~/offline-gpu-notes/checksums/embedding_api_cuda12.1.tar.sha256
sha256sum -c ~/offline-gpu-notes/checksums/milvus.tar.sha256
sha256sum -c ~/offline-gpu-notes/checksums/vllm-openai-latest-working.tar.sha256
```

---

## 3. Target Restore Commands

These commands are for the target host after the artifacts have been copied in.

### A. Host validation first

```bash
lsb_release -a
uname -r
nvidia-smi
docker --version
docker compose version
```

At this stage, do **not** assume any public CUDA test image exists on the target yet.

Only confirm the host-side tools first:

```bash
command -v docker
command -v nvidia-smi
```

### B. Prepare target directories

```bash
mkdir -p ~/offline-pkgs
mkdir -p ~/offline-gpu-notes/scripts
mkdir -p ~/models
```

### C. Verify transferred checksums

First verify the offline package bundles:

```bash
sha256sum -c ~/offline-pkgs/checksums/docker.files.sha256
sha256sum -c ~/offline-pkgs/checksums/nvidia-driver-580.files.sha256
sha256sum -c ~/offline-pkgs/checksums/nvidia-container-toolkit.files.sha256
sha256sum -c ~/offline-pkgs/checksums/ops-tools.files.sha256
sha256sum -c ~/offline-pkgs/checksums/host-support.files.sha256
sha256sum -c ~/offline-pkgs/checksums/host-support-expanded.files.sha256
```

If using the preferred local offline APT repository tarball, verify it before extraction:

```bash
sha256sum -c ~/offline-repo-noble-gpu-min.tar.sha256
```

Then verify the runtime artifacts:

```bash
sha256sum -c ~/offline-gpu-notes/checksums/embedding_api_cuda12.1.tar.sha256
sha256sum -c ~/offline-gpu-notes/checksums/milvus.tar.sha256
sha256sum -c ~/offline-gpu-notes/checksums/vllm-openai-latest-working.tar.sha256
sha256sum -c ~/offline-gpu-notes/checksums/run-vllm-qwen3-32b-awq.sh.sha256
sha256sum -c ~/offline-gpu-notes/checksums/run-vllm-qwen3-14b-awq.sh.sha256
sha256sum -c ~/offline-gpu-notes/checksums/Qwen3-32B-AWQ.files.sha256
sha256sum -c ~/offline-gpu-notes/checksums/Qwen3-14B-AWQ.files.sha256
```

### D. Install package bundles on the target

Recommended order:

1. local offline APT repository or `host-support-expanded`
2. `nvidia-driver-580`
3. reboot
4. `docker`
5. `nvidia-container-toolkit`
6. `ops-tools`

Preferred path: extract and use a target-local offline APT repository.

There are two distinct repo workflows:

- Path A: clean VM validation with `offline-repo-noble-gpu-min.tar`
- Path B: broken real host recovery with `offline-repo-noble-gpu-repair.tar`

This is the recommended fix if raw `dpkg -i ./*.deb` leaves packages in `iU` state or reports missing dependencies such as `libnftables1`, `perl-base`, `libjq1`, `libcurl4t64`, `libevent-core-2.1-7t64`, or `libutempter0`.

Path A was already validated on a clean offline Ubuntu 24.04.4 VM. Use it when the target has no pre-existing APT breakage and only needs the base offline repo for SSH, Docker, and the NVIDIA stack.

Path B is the safer server-room path for the real machine because it adds the package set needed to repair the August 2026 dependency conflicts before installing SSH.

Example target-host extraction for Path A:

```bash
cd ~
sha256sum -c offline-repo-noble-gpu-min.tar.sha256
sudo rm -rf /opt/offline-repo-noble-gpu-min
sudo tar -C /opt -xf offline-repo-noble-gpu-min.tar
echo "deb [trusted=yes] file:/opt/offline-repo-noble-gpu-min ./" | sudo tee /etc/apt/sources.list.d/offline-gpu-local.list
sudo apt-get update
```

Important:

- build the repo on the same Ubuntu release family as the target; for example, `noble` for Ubuntu 24.04.x targets
- do not test these target commands on the source machine by mistake
- prefer a neutral path like `/opt/offline-repo-noble-gpu-min` instead of a home-directory desktop path, because `_apt` may not be able to traverse user-home directories cleanly

For the real host recovery path, use the repaired tar and the server-room checklist in Section G instead of the `noble-gpu-min` commands above.

Then install the driver prerequisites and driver through `apt` from the local repo:

```bash
sudo apt-get install -y "linux-headers-$(uname -r)" dkms build-essential nvidia-driver-580
sudo reboot
```

After reboot:

```bash
nvidia-smi
```

Then install Docker from the same local repo:

```bash
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now containerd docker
sudo systemctl status containerd --no-pager
sudo systemctl status docker --no-pager
docker --version
docker compose version
```

Then install NVIDIA Container Toolkit:

```bash
sudo apt-get install -y nvidia-container-toolkit nvidia-container-toolkit-base libnvidia-container-tools libnvidia-container1
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
sudo systemctl status docker --no-pager
nvidia-ctk --version
```

Then confirm host-side GPU state again:

```bash
nvidia-smi
lsmod | grep nvidia
```

At this point, the real host has reached the validated August 11, 2026 state:

- SSH installed and reachable
- NVIDIA driver `580.173.02` active
- `nvidia-smi` shows all target GPUs
- Docker Engine active
- NVIDIA Container Toolkit configured for Docker

Container-side GPU validation is a separate last-mile step. Do that only with a local image already present on the host:

```bash
docker info | sed -n '/Runtimes/,+5p'
docker images
```

If a suitable local image already exists, then run:

```bash
docker run --rm --gpus all --entrypoint nvidia-smi <LOCAL_IMAGE_NAME>
```

Do not rely on pulling `nvidia/cuda:...` from the internet on the inner-network target.

If you also included SSH packages in the local repo tar, install and enable them after the base host is stable:

```bash
sudo apt-get install -y openssh-server openssh-client openssh-sftp-server
sudo systemctl enable ssh
sudo systemctl start ssh
sudo systemctl status ssh --no-pager
```

This is the preferred way to add SSH on an offline target because `apt` can resolve the same local dependency set instead of relying on manual `.deb` copying.

If the target is fully offline and still has normal Ubuntu internet sources enabled, disable them before retrying package repair so `apt` does not waste time on DNS failures:

```bash
sudo mv /etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources.disabled
sudo apt-get update
```

If the target was already left in a broken package state from an earlier raw `dpkg` attempt, repair that state from the local repo before testing SSH or other add-on packages:

```bash
sudo apt --fix-broken install
```

Fallback path for older artifact-only bundles: install the dependency-expanded support bundle first:

```bash
cd ~/offline-pkgs/host-support-expanded
sudo dpkg -i ./*.deb
```

If `dpkg` still reports missing dependencies here, stop. Do not keep patching individual `.deb` files by hand. Build or reuse a real local/offline APT source for the target release instead.

Then install the NVIDIA driver bundle:

```bash
cd ~/offline-pkgs/nvidia-driver-580
sudo dpkg -i ./*.deb
sudo reboot
```

After reboot, validate the driver:

```bash
nvidia-smi
```

Then install Docker:

```bash
cd ~/offline-pkgs/docker
sudo dpkg -i ./*.deb
docker --version
docker compose version
```

Then install NVIDIA Container Toolkit:

```bash
cd ~/offline-pkgs/nvidia-container-toolkit
sudo dpkg -i ./*.deb
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Validate container GPU passthrough:

```bash
docker info | grep -i runtime
```

At this point, avoid using `docker run ... nvidia/cuda:...` unless that CUDA test image was also copied into the offline environment.

Then install helpful operations tools:

```bash
cd ~/offline-pkgs/ops-tools
sudo dpkg -i ./*.deb
```

`ops-tools` is optional. It is not part of the core success path for SSH, NVIDIA, Docker, or NVIDIA Container Toolkit.

As above, if `dpkg` still reports missing dependencies, do not fall back to a normal internet-backed install. Fix the offline package set or use a local/offline APT source.

### E. Known failure pattern from August 2026

The raw `host-support-expanded` bundle can look complete by checksum and still fail on the target with packages stuck in `iU` state after `sudo dpkg --configure -a`.

Observed symptoms included dependency failures around:

- `libnftables1`
- `perl-base`
- `perl-modules-5.38`
- `libperl5.38*`
- `libjq1`
- `libcurl4t64`
- `libevent-core-2.1-7t64`
- `libutempter0`
- `policykit-1-gnome`

What this means:

- the copied `.deb` files were not enough for that target
- the fix is to use a target-matching local offline APT repo, not to chase missing libraries one by one
- absolute paths inside checksum manifests may also need rewriting if the source and target usernames differ, for example `/home/jj/` versus `/home/user1/`
- if SSH is needed later, add it to the same local offline APT repo tar instead of creating a separate raw package bundle
- a refreshed repo tar may still need to add recovery-only packages exposed by `apt --fix-broken install`, even if the base driver, Docker, and SSH seeds were already present

### F. Verified offline rehearsal on August 6, 2026

The preferred local APT repository path was verified in an Ubuntu `24.04.4` virtual machine with:

- no active NIC or default route
- normal `ubuntu.sources` disabled before the package test
- only `file:/opt/offline-repo-noble-gpu-min` enabled for `apt`

Observed baseline inside the VM before enabling the local repo:

- `lsb_release -a` reported `Ubuntu 24.04.4 LTS`
- `uname -r` reported `6.17.0-14-generic`
- `ip route` was empty
- `apt-cache policy` showed only `/var/lib/dpkg/status` after `ubuntu.sources` was disabled

The following was then validated successfully:

```bash
sudo tar -C /opt -xf offline-repo-noble-gpu-min.tar
printf '%s\n' 'deb [trusted=yes] file:/opt/offline-repo-noble-gpu-min ./' | sudo tee /etc/apt/sources.list.d/offline-gpu-local.list
sudo apt-get update
sudo apt-get install -y openssh-server openssh-client openssh-sftp-server
```

The VM confirmed that:

- `apt-get update` could read the local repo without contacting `archive.ubuntu.com` or `security.ubuntu.com`
- `openssh-server`
- `openssh-client`
- `openssh-sftp-server`

were all installable from:

- `file:/opt/offline-repo-noble-gpu-min ./ Packages`

Important checksum caveat from the rehearsal:

- the copied `offline-repo-noble-gpu-min.tar.sha256` file still referenced `/home/jj/offline-repo-noble-gpu-min.tar`
- on another machine, `sha256sum -c` will fail if that absolute path does not exist
- this does not mean the tar is bad; compare the hash value itself or regenerate a local check file on the target or VM

### G. Server-Room Execution Checklist

Use this section as the practical to-do list when physically at the target host.

This section is Path B: broken real host recovery.

Use the repaired repo tar for the real host:

- `offline-repo-noble-gpu-repair.tar`
- `offline-repo-noble-gpu-repair.tar.sha256`

The older `offline-repo-noble-gpu-min.tar` remains useful as a clean-VM validation artifact, but the August 10, 2026 server-room path should use the repaired tar because it contains the extra packages needed to repair an already-broken APT state before installing SSH.

Summary:

- Path A: clean VM validation using `offline-repo-noble-gpu-min.tar`
- Path B: broken real host recovery using `offline-repo-noble-gpu-repair.tar`

Working rule:

- run one block at a time
- compare the screen output against the expected result below
- if the result does not match, stop there and send the live picture/output before moving on

#### Step 1. Confirm host baseline

```bash
lsb_release -a
uname -r
apt-cache policy | sed -n '1,80p'
apt-mark showhold
```

Expected:

- Ubuntu `24.04.x` / `noble`
- kernel matches the target plan, for example `6.17.0-14-generic`
- if the machine is meant to be offline, `apt-cache policy` should not depend on public mirrors for the recovery path
- `apt-mark showhold` should ideally print nothing

If not:

- do not continue to package install yet
- record the exact package-source state first

#### Step 2. Verify the local repo tar

The repaired tar checksum is expected to reference the local filename directly. Verify it with:

```bash
sha256sum -c offline-repo-noble-gpu-repair.tar.sha256
```

Expected:

- `offline-repo-noble-gpu-repair.tar: OK`

If not:

- stop
- the copied tar may be damaged or incomplete

#### Step 3. Extract and enable the local repo

```bash
sudo mkdir -p /opt
sudo rm -rf /opt/offline-repo-noble-gpu-repair
sudo tar -C /opt -xf offline-repo-noble-gpu-repair.tar
printf '%s\n' 'deb [trusted=yes] file:/opt/offline-repo-noble-gpu-repair ./' | sudo tee /etc/apt/sources.list.d/offline-gpu-local.list
```

Expected:

- `/opt/offline-repo-noble-gpu-repair` exists after extraction
- the `tee` output echoes exactly:
  `deb [trusted=yes] file:/opt/offline-repo-noble-gpu-repair ./`

#### Step 4. Disable normal Ubuntu mirror sources if present

```bash
ls /etc/apt/sources.list.d/
```

If `ubuntu.sources` exists:

```bash
sudo mv /etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources.disabled
```

If it does not exist, that is fine. Do not force this step.

Then:

```bash
sudo apt-get update
apt-cache policy | sed -n '1,80p'
```

Expected:

- `apt-get update` reads from `file:/opt/offline-repo-noble-gpu-repair`
- no dependency on `archive.ubuntu.com` or `security.ubuntu.com` for the offline recovery path

If not:

- stop
- the repo path or source-list state is still wrong

#### Step 5. Try the clean SSH install path first

```bash
sudo apt-get install -y openssh-server openssh-client openssh-sftp-server
```

Expected on a healthy target:

- install completes
- later `ssh.service` or `ssh.socket` exists

If this succeeds, continue with:

```bash
sudo systemctl status ssh --no-pager
sudo systemctl enable ssh || true
sudo systemctl start ssh || sudo systemctl start ssh.socket
```

Then confirm:

```bash
dpkg -l | grep openssh
apt-cache policy openssh-server openssh-client openssh-sftp-server
```

Expected:

- installed versions come from `file:/opt/offline-repo-noble-gpu-repair ./ Packages`

#### Step 6. If SSH install fails, classify it as a broken-package-state issue

The August 2026 real-host failure pattern was:

- local repo enabled correctly
- `apt-get update` succeeded
- `openssh-server` still failed because unrelated packages were already broken

Typical blockers already observed on the real host:

- `curl`
- `jq`
- `libc6-dbg`
- `libncurses6`
- `libncursesw6`
- `nftables`
- `perl`
- `tmux`

Collect the exact state:

```bash
apt-mark showhold
apt-cache policy curl jq libc6 libc6-dbg libtinfo6 libnftables1 perl perl-base perl-modules-5.38 libperl5.38t64 libevent-core-2.1-7t64 libutempter0 openssh-server openssh-client openssh-sftp-server
```

If `apt-mark showhold` prints package names, unhold them first:

```bash
sudo apt-mark unhold <package-name>
```

Do not guess package names. Only unhold what the machine actually reports.

#### Step 7. Repair the existing broken package graph from the local repo

If the host is already in the broken state shown in the August 2026 screenshots, repair the named packages from the local repo side first:

```bash
sudo apt-get install -y \
  libcurl4t64=8.5.0-2ubuntu10.11 \
  libjq1=1.7.1-3ubuntu0.24.04.2 \
  libnftables1=1.0.9-1ubuntu0.1 \
  perl-base=5.38.2-3.2ubuntu0.3 \
  perl-modules-5.38=5.38.2-3.2ubuntu0.3 \
  libperl5.38t64=5.38.2-3.2ubuntu0.3 \
  libevent-core-2.1-7t64=2.1.12-stable-9ubuntu2 \
  libutempter0=1.2.1-3build1 \
  libncurses6=6.4+20240113-1ubuntu2.1 \
  libncursesw6=6.4+20240113-1ubuntu2.1 \
  nftables=1.0.9-1ubuntu0.1 \
  jq=1.7.1-3ubuntu0.24.04.2 \
  curl=8.5.0-2ubuntu10.11 \
  tmux=3.4-1ubuntu0.1 \
  dpkg-dev=1.22.6ubuntu6.6 \
  libdpkg-perl=1.22.6ubuntu6.6
sudo apt --fix-broken install
```

If `apt` prompts `Do you want to continue? [Y/n]`, answer `Y`.

After the repair finishes, normalize and verify the package database:

```bash
sudo dpkg --configure -a
sudo dpkg --audit
```

Expected:

- `sudo dpkg --configure -a` returns without new errors
- `sudo dpkg --audit` prints nothing

That empty `dpkg --audit` result is the success signal that the broken APT/dpkg state is repaired.

If `libc6-dbg` is the blocker and it is not needed on the target, remove it:

```bash
sudo apt-get remove -y libc6-dbg
```

Then simulate the SSH install before doing it for real:

```bash
sudo apt-get -s install openssh-server openssh-client openssh-sftp-server
```

Expected:

- no unresolved dependency error
- `openssh-client` may show an upgrade
- `openssh-server` and `openssh-sftp-server` should appear in the install plan

Then do the real SSH install and service checks:

```bash
sudo apt-get install -y openssh-server openssh-client openssh-sftp-server
sudo systemctl enable --now ssh
systemctl status ssh --no-pager
ss -lntp | grep ':22'
ip -br addr
```

Expected:

- the SSH packages finish installing
- `systemctl status ssh` shows `Active: active (running)`
- `ss -lntp | grep ':22'` shows a listener on port `22`
- `ip -br addr` shows the server IP you will test from another inner-network machine

If not:

- stop there
- send the exact screen output before trying `dpkg -i` bundles again

#### Step 8. Only after package repair succeeds, continue with the rest of the host stack

Use the validated order:

1. `nvidia-driver-580`
2. reboot
3. `docker-ce` / `containerd.io` / compose plugins
4. `nvidia-container-toolkit`
5. `docker load` image tar files
6. model restore
7. final runtime validation

Do not mix raw `dpkg -i` recovery attempts into the middle of the APT-repo recovery path unless a specific package is being repaired on purpose.

### H. Load Docker images

```bash
docker load -i ~/offline-gpu-notes/embedding_api_cuda12.1.tar
docker load -i ~/offline-gpu-notes/milvus.tar
docker load -i ~/offline-gpu-notes/vllm-openai-latest-working.tar
```

Confirm:

```bash
docker images | grep -E 'embedding_api|milvus|vllm'
```

Now that local images exist on the target, you can validate container GPU execution with one of the images you actually copied in.

### I. Restore model directories

If the model directories were copied directly, place them here:

- `~/models/Qwen3-32B-AWQ`
- `~/models/Qwen3-14B-AWQ`

Confirm:

```bash
du -sh ~/models/Qwen3-32B-AWQ
du -sh ~/models/Qwen3-14B-AWQ
find ~/models/Qwen3-32B-AWQ -maxdepth 1 -type f | sort
find ~/models/Qwen3-14B-AWQ -maxdepth 1 -type f | sort
```

### J. Restore and authorize scripts

```bash
chmod +x ~/offline-gpu-notes/scripts/run-vllm-qwen3-32b-awq.sh
chmod +x ~/offline-gpu-notes/scripts/run-vllm-qwen3-14b-awq.sh
```

Recommended working contents for the original single-model validation path:

`run-vllm-qwen3-14b-awq.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

docker run --rm --runtime nvidia --gpus all \
  --name vllm-qwen3-14b-awq \
  -p 8000:8000 \
  --ipc=host \
  -v /home/jj/models/Qwen3-14B-AWQ:/models/Qwen3-14B-AWQ \
  vllm/vllm-openai:latest \
  /models/Qwen3-14B-AWQ \
  --gpu-memory-utilization 0.65 \
  --max-model-len 8192
```

`run-vllm-qwen3-32b-awq.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

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

If the target username is not `jj`, change the host-side mount path in the scripts.

If the target host must run `Qwen3-14B-AWQ` and `Qwen3-32B-AWQ` at the same time on different GPUs, do not reuse these `--gpus all` examples as-is. See [37-qwen3-awq-multi-gpu-concurrency-notes.md](./37-qwen3-awq-multi-gpu-concurrency-notes.md) for explicit per-GPU placement and the working 2-GPU tensor-parallel `32B` launch shape.

### H. Target caveats to check before declaring success

These are the main remaining risk areas after the July 28, 2026 preparation work:

- target kernel does not match the prepared header assumptions
- Secure Boot prevents the NVIDIA module from loading
- target username/path differs from `/home/jj/...` in the scripts
- target uses Ubuntu 24.04 but has a different post-install kernel track

Useful target-side checks:

```bash
uname -r
mokutil --sb-state
dpkg -l | grep linux-image
dpkg -l | grep linux-headers
```

---

## 4. Final Validation Commands

### A. Validate `embedding_api` image presence

```bash
docker images | grep 'embedding_api'
```

### B. Validate `milvus` image presence

```bash
docker images | grep 'milvus'
```

### C. Validate `vllm` image presence

```bash
docker images | grep 'vllm'
```

### D. Start and validate `Qwen3-14B-AWQ`

Start:

```bash
~/offline-gpu-notes/scripts/run-vllm-qwen3-14b-awq.sh
```

In another terminal:

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

Success criteria:

- container reaches `Application startup complete`
- route list includes `/v1/chat/completions`
- curl returns HTTP `200`

### E. Start and validate `Qwen3-32B-AWQ`

Start:

```bash
~/offline-gpu-notes/scripts/run-vllm-qwen3-32b-awq.sh
```

In another terminal:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "/models/Qwen3-32B-AWQ",
    "messages": [
      {"role": "user", "content": "hello"}
    ]
  }'
```

Success criteria:

- container reaches `Application startup complete`
- curl returns HTTP `200`
- model is treated as low-context mode on 1x4090

### F. Validate GPU state while model is running

```bash
nvidia-smi
docker ps
```

### G. If `embedding_api` will also run on the target

Check Docker image load only:

```bash
docker images | grep 'embedding_api:cuda12.1'
```

If you also restore the runtime command for that service, validate:

```bash
docker ps
curl http://127.0.0.1:15006/docs
```

Adjust the port if the target uses a different host mapping.

---

## 5. Operational Meaning After Migration

On a single RTX 4090:

- `Qwen3-14B-AWQ` is the practical default
- `Qwen3-32B-AWQ` is a constrained mode
- `Qwen3-32B-AWQ` should not be treated as the roomy default when another heavy CUDA workload also shares the GPU
- `Qwen3-14B-AWQ` is the better first validation model on a new target host

On a future 4x4090 host:

- keep the same image and model artifacts when practical
- separate GPU assignment by workload
- give `vLLM` more context and more parallelism there if needed

---

## 6. Minimum "Done" Definition

Migration is only considered done when all of these are true on the target machine:

1. `nvidia-smi` works
2. Docker Engine is `active (running)`
3. NVIDIA Container Toolkit is installed and `nvidia-ctk --version` works
4. if a local GPU-capable image is available, `docker run --rm --gpus all --entrypoint nvidia-smi <LOCAL_IMAGE_NAME>` works
5. all three Docker tarballs load successfully
6. both model directories are present and readable
7. `Qwen3-14B-AWQ` returns a successful chat completion
8. `Qwen3-32B-AWQ` returns a successful chat completion with the constrained script

Until then, artifact copying is complete, but migration is not yet fully validated.

---

## 7. Next Step

`docs/32` stops at host-level offline migration and container runtime readiness.

After the following are confirmed on the target host:

- SSH works
- `nvidia-smi` works
- Docker is active
- NVIDIA Container Toolkit is configured

continue with [docs/33-10.42.0.125-vllm-compose-qa-validation.md](docs/33-10.42.0.125-vllm-compose-qa-validation.md) for application-layer bring-up and validation.

Use `docs/33` for the next to-do items involving:

- `embedding_api`
- `document_fragment_api`
- `qa_api`
- compose/service startup checks
- model routing checks
- API-level validation
