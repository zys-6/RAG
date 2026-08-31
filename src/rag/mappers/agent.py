import datetime

from pydantic import Field

from rag.mappers.sqlite_mappers import SqliteMapper
from rag.utils.utils import create_uuid


class Agent(SqliteMapper):
    id: str = Field(default_factory=lambda: 'agent-' + create_uuid(), description="Agent ID")
    agent_name: str = Field(description="Agent Name")
    agent_example: str = Field(description="Agent Example")
    agent_prompt: str = Field(description="Agent Prompt")
    description: str = Field(description="Agent Description")
    agent_temperature: float = Field(description="Agent Temperature")
    agent_type: str = Field(description="Agent type", default="common")
    create_time: datetime.datetime = Field(description="Create Time", default_factory=lambda: datetime.datetime.now())
    is_delete: bool = Field(description="Is Delete ?", default=False)
    icon: str = Field(description="icon Name",default="")


    @classmethod
    def get_single_agent(cls, is_dict=False, **kwargs):
        agent_list = Agent.get_by(is_dict=is_dict, **kwargs)
        if agent_list:
            return agent_list[0]
        else:
            return None

Agent.create_table()