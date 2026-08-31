import asyncio
import io
import json
import pathlib
import traceback
from fastapi import Request
import redis.asyncio as redis
from pathlib import Path
from typing import List, Dict, IO
from fastapi import APIRouter, Body, HTTPException,File, UploadFile,Form
from starlette.responses import StreamingResponse, FileResponse
from starlette.background import BackgroundTasks
from starlette.datastructures  import UploadFile  as StarletteUploadFile


from rag.mappers.task import Dialogue
from rag.services.qa import qa_stream, generate_report, get_table_info_by_sql_query, db_agent_stream, \
    knowledge_agent_stream, knowledge_file_agent_stream, report_agent_stream, week_agent_stream, qa_ocr_stream, \
    template_agent_stream, qa_ocr_stream_org, generate_jira_week_report, generate_jira_week_report_all, \
    request_agent_stream, contract_agent_stream,qa_ocr_team,mermaid_agent_stream
from rag.utils.utils import get_task_status_by_id

qa_router = APIRouter(prefix='/qa',)

# async def stream_generator(task_id, user_id, query, history, thing_pattern,fileinput):
#     yield "event: ping\ndata:正在分析中 请稍候。。。\n\n"
#     await asyncio.sleep(0.1)
#     try:
#         subscription, references, data = await qa_ocr_stream(task_id, user_id, query, history, thing_pattern,fileinput)
#         message = {
#             "question": question,
#             "answer": "",
#             "references": [ref for ref in json.loads(references)],
#             "data": eval(str(data).replace('\"','\''))
#         }
#         answer = ""
#         if data:
#          yield "data:{}\n\n".format(json.dumps(message,ensure_ascii=False))
#         async for chunk in subscription:
#             if chunk.choices[0].delta.content:
#                 answer += chunk.choices[0].delta.content
#                 yield "data: " + json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n\n"
#         message['answer'] = answer
#         _dialogue = Dialogue.get_single_dialogue(id=task_id, user_id=user_id)
#         if _dialogue:
#             _dialogue.llm_text = answer
#             _dialogue.update()
#         print('最终message:', message, flush=True)
#         yield "data: {}\n\n".format(json.dumps(message, ensure_ascii=False))
#         yield "data: [DONE]"
#     except asyncio.TimeoutError:
#         raise HTTPException(status_code=504, detail="Stream timed out")
#     except Exception as e:
#         yield f"event: error\ndata:{str(e)}\n\n"

async def stream_generator(subscription, references, question, data, task_id, user_id):
    print("data", data)
    message = {
        "question": question,
        "answer": "",
        "references": [ref for ref in json.loads(references)],
        "data": eval(str(data).replace('\"','\''))
    }
    answer = ""
    if data:
        yield "data:{}\n\n".format(json.dumps(message,ensure_ascii=False))
    try:
        if subscription:
            async for chunk in subscription:
                if chunk.choices[0].delta.content:
                    answer += chunk.choices[0].delta.content
                    yield "data: " + json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n\n"
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Stream timed out")
    message['answer'] = answer
    _dialogue = Dialogue.get_single_dialogue(id=task_id, user_id=user_id)
    if _dialogue:
        _dialogue.llm_text = answer
        _dialogue.update()
    print('最终message:', message, flush=True)
    yield "data: {}\n\n".format(json.dumps(message, ensure_ascii=False))
    yield "data: [DONE]"

@qa_router.post("/qa", summary="大模型对话")
async def handler(task_id: str = Body(...), query: str = Body(...), history: List[str] = Body(...), thing_pattern: bool = Body(), user_id: str = Body()):
    try:
        subscription, references, data = await qa_stream(task_id, user_id, query, history, thing_pattern)
        return StreamingResponse(stream_generator(subscription, json.dumps(references, ensure_ascii=False),
                                                  query, data, task_id, user_id),
                                 media_type='text/event-stream')
    except Exception as e:
        traceback.print_exc()
        return {"detail": str(e), "status_code": 500}
    
    
# @qa_router.post("/ocr-chat", summary="ocr对话")
# async def handler(task_id: str = Body(...), query: str = Body(...), history: List[str] = Body(...), thing_pattern: bool = Body(), user_id: str = Body(),file: str = Body(...) ):
#     try:
#         print("进来最外边", flush=True)
#         save_file_dir = str(Path(__file__).parent.parent.parent / 'api' / 'static' / 'file' / file)
#         print("save_file_dir"+save_file_dir)
#         fileinput = get_upload_file_from_path(save_file_dir)
#         # subscription, references, data = await qa_ocr_stream(task_id, user_id, query, history, thing_pattern,fileinput)
#         return StreamingResponse(stream_generator(task_id, user_id, query, history, thing_pattern,fileinput),
#                                  media_type='text/event-stream')
#     except Exception as e:
#         traceback.print_exc()
#         return {"detail": str(e), "status_code": 500}


