import asyncio
import importlib
import json
import math
import os
import sys
import types
from pathlib import Path

from starlette.background import BackgroundTasks


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _purge_modules(prefix: str) -> None:
    for name in list(sys.modules):
        if name == prefix or name.startswith(f"{prefix}."):
            del sys.modules[name]


def _install_module(name: str, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


class _DummyArray:
    def __init__(self, values):
        self._values = list(values)

    def tolist(self):
        return list(self._values)


class _DummyTensor:
    def __init__(self, values):
        self.values = list(values)

    def to(self, _device):
        return self

    def view(self, *_args, **_kwargs):
        return self

    def float(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return _DummyArray(self.values)

    def softmax(self, _dim):
        exps = [math.exp(value) for value in self.values]
        total = sum(exps) or 1.0
        return _DummyTensor([value / total for value in exps])


class _NoGrad:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyChunk:
    def __init__(self, content: str):
        delta = types.SimpleNamespace(content=content)
        choice = types.SimpleNamespace(delta=delta)
        self.choices = [choice]

    def model_dump(self):
        return {"choices": [{"delta": {"content": self.choices[0].delta.content}}]}


def _make_subscription():
    async def generator():
        yield _DummyChunk("stub-answer")

    return generator()


def _chdir_to_src():
    os.chdir(SRC_ROOT)


def _install_document_stubs():
    multipart_pkg = _install_module("multipart", __version__="0.0-test")
    _install_module("multipart.multipart", parse_options_header=lambda value: ("", {}))
    multipart_pkg.multipart = sys.modules["multipart.multipart"]
    _install_module("api.services.pdf", process_pdf=lambda *args, **kwargs: None)
    _install_module("api.services.caj", process_caj=lambda *args, **kwargs: None)
    _install_module(
        "api.services.word",
        process_word=lambda *args, **kwargs: None,
        convert_doc_to_docx=lambda content: content,
    )
    _install_module(
        "api.services.zip",
        process_zip=lambda *args, **kwargs: None,
        process_ftp_zip=lambda *args, **kwargs: None,
    )
    _install_module(
        "api.services.manage",
        get_libraries_list=lambda *args, **kwargs: [{"id": "library-1"}],
        update_libraries=lambda *args, **kwargs: None,
        delete_libraries=lambda *args, **kwargs: None,
        get_files_by_ids=lambda ids: [{"id": file_id} for file_id in ids],
    )
    _install_module(
        "api.services.utils",
        requests_create_file=lambda **kwargs: None,
        requests_update_file=lambda **kwargs: None,
        create_file_uuid=lambda: "task-1",
    )


def _install_embedding_stubs():
    class DummySentenceModel:
        def __init__(self, _path):
            pass

        def encode(self, inputs, convert_to_numpy=False):
            return [_DummyArray([float(index), float(len(item))]) for index, item in enumerate(inputs)]

    class DummyTokenizer:
        @classmethod
        def from_pretrained(cls, _path):
            return cls()

        def __call__(self, batch, **_kwargs):
            return {"input_ids": _DummyTensor([len(batch)])}

    class DummySequenceModel:
        @classmethod
        def from_pretrained(cls, _path):
            return cls()

        def to(self, _device):
            return self

        def eval(self):
            return self

        def __call__(self, **_kwargs):
            return types.SimpleNamespace(logits=_DummyTensor([0.25, 0.75]))

    _install_module("text2vec", SentenceModel=DummySentenceModel)
    _install_module(
        "torch",
        device=lambda name: name,
        no_grad=_NoGrad,
        concat=lambda tensors, dim=0: _DummyTensor(
            [item for tensor in tensors for item in tensor.values]
        ),
        cuda=types.SimpleNamespace(is_available=lambda: False),
    )
    _install_module(
        "transformers",
        AutoTokenizer=DummyTokenizer,
        AutoModelForSequenceClassification=DummySequenceModel,
    )


def _install_rag_stubs():
    multipart_pkg = _install_module("multipart", __version__="0.0-test")
    _install_module("multipart.multipart", parse_options_header=lambda value: ("", {}))
    multipart_pkg.multipart = sys.modules["multipart.multipart"]
    async def _stream_response(*_args, **_kwargs):
        return _make_subscription(), [{"id": "ref-1"}], {"phase": "ok"}

    async def _retrieval_response(*_args, **_kwargs):
        return {"items": [{"id": "doc-1"}]}

    async def _agent_list():
        return [{"id": "agent-1"}]

    async def _agent_get(_agent_id):
        return 200, {"id": "agent-1"}, "成功"

    async def _agent_create(**_kwargs):
        return {"id": "agent-1"}

    async def _agent_delete(**_kwargs):
        return "成功"

    async def _agent_update(*_args, **_kwargs):
        return 200, "成功"

    async def _agent_stream(*_args, **_kwargs):
        return _make_subscription()

    async def _package_list(*_args, **_kwargs):
        return [{"id": "pkg-1"}]

    async def _knowledge_tree(*_args, **_kwargs):
        return [{"id": "root"}]

    async def _knowledge_get(*_args, **_kwargs):
        return 200, {"id": "pkg-1"}, "成功"

    async def _knowledge_recommend(*_args, **_kwargs):
        return 200, [{"id": "pkg-1"}], "成功"

    async def _package_create(*_args, **_kwargs):
        return 200, {"id": "pkg-1"}, "成功"

    async def _package_update(*_args, **_kwargs):
        return 200, "成功"

    async def _package_delete(*_args, **_kwargs):
        return 200, "成功"

    async def _file_create(*_args, **_kwargs):
        return "成功"

    async def _file_upload(*_args, **_kwargs):
        return {"id": "file-1"}

    async def _file_list(*_args, **_kwargs):
        return [{"id": "file-1"}]

    async def _file_update(*_args, **_kwargs):
        return "成功"

    async def _file_delete(*_args, **_kwargs):
        return 200, "pkg-1", "成功"

    async def _delete_milvus():
        return None

    async def _milvus_file():
        return [{"id": "file-1"}]

    def _construct_response(data, detail, status_code=200):
        return {"data": data, "detail": detail, "status_code": status_code}

    def _ready_list():
        return [{"id": 1, "name": "unit"}]

    class _DialogueRecord:
        llm_text = ""

        def update(self):
            return None

    class Dialogue:
        @staticmethod
        def get_single_dialogue(**_kwargs):
            return _DialogueRecord()

    _install_module(
        "rag.utils.utils",
        construct_response=_construct_response,
        insert_api_field=lambda *args, **kwargs: None,
        insert_api_data=lambda *args, **kwargs: None,
        delete_api_data_by_fields=lambda *args, **kwargs: None,
        get_api_data_list=lambda *args, **kwargs: [{"id": "field-1"}],
        get_api_field_desc=lambda *args, **kwargs: {"name": "api"},
        api_data_update=lambda *args, **kwargs: None,
        get_api_updatable_fields=lambda *args, **kwargs: ["field_a"],
        get_task_status_by_id=lambda *args, **kwargs: {"status": "ok"},
    )
    _install_module(
        "rag.services.agent",
        get_agent_list=_agent_list,
        create_agent=_agent_create,
        delete_agent=_agent_delete,
        update_agent=_agent_update,
        agent_stream=_agent_stream,
        get_agent=_agent_get,
    )
    _install_module(
        "rag.services.knowledge",
        get_package_list=_package_list,
        create_package=_package_create,
        update_package=_package_update,
        delete_package=_package_delete,
        create_file=_file_create,
        update_file=_file_update,
        upload_file=_file_upload,
        get_file_list=_file_list,
        get_knowledge_tree=_knowledge_tree,
        delete_file=_file_delete,
        get_knowledge=_knowledge_get,
        delete_milvus=_delete_milvus,
        get_milvus_file=_milvus_file,
        knowledge_recommend=lambda *args, **kwargs: None,
        get_knowledge_recommend=_knowledge_recommend,
        update_maybe_question=lambda *args, **kwargs: None,
    )
    _install_module(
        "rag.services.qa",
        qa_stream=_stream_response,
        generate_report=lambda *args, **kwargs: None,
        get_table_info_by_sql_query=lambda *args, **kwargs: {},
        db_agent_stream=_stream_response,
        knowledge_agent_stream=_stream_response,
        knowledge_file_agent_stream=_stream_response,
        report_agent_stream=_stream_response,
        week_agent_stream=_stream_response,
        qa_ocr_stream=_stream_response,
        template_agent_stream=_stream_response,
        qa_ocr_stream_org=_stream_response,
        generate_jira_week_report=lambda *args, **kwargs: None,
        generate_jira_week_report_all=lambda *args, **kwargs: None,
        request_agent_stream=_stream_response,
        contract_agent_stream=_stream_response,
        qa_ocr_team=lambda *args, **kwargs: {"status": "ok"},
        mermaid_agent_stream=_stream_response,
        retrieval_search=_retrieval_response,
        retrieval_search_by_file_ids=_retrieval_response,
    )
    _install_module(
        "rag.services.api_manage",
        get_all_apis=lambda: [{"name": "api-a"}],
        insert_api=lambda data: None,
        update_api_info=lambda *args, **kwargs: None,
    )
    _install_module(
        "rag.services.unit_aliases",
        add_unit=lambda *args, **kwargs: None,
        delete_unit=lambda *args, **kwargs: None,
        update_unit=lambda *args, **kwargs: None,
        search_unit=lambda unit_name: {"name": unit_name},
        save_units=lambda *args, **kwargs: None,
        load_units=_ready_list,
    )
    _install_module("rag.mappers.task", Dialogue=Dialogue)
    redis_asyncio = _install_module("redis.asyncio")
    _install_module("redis", asyncio=redis_asyncio)


def _load_document_app():
    _purge_modules("api")
    _install_document_stubs()
    _chdir_to_src()
    return importlib.import_module("api.main").app


def _load_embedding_app():
    _purge_modules("embedding")
    _install_embedding_stubs()
    _chdir_to_src()
    return importlib.import_module("embedding.api").app


def _load_rag_app():
    _purge_modules("rag")
    _install_rag_stubs()
    _chdir_to_src()
    return importlib.import_module("rag.api").app


def _find_route(app, path: str, method: str):
    for route in app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route
    raise AssertionError(f"Route not found: {method} {path}")


def test_document_app_startup_and_contracts():
    app = _load_document_app()

    paths = set(app.openapi()["paths"])
    assert "/word/sync" in paths
    assert "/manage/file_info" in paths

    route_paths = {route.path for route in app.routes}
    assert "/word/sync" in route_paths
    assert "/pdf/sync" in route_paths
    assert "/ocr/sync" in route_paths
    assert "/caj/sync/caj" in route_paths
    assert "/zip/sync" in route_paths
    assert "/manage/file_info" in route_paths

    zip_route = _find_route(app, "/zip/ftp", "POST")
    response = asyncio.run(zip_route.endpoint(ftp_url="ftp://example.invalid/test.zip", background_task=BackgroundTasks()))
    assert response == {
        "data": "success",
        "detail": "success",
        "status_code": 200,
    }

    manage_route = _find_route(app, "/manage/file_info", "POST")
    manage_response = manage_route.endpoint(ids=["a", "b"])
    assert set(json.loads(manage_response.body)) == {"detail", "status_code"}


def test_embedding_app_startup_and_contracts():
    app = _load_embedding_app()

    paths = set(app.openapi()["paths"])
    assert paths == {"/embeddings", "/rerank"}

    embedding_route = _find_route(app, "/embeddings", "POST")
    body = asyncio.run(embedding_route.endpoint(input=types.SimpleNamespace(input=["alpha", "beta"])))
    body = body.model_dump() if hasattr(body, "model_dump") else body.dict()
    assert body["object"] == "list"
    assert body["model"] == "embeddings"
    assert len(body["data"]) == 2
    assert set(body["usage"]) == {"prompt_tokens", "total_tokens"}

    rerank_route = _find_route(app, "/rerank", "POST")
    rerank_response = asyncio.run(rerank_route.endpoint(query="q", texts=["a", "b"]))
    assert set(rerank_response) == {"scores", "softmax_scores"}


def test_rag_app_startup_route_presence_and_contracts():
    app = _load_rag_app()

    openapi_paths = set(app.openapi()["paths"])
    assert "/knowledge_manage/tree" in openapi_paths
    assert "/knowledge_manage/retrieval/search" in openapi_paths
    assert "/api_manage/api_list" in openapi_paths
    assert "/agent/list" in openapi_paths
    assert "/qa/qa" in openapi_paths
    assert "/unit_aliases/unit_list" in openapi_paths

    route_paths = {route.path for route in app.routes}
    assert "/knowledge_manage/retrieval/file_search" in route_paths
    assert "/qa/agent/knowledge_file_agent" in route_paths
    assert "/qa/agent/mermaid_agent" in route_paths
    assert "/unit_aliases/unit_delete" in route_paths

    retrieval_route = _find_route(app, "/knowledge_manage/retrieval/search", "POST")
    retrieval_response = asyncio.run(
        retrieval_route.endpoint(
            query="hello",
            package_id="",
            document_ids=[],
            mode="pipeline",
            limit=30,
            top_k=8,
        )
    )
    assert set(retrieval_response) == {"data", "detail", "status_code"}

    unit_route = _find_route(app, "/unit_aliases/unit_list", "GET")
    unit_response = unit_route.endpoint()
    unit_body = unit_response.model_dump() if hasattr(unit_response, "model_dump") else unit_response.dict()
    assert set(unit_body) == {"status", "detail", "data"}


def test_rag_sse_routes_emit_event_stream_and_done_marker():
    app = _load_rag_app()
    qa_route = _find_route(app, "/qa/qa", "POST")
    response = asyncio.run(
        qa_route.endpoint(
            task_id="task-1",
            query="hello",
            history=[],
            thing_pattern=False,
            user_id="user-1",
        )
    )

    async def _collect_streaming_body(streaming_response):
        parts = []
        async for chunk in streaming_response.body_iterator:
            parts.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        return "".join(parts)

    assert response.media_type == "text/event-stream"
    body = asyncio.run(_collect_streaming_body(response))
    assert "data: [DONE]" in body
    assert "stub-answer" in body
