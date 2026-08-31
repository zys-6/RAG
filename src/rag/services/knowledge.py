import random
from typing import Optional

from api.services.utils import milvus_client
from rag.domain.chat_request import generate_recommend
from rag.mappers.knowledge import Package, File
from rag.utils.utils import async_wrap, requests_upload_file
from rag.configs import app_config

COLLECTION_NAME = app_config['MILVUS_COLLECTION']
MILVUS_URI = app_config['MILVUS_URI']

@async_wrap
def get_knowledge_tree(user_id: Optional[str], group_id: str):
    knowledge_tree = {'children': [], 'user_id': user_id}
    package_list = Package.get_by(name='公共知识库', type='public')
    if group_id:
        package_list.extend(Package.get_by(group_id=group_id, type='group'))
    if user_id:
        package_list.extend(Package.get_by(user_id=user_id, type='person'))
    else:
        package_list.extend(Package.get_by(type='person'))
    for package in package_list:
        package_info = {
            'id': package.id,
            'package_name': package.name,
            'package_type': package.type,
            'description': package.description,
            'create_time': package.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            'children': []
        }
        file_list = [{
            'id': _file.id,
            'file_name': _file.file_name,
            'file_path': '/static/file/' + _file.file_path,
            'file_type': _file.file_type,
            'file_size': _file.file_size,
            'status': _file.status,
            'read': _file.read,
            'write': _file.write,
            'share': _file.share,
        } for _file in File.get_by(package_id=package.id)]
        package_info['children'] = file_list
        knowledge_tree['children'].append(package_info)
    return knowledge_tree


@async_wrap
def get_package_list(user_id: Optional[str], group_id: str):
    package_list = Package.get_by(is_dict=True, name='公共知识库')
    if group_id:
        package_list.extend(Package.get_by(is_dict=True, group_id=group_id, type='group'))
    if user_id:
        package_list.extend(Package.get_by(is_dict=True, user_id=user_id, type='person'))
    else:
        package_list.extend(Package.get_by(is_dict=True, type='person'))
    package_list = list({package['id']: package for package in package_list}.values())
    return [{
        'id': package['id'],
        'package_name': package['name'],
        'package_type': package['type'],
        'description': package['description'],
        'user_id': package['user_id'],
        'group_id': package['group_id'],
        'create_time': package['create_time'],
    } for package in package_list]


@async_wrap
def get_knowledge(knowledge_id):
    _knowledge = Package.get_single_package(is_dict=True, id=knowledge_id)
    if _knowledge:
        _knowledge['package_name'] = _knowledge['name']
        del _knowledge['name']
        return 200, _knowledge, '成功'
    else:
        return 409, {}, '目标知识库不存在'


@async_wrap
def get_knowledge_recommend(knowledge_id):
    _knowledge = Package.get_single_package(id=knowledge_id)
    if _knowledge:
        if _knowledge.knowledge_recommend:
            knowledge_recommend = random.sample(_knowledge.knowledge_recommend, 5)
        else:
            knowledge_recommend = []
        return 200, knowledge_recommend, '成功'
    else:
        return 409, {}, '目标知识库不存在'


@async_wrap
def create_package(package_name, description, user_id, group_id):
    package_name_list = [_package.name for _package in Package.get_by()]
    if package_name in package_name_list:
        return 409, {}, 'Package 名称重复'
    if group_id:
        package = Package(name=package_name, type='group', group_id=group_id, description=description, user_id=user_id)
    else:
        package = Package(name=package_name, type='person', description=description, user_id=user_id)
    package.update()
    return 200, package.model_dump(), '成功'


@async_wrap
def update_package(package_id, package_name, description):
    package = Package.get_single_package(id=package_id)
    if package:
        package.name = package_name
        package.description = description
        package.update()
        return 200, '成功'
    else:
        return 409, 'Package 不存在'


@async_wrap
def delete_package(package_id):
    package = Package.get_single_package(id=package_id)
    if package:
        package.delete()
        return 200, '成功'
    else:
        return 409, 'Package 不存在'