@qa_router.post("/ocr-chat", summary="ocr对话")
async def handler(task_id: str = Body(...), query: str = Body(...), history: List[str] = Body(...), thing_pattern: bool = Body(), user_id: str = Body(),file: str = Body(...) ):
    try:
        print("进来最外边",task_id, flush=True)
        save_file_dir = str(Path(__file__).parent.parent.parent / 'api' / 'static' / 'file' / file)
        print("save_file_dir"+save_file_dir)
        fileinput = get_upload_file_from_path(save_file_dir)
        subscription, references, data = await qa_ocr_stream_org(task_id, user_id, query, history, thing_pattern,fileinput)
        return StreamingResponse(stream_generator(subscription, json.dumps(references, ensure_ascii=False),
                                                  query, data, task_id, user_id),
                                 media_type='text/event-stream')
    except Exception as e:
        traceback.print_exc()
        return {"detail": str(e), "status_code": 500}

@qa_router.post("/ocr-org", summary="ocr团队模板")
async def handler(task_id: str = Body(...), query: str = Body(...), history: List[str] = Body(...), thing_pattern: bool = Body(), user_id: str = Body(),file: str = Body(...) ):
    try:
        print("进来最外边",task_id, flush=True)
        save_file_dir = str(Path(__file__).parent.parent.parent / 'api' / 'static' / 'file' / file)
        print("save_file_dir"+save_file_dir)
        fileinput = get_upload_file_from_path(save_file_dir)
        subscription, references, data = await qa_ocr_stream_org(task_id, user_id, query, history, thing_pattern,fileinput)
        return StreamingResponse(stream_generator(subscription, json.dumps(references, ensure_ascii=False),
                                                  query, data, task_id, user_id),
                                 media_type='text/event-stream')
    except Exception as e:
        traceback.print_exc()
        return {"detail": str(e), "status_code": 500}



@qa_router.post("/ocr-team", summary="ocrTeam团队模板")
async def handler(team_id: str = Body(...), file: str = Body(...) ,creator_guid: str = Body(...)):
    try:
        print("进来最外边",team_id, flush=True)
        save_file_dir = str(Path(__file__).parent.parent.parent / 'api' / 'static' / 'file' / file)
        print("save_file_dir"+save_file_dir)
        fileinput = get_upload_file_from_path(save_file_dir)
        result= await qa_ocr_team(team_id, fileinput,creator_guid)
        return {"data": result, "status_code":'0'}
    except Exception as e:
        traceback.print_exc()
        return {"detail": str(e), "status_code": "1"}




# #2025年8月7日  判断去重
# # 初始化 Redis 客户端（全局）
# redis_client = redis.Redis(host="192.168.1.172", port=6379, db=0, username="root",password="ebp999", decode_responses=True)
#
# @qa_router.post("/ocr-chat", summary="ocr对话")
# async def handler(
#     task_id: str = Body(...),
#     query: str = Body(...),
#     history: List[str] = Body(...),
#     thing_pattern: bool = Body(),
#     user_id: str = Body(),
#     file: str = Body(...),
# ):
#     redis_key = f"ocr_chat:{task_id}"
#     try:
#         # 步骤 1：检查是否已存在
#         existing = await redis_client.get(redis_key)
#         if existing:
#             return {"detail": "重复请求或正在处理中", "status_code": 429}
#
#         # 步骤 2：设置为处理中，设置短暂 TTL 防止死锁
#         await redis_client.set(redis_key, "processing", ex=600)
#
#         print("进来最外边", flush=True)
#         save_file_dir = str(Path(__file__).parent.parent.parent / 'api' / 'static' / 'file' / file)
#         print("save_file_dir"+save_file_dir)
#         fileinput = get_upload_file_from_path(save_file_dir)
#         subscription, references, data = await qa_ocr_stream(task_id, user_id, query, history, thing_pattern, fileinput)
#
#         # 可选：更新 Redis 状态（如缓存部分结果）
#         await redis_client.set(redis_key, "done", ex=600)
#
#         return StreamingResponse(
#             stream_generator(subscription, json.dumps(references, ensure_ascii=False), query, data, task_id, user_id),
#             media_type='text/event-stream'
#         )
#     except Exception as e:
#         # 失败时清理 Redis 键（避免卡住）
#         await redis_client.delete(redis_key)
#         traceback.print_exc()
#         return {"detail": str(e), "status_code": 500}
#


