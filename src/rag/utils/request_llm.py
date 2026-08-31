import datetime
import json
import logging
from typing import Dict, List
import re
import openai
import requests

from rag.configs import app_config,prompt_config
from datetime import date, timedelta

logger = logging.getLogger(__name__)


MODEL_NAME = app_config['MODEL_NAME']
API_KEY = app_config['API_KEY']
API_BASE_URL = app_config['API_BASE_URL']

MODEL_NAME2 = app_config['MODEL_NAME2']
API_KEY2 = app_config['API_KEY2']
API_BASE_URL2 = app_config['API_BASE_URL2']

MAPPING_URL = app_config['MAPPING_URL']
TOKEN = app_config['TOKEN']
BQ_DATA_DESC_URL = app_config['BQ_DATA_DESC_URL']
STATISTIC_URL = app_config['STATISTIC_URL']
MAYBE_QUESTION_PROMPT = prompt_config['maybe_question_prompt']
TASK_DIVIDE_PROMPT = prompt_config['task_divide_prompt']
EXTRACT_YEAR_PROMPT = prompt_config['extract_year_prompt']
MAPPING_TYPE_PROMPT = prompt_config['mapping_type_prompt']
MAPPING_TYPE_EXAMPLE = prompt_config['mapping_type_example']
GENERATE_QUESTION_PROMPT = prompt_config['generate_question_prompt']
GENERATE_TITLE_PROMPT = prompt_config['generate_title_prompt_2']
GENERATE_DELAY_PROMPT = prompt_config['generate_delay_prompt']
GENERATE_SUMMARY_PROMPT = prompt_config['generate_summary_prompt']
LLM_ANSWER_SYSTEM_TEMPLATE_ = prompt_config['llm_answer_system_template_']
LLM_ANSWER_HUMAN_TEMPLATE_ = prompt_config['llm_answer_human_template_']
GENERATE_EXAMPLE_INPUT_PROMPT = prompt_config['generate_example_input_prompt']
GENERATE_EXAMPLE_INPUT_EXAMPLE = prompt_config['generate_example_input_example']
JUDGE_QUESTION_INTENT_API_PROMPT = prompt_config['judge_question_intent_api_prompt']
JUDGE_QUESTION_INTENT_API_EXAMPLE = prompt_config['judge_question_intent_api_example']
report_analysis_prompt = prompt_config['report_analysis_prompt']
contract_prompt = prompt_config['contract_prompt']
contract_convert_prompt = prompt_config['contract_convert_prompt']
mermaid_prompt = prompt_config['mermaid_prompt']




openai_client = openai.AsyncClient(api_key=API_KEY,
                                   base_url=API_BASE_URL)

openai_client2 = openai.AsyncClient(api_key=API_KEY2,
                                   base_url=API_BASE_URL2)

BQ_DATA_NO_PAGE = app_config['BQ_DATA_NO_PAGE']

async def get_year_by_question(question):
    template = EXTRACT_YEAR_PROMPT.format(question=question,today=datetime.datetime.today(), last_year=datetime.datetime.now().year - 1)
    messages = [{
            "role": "user",
            "content": template
        }]
    llm_response = await openai_client.chat.completions.create(messages=messages,
                                                               model=MODEL_NAME,
                                                               stream=False, temperature=0)
    try:
        resp_json = llm_response.choices[0].message.content.strip()
        date = eval(resp_json)
        if not isinstance(date, list) or not date:
            date = ['2024-01-01 00:00:00', '2024-12-31 23:59:59']
    except Exception as e:
        logger.error(e)
        date = ['2024-01-01 00:00:00', '2024-12-31 23:59:59']
    return date


async def get_type_mapping(content: str, type_list: str) -> str:
    expend_template = MAPPING_TYPE_PROMPT.format(type_list=type_list) + '\t示例:' + MAPPING_TYPE_EXAMPLE
    messages = [{
            "role": "system",
            "content": expend_template
        },
        {
            "role": "user",
            "content": str(content)
    }]

    try:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME,
                                                                   stream=False, temperature=0.2)
        resp_json = llm_response.choices[0].message.content.strip()
        type_mapping = eval(resp_json)
    except Exception as e:
        logger.error(e)
        type_mapping = {}
    return type_mapping


def get_index_by_bq_api(organization: str,_type: str) -> str:
    params = {
        'name': organization,
        'orgType': _type
    }
    cookie = {
        'access_token': TOKEN
    }
    try:
    #    print('org',organization)
        resp = requests.get(MAPPING_URL, params=params, cookies=cookie)
        resp = resp.json()
     #   print('get_index_resp:',resp)
        unit = resp['data'][0]
    except Exception as e:
        print(e)
        print('get_index_by_api_error',MAPPING_URL)
        unit = ''

    if unit:
        return unit
    else:
        return ''



async def generate_question_by_history(question, history):
    """TODO：把history改成上一次重新生成的问题"""
    if len(history) > 5:
        history = ["前{index}个问题：{question}".format(index=index+1, question=question) for index,question in enumerate(history)]
    generate_question_template = GENERATE_QUESTION_PROMPT.format(question=question, history=history)
    messages = [{
        "role": "system",
        "content": generate_question_template
    },
        {
            "role": "user",
            "content": 'question: ' + question + ' history: ' + str(history)
        }]
    llm_response = await openai_client.chat.completions.create(messages=messages,
                                                               model=MODEL_NAME,
                                                               stream=False, temperature=0.2)
    try:
        resp_json = llm_response.choices[0].message.content.strip()
        _question = eval(resp_json)
    except Exception as e:
        logger.error(e)
        return question
    if isinstance(_question, dict):
        return _question.get('result') or _question.get('question') or question
    if isinstance(_question, str):
        return _question
    return question


