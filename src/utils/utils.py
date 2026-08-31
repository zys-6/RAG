import hashlib

import yaml


def read_yaml(yaml_file, section):
    with open(yaml_file, 'r', encoding="utf-8") as file:
        cfg = yaml.load(file, Loader=yaml.FullLoader)
    return cfg[section]


def get_hash_code(content):
    return hashlib.md5(content).hexdigest()
