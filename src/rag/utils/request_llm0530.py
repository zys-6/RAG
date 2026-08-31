import datetime
import logging
from typing import Dict, List

import openai
import requests

from rag.configs import app_config,prompt_config

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
LLM_ANSWER_SYSTEM_TEMPLATE_ = prompt_config['llm_answer_system_template_']
LLM_ANSWER_HUMAN_TEMPLATE_ = prompt_config['llm_answer_human_template_']
GENERATE_EXAMPLE_INPUT_PROMPT = prompt_config['generate_example_input_prompt']
GENERATE_EXAMPLE_INPUT_EXAMPLE = prompt_config['generate_example_input_example']
JUDGE_QUESTION_INTENT_API_PROMPT = prompt_config['judge_question_intent_api_prompt']
JUDGE_QUESTION_INTENT_API_EXAMPLE = prompt_config['judge_question_intent_api_example']
report_analysis_prompt = prompt_config['report_analysis_prompt']

openai_client = openai.AsyncClient(api_key=API_KEY,
                                   base_url=API_BASE_URL)

openai_client2 = openai.AsyncClient(api_key=API_KEY2,
                                   base_url=API_BASE_URL2)



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


def get_processing_count(sql_query: Dict, total_status: bool = True) -> Dict:
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
            ret = {{'name': '合计', 'value': value}}
        else:
            ret.update({'name': '合计', 'value': value})
    except Exception as e:
        ret = {}
        # logger.error(e)
    # print('result', str(ret))
    return ret


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
