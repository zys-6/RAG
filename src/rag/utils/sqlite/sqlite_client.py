import datetime
import inspect
import json
import sqlite3
import traceback
from typing import List, Dict

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


class SQLiteClient:

    def __init__(self, db_path: str):
        self.db_path = db_path

    def create_table(self, table_name: str):
        sql = f'''CREATE TABLE IF NOT EXISTS {table_name}(p {table_name})'''
        self.execute(sql)

    def execute(self, sql: str):
        client = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        cur = client.cursor()
        try:
            results = cur.execute(sql).fetchall()
        except Exception as e:
            traceback.print_exc()
            print(sql, flush=True)
            results = []
        finally:
            client.commit()
            cur.close()
            client.close()
        return results

    def executemany(self, sql, data):
        client = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        cur = client.cursor()
        try:
            results = cur.executemany(sql, data)
        except Exception as e:
            traceback.print_exc()
            print(sql, flush=True)
            # print(data)
            results = []
        finally:
            client.commit()
            cur.close()
            client.close()
        return results

    def construct_where_sql(self, many: bool = False, **kwargs):
        if not many:
            where_sqls = []
            for key, val in kwargs.items():
                if val is not None:
                    if isinstance(val, List):
                        if len(val) != 1:
                            where_sqls.append(f"{key} IN {tuple(val)}")
                        else:
                            where_sqls.append(f"{key} = '{val[0]}'")
                    elif isinstance(val, str):
                        where_sqls.append(f"{key} = '{val}'")
                    else:
                        where_sqls.append(f"{key} = {val}")
            where_sql = " AND ".join(where_sqls)
            if where_sql.strip():
                return f" WHERE {where_sql}"
            return ""
        else:
            keys = []
            values = []
            for key, val in kwargs.items():
                if val is not None:
                    if isinstance(val, List):
                        if len(val) != 1:
                            keys.append(f"{key} IN ?")
                            values.append(f"{tuple(val)}")
                        else:
                            keys.append(f"{key} = ?")
                            values.append(f"{val[0]}")
                    elif isinstance(val, str):
                        keys.append(f"{key} = ?")
                        values.append(f"{val}")
                    else:
                        keys.append(f"{key} = ?")
                        values.append(f"{val}")
            where_sql = " AND ".join(keys)
            if where_sql.strip():
                return f" WHERE {where_sql}", values
            return "", []

    def construct_select_sql(self, cls, limit=None, **kwargs):
        sql = f"SELECT {','.join(self.get_cls_keys(cls))} FROM {cls.__name__.lower()} {self.construct_where_sql(**kwargs)}"
        if limit:
            sql = sql + " limit {}".format(limit)
        return sql

    def get_by_sql(self, sql: str):
        result = self.execute(sql)
        return result

    @classmethod
    def get_cls_keys(cls, class_):
        keys = list(map(lambda x: x if x != 'index' else '[index]', inspect.signature(class_).parameters.keys()))
        return keys

    @classmethod
    def convert(cls, class_, item):
        kvs = {k: v for k, v in zip(cls.get_cls_keys(class_), item)}
        field_names = cls.get_cls_keys(class_)
        for field_name in field_names:
            field_type = inspect.signature(class_).parameters[field_name].annotation
            if field_type not in (str, int, float, datetime.datetime):
                kvs[field_name] = json.loads(kvs[field_name])
            elif field_type == datetime.datetime:
                kvs[field_name] = datetime.datetime.strptime(kvs[field_name], DATETIME_FORMAT)
        return class_(**kvs)

    @classmethod
    def adapter(cls, class_, item):
        kvs = item.model_dump()
        field_names = cls.get_cls_keys(class_)
        for field_name in field_names:
            field_type = inspect.signature(class_).parameters[field_name].annotation
            if field_type not in (str, int, float, datetime.datetime):
                kvs[field_name] = json.dumps(kvs[field_name], ensure_ascii=False)
            elif field_type == datetime.datetime:
                kvs[field_name] = datetime.datetime.strftime(kvs[field_name], DATETIME_FORMAT)
        return kvs

    @classmethod
    def create_sql_by_cls(cls, class_, type_mapping=None):
        if type_mapping is None:
            type_mapping = dict()
        field_names = list(
            map(lambda x: x if x != 'index' else '[index]', inspect.signature(class_).parameters.keys()))
        fields = []
        for field_name in field_names:
            field_type = inspect.signature(class_).parameters[field_name].annotation
            NOT_NULL = "NOT NULL" if inspect.signature(class_).parameters[field_name].default != inspect._empty or \
                                     inspect.signature(class_).parameters[field_name].default is not None else ""
            if field_type == str:
                fields.append(f"{field_name} {type_mapping.get(field_name, 'VARCHAR(255)')} {NOT_NULL}")
            elif field_type == int:
                fields.append(f"{field_name} {type_mapping.get(field_name, 'INT')} {NOT_NULL}")
            elif field_type == float:
                fields.append(f"{field_name} {type_mapping.get(field_name, 'FLOAT')} {NOT_NULL}")
            elif field_type == datetime.datetime:
                fields.append(f"{field_name} {type_mapping.get(field_name, 'VARCHAR(255)')} {NOT_NULL}")
            else:
                fields.append(f"{field_name} {type_mapping.get(field_name, 'TEXT')} {NOT_NULL}")
        return f"CREATE TABLE IF NOT EXISTS {class_.__name__}({', '.join(fields)});"

    def insert_one(self, cls, item: Dict):
        self.insert_many(cls, [item])

    def insert_many(self, cls, items: List[Dict]):
        keys = self.get_cls_keys(cls)
        vals = ",".join(["?"] * len(keys))
        sql = f"INSERT INTO {cls.__name__.lower()} ({','.join(keys)}) VALUES ({vals})"
        values = []
        for item in items:
            _values = []
            for key, val in item.items():
                if key == 'index': continue
                if val is not None:
                    _values.append(f"{val}")
                else:
                    _values.append(None)
            values.append(tuple(_values))
        self.executemany(sql, values)

    def update_one(self, cls, item: Dict):
        self.update_many(cls, [item])

    def drop_table(self, table_name: str):
        client = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        try:
            client.execute(f"""DROP TABLE IF EXISTS {table_name}""")
        except:
            traceback.print_exc()
        finally:
            client.commit()
            client.close()

    def update_many(self, cls, items: List[Dict]):
        keys = self.get_cls_keys(cls)
        values = []
        id_in_item = False
        for item in items:
            if 'id' in item:
                id_in_item = True
            _values = []
            for key, val in item.items():
                if key == 'index': continue
                if val is not None:
                    _values.append(f"{val}")
                else:
                    _values.append(None)
            if id_in_item:
                _values.append(item['id'])
            else:
                where_sql, where_values = self.construct_where_sql(**item, many=True)
                _values.extend(where_values)
            values.append(tuple(_values))
        sql = ",".join([f"{k}=?" for k in keys])
        if id_in_item:
            self.executemany(f"UPDATE {cls.__name__.lower()} SET {sql} WHERE id=?", values)
        else:
            self.executemany(f"UPDATE {cls.__name__.lower()} SET {sql} {where_sql}", values)

    def delete_by(self, cls, **kwargs):
        where_sql = self.construct_where_sql(**kwargs)
        sql = f"DELETE FROM {cls.__name__.lower()} {where_sql}"
        self.execute(sql)

    def construct_sql_by_body(self, cls, body, count=False):
        """需要对body进行分析，获取其中的信息
        size: limit
        from: offset
        must: AND
        terms: IN
        term: =
        match_phrase: like
        """
        other_sqls = []
        if 'size' in body:
            other_sqls.append(f"LIMIT {body['size']}")
        if 'from' in body:
            other_sqls.append(f"OFFSET {body['from']}")
        other_sql = " ".join(other_sqls)
        where_sqls = []
        if 'bool' in body['query']:
            and_where_sqls = []
            should_where_sqls = []
            if 'must' in body['query']['bool']:

                for must in body['query']['bool']['must']:
                    if 'term' in must:
                        k, v = list(must['term'].items())[0]
                        and_where_sqls.append(f"{k.replace('.keyword', '')}='{v}'")
                    elif 'terms' in must:
                        k, v = list(must['terms'].items())[0]
                        and_where_sqls.append(f"{k.replace('.keyword', '')} in " + (f"{tuple(v)}" if len(v) != 1
                                                                                    else f"('{v[0]}')"))
                    elif 'match_phrase' in must:
                        k, v = list(must['match_phrase'].items())[0]
                        and_where_sqls.append(f"{k} LIKE '%{v}%'")
                    elif 'bool' in must and 'should' in must['bool']:
                        _or_where_sqls = []
                        for _should in must['bool']['should']:
                            if 'match_phrase' in _should:
                                k, v = list(_should['match_phrase'].items())[0]
                                _or_where_sqls.append(f"{k} LIKE '%{v}%'")
                        if _or_where_sqls:
                            and_where_sqls.append("({})".format(" OR ".join(_or_where_sqls)))
                    else:
                        raise ValueError(body)

            elif 'should' in body['query']['bool']:

                for should in body['query']['bool']['should']:
                    if 'term' in should:
                        k, v = list(should['term'].items())[0]
                        should_where_sqls.append(f"{k.replace('.keyword', '')}='{v}'")
                    elif 'terms' in should:
                        k, v = list(should['terms'].items())[0]
                        should_where_sqls.append(f"{k.replace('.keyword', '')} in" + (f"{tuple(v)}" if len(v) != 1
                                                                                      else f"('{v[0]}')"))
                    elif 'match_phrase' in should:
                        k, v = list(should['match_phrase'].items())[0]
                        should_where_sqls.append(f"{k} LIKE '%{v}%'")
                    else:
                        raise ValueError(body)

            else:
                pass
            if 'filter' in body['query']['bool']:
                _should_where_sqls = []
                for _filter in body['query']['bool']['filter']:
                    _and_where_sqls = []
                    if 'range' in _filter:
                        for _range_key in _filter['range']:
                            if 'gte' in _filter['range'][_range_key]:
                                _and_where_sqls.append(f"{_range_key} >= '{_filter['range'][_range_key]['gte']}'")
                            if 'lte' in _filter['range'][_range_key]:
                                _and_where_sqls.append(f"{_range_key} <= '{_filter['range'][_range_key]['lte']}'")
                    if _and_where_sqls:
                        _should_where_sqls.append("(" + " AND ".join(_and_where_sqls) + ")")
                if _should_where_sqls:
                    and_where_sqls.append("(" + " OR ".join(_should_where_sqls) + ")")

            if and_where_sqls:
                where_sqls.append("(" + " AND ".join(and_where_sqls) + ")")
            if should_where_sqls:
                where_sqls.append("(" + " OR ".join(should_where_sqls) + ")")
        elif "terms" in body['query']:
            k, v = list(body['query']['terms'].items())[0]
            where_sqls.append(f"{k.replace('.keyword', '')} in " + (f"{tuple(v)}" if len(v) != 1
                                                                    else f"('{v[0]}')"))
        elif "term" in body['query']:
            k, v = list(body['query']['term'].items())[0]
            where_sqls.append(f"{k.replace('.keyword', '')}='{v}'")
        elif "match_phrase" in body['query']:
            k, v = list(body['query']['match_phrase'].items())[0]
            where_sqls.append(f"{k} LIKE '%{v}%'")
        elif "match_all" in body['query']:
            pass
        else:
            raise ValueError(body)
        where_sql = " WHERE " + " AND ".join(where_sqls) + " " + other_sql
        if where_sql.strip() == 'WHERE':
            where_sql = ""
        if count:
            sql = f"SELECT count(*) FROM {cls.__name__.lower()} {where_sql}"
        else:
            sql = f"SELECT {','.join(self.get_cls_keys(cls))} FROM {cls.__name__.lower()} {where_sql}"
        return sql
