import asyncio
import json
import traceback
from typing import List, Dict
from fastapi import APIRouter, Body, HTTPException, Query
from starlette.responses import StreamingResponse

from rag.services.agent import get_agent_list, create_agent, delete_agent, update_agent, agent_stream, get_agent
from rag.utils.utils import construct_response

agent_router = APIRouter(prefix='/agent')


@agent_router.get('/list', summary='获取Agent列表')
async def handler():
    try:
        resp = await get_agent_list()
        return construct_response(data=resp, detail='成功')
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@agent_router.get('/get', summary='获取Agent详细')
async def handler(agent_id: str = Query(...)):
    try:
        status_code, resp, detail = await get_agent(agent_id)
        return construct_response(data=resp, detail=detail, status_code=status_code)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)

@agent_router.post('/create', summary='创建Agent')
async def handler(name: str = Body(...), agent_prompt: str = Body(...), description: str = Body(...),
                  agent_type: str = Body('common'), agent_example: str = Body(''),icon: str = Body(...),
                  agent_temperature: float = Body(0.7)):
    try:
        resp = await create_agent(name=name, prompt=agent_prompt, agent_type=agent_type, description=description,
                                  agent_example=agent_example, agent_temperature=agent_temperature, icon=icon)
        return construct_response(data=resp, detail='成功')
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@agent_router.delete('/delete', summary='删除Agent')
async def handler(agent_id: str = Body(...)):
    try:
        resp = await delete_agent(agent_id=agent_id)
        return construct_response(data={}, detail=resp)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


@agent_router.post('/update', summary='修改Agent')
async def handler(agent_id: str = Body(...), agent_attr: str = Body(...), agent_value: str = Body(...)):
    try:
        status_code, resp = await update_agent(agent_id, agent_attr, agent_value)
        return construct_response(data={}, detail=resp, status_code=status_code)
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)


async def stream_generator(subscription):
    answer = ""
    try:
        async for chunk in subscription:
            if chunk.choices[0].delta.content:
                answer += chunk.choices[0].delta.content
                yield "data: " + json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n\n"
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Stream timed out")

    yield "data: [DONE]"


@agent_router.post('/stream', summary="Agent对话")
async def handler(agent_id: str = Body(...), query: str = Body(...), thing_pattern: bool = Body(False)):
    try:
        subscription = await agent_stream(agent_id, query, thing_pattern)
        return StreamingResponse(stream_generator(subscription), media_type='text/event-stream')
    except Exception as e:
        print(e)
        traceback.print_exc()
        return construct_response(data={}, detail=str(e), status_code=500)
