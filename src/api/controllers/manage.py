from typing import List

from fastapi import APIRouter, Query, Body
from starlette import status
from starlette.responses import JSONResponse

from api.services.manage import get_libraries_list, update_libraries, delete_libraries, get_files_by_ids

manage_router = APIRouter(prefix="/manage")




def construct_response(detail,status_code=status.HTTP_200_OK,headers=None):
    return JSONResponse(
        content={'detail':detail,'status_code':status_code},headers=headers
    )


@manage_router.get('/list')
def handler(page_no: int = Query(1),
            page_size: int = Query(10),
            sort_field: str = Query(None),
            sort_type: str = Query('desc')
            ):
    """获取全部文库列表"""
    library_list = get_libraries_list(page_no, page_size, sort_field, sort_type)
    return construct_response(library_list)


@manage_router.post('/update')
def handler(task_id: str = Body(...), kwargs: dict = Body(...)):
    """更新文库"""
    try:
        update_libraries(task_id, **kwargs)
        return construct_response({'message': '更新成功'})
    except Exception as e:
        print(e)
        return construct_response({'message': '更新失败'}, status_code=400)


@manage_router.delete('/document_delete')
def handler(md5: str = Body(None)
            ):
    """删除文库"""
    try:
        delete_libraries(md5)
    except Exception as e:
        print(e)
        return construct_response({'message': '删除失败'}, status_code=400)
    return construct_response({'message': '删除成功'})


@manage_router.post('/file_info')
def handler(ids: List[str] = Body(..., embed=True)):
    """根据固定字段 ids 的值获取文件信息"""
    try:
        file_list = get_files_by_ids(ids)
        return construct_response(file_list)
    except Exception as e:
        print(e)
        return construct_response({'message': '获取文件信息失败'}, status_code=400)