async def get_llm_response(question, data, stream=True, is_text=True):
    messages = [{"role": "system",
                 "content": LLM_ANSWER_SYSTEM_TEMPLATE_},
                {"role": "user", "content": LLM_ANSWER_HUMAN_TEMPLATE_.format(question=question,data=data)}]

    subscription = await openai_client.chat.completions.create(messages=messages,
                                                                   # model=os.environ['MODEL_NAME'],
                                                                   model=MODEL_NAME,
                                                                   stream=stream, max_tokens=2048, temperature=0.7)
    if is_text:
        return subscription.choices[0].message.content.strip()
    return subscription


# async def get_llm_other_response(question):
#     messages = [{'role': 'system',
#                  'content': '现在你的角色是中国兵器工业信息中心研发的数据库助手，你可以对用户的问题进行简单的回答'},
#                 {'role': 'user', 'content': f'用户问题：{question}'}]
#
#     json_data = {
#         'model': MODEL_NAME2,
#         'messages': messages,
#         'temperature': 0.7,
#         # 'max_tokens': ,
#         'stream': True
#     }
#     resp = requests.post(API_BASE_URL2, json=json_data, timeout=(3,100))
#     if resp.status_code == 200:
#         return resp
#     else:
#         return '服务错误'



async def get_llm_other_response(question, thing_pattern):
    messages = [{'role': 'system',
                 'content': '现在你的角色是中国兵器工业信息中心研发的数据库助手，你可以对用户的问题进行简单的回答'},
                {'role': 'user', 'content': f'用户问题：{question}'}]
    if thing_pattern:
        return await openai_client2.chat.completions.create(messages=messages, model=MODEL_NAME2, stream=True,
                                                           max_tokens=2048, temperature=0.7)
    else:
        return await openai_client.chat.completions.create(messages=messages, model=MODEL_NAME, stream=True,
                                                           max_tokens=2048, temperature=0.7)


async def get_sql_llm_response(question, data, sql_query, stream=True, thing_pattern=False, is_text=True):
    prompt = """
      # Objective:
      You are a data analyst, you need to analyze all aspects of user question, final query statements, and query results.
      First Answer the user question by query result(Text only), Second conduct a comprehensive analysis of the following data, including its basic characteristics, trends, outliers, and potential explanations, while clearly documenting your thought process at each step.
      # Rules:
      1. Answers are in markdown format and in chinese
      2. don't display user question
      3. The data unit is ten thousand yuan
      # Arguments:
      user question: {question}
      query results: {data}
    """
    messages = [{"role": "user",
                 "content": prompt.format(question=question,data=data)}]

    if thing_pattern:
        subscription = await openai_client2.chat.completions.create(messages=messages, model=MODEL_NAME2, stream=stream,
                                                                   max_tokens=2048, temperature=0.7)
    else:
        subscription = await openai_client.chat.completions.create(messages=messages, model=MODEL_NAME, stream=stream,
                                                               max_tokens=2048, temperature=0.7)
    if is_text:
        return subscription.choices[0].message.content.strip()
    return subscription


async def get_docs_subscription(temperature: float,
                                template: str, thing_pattern=False):
    messages = [
        {
            'role': 'user',
            'content': template
        }
    ]
    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(model=MODEL_NAME2, temperature=temperature,
                                                                   messages=messages, stream=True)
    else:
        llm_response = await openai_client.chat.completions.create(model=MODEL_NAME, temperature=temperature,
                                                               messages=messages,stream=True)
    return llm_response



async def get_maybe_questions(question: str, api_name: str, category_schema: Dict) -> List[str]:

    maybe_question_template = MAYBE_QUESTION_PROMPT.format(question=question, category_schema=category_schema)
    messages = [{
        'role': 'user', 'content': maybe_question_template
    }]
    maybe_question_resp = await openai_client.chat.completions.create(messages=messages, model=MODEL_NAME, stream=False, temperature=0.2)
    try:
        maybe_questions_raw = maybe_question_resp.choices[0].message.content.replace('json', '')
        maybe_questions_json = eval(maybe_questions_raw)
        maybe_questions = maybe_questions_json.get('result', [])
    except Exception as e:
        logger.error(e)
        print('获取maybe_questions error')
        maybe_questions = []
    return maybe_questions


def get_processing_count(sql_query: Dict, total_status: bool = False) -> Dict:
    ret = {}
    value = 0
    print('年度报告sql:', sql_query)
    # print('年度报告地址:', STATISTIC_URL)
    resp = requests.post(STATISTIC_URL, json=sql_query, cookies={'access_token': TOKEN}).json()
    print('年度报告resp:', resp)
    try:
        for data in resp['data'][0]['data']:
            ret.update({'name': data['name'], 'value': data['value']})
            value += data['value']
        if total_status:
            print("true",flush=True)
            ret = {{'name': '合计', 'value': value}}
        else:
            print("false",flush=True)
            ret.update({'name': '合计', 'value': value})
    except Exception as e:
        ret = {}
        # logger.error(e)
    print('result', str(ret),flush=True)
    return ret



