import hashlib
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Body
from fastapi.concurrency import run_in_threadpool

from api.controllers.utils import make_response
from api.services.caj import process_caj
from api.services.utils import requests_create_file, create_file_uuid

caj_router = APIRouter(prefix="/caj")
DEFAULT_SYNC_PACKAGE_ID = "package-00000000000000000000000000000000"


@caj_router.post("/sync/caj")
async def handler(
    file: UploadFile = File(...),
    package_id: Optional[str] = Body(None),
    user_id: Optional[str] = Body(None),
):
    save_file_dir = Path(__file__).parent.parent / 'static' / 'file'
    content = await file.read()
    id = create_file_uuid()
    file_id = hashlib.md5(content).hexdigest()
    package_id = package_id or DEFAULT_SYNC_PACKAGE_ID
    user_id = user_id or ""
    save_file_path = os.path.join(save_file_dir, file_id + '.caj')
    with open(save_file_path, 'wb') as _file:
        _file.write(content)
    try:
        requests_create_file(id=id, file_id=file_id, file_name=file.filename, file_size=content.__sizeof__() / 1024,
                             file_path=str(file_id + '.' + 'caj'), file_type='caj',
                             package_id=package_id, user_id=user_id)

    except Exception as e:
        print(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    await run_in_threadpool(process_caj, save_file_path, None, file.filename, id, package_id, file_id)
    return make_response('success')
