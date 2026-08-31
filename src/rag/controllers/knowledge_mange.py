import asyncio
import json
import traceback
from typing import List, Dict
from fastapi import APIRouter, Body, HTTPException, Query, BackgroundTasks
from starlette.responses import StreamingResponse

from rag.services.knowledge import get_package_list, create_package, update_package, delete_package, create_file, \
    update_file, upload_file, get_file_list, get_knowledge_tree, delete_file, get_knowledge, delete_milvus, \
    get_milvus_file, knowledge_recommend, get_knowledge_recommend, update_maybe_question
from rag.services.qa import retrieval_search, retrieval_search_by_file_ids
from rag.utils.utils import construct_response

knowledge_router = APIRouter(prefix='/knowledge_manage')


@knowledge_router.get('/tree', summary="获取知识库结构树")
async def handler(user_id: str = Query(None), group_id: str = Query(None)):
    try:
        resp = await get_knowledge_tree(user_id, group_id)
        return construct_response(data=resp, detail='成功')
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@knowledge_router.get('/package/list', summary="获取知识库列表")
async def handler(user_id: str = Query(None), group_id: str = Query((None))):
    try:
        resp = await get_package_list(user_id, group_id)
        return construct_response(data=resp, detail='成功')
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)

@knowledge_router.get('/package/get', summary="获取知识库详细")
async def handler(knowledge_id: str = Query(...)):
    try:
        status_code, resp, detail = await get_knowledge(knowledge_id)
        return construct_response(data=resp, detail=detail, status_code=status_code)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@knowledge_router.get('/package/recommend', summary="获取知识库推荐知识")
async def handler(knowledge_id: str = Query(...)):
    try:
        status_code, resp, detail = await get_knowledge_recommend(knowledge_id)
        return construct_response(data=resp, detail=detail, status_code=status_code)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)



@knowledge_router.post('/package/create', summary="创建知识库")
async def handler(package_name: str = Body(...), description: str = Body(...), user_id: str = Body(...), group_id: str = Body((None))):
    try:
        status_code, resp, detail = await create_package(package_name, description, user_id, group_id)
        return construct_response(data=resp, detail=detail, status_code=status_code)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@knowledge_router.post('/package/update', summary="更新知识库属性")
async def handler(package_id: str = Body(...), package_name: str = Body(...), description: str = Body(...)):
    try:
        status_code, resp = await update_package(package_id, package_name, description)
        return construct_response(data={}, detail=resp, status_code=status_code)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@knowledge_router.delete('/package/delete', summary="删除知识库")
async def handler(package_id: str = Body(...)):
    try:
        status_code, resp = await delete_package(package_id)
        return construct_response(data={}, detail=resp, status_code=status_code)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@knowledge_router.get('/file/list', summary="获取知识库下文件")
async def handler(package_id: str = Query(None)):
    try:
        resp = await get_file_list(package_id)
        return construct_response(data=resp, detail='成功')
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@knowledge_router.post('/file/create', summary="非公共/接口")
async def handler(id: str = Body(...), file_id: str = Body(...), file_name: str = Body(...), file_size: float = Body(...),
                  file_path: str = Body(...), file_type: str = Body(...),
                  package_id: str = Body(...), user_id: str = Body(...)):
    try:
        resp = await create_file(id, file_id, file_name, file_size, file_type,
                                 file_path,
                                 package_id, user_id)
        return construct_response(data={}, detail=resp)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@knowledge_router.post('/file/upload', summary="上传文件到知识库")
async def handler(package_id: str = Body(...), ftp_url: str = Body(...), user_id: str = Body(...)):
    try:
        resp = await upload_file(package_id, ftp_url, user_id)
        return construct_response(data=resp, detail='')
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@knowledge_router.post('/file/update', summary="文件属性更新")
async def handler(background_task: BackgroundTasks, package_id: str = Body(...), file_id: str = Body(...), attr: str = Body(...), value: str = Body(...),
                  ):
    try:
        print('更新状态:', attr, value)
        resp = await update_file(package_id, file_id, attr, value)
        if value == 'success':
            background_task.add_task(knowledge_recommend, package_id)
        return construct_response(data={}, detail=resp)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@knowledge_router.delete('/file/delete', summary="删除文件")
async def handler(background_task: BackgroundTasks, file_id: str = Body(...)):
    try:
        status_code, package_id, detail = await delete_file(file_id)
        if status_code == 200:
            background_task.add_task(update_maybe_question, package_id)
        return construct_response(data={}, detail=detail, status_code=status_code)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@knowledge_router.delete('/delete', summary="清空知识库milvus")
async def handler():
    try:
        await delete_milvus()
        return construct_response(data={}, detail='成功')
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)

@knowledge_router.get('/get', summary="查看知识库已有文件")
async def handler():
    try:
        resp = await get_milvus_file()
        return construct_response(data=resp, detail='成功')
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@knowledge_router.post('/retrieval/search', summary="检索测试（无LLM，开发/调试）")
async def handler(
        query: str = Body(...),
        package_id: str = Body(None),
        document_ids: List[str] = Body(None),
        mode: str = Body("pipeline"),
        limit: int = Body(30),
        top_k: int = Body(8),
):
    try:
        resp = await retrieval_search(
            query=query,
            package_id=package_id or "",
            document_ids=document_ids,
            mode=mode,
            limit=limit,
            top_k=top_k,
        )
        return construct_response(data=resp, detail='成功')
    except ValueError as e:
        return construct_response(data={}, detail=str(e), status_code=400)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@knowledge_router.post('/retrieval/file_search', summary="按File表id检索测试（无LLM，开发/调试）")
async def handler(
        query: str = Body(...),
        ids: List[str] = Body(..., embed=True),
        mode: str = Body("pipeline"),
        limit: int = Body(30),
        top_k: int = Body(8),
):
    try:
        resp = await retrieval_search_by_file_ids(
            query=query,
            ids=ids,
            mode=mode,
            limit=limit,
            top_k=top_k,
        )
        return construct_response(data=resp, detail='成功')
    except ValueError as e:
        return construct_response(data={}, detail=str(e), status_code=400)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)
