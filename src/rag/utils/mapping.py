import datetime
import os

import requests
from typing import List
from rag.configs import app_config


RERANK_URL = app_config['RERANK_URL']
MAPPING_URL = app_config['MAPPING_URL']
TOKEN = app_config['TOKEN']

PROJECT_SOURCE = {'军委机关': ['1401_14001', '1401_14002', '1401_14003', '1401_14004'], '军委装备发展部': ['1401_14002'], '军委科技委': ['1401_14003'], '军委后勤保障部': ['1401_14004'], '各兵种及其他': ['1401_14005', '1401_14006', '1401_14007', '1401_14008', '1401_14009', '1401_14010', '1401_14011', '1401_14012', '1401_14013', '1401_14014', '1401_14015'], '陆军装备部': ['1401_14006'], '海军装备部': ['1401_14007'], '空军装备部': ['1401_14008'], '火箭军装备部': ['1401_14009'], '战略支援装备部': ['1401_14010'], '联勤保障部队': ['1401_14011'], '武警部队': ['1401_14012'], '战区': ['1401_14013'], '军事院校（科研院所和高校）': ['1401_14014'], '试验基地': ['1401_14015'], '国家部委': ['1401_14016', '1401_14017', '1401_14018', '1401_14019', '1401_14023'], '国防科工局': ['1401_14017'], '国家科技部': ['1401_14018'], '公安部': ['1401_14019'], '国家自然科学基金委': ['1401_14023'], '集团公司': ['1401_14020', '1401_14021'], '子集团及直管单位（含北方公司）': ['1401_14022'], '其他军工集团': ['1401_14024'], '地方科研院所和高校': ['1401_14025'], '地方企事业单位': ['1401_14026']}
PROJECT_SOURCE_ALIAS = {'军委': ['1401_14001', '1401_14002', '1401_14003', '1401_14004'], '装备发展部': ['1401_14002'], '科技委': ['1401_14003'], '后勤保障部': ['1401_14004'], '各兵种': ['1401_14005', '1401_14006', '1401_14007', '1401_14008', '1401_14009', '1401_14010', '1401_14011', '1401_14012', '1401_14013', '1401_14014', '1401_14015'], '陆军': ['1401_14006'], '海军': ['1401_14007'], '空军': ['1401_14008'], '火箭军': ['1401_14009'], '战略支援部队': ['1401_14010'], '联保部队': ['1401_14011'], '武警': ['1401_14012'], '': ['1401_14024'], '军校、军事院校': ['1401_14014'], '科工局': ['1401_14017'], '科技部': ['1401_14018'], '自然科学基金委': ['1401_14023'], '集团总部、集团': ['1401_14020', '1401_14021'], '子集团': ['1401_14022'], '高校': ['1401_14025'], '事业单位': ['1401_14026']}
SUGGEST_DEPARTMENT = ["装备研发部(装研部)", "综合计划处(计划处)", "体系与突击系统处(体突处)", "火力与防御系统处(火力处)", "弹箭与引信装备处(弹引处)", "网信与光电装备处(网电处)", "海军装备处(海军处)", "空军装备处(空军处)", "火箭军装备处(火箭军处)", "通用装备处(通用处)", "前沿创新处(前沿处)", "火炸药专项工作办公室(火专项)", "综合管理处(综合处)", "研发与工艺创新管理处(创新处)"]
LABEL = {'子集团级竞标': ['ZJTJJB'], '装研部级竞标': ['ZYBJJB'], '集团级竞标': ['JTJJB'], '重大工程子项': ['ZDGCZX'], '重大工程': ['ZDGC'], '科研生产交叉项目': ['kyscjc'], '拖期项目': ['TQXM']}
BIDDING = {'正在竞标': ['bidding'], '竞标成功': ['won'], '竞标失利': ['failed'], '准备竞标': ['preparing']}
SIGNIFICANCE = {'一般项目': ['3'], '装研部重点项目': ['4'], '集团重大项目': ['5']}
STATUS = {'论证': ['0'], '竞标': ['8'], '在研': ['1'], '已完成': ['5'], '中止关闭': ['6'], '在研拖期': ['9']}
TYPE = {'型号研制': ['1402_14027'], '预先研究': ['1402_14028', '1402_14029', '1402_14030', '1402_14031', '1402_14032', '1402_14033', '1402_14034', '1402_14035', '1402_14050'], '演示验证': ['1402_14029'], '预研背景': ['1402_14030'], '预研专项': ['1402_14031'], '共用技术': ['1402_14033'], '专用技术': ['1402_14034'], '应用创新（联合基金）': ['1402_14035'], '政策理论研究': ['1402_14050'], '预研基金': ['1402_14032'], '军委科技委前沿项目': ['1402_14036', '1402_14037', '1402_14038', '1402_14039', '1402_14040', '1402_14041', '1402_14056', '1402_14057', '1402_14094'], '战略先导': ['1402_14040'], '前沿创新': ['1402_14037'], '基础加强': ['1402_14039'], '应用推进': ['1402_14038'], '国家重大科技专项': ['1402_14041'], '国防科技交流合作专项': ['1402_14056'], '军事理论科研': ['1402_14057'], '技术引进': ['1402_14042'], '装备体系': ['1402_14043'], '军贸科研': ['1402_14044', '1402_14051', '1402_14052'], '军贸科研重点项目': ['1402_14051'], '军贸科研一般项目': ['1402_14052'], '科技开发费': ['1402_14045', '1402_14053', '1402_14054'], '技开费重大科技专项': ['1402_14053'], '技开费一般项目': ['1402_14054'], '科工局项目': ['1402_14046', '1402_14047', '1402_14048'], '技术基础': ['1402_14047'], '基础科研': ['1402_14048'], '横向项目（含军内科研）': ['1402_14049'], '自筹项目': ['1402_14055'], '科研采购': ['1402_14058']}
TYPE_ALIAS = {'型号、型号项目': ['1402_14027'], '预研、预研项目': ['1402_14028', '1402_14029', '1402_14030', '1402_14031', '1402_14032', '1402_14033', '1402_14034', '1402_14035', '1402_14050'], '': ['1402_14058'], '军科委': ['1402_14036', '1402_14037', '1402_14038', '1402_14039', '1402_14040', '1402_14041', '1402_14056', '1402_14057', '1402_14094'], '军贸': ['1402_14044', '1402_14051', '1402_14052'], '军贸重点': ['1402_14051'], '技开费': ['1402_14045', '1402_14053', '1402_14054'], '技开费重大专项': ['1402_14053'], '横向项目': ['1402_14049']}



