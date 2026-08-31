import datetime

from pydantic import Field

from rag.mappers.sqlite_mappers import SqliteMapper
from rag.utils.utils import create_uuid


class Package(SqliteMapper):
    id: str = Field(default_factory=lambda: 'package-' + create_uuid(), description="Package ID")
    name: str = Field(description="Package Name")
    type: str = Field(description="Package Name", default='person')
    user_id: str = Field(description="User ID")
    group_id: str = Field(description="Group ID", default='')
    description: str = Field(description="Package Description")
    knowledge_recommend: list = Field(description="Knowledge Recommend", default=[])
    create_time: datetime.datetime = Field(description="Create Time", default_factory=lambda: datetime.datetime.now())
    is_delete: str = Field(description="Is Delete ?", default="false")

    @classmethod
    def get_single_package(cls, is_dict=False, **kwargs):
        package_list = Package.get_by(is_dict=is_dict, **kwargs)
        if package_list:
            return package_list[0]
        else:
            return None

class File(SqliteMapper):
    id: str = Field(default_factory=lambda: 'file-' + create_uuid(), description="ID")
    file_id: str = Field(description="File ID")
    file_name: str = Field(description="File Name")
    file_path: str = Field(description="File Path")
    file_size: float = Field(description="File Size")
    file_type: str = Field(description="File type")
    user_id: str = Field(description="User ID")
    package_id: str = Field(description="Package ID")
    read: str = Field(default="true")
    write: str = Field(default="true")
    share: str = Field(default="true")
    status: str = Field(description="File status", default='upload')
    create_time: datetime.datetime = Field(description="Create Time", default_factory=lambda: datetime.datetime.now())
    is_delete: str = Field(description="Is Delete ?", default="false")

    @classmethod
    def get_single_file(cls, is_dict=False, **kwargs):
        file_list = File.get_by(is_dict=is_dict, **kwargs)
        if file_list:
            return file_list[0]
        else:
            return None

File.create_table()
Package.create_table()
if not Package.get_single_package(id='package-00000000000000000000000000000000'):
    Package(id='package-00000000000000000000000000000000', name='公共知识库', type='public', description='公开知识库，所有人可见', user_id='', group_id='').update()