import logging
import traceback
from email.policy import default
from typing import Dict, List
from fastapi import APIRouter, status, Body, Query

from typing import Dict,Any

from rag.services.unit_aliases import add_unit, delete_unit, update_unit,search_unit,save_units,load_units
from rag.view.response import ReadyResponse

unit_router = APIRouter(prefix='/unit_aliases')
logger = logging.getLogger(__name__)


@unit_router.post('/unit_insert', summary="新增单位及别名")
def handler(data: Dict[str, Any] = Body(...)):
    try:
        name = data['name']
        aliases = data['aliases']
        add_unit(name, aliases)
        return ReadyResponse(detail='ok',data='')
    except Exception as e:
        logger.error(e)
        return ReadyResponse(detail=str(e), data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@unit_router.get('/unit_search', summary="查询单位")
def handler(unit_name: str):
    try:
        unit_info = search_unit(unit_name)
        return ReadyResponse(data=unit_info,detail='')
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
        return ReadyResponse(detail=str(e), data={},status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@unit_router.get('/unit_list', summary="unit列表")
def handler():
    try:
        unit_list = load_units()
        return ReadyResponse(data=unit_list,detail='')
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
        return ReadyResponse(detail=str(e), data={},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@unit_router.post('/unit_update', summary="修改单位信息")
def handler(
        unit_id: int = Body(...),
        data: Dict[str, Any] = Body(default = {})
    ):
    try:
        name = data.get('name')
        aliases = data.get('aliases',[])
        update_unit(unit_id,name = name, aliases = aliases)
        return ReadyResponse(detail='ok',data='')
    except Exception as e:
        logger.error(e)
        return ReadyResponse(detail=str(e),data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





@unit_router.delete('/unit_delete', summary="删除某个单位")
def handler(unit_id: int):
    try:
        delete_unit(unit_id)
        return ReadyResponse(data='',detail='ok')
    except Exception as e:
        logger.error(e)
        return ReadyResponse(detail=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