def get_week_processing_count(sql_query: Dict, total_status: bool = True) -> Dict:
    result = {}
    projectReport = {}
    value = 0
    result = []
    print('周报sql:', sql_query)
    # print('年度报告地址:', STATISTIC_URL)
    resp = requests.post(BQ_DATA_DESC_URL, json=sql_query, cookies={'access_token': TOKEN}).json()
    print('周报resp:', resp)
    try:
        for item in resp['data']:
            # 提取 projectInformation 的 name
            pi_name = item.get("projectInformation", {}).get("name")
            print('name1111',pi_name)
            # 处理 projectReport，假设键是 "projctReport"（可能拼写错误）
            pr_list = item.get("prjReport", [])  # 如果键名正确，改为 "projectReport"
            print('list',pr_list)
            if pr_list:
                 qualified_reports = [report for report in pr_list if report.get('report_status') == 'pass' and   report.get('report_type') == 'monthly']
                 print('quList',qualified_reports)
                 if qualified_reports:
        # 找到时间最新的报告
                     print('1111')
                     latest_qualified_report = max(qualified_reports, key=lambda x: x['report_time'])
                     print('latest',latest_qualified_report)
                     current_content = latest_qualified_report['report_current_content']
                     print('current',current_content)
                     next_content = latest_qualified_report['report_next_content']
                     print('next',next_content)
                     problem_content = latest_qualified_report['problem_cotent']
                     print('problem_content',problem_content)

                # 找到 report_time 最新的记录
               # latest_report = max(pr_list, key=lambda x: x["report_time"])
                #qualified_reports = [report for report in pr_list if report.get('report_status') == 'pass']
                #latest_report = max(latest_qualified_report, key=lambda x: x['report_time'])
                #print('reportNew',latest_report)
                #pr_name = latest_report["name"]
            else:
                report_name = None

            # 将结果存储为字典或元组，根据需要
            result.append({
                "项目名称": pi_name,
                "当前进展情况": current_content,
                "下期计划": next_content,
                "存在问题": problem_content
            })
        print("222222")
        # 打印结果
        for res in result:
            print(res)
    except Exception as e:
        result = {}
        # logger.error(e)
    # print('result', str(ret))
    return result




def get_week_problem_processing_count(sql_query: Dict, total_status: bool = True) -> Dict:
    # 获取当前日期
    today = date.today()

    # 计算当前月份的第一天
    start_of_month = today.replace(day=1)

    # 计算下个月的第一天（当前月的最后一天 + 1 天）
    next_month_first_day = start_of_month + timedelta(days=32)
    next_month_first_day = next_month_first_day.replace(day=1)
    result = {}
    projectReport = {}
    value = 0
    result = []

    result_resolve = []
    print('周报问题个数sql:', sql_query)
    # print('年度报告地址:', STATISTIC_URL)
    resp = requests.post(BQ_DATA_DESC_URL, json=sql_query, cookies={'access_token': TOKEN}).json()
    print('周报问题个数resp:', resp)
    resolved_problems_count = 0
    no_resolved_problems_count = 0

    problems_details = []

    try:
        # 假设your_data_list是您的数据列表，需要根据实际情况替换
        for item in resp['data']:
            pi_name = item.get("projectInformation", {}).get("name")
            print('name1111', pi_name)
            problem = item.get('problemManage', {})
            if problem.get('problem_status') == '3':
                resolved_problems_count += 1

                # 提取详细信息
                problem_name = problem.get('name', '')
                solution = problem.get('person_solution', '')
                responsible_person = problem.get('charge_person_text', '')
                problem_init_user= problem.get('problem_init_user', '')
                problem_init_time = problem.get('problem_init_time', '')
                # 将问题详情存储到列表中
                problems_details.append({
                    "问题状态": "已解决",
                    "问题名称": problem_name,
                    "解决方法": solution,
                    "负责人": responsible_person,
                    "提交人" : problem_init_user,
                    "发生时间": problem_init_time,
                })
            else:
                no_resolved_problems_count += 1

                # 提取详细信息
                problem_name = problem.get('name', '')
                solution = problem.get('person_solution', '')
                responsible_person = problem.get('charge_person_text', '')
                problem_init_user = problem.get('problem_init_user', '')
                problem_init_time = problem.get('problem_init_time', '')
                # 将问题详情存储到列表中
                problems_details.append({
                    "问题状态": "未解决",
                    "问题名称": problem_name,
                    "解决方法": solution,
                    "负责人": responsible_person,
                    "提交人": problem_init_user,
                    "发生时间": problem_init_time,
                })
    except Exception as e:
        print('发生错误:', str(e))

    problems_details.append({
        "解决问题总数": resolved_problems_count
    })
    print("详细信息",problems_details)

    return problems_details





def get_week_nomal_processing_count(sql_query: Dict, total_status: bool = True) -> Dict:
    # resp = requests.post("http://192.168.1.172/gateway/ebpAppSomRuntime/api/som-mgr-objects/query-not-page", json=sql_query, cookies={'access_token': TOKEN}).json()
    resp = requests.post(BQ_DATA_NO_PAGE, json=sql_query, cookies={'access_token': TOKEN}).json()

    return resp



