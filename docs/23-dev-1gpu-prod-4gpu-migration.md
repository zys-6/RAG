# 23 - Windows 1-GPU Development, CentOS 4-GPU Deployment

**Related:** [25-deploy-code-updates.md](./25-deploy-code-updates.md) (step-by-step: push code to prod containers).

This note summarizes the practical deployment rule for this project:

- develop and debug application code on Windows with one RTX 4090
- deploy the same code to the CentOS Linux product environment with four RTX 4090 GPUs
- keep the application GPU-agnostic and move GPU-specific logic into the model server layer

The goal is portability. The app should not care whether the model backend runs on one GPU or four.

---

## Core rule

The RAG application can be developed locally on one GPU if:

- the code does not depend on Windows-only paths
- the runtime config is externalized
- the model is reached through an API contract, not through direct device assumptions
- persistent data is stored outside the container image

If those conditions hold, the same code can be deployed to the product environment with only configuration changes.

---

## What one GPU is enough for

A Windows dev machine with one RTX 4090 is enough to validate:

- API request and response behavior
- document parsing and fragmentation
- Milvus insert, search, query, and delete flows
- prompt routing and agent selection
- config loading
- error handling for missing files, bad URLs, and timeouts
- single-GPU model serving behavior

This is enough to confirm the app logic is correct.

---

## What must be validated on the 4-GPU product host

The product host still needs a dedicated validation pass for:

- tensor parallel inference across four GPUs
- model sharding and memory distribution
- inter-GPU communication behavior
- throughput and latency under production load
- long-context performance
- driver, CUDA, and container-toolkit compatibility
- contention between LLM, embedding, and reranker workloads

These are not fully proven by a one-GPU Windows test.

---

## Deployment pattern

Recommended pattern:

1. Keep the app code GPU-neutral.
2. Expose the LLM through an OpenAI-compatible API.
3. In development, point that API to a local or test model server.
4. In production, point the same API contract to the 4-GPU model server.
5. Change only configuration, not application logic, between environments.

This reduces migration risk and keeps dev/prod behavior aligned.

---

## What usually changes between dev and prod

Expect these values to differ:

- model API base URL
- API keys or tokens
- Milvus address
- OCR / Jira / FTP / internal service URLs
- persistent volume paths
- GPU runtime settings
- database and vector store locations

If any of these are hardcoded, the deployment is not portable yet.

---

## Notes on RTX 4090

RTX 4090 does not provide NVLink. Multi-GPU serving will use PCIe communication instead.

That means:

- app correctness can still be portable
- multi-GPU performance must be tested on the product host
- the final serving stack should be chosen with PCIe topology in mind

---

## Practical validation split

Validate on Windows now:

- app code changes
- config loading
- document pipeline
- embedding and retrieval logic
- error paths
- single-GPU inference

Validate later on product:

- 4-GPU parallel inference
- performance tuning
- memory and batch sizing
- production networking
- driver and CUDA compatibility

---

## Migration checklist

- [ ] Remove Windows-only path assumptions
- [ ] Externalize all environment-specific config
- [ ] Keep the model behind an API
- [ ] Use the same image across environments where possible
- [ ] Store state in volumes, not in the image
- [ ] Test the app on Linux before release
- [ ] Test the 4-GPU serving stack on the product host

---

## Short conclusion

Yes, you can improve the project on Windows with one RTX 4090 and deploy the new code to a 4-GPU CentOS environment.

That works only if the code is portable and the multi-GPU behavior is isolated to the model serving layer.
