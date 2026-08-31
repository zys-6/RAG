import datetime
import random
import uuid

from pydantic import Field

from rag.mappers.sqlite_mappers import SqliteMapper


def create_uuid():
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(uuid.uuid1()) + str(random.random())))

class TeamInfo(SqliteMapper):
    id: str = Field(default_factory=lambda: 'team_info-' + create_uuid(), description="teamInfo")
    team_guid: str = Field(default='')
    org_name: str = Field(default='')
    user_name: str = Field(default='')
    unit: str = Field(default={})
    phone_number: str = Field(default='')
    description: str = Field(default='')
    creator_guid: str = Field(default='')
    create_time: datetime.datetime = Field(description="Create Time", default_factory=lambda: datetime.datetime.now())
    modify_time: datetime.datetime = Field(description="Modify Time", default_factory=lambda: datetime.datetime.now())


    @classmethod
    def get_team_info(cls, **kwargs):
        dialogue_list = cls.get_by(**kwargs)
        if dialogue_list:
            return dialogue_list
        else:
            return None


TeamInfo.create_table()