import hashlib
import os
import traceback
from pathlib import Path
from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from api.controllers.utils import make_response
from api.services.utils import requests_create_file, requests_update_file, create_file_uuid
from api.services.word import process_word, convert_doc_to_docx

word_router = APIRouter(prefix="/word")
DEFAULT_SYNC_PACKAGE_ID = "package-00000000000000000000000000000000"


@word_router.post("/sync")
async def handler(
    file: UploadFile = File(...),
    package_id: Optional[str] = Body(None),
    user_id: Optional[str] = Body(None),
):
    content = await file.read()
    id = create_file_uuid()
    file_id = hashlib.md5(content).hexdigest()
    package_id = package_id or DEFAULT_SYNC_PACKAGE_ID
    user_id = user_id or ""
    if file.filename.endswith(".doc"):
        content = convert_doc_to_docx(content)
    try:
        save_file_dir = Path(__file__).parent.parent / 'static' / 'file'
        save_path = os.path.join(save_file_dir, file_id + '.docx')
        with open(save_path, 'wb') as f:
            f.write(content)
        requests_create_file(id=id, file_id=file_id, file_name=file.filename, file_size=content.__sizeof__() / 1024,
                             file_path=str(file_id  + '.' + 'docx'), file_type='docx',
                             package_id=package_id, user_id=user_id)
    except Exception as e:
        print(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    print('file_name', file.filename)
    await run_in_threadpool(process_word, content, True, file.filename, id, package_id, file_id)
    return make_response("success")


@word_router.post("/doc2docx")
async def handler(file: UploadFile = File(...)):
    filepath = Path(f"/tmp/{file.filename}x")
    content = await file.read()
    content = convert_doc_to_docx(content)
    with open(filepath, "wb") as fout:
        fout.write(content)

    headers = {
        "Access-Control-Expose-Headers": "Content-Disposition",
        "Content-Disposition": "attachment; filename*=utf-8''{}".format(quote(filepath.name))
    }
    return FileResponse(filepath,
                        headers=headers,
                        filename=filepath.name,
                        media_type="application/octet-stream")