def get_week_risk_processing_count(sql_query: Dict, total_status: bool = True) -> Dict:
    # 获取当前日期
    today = date.today()

    # 计算当前月份的第一天
    start_of_month = today.replace(day=1)

    # 计算下个月的第一天（当前月的最后一天 + 1 天）
    next_month_first_day = start_of_month + timedelta(days=32)
    next_month_first_day = next_month_first_day.replace(day=1)
    result = {}
    projectReport = {}
    value = 0
    result = []

    result_resolve = []
#    print('周报风险个数sql:', sql_query)
    # print('年度报告地址:', STATISTIC_URL)
    # BQ_DATA_DESC_URL
    # resp = requests.post("http://192.168.1.172/gateway/ebpAppSomRuntime/api/som-mgr-objects/query-not-page", json=sql_query, cookies={'access_token': TOKEN}).json()
    resp = requests.post(BQ_DATA_NO_PAGE, json=sql_query, cookies={'access_token': TOKEN}).json()

#    print('周报风险问题个数resp:', resp)
#     resolved_risks_count = 0
#     risk_details = []
#     risk_details_pending = []
#     no_resolved_risks_count = 0
#
#
#     try:
#         # 假设your_data_list是您的数据列表，需要根据实际情况替换
#         for item in resp['data']:
#             problem = item.get('riskManage', {})
#
#             risk_content = problem.get('risk_content', '')
#             orgization = problem.get('recognize_org', '')
#             recognize_user = problem.get('recognize_user', '')
#             #recognize_time= problem.get('recognize_time', '')
#
#             if problem.get('risk_status') == '3':
#                 resolved_risks_count += 1
#                 status = "已规避"
#             else:
#                 no_resolved_risks_count += 1
#                 status = "未规避"
#                 # 存储问题详情
#             risk_details.append({
#                  "是否规避": status,
#                  "风险名称": risk_content,
#                  "责任部门": orgization,
#                  "识别人": recognize_user,
#                 })
#     except Exception as e:
#         print('发生错误:', str(e))
#     risk_details.append({
#         "规避风险总数": resolved_risks_count,
#         "未规避风险总数": no_resolved_risks_count
#     })
# #    print("详细信息",risk_details)

    return resp


#
# def get_week_risk_processing_count(sql_query: Dict, total_status: bool = True) -> Dict:
#     # 获取当前日期
#     today = date.today()
#
#     # 计算当前月份的第一天
#     start_of_month = today.replace(day=1)
#
#     # 计算下个月的第一天（当前月的最后一天 + 1 天）
#     next_month_first_day = start_of_month + timedelta(days=32)
#     next_month_first_day = next_month_first_day.replace(day=1)
#     result = {}
#     projectReport = {}
#     value = 0
#     result = []
#
#     result_resolve = []
# #    print('周报风险个数sql:', sql_query)
#     # print('年度报告地址:', STATISTIC_URL)
#     resp = requests.post(BQ_DATA_DESC_URL, json=sql_query, cookies={'access_token': TOKEN}).json()
# #    print('周报风险问题个数resp:', resp)
#     resolved_risks_count = 0
#     risk_details = []
#     risk_details_pending = []
#     no_resolved_risks_count = 0
#
#
#     try:
#         # 假设your_data_list是您的数据列表，需要根据实际情况替换
#         for item in resp['data']:
#             problem = item.get('riskManage', {})
#
#             risk_content = problem.get('risk_content', '')
#             orgization = problem.get('recognize_org', '')
#             recognize_user = problem.get('recognize_user', '')
#             #recognize_time= problem.get('recognize_time', '')
#
#             if problem.get('risk_status') == '3':
#                 resolved_risks_count += 1
#                 status = "已规避"
#             else:
#                 no_resolved_risks_count += 1
#                 status = "未规避"
#                 # 存储问题详情
#             risk_details.append({
#                  "是否规避": status,
#                  "风险名称": risk_content,
#                  "责任部门": orgization,
#                  "识别人": recognize_user,
#                 })
#     except Exception as e:
#         print('发生错误:', str(e))
#     risk_details.append({
#         "规避风险总数": resolved_risks_count,
#         "未规避风险总数": no_resolved_risks_count
#     })
# #    print("详细信息",risk_details)
#
#     return risk_details





