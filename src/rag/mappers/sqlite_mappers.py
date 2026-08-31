from typing import List

from pydantic import BaseModel

from rag.utils.sqlite import sqlite_client


class SqliteMapper(BaseModel):

    @classmethod
    def create_table(cls):
        sql = sqlite_client.create_sql_by_cls(cls)
        sqlite_client.execute(sql)
        return sql

    @classmethod
    def convert(cls, item):
        """将字典转换为实例"""
        return sqlite_client.convert(cls, item)

    @classmethod
    def adapter(cls, item):
        """将实例转换为字典"""
        return sqlite_client.adapter(cls, item)

    @classmethod
    def get_by(cls, is_dict: bool = False, **kwargs) -> List:
        sql = sqlite_client.construct_select_sql(cls, **kwargs)
        if is_dict:
            ret = [cls.adapter(cls.convert(item)) for item in sqlite_client.execute(sql)]
        else:
            ret = [cls.convert(item) for item in sqlite_client.execute(sql)]
        return ret
    @classmethod
    def get_by_body(cls, body, count: bool = False):
        sql = sqlite_client.construct_sql_by_body(cls, body, count)
        if not count:
            ret = []
            for item in sqlite_client.execute(sql):
                ret.append(cls.convert(item))
        else:
            ret = sqlite_client.execute(sql)[0][0]
        return ret

    @classmethod
    def updates(cls, items):
        """检查存在性"""
        inserts = []
        updates = []
        for item in items:
            sql = sqlite_client.construct_select_sql(cls, id=item.id)
            if len(sqlite_client.execute(sql)) == 0:
                """新增"""
                inserts.append(cls.adapter(item))
            else:
                """更新"""
                updates.append(cls.adapter(item))
        if inserts:
            sqlite_client.insert_many(cls, inserts)
        if updates:
            sqlite_client.update_many(cls, updates)

        ids = [item.id for item in items]
        result_records = sqlite_client.executemany(cls, ids)
        return result_records

    def update(self):
        sql = sqlite_client.construct_select_sql(self.__class__, id=self.id)
        if len(sqlite_client.execute(sql)) == 0:
            """新增"""
            sqlite_client.insert_one(self.__class__, self.adapter(self))
        else:
            """更新"""
            sqlite_client.update_one(self.__class__, self.adapter(self))

    def delete(self):
        sqlite_client.delete_by(self.__class__, id=self.id)

    @classmethod
    def delete_by(cls, **kwargs):
        sqlite_client.delete_by(cls, **kwargs)

    def show_databases(self):
        sq


