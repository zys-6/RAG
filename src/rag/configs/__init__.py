import pathlib
import os

import yaml

def read_prompt_config():
    with open(pathlib.Path(__file__).parent / 'prompt_config.yaml', 'r', encoding='utf-8') as file:
        prompt_config = yaml.load(file, Loader=yaml.FullLoader)
    return prompt_config

def read_app_config():
    with open(pathlib.Path(__file__).parent / 'app_config_pro.yaml', 'r', encoding='utf-8') as file:
        app_config = yaml.load(file, Loader=yaml.FullLoader)
    for key, value in os.environ.items():
        if key in app_config:
            app_config[key] = value
    return app_config

prompt_config = read_prompt_config()
app_config = read_app_config()