def rerank(query: str, rerank_list: List[str], again_flag=False):
    if query in rerank_list:
        return query, rerank_list.index(query)
    data = {
        'query': query,
        'texts': rerank_list
    }
    resp = requests.post(RERANK_URL, json=data)
    resp = resp.json()
    print('rerank_resp: ',resp)
    rerank_scores = resp['scores']
    max_score = 0
    max_index = 0
    greater_than_zero_list = []
    for index, score in enumerate(rerank_scores):
        if score > 0:
            greater_than_zero_list.append(rerank_list[index])
        if score > max_score:
            max_score = score
            max_index = index
    if max_score > 2:
        other_list = [rerank_scores[i] for i in range(len(rerank_scores)) if i != max_index]
        avg_score = sum(other_list) / len(other_list)
        if len(greater_than_zero_list) < 2 or max_score - avg_score > 5:
            return rerank_list[max_index],max_index
        elif again_flag:
            return rerank(query, greater_than_zero_list, False)
        else:
            """都是大于0，rerank alias"""
            return '', None
    else:
        return '', None


def get_undertaking_unit(organization: str,_type: str) -> str:
    params = {
        'name': organization,
        'orgType': _type
    }
    cookie = {
        'access_token': TOKEN
    }
    try:
        resp = requests.get(MAPPING_URL, params=params, cookies=cookie)
        resp = resp.json()
        unit = resp['data'][0]
    except Exception as e:
        print(e)
        unit = ''

    if unit:
        return unit
    else:
        return ''


def get_organization_mapping(organizations: List[str]):

    mapping_result = []
   #TODO：明天要一下
    for organization in organizations:
        '''rerank判断是否位于项目来源中'''
        project_source,_ = rerank(organization, list(PROJECT_SOURCE.keys()), True)
        if project_source:
            mapping_result.append(organization)
        else:
            project_alias_source,_ = rerank(organization, list(PROJECT_SOURCE_ALIAS.keys()), True)
            if project_alias_source:
                mapping_result.append(project_alias_source)
            else:
                """rerank判断是否位于建议主管部门中"""
                suggest_department,_ = rerank(organization, SUGGEST_DEPARTMENT, True)
                if suggest_department:
                    mapping_result.append(suggest_department)
                # TODO：先屏蔽
                # else:
                #     """rerank判断是否位于承研单位  by api"""
                    undertaking_unit = get_undertaking_unit(organization)
                #     if undertaking_unit:
                #         mapping_result.append(undertaking_unit)

    return mapping_result



def get_normal_mapping(normal_mapping: List[str]):
    ret = {
        'label': [],
        'bidding': [],
        'significance': [],
        'status': [],
        'type': []
    }
    wait_mapping = []
    wait_mapping.extend(list(LABEL.keys()))
    wait_mapping.extend(list(BIDDING.keys()))
    wait_mapping.extend(list(SIGNIFICANCE.keys()))
    wait_mapping.extend(list(STATUS.keys()))
    wait_mapping.extend(list(TYPE.keys()))
    wait_mapping.extend(list(TYPE_ALIAS.keys()))

    for normal_list in normal_mapping:
        for normal in normal_list:
            result,_ = rerank(normal, wait_mapping, True)
            if result:
                if LABEL.get(result):
                    ret['label'].append(result)
                elif BIDDING.get(result):
                    ret['bidding'].append(result)
                elif SIGNIFICANCE.get(result):
                    ret['significance'].append(result)
                elif STATUS.get(result):
                    ret['status'].append(result)
                elif TYPE_ALIAS.get(result):
                    ret['type'].append(result)
                elif TYPE.get(result):
                    ret['type'].append(result)

    return ret

def _strftime(date):
    return date.strftime("%Y-%m-%d %H:%M:%S")

def get_project_date_mapping(project_date):
    date_len = len(project_date)
    try:
        if date_len == 1:
            cur_date = datetime.datetime.strptime(project_date[0], '%Y年%m月%d日')
            next_date = cur_date + datetime.timedelta(days=365, hours=23, minutes=59, seconds=59)
            return [_strftime(cur_date), _strftime(next_date)]
        else:
            ret = []
            for index, date in enumerate(project_date):

                date = datetime.datetime.strptime(date, '%Y年%m月%d日')
                if index > 0:
                    date = date + datetime.timedelta(hours=23, minutes=59, seconds=59)
                ret.append(_strftime(date))
            return ret
    except Exception as e:
        print(e)
        return ['2020年1月1日', '2025年1月1日']

