import datetime

from pydantic import Field

from rag.mappers.sqlite_mappers import SqliteMapper
from rag.utils.utils import create_uuid


class UserConfig(SqliteMapper):
    id: str = Field(default_factory=lambda: 'userconfig-' + create_uuid(), description="Config ID")
    user_id: str = Field(description="User ID")
    config_name: str = Field(description="Config Name")
    config_json: str = Field(description="config_json")
    create_time: datetime.datetime = Field(description="Create Time", default_factory=lambda: datetime.datetime.now())
    modify_time: datetime.datetime = Field(description="Modify Time", default_factory=lambda: datetime.datetime.now())

    @classmethod
    def get_single_user_config(cls, is_dict=False, **kwargs):
        user_config_list = UserConfig.get_by(is_dict=is_dict, **kwargs)
        if user_config_list:
            return user_config_list[0]
        else:
            return None


UserConfig.create_table()