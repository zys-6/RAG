import traceback
from typing import List

import openai

from rag.configs import app_config, prompt_config

MODEL_NAME = app_config['MODEL_NAME']
API_KEY = app_config['API_KEY']
API_BASE_URL = app_config['API_BASE_URL']

knowledge_recommend_prompt = prompt_config['knowledge_recommend']

openai_client = openai.AsyncClient(api_key=API_KEY,
                                   base_url=API_BASE_URL)

async def generate_recommend(id2text: dict) -> str:
    content = '\n'.join(list(id2text.values()))[:2000]
    knowledge_recommend_template = knowledge_recommend_prompt.format(content=content)
    messages = [{
            "role": "user",
            "content": knowledge_recommend_template
        }]
    llm_response = await openai_client.chat.completions.create(messages=messages,
                                                               model=MODEL_NAME,
                                                               stream=False, temperature=0)
    try:
        resp_json = llm_response.choices[0].message.content.strip()
        recommend = eval(resp_json).get('questions', [])
    except Exception as e:
        print(e)
        traceback.print_exc()
        recommend = []
    return recommend