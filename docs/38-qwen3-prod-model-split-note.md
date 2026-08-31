# Qwen3 Prod Model Split Note

Date: 2026-08-26

Current production-style split:

- `8001 -> /models/Qwen3-32B-AWQ`
- `8000 -> /models/Qwen3-14B-AWQ`
- `MODEL_NAME` points to the primary path
- `MODEL_NAME2` points to the secondary path

Observed issue:

- backend requests can fail with `404 NotFoundError` if the port and model id are crossed
- example: sending `"/models/Qwen3-14B-AWQ"` to `8001` fails even when both model servers are healthy

Checks used:

```bash
curl http://192.168.1.100:8001/v1/models
curl http://192.168.1.100:8000/v1/models
docker exec <qa-container> env | grep -E 'MODEL_NAME|API_BASE'
```

Outcome:

- backend host and model server both confirmed the split worked after config alignment

Follow-up issue on the same day:

- after the model-id/port alignment was fixed, another backend failure appeared:
  - `400 BadRequestError`
  - `max_tokens=4080 cannot be greater than max_model_len=max_total_tokens=2048`
- this was not a connectivity issue and not a wrong-model issue
- it came from a backend request asking for more output tokens than the active model server allowed

Backend source tied to this symptom:

- [`src/rag/services/qa.py`](/home/z/projects/rag/src/rag/services/qa.py:493)
- `get_question_classification_from_question(...)` called `openai_client.chat.completions.create(...)` with:
  - `max_tokens=4080`

Observed context on 2026-08-26:

- the `32B` server launch script used `--max-model-len 8192`
- a separate failing path reported `max_model_len=max_total_tokens=2048`
- the practical fix used on the host was to reduce the requested `max_tokens`

Operational rule:

- do not assume a request-side `max_tokens` value is safe just because another model or port worked
- when switching models or launch profiles, re-check both:
  - server-side context/output limits
  - backend hardcoded `max_tokens` values

Related earlier record:

- [docs/33-10.42.0.125-vllm-compose-qa-validation.md](./33-10.42.0.125-vllm-compose-qa-validation.md#4-model-id-mismatch-between-vllm-and-backend)
- especially the note that `MODEL_NAME` and `MODEL_NAME2` must match the exact model id exposed by `vLLM`; see [docs/33-10.42.0.125-vllm-compose-qa-validation.md](/home/z/projects/rag/docs/33-10.42.0.125-vllm-compose-qa-validation.md:220)