def get_week_delay_processing_count(sql_query: Dict, total_status: bool = True) -> Dict:
    result = {}
    projectReport = {}
    value = 0
    result = []
    print('拖期sql:', sql_query)
    # print('年度报告地址:', STATISTIC_URL)
    resp = requests.post(BQ_DATA_DESC_URL, json=sql_query, cookies={'access_token': TOKEN}).json()
    print('拖期resp:', resp)

    delay_count = 0
    try:
        for item in resp['data']:
            # 提取 projectInformation 的 name
            pi_name = item.get("projectInformation", {}).get("name")
            bool_delay = item.get("projectInformation", {}).get("bool_delay")
            if bool_delay=='1':
             delay_count += 1
             # 处理 projectReport，假设键是 "projctReport"（可能拼写错误）
             pr_list = item.get("prjReport", [])  # 如果键名正确，改为 "projectReport"
             print('list',pr_list)
             if pr_list:
                 qualified_reports = [report for report in pr_list if report.get('report_status') == 'pass' ]
                 print('quList',qualified_reports)
                 if qualified_reports:
        # 找到时间最新的报告
                     print('1111')
                     latest_qualified_report = max(qualified_reports, key=lambda x: x['report_time'])
                     print('latest',latest_qualified_report)
                     current_content = latest_qualified_report['report_current_content']
                     print('current',current_content)
                     next_content = latest_qualified_report['report_next_content']
                     print('next',next_content)
                     problem_content = latest_qualified_report['problem_cotent']
                     print('problem_content',problem_content)
             else:
                report_name = None

            # 将结果存储为字典或元组，根据需要
             result.append({
                "项目名称": pi_name,
                "当前进展情况": current_content,
                "下期计划": next_content,
                "存在问题": problem_content
             })
        print("222222")
        # 打印结果
        for res in result:
            print(res)
    except Exception as e:
        result = {}
    result.append({
        "拖期项目总数": delay_count,
    })
        # logger.error(e)
    # print('result', str(ret))
    return result





def get_week_contractInformation_processing_count(sql_query: Dict, total_status: bool = True) -> Dict:
    # 获取当前日期
    today = date.today()

    # 计算当前月份的第一天
    start_of_month = today.replace(day=1)

    # 计算下个月的第一天（当前月的最后一天 + 1 天）
    next_month_first_day = start_of_month + timedelta(days=32)
    next_month_first_day = next_month_first_day.replace(day=1)
    result = {}
    projectReport = {}
    value = 0
    result = []

    result_resolve = []
    print('周报风险个数sql:', sql_query)
    # print('年度报告地址:', STATISTIC_URL)
    resp = requests.post(BQ_DATA_DESC_URL, json=sql_query, cookies={'access_token': TOKEN}).json()
    print('周报风险问题个数resp:', resp)
    resolved_risks_count = 0
    risk_details = []
    risk_details_pending = []
    no_resolved_risks_count = 0


    try:
        # 假设your_data_list是您的数据列表，需要根据实际情况替换
        for item in resp['data']:
            contractInformation = item.get('contractInformation', {})
            #这是已经规避的风险
            if contractInformation.get('risk_status') == '3':
                resolved_risks_count += 1

                # 提取详细信息
                risk_content = contractInformation.get('risk_content', '')
                orgization = contractInformation.get('recognize_org', '')
                recognize_user = contractInformation.get('recognize_user', '')
                recognize_time= contractInformation.get('recognize_time', '')

                # 将问题详情存储到列表中
                risk_details.append({
                    "是否规避":"已规避",
                    "风险名称": risk_content,
                    "责任部门": orgization,
                    "识别人": recognize_user,
                    "报告时间": recognize_time,
                })


    except Exception as e:
        print('发生错误:', str(e))
    risk_details.append({
        "规避风险总数": resolved_risks_count,
        "未规避风险总数": no_resolved_risks_count
    })
    print("详细信息",risk_details)

    return risk_details


async def get_task_divide_from_question(question: str) -> List[str]:
    task_divide_template = TASK_DIVIDE_PROMPT.format(question=question)
    messages = [{
        'role': 'user', 'content': task_divide_template
    }]
    maybe_question_resp = await openai_client.chat.completions.create(messages=messages,
                                                                      model=MODEL_NAME,
                                                                      stream=False, temperature=0.2)
    try:
        questions_raw = maybe_question_resp.choices[0].message.content.replace('json', '')
        questions_json = eval(questions_raw)
        questions = questions_json.get('result', [])
    except Exception as e:
        logger.error(e)
        print('question 拆分 error')
        questions = []
    return questions


async def get_api_example_input(prompt_example):

    generate_example_input_template = GENERATE_EXAMPLE_INPUT_PROMPT + '\t示例:' + GENERATE_EXAMPLE_INPUT_EXAMPLE
    messages = [{
        "role": "system",
        "content": generate_example_input_template
    },
        {
            "role": "user",
            "content": str(prompt_example)
        }]
    llm_response = await openai_client.chat.completions.create(messages=messages,
                                                               model=MODEL_NAME,
                                                               stream=False, temperature=0.2)
    try:
        resp_json = llm_response.choices[0].message.content.strip()
        _question = eval(resp_json)
    except Exception as e:
        logger.error(e)
        _question = []
    return _question


async def get_question_intent_api(question, api_list):
    judge_question_intent_api_template = JUDGE_QUESTION_INTENT_API_PROMPT.format(api_list=api_list) + '\t示例:' + JUDGE_QUESTION_INTENT_API_EXAMPLE
    messages = [{
        "role": "system",
        "content": judge_question_intent_api_template
    },
        {
            "role": "user",
            "content": question
        }]
    llm_response = await openai_client.chat.completions.create(messages=messages,
                                                               model=MODEL_NAME,
                                                               stream=False, temperature=0.2)
    try:
        resp_json = llm_response.choices[0].message.content.strip()
        _question = eval(resp_json).get('result')
    except Exception as e:
        logger.error(e)
        _question = 'project_api'
    return _question


def get_table_info(new_query):
    resp = requests.post(BQ_DATA_DESC_URL, json=new_query)
    if resp.status_code != 200:
        return {}
    else:
        return resp.json()


