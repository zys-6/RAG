import pathlib

from fastapi import FastAPI, applications
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles

from api.controllers.ocr import ocr_router
from api.controllers.pdf import pdf_router
from api.controllers.caj import caj_router
from api.controllers.word import word_router
from api.controllers.zip import zip_router
from api.controllers.manage import manage_router

static_path = pathlib.Path(__file__).parent / "static"
def swagger_monkey_patch(*args, **kwargs):
    return get_swagger_ui_html(
        *args,
        **kwargs,
        swagger_js_url="api/v1/static/swagger-ui-bundle-min.js",
        swagger_css_url="api/v1/static/swagger-ui-min.css"
    )


applications.get_swagger_ui_html = swagger_monkey_patch

app = FastAPI(root_path="/api/v1", summary="文档碎片化API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(word_router, tags=['word文档碎片化'])
app.include_router(pdf_router, tags=['pdf文档碎片化'])

app.include_router(ocr_router, tags=['ocr文档碎片化'])
app.include_router(caj_router, tags=['caj文档碎片化'])
app.include_router(zip_router, tags=["压缩包上传"])
app.include_router(manage_router,tags=['文档管理'])

app.mount("/static", StaticFiles(directory='./api/static'), name='static')

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=12355)
