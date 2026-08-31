from rag.mappers.agent import Agent
from rag.utils.request_llm import openai_client2, openai_client, MODEL_NAME2, MODEL_NAME
from rag.utils.utils import async_wrap


@async_wrap
def get_agent_list():
    agent_list = Agent.get_by(is_dict=True, is_delete="false")
    if agent_list:
        return agent_list
    else:
        return []

@async_wrap
def get_agent(agent_id: str):
    agent = Agent.get_single_agent(is_dict=True, id=agent_id)
    if agent:
        return 200, agent, 'success'
    else:
        return 409, {}, '目标agent不存在'


@async_wrap
def create_agent(name, prompt, agent_type, description: str = '', agent_example: str = '',
                 agent_temperature: float = 0.7,icon : str = ''):
    agent = Agent(agent_name=name, agent_type=agent_type, agent_prompt=prompt, description=description,
                  agent_example=agent_example, agent_temperature=agent_temperature,icon=icon)
    agent.update()
    return {
        'id': agent.id,
        'agent_name': agent.agent_name,
        'agent_type': agent.agent_type,
        'agent_prompt': agent.agent_prompt,
        'description': agent.description,
        'agent_example': agent.agent_example,
        'agent_temperature': agent.agent_temperature,
        'icon': agent.icon,
    }


@async_wrap
def delete_agent(agent_id: str):
    _agent = Agent.get_single_agent(id=agent_id)
    if _agent:
        _agent.delete()
        return '成功'
    else:
        return '目标Agent不存在'


@async_wrap
def update_agent(agent_id, agent_attr, agent_value):
    _agent = Agent.get_single_agent(id=agent_id)
    if _agent:
        if getattr(_agent, agent_attr):
            setattr(_agent, agent_attr, agent_value)
            return 200, Agent.get_single_agent(is_dict=True, id=agent_id)
        else:
            return 409, '目标Agent字段不存在'
    else:
        return 409, '目标Agent不存在'


async def agent_stream(agent_id: str, query: str, thing_pattern: bool):
    _agent = Agent.get_single_agent(id=agent_id)
    if _agent:
        agent_prompt = _agent.agent_prompt
        messages = [{
            "role": "system",
            "content": agent_prompt
        },
            {
                "role": "user",
                "content": 'question: ' + query
            }]
        if thing_pattern:
            llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                        model=MODEL_NAME2,
                                                                        stream=True,
                                                                        temperature=_agent.agent_temperature)
        else:
            llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                       model=MODEL_NAME,
                                                                       stream=True,
                                                                       temperature=_agent.agent_temperature)
        return llm_response