async def generate_title_analysis(title, data_info, year, thing_pattern=False, stream=False):
    template = GENERATE_TITLE_PROMPT.format(title=title,data_info=data_info, year=year)
    messages = [{
            "role": "user",
            "content": template
        }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME2,
                                                                   stream=stream, temperature=0)
    else:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                               model=MODEL_NAME,
                                                               stream=stream, temperature=0)
    try:
        if stream:
            return llm_response
        else:
            resp_json = llm_response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(e)
        resp_json = ''
    return resp_json


async def generate_delay_analysis(title, data_info,  thing_pattern=False, stream=False):
    template = GENERATE_DELAY_PROMPT.format(title=title,data_info=data_info)
    messages = [{
            "role": "user",
            "content": template
        }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME2,
                                                                   stream=stream, temperature=0)
    else:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                               model=MODEL_NAME,
                                                               stream=stream, temperature=0)
    try:
        if stream:
            return llm_response
        else:
            resp_json = llm_response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(e)
        resp_json = ''
    return resp_json
async def generate_summary_analysis(title, data_info,  thing_pattern=False, stream=False):
    template = GENERATE_SUMMARY_PROMPT.format(title=title,data_info=data_info)
    messages = [{
            "role": "user",
            "content": template
        }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME2,
                                                                   stream=stream, temperature=0)
    else:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                               model=MODEL_NAME,
                                                               stream=stream, temperature=0)
    try:
        if stream:
            return llm_response
        else:
            resp_json = llm_response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(e)
        resp_json = ''
    return resp_json


async def generate_question_analysis(data_info, year, thing_pattern=False):
    template = report_analysis_prompt.format(report_data=data_info, year=year)
    messages = [{
        "role": "user",
        "content": template
    }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                    model=MODEL_NAME2,
                                                                    stream=True, temperature=0.3)
    else:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME,
                                                                   stream=True, temperature=0.3)
    return llm_response


async def generate_ocr_result(data_info, thing_pattern=False):
    data_info_str = str(data_info)
    messages = [{
        "role": "system",
        "content": "请忽略文字中think标签中的信息，直接输出结果"+data_info_str
    }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                    model=MODEL_NAME2,
                                                                    stream=True, temperature=0.3)
    else:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME,
                                                                   stream=True, temperature=0.3)
    return llm_response

async def generate_stream_result(data_info, thing_pattern=False):
    messages = [{
        "role": "system",
        "content": "直接返回以下字符串即可，字符串如下："+data_info
    }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                    model=MODEL_NAME2,
                                                                    stream=True, temperature=0.3)
    else:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME,
                                                                   stream=True, temperature=0.3)
    return llm_response

async def generate_ocr_org_result(data_info, thing_pattern=True):
    prompt = ""
    messages = [{
        "role": "system",
        "content": "将下面的文本解析成结构化 JSON，不要更改任何信息，每条记录包括： - 组织名称（多级用 / 分隔）如行政指挥系统/行政指挥  - 是否用户（所有填否）  - 姓名 -  - 所属单位 - 登录名（仅限用户） - 所属单位 - 部门 - 联系方式 - 上任日期 - 职责描述（如有则为 主任  副主任 或者成员等 如没有则空着） 成员行中如果有多个人共享同一个单位(单位是文本中括号中的内容)，需要拆成多条记录。，上述内容没有就空着，直接输出结果"+data_info
    }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                    model=MODEL_NAME2,
                                                                    stream=False, temperature=0.3)
    else:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME,
                                                                   stream=False, temperature=0.3)
    return llm_response


async def generate_ocr_team_result(data_info, thing_pattern=True):
    prompt = ""
    messages = [{
        "role": "system",
        "content": "将下面的文本解析成结构化 JSON，不要更改任何信息，每条记录包括： - org_name（多级用 / 分隔）如行政指挥系统/行政指挥    - user_name  - unit   - phone_number  - description（如有则为 主任  副主任 或者成员等 如没有则空着） 成员行中如果有多个人共享同一个单位(单位是文本中括号中的内容)，需要拆成多条记录。，上述内容没有就空着，直接输出结果"+data_info
    }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                    model=MODEL_NAME2,
                                                                    stream=False, temperature=0.3)
    else:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME,
                                                                   stream=False, temperature=0.3)
    return llm_response




async def generate_markdown_normal_result(data_info,prompt,thing_pattern=False):
    template = prompt.format(data_info=data_info)
    print("template",template)
    messages = [{
        "role": "system",
        "content": template
    }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                    model=MODEL_NAME2,
                                                                    stream=False, temperature=0.3)
    else:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME,
                                                                   stream=False, temperature=0.3)
    return llm_response.choices[0].message.content


async def generate_request_normal_result(data_info,prompt,thing_pattern=False):
    # template = prompt.format(data_info=data_info)
    print("template",data_info)
    messages = [{
        "role": "system",
        "content": data_info
    }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                    model=MODEL_NAME2,
                                                                    stream=False, temperature=0.3)
    else:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME,
                                                                   stream=False, temperature=0.3)
    return llm_response.choices[0].message.content


async def generate_mermaid_result(question, thing_pattern=False):
    template = mermaid_prompt.format(question=question)
    # print("template",template)
    messages = [{
        "role": "system",
        "content": template
    }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                    model=MODEL_NAME2,
                                                                    stream=True, temperature=0.3)
    else:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME,
                                                                   stream=True, temperature=0.3)
    return llm_response


