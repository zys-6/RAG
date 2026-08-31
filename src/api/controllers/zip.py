import traceback
from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from api.controllers.utils import make_response
from api.services.zip import process_zip, process_ftp_zip
from starlette.background import BackgroundTasks
save_path = 'static/data'
zip_router = APIRouter(prefix='/zip')


@zip_router.post('/sync')
async def handler(background_task: BackgroundTasks, file: UploadFile = File(...), package_id: str = Body(...), user_id: str = Body(...)):
    content = await file.read()
    try:
        background_task.add_task(process_zip, content, package_id, user_id)
    except Exception as e:
        print(e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    return make_response("success")


@zip_router.post('/ftp')
async def handler(ftp_url: str, background_task: BackgroundTasks):
    background_task.add_task(process_ftp_zip, ftp_url)
    return make_response("success")


@zip_router.post('/upload_ftp')
async def handler(ftp_url: str, package_id: str, user_id: str, background_task: BackgroundTasks):
    try:
        background_task.add_task(process_ftp_zip, ftp_url, package_id, user_id)
    except Exception as e:
        print(e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    return make_response("success")
