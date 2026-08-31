import datetime
from typing import Dict

from rag.utils.utils import get_api_config, save_api_config, get_api_field_name_example, save_api_data, \
    generate_alias2name


def search_api_by_name(api_name):
    api_config = get_api_config()
    return api_config.get(api_name, {})


def get_all_apis():
    api_info = []
    config = get_api_config()
    for name, info in config.items():
        api_info.append({
            'name': name,
            'desc': info['info'].get('desc', ''),
            'url': info['info'].get('url',''),
            'create_time': info['info']['create_time'],
            'author': info['info']['author']
        })
    return api_info


def update_api_info(api_name, **info):
    config = get_api_config()
    api_config = config.get(api_name, {})
    if api_config:
        for key, value in info.items():
            api_attr = api_config['info'].get(key, '')
            if api_attr:
                api_config['info'][key] = value
        config[api_name] = api_config
        save_api_config(config)



def get_api_url(api_name):
    search_result = search_api_by_name(api_name)
    if search_result:
        return search_result.get('info',{}).get('url', '')
    else:
        # TODO:
        '''url不存在的情况'''
        return ''


def insert_api(data: Dict, author: str = 'admin'):
    api_config = get_api_config()
    api_name = ''
    for name, info in data.items():
        existing_info = info.get('info', {})
        api_name = name
        data[name]['info'] = {
        **existing_info,
        'create_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'author': author,
        }
    api_config.update(data)
    save_api_config(api_config)
    field_list = get_api_field_name_example(api_name)
    alias2name = generate_alias2name(field_list)
    save_api_data(api_name,{
        'name': api_name,
        'alias2name': alias2name,
        'name2index': {},
        'fields': field_list
    })

