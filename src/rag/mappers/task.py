import datetime
import random
import uuid

from pydantic import Field

from rag.mappers.sqlite_mappers import SqliteMapper


def create_uuid():
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(uuid.uuid1()) + str(random.random())))

class Dialogue(SqliteMapper):
    id: str = Field(default_factory=lambda: 'dialogue-' + create_uuid(), description="Dialogue ID")
    query: str = Field(default='')
    llm_sql: str = Field(default='')
    llm_text: str = Field(default='')
    llm_data: dict = Field(default={})
    think_pattern: str = Field(default='')
    think_time: str = Field(default='0')
    api_name: str = Field(default='')
    maybe_query: list = Field(default=[])
    user_id: str = Field(description="User ID")
    type: str = Field(description="dialogue type", default='agent')
    status: str = Field(description="dialogue status", default='extract')
    create_time: datetime.datetime = Field(description="Create Time", default_factory=lambda: datetime.datetime.now())
    modify_time: datetime.datetime = Field(description="Modify Time", default_factory=lambda: datetime.datetime.now())


    def update_status(self, status: str):
        self.status = status
        self.update()

    @classmethod
    def get_single_dialogue(cls, **kwargs):
        dialogue_list = cls.get_by(**kwargs)
        if dialogue_list:
            return dialogue_list[0]
        else:
            return None

Dialogue.create_table()