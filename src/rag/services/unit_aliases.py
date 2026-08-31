import json
import os
import pathlib
import sys

api_config_path = pathlib.Path(__file__).parent.parent / 'configs' / 'unit_aliases.json'



# -------------------- 工具函数 ----------------------
def load_units():
    with open(api_config_path, 'r', encoding='utf-8') as file:
        config = json.load(file)
    return config

def save_units(units):
    with open(api_config_path, 'w', encoding='utf-8') as file:
        json.dump(units, file, ensure_ascii=False, indent=4)

# -------------------- CRUD（带判重） ----------------------

def add_unit(name, aliases=None):
    if aliases is None:
        aliases = []

    units = load_units()

    name_lower = name.lower()
    aliases_lower = [a.lower() for a in aliases]

    # 判重
    for u in units:
        u_name = u["name"].lower()
        u_aliases = [a.lower() for a in u["aliases"]]

        if name_lower == u_name:
            raise ValueError(f"单位名称 '{name}' 已存在")

        if name_lower in u_aliases:
            raise ValueError(f"单位名称 '{name}' 已被用作其它单位的别名")

        if any(a == u_name for a in aliases_lower):
            raise ValueError(f"别名不能与已有单位名称重复：{u['name']}")

        if any(a in u_aliases for a in aliases_lower):
            raise ValueError(f"别名重复")

    # 创建新 unit
    new_id = max([u["id"] for u in units], default=0) + 1
    new_unit = {
        "id": new_id,
        "name": name,
        "aliases": aliases
    }

    units.append(new_unit)
    save_units(units)
    return new_unit


def delete_unit(unit_id: int):
    units = load_units()
    print("所有单位",units,flush=True)
    new_units = [u for u in units if u["id"] != unit_id]
    print("修单位",new_units,flush=True)
    save_units(new_units)
    return True


def update_unit(unit_id: int, name=None, aliases=None):
    units = load_units()

    for u in units:
        if u["id"] == unit_id:

            if name:
                u["name"] = name

            if aliases is not None:
                u["aliases"] = aliases

            save_units(units)
            return u

    return None


def search_unit(keyword: str):
    keyword = keyword.lower()
    units = load_units()

    result = []
    for u in units:
        if keyword in u["name"].lower() or \
           any(keyword in a.lower() for a in u["aliases"]):
            result.append(u)
    return result


