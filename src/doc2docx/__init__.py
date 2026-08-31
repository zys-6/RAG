import logging
import os
import platform
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, UploadFile, File, applications
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

def swagger_monkey_patch(*args, **kwargs):
    return get_swagger_ui_html(
        *args,
        **kwargs,
        swagger_js_url="static/swagger-ui-bundle-min.js",
        swagger_css_url="static/swagger-ui-min.css"
    )


applications.get_swagger_ui_html = swagger_monkey_patch

app = FastAPI()

app.mount("/static", StaticFiles(directory="static", html=True))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger = logging.getLogger(__name__)


def is_windows():
    return 'windows' in platform.system().lower()


if is_windows():
    import pythoncom
    import win32com.client as win32
    from win32com.client import constants


def convert_to_file_response(content: bytes, filename: str):
    headers = {
        "Access-Control-Expose-Headers": "Content-Disposition",
        "Content-Disposition": "attachment; filename*=utf-8''{}".format(quote(filename))
    }
    filepath = Path(filename)
    with open(filepath, "wb") as fout:
        fout.write(content)
    return FileResponse(filepath,
                        headers=headers,
                        media_type="application/octet-stream")

def convert_doc_to_docx(content: bytes) -> bytes:


@app.post("/convert")
async def handler(file: UploadFile = File(...)):
    content = await file.read()
    doc_filepath = Path(Path(__file__).parent, str(time.time()).replace(".", "") + ".doc")
    with open(doc_filepath, "wb") as fout:
        fout.write(content)
    filename = file.filename

    if is_windows():
        doc_filepath = Path(doc_filepath).resolve()
        try:
            pythoncom.CoInitialize()
            word = win32.gencache.EnsureDispatch('Word.Application')
            doc = word.Documents.Open(str(doc_filepath))
            doc.Activate()
            docx_filepath = doc_filepath.with_suffix(".docx")
            word.ActiveDocument.SaveAs(
                str(docx_filepath), FileFormat=constants.wdFormatXMLDocument
            )
            doc.Close(False)
            word.Quit()
            with open(docx_filepath, "rb") as fin:
                content = fin.read()
            filename += "x"
        except Exception as e:
            logger.error(f"_convert_doc_to_docx: {e}")
            raise e
        finally:
            doc_filepath.unlink(missing_ok=True)
            if doc_filepath.with_suffix(".docx").exists():
                try:
                    doc_filepath.with_suffix(".docx").unlink(missing_ok=True)
                except PermissionError:
                    logger.warning("未删除 {} 该文件".format(doc_filepath.with_suffix(".docx")))

            pythoncom.CoUninitialize()
        return convert_to_file_response(content, filename)
    else:
        os.system(f"unoconv -d document --format=docx {doc_filepath}")
        time.sleep(3)
        if doc_filepath.with_suffix(".docx").exists():
            with open(doc_filepath.with_suffix(".docx"), "rb") as fin:
                content = fin.read()
            filename += 'x'
        else:
            logger.error(f"_convert_doc_to_docx: convert failed")
            raise FileNotFoundError(f"Can't find {doc_filepath.with_suffix('.docx').name}")
        doc_filepath.unlink(missing_ok=True)
        return convert_to_file_response(content, filename)
