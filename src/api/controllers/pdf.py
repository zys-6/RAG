import hashlib
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Body
from fastapi.concurrency import run_in_threadpool

from api.controllers.utils import make_response
from api.services.pdf import process_pdf
from api.services.utils import requests_create_file, requests_update_file, create_file_uuid
pdf_router = APIRouter(prefix="/pdf")
DEFAULT_SYNC_PACKAGE_ID = "package-00000000000000000000000000000000"


@pdf_router.post("/sync")
async def handler(
    file: UploadFile = File(...),
    package_id: Optional[str] = Body(None),
    user_id: Optional[str] = Body(None),
    max_threads: int = Form(None),
):
    content = await file.read()
    id = create_file_uuid()
    file_id = hashlib.md5(content).hexdigest()
    package_id = package_id or DEFAULT_SYNC_PACKAGE_ID
    user_id = user_id or ""
    save_file_dir = Path(__file__).parent.parent / 'static' / 'file'
    save_path = os.path.join(save_file_dir, file_id + '.pdf')
    with open(save_path, 'wb') as f:
        f.write(content)

    try:
        requests_create_file(id=id, file_id=file_id, file_name=file.filename, file_size=content.__sizeof__() / 1024,
                             file_path=str(file_id + '.' + 'pdf'), file_type='pdf',
                             package_id=package_id, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    await run_in_threadpool(process_pdf, content, True, file.filename, id, package_id, file_id)
    return make_response('success')
