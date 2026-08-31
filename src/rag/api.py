import logging
from fastapi import FastAPI, applications
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html

from rag.controllers.qa import qa_router
from rag.controllers.api_manage import manage_router
from rag.controllers.agent_manage import agent_router
from rag.controllers.knowledge_manage import knowledge_router
from rag.controllers.unit_aliases import unit_router

logger = logging.getLogger(__name__)


def swagger_monkey_patch(*args, **kwargs):
    return get_swagger_ui_html(
        *args,
        **kwargs,
        swagger_js_url="static/swagger-ui-bundle-min.js",
        swagger_css_url="static/swagger-ui-min.css"
    )

app = FastAPI()

applications.get_swagger_ui_html = swagger_monkey_patch
app.mount("/static", StaticFiles(directory="rag/static", html=True))
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"],
                   allow_headers=["*"])


app.include_router(knowledge_router, tags=["知识库管理"])
app.include_router(manage_router, tags=["系统管理"])
app.include_router(agent_router, tags=["Agent管理"])
app.include_router(qa_router,tags=["问答"])

app.include_router(unit_router,tags=["团队别名管理"])

# app.include_router(user_config_router,tags=["配置模板管理"])



