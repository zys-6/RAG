import hashlib
import os
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException, Form, Body

from api.controllers.utils import make_response
from api.services.pdf import process_pdf
from api.services.utils import requests_create_file, requests_update_file, create_file_uuid
ocr_router = APIRouter(prefix="/ocr")


@ocr_router.post("/sync")
async def handler( file: UploadFile = File(...)):
    try:
        back = Path(file.filename).suffix.lower()
        print("back"+back)
        content = await file.read()
        id = create_file_uuid()
        file_id = hashlib.md5(content).hexdigest()
        print("文件id"+file_id)
        save_file_dir = Path(__file__).parent.parent / 'static' / 'file'
        save_path = os.path.join(save_file_dir, file_id + back)
        with open(save_path, 'wb') as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return make_response(file_id)


