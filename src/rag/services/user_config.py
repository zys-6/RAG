from rag.mappers.user_config import UserConfig
from rag.utils.utils import async_wrap
import datetime

@async_wrap
def get_user_config(user_config_id: str):
    user_config = UserConfig.get_single_user_config(is_dict=True, id=user_config_id)
    if user_config:
        return 200, user_config, 'success'
    else:
        return 409, {}, '目标agent不存在'


@async_wrap
def get_user_config_list():
    user_config_list = UserConfig.get_by(is_dict=True, is_delete="false")
    if user_config_list:
        return user_config_list
    else:
        return []

@async_wrap
def get_user_config_list_by_user_id(user_id: str):
    user_config_list = UserConfig.get_by(is_dict=True, user_id=user_id)
    if user_config_list:
        return 200, user_config_list, 'success'
    else:
        return 409, {}, '目标配置文件不存在'


@async_wrap
def create_user_config(user_id, config_json,config_name):
    userconfig = UserConfig(user_id=user_id, config_json=config_json,config_name=config_name)
    userconfig.update()
    return {
        'id': userconfig.id,
        'user_id': userconfig.user_id,
        'config_name': userconfig.config_name,
        'config_json': userconfig.config_json,
        'create_time': userconfig.create_time,
        'modify_time': userconfig.modify_time
    }


@async_wrap
def delete_user_config(user_config_id: str):
    user_config = UserConfig.get_single_user_config(id=user_config_id)
    if user_config:
        user_config.delete()
        return '成功'
    else:
        return '目标Config不存在'


@async_wrap
def update_user_config(user_config_id, user_id, config_json,config_name):
    _user_config = UserConfig.get_single_user_config(id=user_config_id)
    if _user_config:
        if getattr(_user_config, "config_json"):
            setattr(_user_config,  "config_json", config_json)
            setattr(_user_config, "config_name", config_name)
            setattr(_user_config, "modify_time", datetime.datetime.now())
            _user_config.update()
            return 200, UserConfig.get_single_user_config(is_dict=True, id=user_config_id)
        else:
            return 409, '目标Config字段不存在'
    else:
        return 409, '目标Config不存在'