async def generate_contract_result(question, ocr_text,thing_pattern=False):
    template = contract_prompt.format(ocr_text=ocr_text,question=question)
    print("template",template)
    messages = [{
        "role": "system",
        "content": template
    }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                    model=MODEL_NAME2,
                                                                    stream=False, temperature=0.3)
    else:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME,
                                                                   stream=False, temperature=0.3)
    return llm_response



#这个方法的目的是将源文件的文本进行处理得到需要的json格式
async def generate_contract_end_json_result(inputData, fieldMapping,thing_pattern=False):
    template = contract_convert_prompt.format(inputData=inputData,fieldMapping=fieldMapping)
    print("template",template)
    messages = [{
        "role": "system",
        "content": template
    }]
    print("thing_pattern",thing_pattern)

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                    model=MODEL_NAME2,
                                                                    stream=False, temperature=0.3)
    else:
        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME,
                                                                   stream=False, temperature=0.3)
    return llm_response




async def generate_jira_normal_result_report(data_info,prompt,thing_pattern=True):
    template = prompt.format(data_info=data_info)
    messages = [{
        "role": "system",
        "content": template
    }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME2,
                                                                   stream=False, temperature=0.3)
    else:

        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME,
                                                                   stream=False, temperature=0.3)
    return llm_response.choices[0].message.content



async def generate_jira_normal_result(data_info,prompt,thing_pattern=True):
    template = prompt.format(data_info=data_info)
    messages = [{
        "role": "system",
        "content": template
    }]

    if thing_pattern:
        llm_response = await openai_client2.chat.completions.create(messages=messages,
                                                                   model="qwen2.5-coder:14b",
                                                                   max_tokens=1500000222222,
                                                                   stream=False, temperature=0.3)
    else:

        llm_response = await openai_client.chat.completions.create(messages=messages,
                                                                   model=MODEL_NAME,
                                                                   stream=False, temperature=0.3)
    return llm_response.choices[0].message.content



# #原来可用
# MAX_PROMPT_CHARS = 4000  # 根据模型 token 限制调整
#
#
# async def generate_normal_result(data_info, prompt, thing_pattern=False):
#     """
#     根据 prompt 和数据调用大模型
#     - 自动切分 data_info 防止超长
#     - 支持 thing_pattern 切换不同 client/model
#     """
#     # 选择模型和 client
#     client = openai_client2 if thing_pattern else openai_client
#     model_name = MODEL_NAME2 if thing_pattern else MODEL_NAME
#
#     # 将 data_info 转成字符串
#     data_str = str(data_info)
#
#     # 如果太长则分块
#     chunks = [data_str[i:i+MAX_PROMPT_CHARS] for i in range(0, len(data_str), MAX_PROMPT_CHARS)]
#     results = []
#
#     for idx, chunk in enumerate(chunks, start=1):
#         # 构建 prompt
#         chunk_prompt = f"{prompt.format(data_info=chunk)}\n\n(第 {idx}/{len(chunks)} 块)"
#         messages = [{"role": "system", "content": chunk_prompt}]
#
#         # 调用 LLM（流式或非流式）
#         llm_response = await client.chat.completions.create(
#             messages=messages,
#             model=model_name,
#             stream=False,  # 如果要 stream 就改 True 并消费
#             temperature=0.3
#         )
#
#         # 从响应中取文本
#         content = llm_response.choices[0].message.content
#         results.append(content)
#
#         print("模型返回值 :", repr(results), flush=True)
#
#     # 如果有多块，最后合并结果
#     if len(results) > 1:
#         summary_prompt = "请基于以下分块分析结果生成总体结论：\n" + "\n".join(results)
#         messages = [{"role": "system", "content": summary_prompt}]
#         final_response = await client.chat.completions.create(
#             messages=messages,
#             model=model_name,
#             stream=False,
#             temperature=0.3
#         )
#         return final_response.choices[0].message.content
#
#     return results[0]


async def generate_graph_normal_result(data_info, prompt, thing_pattern=False):
    """
    根据 prompt 和数据调用大模型
    - 自动切分 data_info 防止超长
    - 支持 thing_pattern 切换不同 client/model
    """
    # 选择模型和 client
    client = openai_client2 if thing_pattern else openai_client
    model_name = MODEL_NAME2 if thing_pattern else MODEL_NAME

    # 将 data_info 转成字符串
    data_str = str(data_info)

    # 如果太长则分块
    chunks = [data_str[i:i+MAX_PROMPT_CHARS] for i in range(0, len(data_str), MAX_PROMPT_CHARS)]
    results = []

    for idx, chunk in enumerate(chunks, start=1):
        # 构建 prompt
        chunk_prompt = f"{prompt.format(data_info=chunk)}\n\n(第 {idx}/{len(chunks)} 块)"
        messages = [{"role": "system", "content": chunk_prompt}]

        # 调用 LLM（流式或非流式）
        llm_response = await client.chat.completions.create(
            messages=messages,
            model=model_name,
            stream=False,  # 如果要 stream 就改 True 并消费
            temperature=0.3
        )

        # 从响应中取文本
        content = llm_response.choices[0].message.content
        results.append(content)

        print("模型返回值 :", repr(results), flush=True)

    # 如果有多块，最后合并结果


    return results[0]

