import logging
import traceback
from typing import Dict, List
from fastapi import APIRouter, status, Body, Query

from rag.services.api_manage import get_all_apis, insert_api, update_api_info
from rag.utils.utils import insert_api_field, insert_api_data, delete_api_data_by_fields, \
    get_api_data_list, get_api_field_desc, api_data_update, get_api_updatable_fields
from rag.view.response import ReadyResponse

manage_router = APIRouter(prefix='/api_manage',)
logger = logging.getLogger(__name__)


@manage_router.post('/api_insert', summary="新增API配置文件")
def handler(data: Dict):
    try:
        insert_api(data)
        return ReadyResponse(detail='ok',data='')
    except Exception as e:
        logger.error(e)
        return ReadyResponse(detail=str(e), data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@manage_router.get('/api_search', summary="获取API详细信息")
def handler(api_name: str):
    try:
        api_info = get_api_field_desc(api_name)
        return ReadyResponse(data=api_info,detail='')
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
        return ReadyResponse(detail=str(e), data={},status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@manage_router.get('/api_list', summary="API列表")
def handler():
    try:
        configs = get_all_apis()
        return ReadyResponse(data=configs,detail='')
    except Exception as e:
        logger.error(e)
        traceback.print_exc()
        return ReadyResponse(detail=str(e), data={},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@manage_router.post('/api_update', summary="修改API信息")
def handler(api_name: str = Body(...), info: Dict = Body({
      "desc": "用于获取...信息",
      "url": "http://192.168...isticQuery",
      "create_time": "2024-10-11 10:38:33",
      "author": ""
    })):
    '''api配置文件信息修改'''
    try:
        update_api_info(api_name, **info)
        return ReadyResponse(detail='ok',data='')
    except Exception as e:
        logger.error(e)
        return ReadyResponse(detail=str(e),data={}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@manage_router.get('/field_list', summary="API字段列表")
def handler(api_name: str):
    try:
        fields = get_api_updatable_fields(api_name)
        return ReadyResponse(data=fields,detail='')
    except Exception as e:
        logger.error(e)
        return ReadyResponse(detail=str(e), data={},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@manage_router.post('/api_field_insert', summary="新增API字段")
def handler(api_name: str = Body(...), type: str = Body(...), field_data: Dict = Body({
    "zh_": "项目状态",
    "key": "projectInformation",
    "name": "project_status",
    "example": "竞标",
    "type": "equals",
    "is_time": False
})):
    '''api配置文件字段新增'''
    try:
        insert_api_field(api_name, type, field_data)
        return ReadyResponse(detail='ok',data='')
    except Exception as e:
        logger.error(e)
        return ReadyResponse(detail=str(e), data={},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@manage_router.post('/api_data_insert', summary="新增API字段下数据")
def handler(api_name: str = Body(...), field_name: str = Body(...), field_data: Dict = Body({
    'alias': ['军委'],
    'name': '军委机关',
    'index': ['1401_14005']
})):
    '''api数据新增'''
    try:
        insert_api_data(api_name, field_name, field_data)
        return ReadyResponse(detail='ok',data='')
    except Exception as e:
        logger.error(e)
        return ReadyResponse(detail=str(e), data={},status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@manage_router.post('/api_data_update', summary="修改API字段下数据")
def handler(api_name: str = Body(...), field_name: str = Body(...), field_data: Dict = Body({
    'org_data': {'alias':['军委','解放军军委'],'index':['1401_14005']},
    'name': '军委机关',
    'new_data': {'alias':['军委'],'index':['1401_14005','1401_14006']}
})):
    '''api数据新增'''
    try:
        api_data_update(api_name, field_name, field_data)
        return ReadyResponse(detail='ok',data='')
    except Exception as e:
        logger.error(e)
        return ReadyResponse(detail=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@manage_router.get('/api_data_list', summary="API字段下数据列表")
def handler(page_on: int = Query(1), page_size: int = Query(10),api_name: str = Query(''), field_name: str = Query('')):
    '''api数据列表'''
    try:
        data_list = get_api_data_list(page_on, page_size, api_name, field_name)
        return ReadyResponse(data=data_list,detail='')
    except Exception as e:
        logger.error(e)
        return ReadyResponse(detail=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@manage_router.delete('/api_data_delete', summary="删除某个API字段下的数据")
def handler(api_name: str = Body(...), field_name: str = Body(...), data_list: List = Body(...)):
    '''api数据删除'''
    try:
        delete_api_data_by_fields(api_name, field_name,data_list)
        return ReadyResponse(data='',detail='ok')
    except Exception as e:
        logger.error(e)
        return ReadyResponse(detail=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