@async_wrap
def upload_file(package_id, ftp_url, user_id):
    resp = requests_upload_file(package_id=package_id, ftp_url=ftp_url, user_id=user_id)
    return resp


@async_wrap
def get_file_list(package_id):
    file_list = File.get_by(package_id=package_id)
    if file_list:
        return [{
            'id': _file.id,
            'file_name': _file.file_name,
            'file_type': _file.file_type,
            'file_path': '/static/file/' + _file.file_path,
            'file_size': _file.file_size,
            'create_time': _file.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            'status': _file.status
        } for _file in file_list]
    else:
        return []


@async_wrap
def create_file(id, file_id, file_name, file_size, file_type,
                file_path,
                package_id, user_id):
    _file = File(id=id, file_id=file_id, file_name=file_name, file_size=file_size, file_type=file_type, file_path=file_path,
                 package_id=package_id,
                 user_id=user_id)
    _file.update()


async def knowledge_recommend(package_id):
    file_ids = [_file.file_id for _file in File.get_by(package_id=package_id)]
    if not file_ids:
        package = Package.get_single_package(id=package_id)
        package.knowledge_recommend = []
        package.update()
    else:
        output_fields = ["page_content", "document_id", "index"]
        filter = f"document_id in {file_ids}"
        result = milvus_client.query(COLLECTION_NAME, filter=filter, output_fields=output_fields)
        id2content = {}
        result = sorted(result, key=lambda x: x['index'])
        for item in result:
            page_content = item['page_content']
            document_id = item['document_id']
            info = id2content.get(document_id)
            if info:
                id2content[document_id].append(page_content)
            else:
                id2content[document_id] = [page_content]

        id2text = {}
        for id, page_content_list in id2content.items():
            id2text[id] = ' '.join(page_content_list)[200:400]

        recommends = await generate_recommend(id2text)
        package = Package.get_single_package(id=package_id)
        package.knowledge_recommend = recommends
        package.update()



@async_wrap
def update_file(package_id, file_id, _attr, _value):
    _file = File.get_single_file(id=file_id, package_id=package_id)
    if _file:
        if getattr(_file, _attr):
            setattr(_file, _attr, _value)
            _file.update()
        else:
            return 'File目标字段不存在'
    else:
        return 'File不存在'


@async_wrap
def delete_file(file_id):
    _file = File.get_single_file(id=file_id)
    if _file:
        package_id = _file.package_id
        _file.delete()
        return 200, package_id, '成功'
    else:
        return 409, '', 'Package 不存在'

async def update_maybe_question(package_id):
    file_ids = [_file.file_id for _file in File.get_by(package_id=package_id)]
    if not file_ids:
        package = Package.get_single_package(id=package_id)
        package.knowledge_recommend = []
        package.update()
    else:
        output_fields = ["page_content", "document_id", "index"]
        filter = f"document_id in {file_ids}"
        result = milvus_client.query(COLLECTION_NAME, filter=filter, output_fields=output_fields)
        id2content = {}
        result = sorted(result, key=lambda x: x['index'])
        for item in result:
            page_content = item['page_content']
            document_id = item['document_id']
            info = id2content.get(document_id)
            if info:
                id2content[document_id].append(page_content)
            else:
                id2content[document_id] = [page_content]

        id2text = {}
        for id, page_content_list in id2content.items():
            id2text[id] = ' '.join(page_content_list)[200:400]

        recommends = await generate_recommend(id2text)
        package = Package.get_single_package(id=package_id)
        package.knowledge_recommend = recommends
        package.update()


@async_wrap
def delete_milvus():
    from pymilvus import MilvusClient
    client = MilvusClient(uri=MILVUS_URI, tokem='root:Milvus')
    client.drop_collection(collection_name=COLLECTION_NAME)

@async_wrap
def get_milvus_file():
    from pymilvus import MilvusClient
    client = MilvusClient(uri=MILVUS_URI, tokem='root:Milvus')
    result = client.query(collection_name=COLLECTION_NAME,  limit=16384)
    id2name = {_doc['document_id']: _doc['file_name'] for _doc in result}
    return id2name