# 自己写的
# async def generate_json_normal_result(data_info, prompt, thing_pattern=False):
#     """
#     根据 prompt 和数据调用大模型
#     - 自动切分 data_info 防止超长
#     - 支持 thing_pattern 切换不同 client/model
#     """
#     # 选择模型和 client
#     client = openai_client2 if thing_pattern else openai_client
#     model_name = MODEL_NAME2 if thing_pattern else MODEL_NAME
#
#     # 将 data_info 转成字符串
#     data_str = str(data_info)
#
#     # 如果太长则分块
#     chunks = [data_str[i:i+MAX_PROMPT_CHARS] for i in range(0, len(data_str), MAX_PROMPT_CHARS)]
#     results = []
#
#     for idx, chunk in enumerate(chunks, start=1):
#         # 构建 prompt
#         chunk_prompt = f"{prompt.format(data_info=chunk)}\n\n(第 {idx}/{len(chunks)} 块)"
#         messages = [{"role": "system", "content": chunk_prompt}]
#
#         # 调用 LLM（流式或非流式）
#         llm_response = await client.chat.completions.create(
#             messages=messages,
#             model=model_name,
#             stream=False,  # 如果要 stream 就改 True 并消费
#             temperature=0.3
#         )
#
#         # 从响应中取文本
#         content = llm_response.choices[0].message.content
#         results.append(content)
#
#         print("模型返回值 :", repr(results), flush=True)
#         # 如果有多块，最后合并结果
#     if len(results) > 1:
#         summary_prompt = "请将所有json合并成一个大json并只返回json,不需要多余的数据 ：\n" + "\n".join(results)
#         messages = [{"role": "system", "content": summary_prompt}]
#         final_response = await client.chat.completions.create(
#             messages=messages,
#             model=model_name,
#             stream=False,
#             temperature=0.3
#         )
#         return final_response.choices[0].message.content
#
#     return results[0]



MAX_PROMPT_CHARS = 4000  # 根据模型 token 限制调整


def split_data_objects(data_list, max_chars):
    """
    按对象切分 data_list，保证每片不超过 max_chars
    """
    chunks, current, current_size = [], [], 0
    for obj in data_list:
        obj_str = json.dumps(obj, ensure_ascii=False)
        if current_size + len(obj_str) > max_chars and current:
            chunks.append(current)
            current, current_size = [], 0
        current.append(obj)
        current_size += len(obj_str)
    if current:
        chunks.append(current)
    return chunks


async def generate_normal_result(data_info, prompt, thing_pattern=False):
    """
    根据 prompt 和数据调用大模型
    - 自动切分 data_info["data"]
    - 每片提取关键字段
    - 最终合并成一个大 JSON
    """
    # 选择模型和 client
    client = openai_client2 if thing_pattern else openai_client
    model_name = MODEL_NAME2 if thing_pattern else MODEL_NAME

    # 只取 data 部分
    data_list = data_info.get("data", [])
    chunks = split_data_objects(data_list, MAX_PROMPT_CHARS)

    intermediate_results = []

    # 1. 分片处理
    for idx, chunk in enumerate(chunks, start=1):
        chunk_str = json.dumps(chunk, ensure_ascii=False)
        chunk_prompt = f"""
你是数据清洗助手。
下面是一部分原始数据，请你提取关键字段（例如 项目名称为projectInformation下的name
风险名称为riskManage的name
编号为riskManage的code
风险严重性为riskManage的risk_seriously（1为特别不严重  2为比较不严重）
风险状态为riskManage 的 risk_status（1为已发生  2为未发生  3为已规避）
风险说明为riskManage 的 risk_content 等），
输出为简洁的 JSON 数组，不要总结。

原始数据 (第 {idx}/{len(chunks)} 块)：
{chunk_str}
"""
        messages = [{"role": "system", "content": chunk_prompt}]
        llm_response = await client.chat.completions.create(
            messages=messages,
            model=model_name,
            stream=False,
            temperature=0.2
        )
        content = llm_response.choices[0].message.content

        intermediate_results.append(content)

    # 2. 合并成最终 JSON
    summary_prompt = f"""
你是一个 JSON 清洗助手。
以下是多个分片的提取结果，请你合并它们，输出一个严格的 JSON 对象，格式为：
{{
  "data": [
    {{ "项目名称": "...", "风险名称": "...", "风险严重性": "...", "风险状态": "..." }},
    ...
  ]
}}

不要包含解释或多余内容，确保输出合法 JSON。

分片结果：
{json.dumps(intermediate_results, ensure_ascii=False)}
"""
    messages = [{"role": "system", "content": summary_prompt}]
    final_response = await client.chat.completions.create(
        messages=messages,
        model=model_name,
        stream=False,
        temperature=0.2
    )

    final_content = final_response.choices[0].message.content

    final_content = re.sub(r"```(?:json)?\n", "", final_content)
    final_content = re.sub(r"```", "", final_content)
    print("finalcontent:", final_content, flush=True)

    # 3. 尝试解析 JSON
    try:
        return json.loads(final_content)
    except Exception:
        print("⚠️ 最终 JSON 解析失败，原始输出：", final_content[:300])
        return {"data": []}