def   get_upload_file_from_path(path:str) -> UploadFile:
    filename = pathlib.Path(path).name
    file_bytes = pathlib.Path(path).read_bytes()
    file_stream = io.BytesIO(file_bytes)
    return StarletteUploadFile(filename=filename, file=file_stream)



@qa_router.post("/agent/db_agent", summary="数据库助手Agent")
async def handler(task_id: str = Body(...), query: str = Body(...), history: List[str] = Body(...), thing_pattern: bool = Body(), user_id: str = Body(...)):
    try:
        subscription, references, data = await db_agent_stream(task_id, user_id, query, history, thing_pattern)
        return StreamingResponse(stream_generator(subscription, json.dumps(references, ensure_ascii=False),
                                                  query, data, task_id, user_id),
                                 media_type='text/event-stream')
    except Exception as e:
        traceback.print_exc()
        return {"detail": str(e), "status_code": 500}

@qa_router.post("/agent/knowledge_agent", summary="文档库助手Agent")
async def handler(package_id: str = Body(...), task_id: str = Body(...), query: str = Body(...), history: List[str] = Body(...), thing_pattern: bool = Body(), user_id: str = Body(...)):
    try:
        subscription, references, data = await knowledge_agent_stream(package_id, task_id, user_id, query, history, thing_pattern)
        return StreamingResponse(stream_generator(subscription, json.dumps(references, ensure_ascii=False),
                                                  query, data, task_id, user_id),
                                 media_type='text/event-stream')
    except Exception as e:
        traceback.print_exc()
        return {"detail": str(e), "status_code": 500}


@qa_router.post("/agent/knowledge_file_agent", summary="文档文件助手Agent")
async def handler(ids: List[str] = Body(..., embed=True), task_id: str = Body(...), query: str = Body(...), history: List[str] = Body(...), thing_pattern: bool = Body(), user_id: str = Body(...)):
    try:
        subscription, references, data = await knowledge_file_agent_stream(ids, task_id, user_id, query, history, thing_pattern)
        return StreamingResponse(stream_generator(subscription, json.dumps(references, ensure_ascii=False),
                                                  query, data, task_id, user_id),
                                 media_type='text/event-stream')
    except Exception as e:
        traceback.print_exc()
        return {"detail": str(e), "status_code": 500}

@qa_router.post("/agent/report_agent", summary="年度报告助手Agent")
async def handler(task_id: str = Body(...), query: str = Body(...), thing_pattern: bool = Body(), user_id: str = Body(...)):
    try:
        subscription, references, data = await report_agent_stream(task_id, user_id, query, thing_pattern)
        return StreamingResponse(stream_generator(subscription, json.dumps(references, ensure_ascii=False),
                                                  query, data, task_id, user_id),
                                 media_type='text/event-stream')
    except Exception as e:
        traceback.print_exc()
        return {"detail": str(e), "status_code": 500}

@qa_router.post("/agent/week_agent", summary="周报助手Agent")
async def handler(task_id: str = Body(...), query: str = Body(...), thing_pattern: bool = Body(), user_id: str = Body(...)):
        try:
            subscription, references, data = await week_agent_stream(task_id, user_id, query, thing_pattern)
            return StreamingResponse(stream_generator(subscription, json.dumps(references, ensure_ascii=False),
                                                      query, data, task_id, user_id),
                                     media_type='text/event-stream')
        except Exception as e:
            traceback.print_exc()
            return {"detail": str(e), "status_code": 500}


@qa_router.post("/agent/template_agent", summary="模板助手Agent")
async def handler(task_id: str = Body(...), query: str = Body(...), thing_pattern: bool = Body(), user_id: str = Body(...),config_id: str = Body(...)):
        try:
            subscription, references, data = await template_agent_stream(task_id, user_id, query, thing_pattern,config_id)
            print("data111",data)
            return StreamingResponse(stream_generator(subscription, json.dumps(references, ensure_ascii=False),
                                                      query, data, task_id, user_id),
                                     media_type='text/event-stream')
        except Exception as e:
            traceback.print_exc()
            return {"detail": str(e), "status_code": 500}

