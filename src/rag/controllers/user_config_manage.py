import asyncio
import json
import traceback
from typing import List, Dict
from fastapi import APIRouter, Body, HTTPException, Query
from starlette.responses import StreamingResponse

from rag.services.user_config import get_user_config, create_user_config, delete_user_config, update_user_config, get_user_config_list_by_user_id
from rag.utils.utils import construct_response

user_config_router = APIRouter(prefix='/user_config_manage')


@user_config_router.get('/list', summary='获取当前人的config列表')
async def handler(user_id: str = Query(...)):
    try:
        status_code, resp, detail = await get_user_config_list_by_user_id(user_id)
        return construct_response(data=resp, detail='成功',status_code=200)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@user_config_router.get('/get', summary='获取config详细')
async def handler(user_config_id: str = Query(...)):
    try:
        status_code, resp, detail = await get_user_config(user_config_id)
        return construct_response(data=resp, detail=detail, status_code=status_code)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)

@user_config_router.post('/create', summary='创建json模板')
async def handler(user_id: str = Body(...), config_json: str = Body(...),config_name: str = Body(...)):
    try:
        resp = await create_user_config(user_id=user_id, config_json=config_json,config_name=config_name)
        return construct_response(data=resp, detail='成功',status_code=200)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@user_config_router.delete('/delete', summary='删除json模板')
async def handler(user_config_id: str = Body(...)):
    try:
        resp = await delete_user_config(user_config_id=user_config_id)
        return construct_response(data={}, detail=resp,status_code=200)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@user_config_router.post('/update', summary='修改json')
async def handler(user_config_id: str = Body(...),user_id: str = Body(...), config_json: str = Body(...),config_name: str = Body(...)):
    try:
        status_code, resp = await update_user_config(user_config_id, user_id, config_json,config_name)
        return construct_response(data={}, detail=resp, status_code=status_code)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)