@qa_router.post("/agent/jira_week_agent", summary="jira周报助手Agent")
async def handler(task_id: str = Body(...), query: str = Body(...), thing_pattern: bool = Body(), user_id: str = Body(...)):
        try:
            print("进来jira",flush=True)
            subscription, references, data = await generate_jira_week_report_all()
            print("data111",data,flush=True)
            return StreamingResponse(stream_generator(subscription, json.dumps(references, ensure_ascii=False),
                                                      query, data, task_id, user_id),
                                     media_type='text/event-stream')
        except Exception as e:
            traceback.print_exc()
            return {"detail": str(e), "status_code": 500}


@qa_router.post("/agent/request_agent", summary="需求助手Agent")
async def handler(task_id: str = Body(...), user_id: str = Body(...),query: str = Body(...), thing_pattern: bool = Body(),document_id:str = Body(...) ,token:str = Body(...)):
        try:
            print("进入需求助手agent",flush=True)
            await request_agent_stream(task_id,user_id,query,thing_pattern,document_id,token)
            print("已经保存需求相关文件",flush=True)
            return  {
                      "data":None,
                      "extendMap" : None,
                      "success":True,
                      "message":"ok",
                      "code" : 200,
                      "stateCode": 0
            }
        except Exception as e:
            traceback.print_exc()
            return {
                      "data":None,
                      "extendMap" : None,
                      "success":False,
                      "message":"失败",
                      "code" : 500,
                      "stateCode": 1
            }




@qa_router.post("/agent/mermaid_agent", summary="mermaid图表 Agent")
async def handler(task_id: str = Body(...), user_id: str = Body(...),query: str = Body(...), thing_pattern: bool = Body()):
        try:
            print("进入mermaid助手 生成图表",flush=True)
            subscription, references, data  = await mermaid_agent_stream(task_id,user_id,query,thing_pattern)
            return StreamingResponse(stream_generator(subscription, json.dumps(references, ensure_ascii=False),
                                                      query, data, task_id, user_id),
                                     media_type='text/event-stream')
        except Exception as e:
            traceback.print_exc()
            return {"detail": str(e), "status_code": 500}

@qa_router.post("/agent/contract_agent", summary="合同助手Agent")
async def handler(task_id: str = Body(...), query: str = Body(...), history: List[str] = Body(...), thing_pattern: bool = Body(), user_id: str = Body(),file: str = Body(...) ):
        try:
            print("合同助手", task_id, flush=True)
            save_file_dir = str(Path(__file__).parent.parent.parent / 'api' / 'static' / 'file' / file)
            print("保存合同相关文件" + save_file_dir)
            fileinput = get_upload_file_from_path(save_file_dir)
            json_result = await contract_agent_stream(task_id, user_id, query, history, thing_pattern,
                                                                     fileinput)
            return json_result
        except Exception as e:
            traceback.print_exc()
            return {"detail": str(e), "status_code": 500}
        #     print("合同助手",flush=True)
        #     #首先拿到合同返回值
        #
        #     subscription, references, data = await contract_agent_stream(task_id,user_id,query,thing_pattern)
        #     print("data111",data,flush=True)
        #     return StreamingResponse(stream_generator(subscription, json.dumps(references, ensure_ascii=False),
        #                                               query, data, task_id, user_id),
        #                              media_type='text/event-stream')
        # except Exception as e:
        #     traceback.print_exc()
        #     return {"detail": str(e), "status_code": 500}


@qa_router.post("/qa_desc", summary="获取数据库详细")
def handler(sql_query: Dict = Body(...), page: int = Body(1), page_size: int = Body(15)):
    try:
        result = get_table_info_by_sql_query(sql_query, page, page_size)
        return {'detail': {'result': result},'status_code': 200}
    except Exception as e:
        traceback.print_exc()
        return {"detail": str(e), "status_code": 500}


@qa_router.post("/get_status", summary="获取QA状态")
def handler(task_id: str = Body(...)):
    try:
        status = get_task_status_by_id(task_id)
        return {'detail': {'task_status': status}, 'status_code': 200}
    except Exception as e:
        traceback.print_exc()
        return {"detail": str(e), "status_code": 500}

@qa_router.post("/report", summary="上传报告")
async def handler(query: str = Body(...)):
    try:
        file_path = await generate_report(query,history=[])
        return FileResponse(file_path, media_type='application/octet-stream')
    except Exception as e:
        traceback.print_exc()
        return {"detail": str(e), "status_code": 500}




