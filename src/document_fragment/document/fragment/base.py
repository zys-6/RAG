from typing import List, Dict

from pydantic import BaseModel, Field

from .utils import bytes2str


class FragmentLevel:
    PARAGRAPH: str = "paragraph"
    SENTENCE: str = "sentence"


class FragmentType:
    CONTENT: str = "content"
    TABLE: str = "table"
    PICTURE: str = "picture"
    SHAPE: str = "shape"
    FORMULA: str = "formula"
    CHART: str = "chart"


class BaseFragment(BaseModel):
    type: str

    """PDF解析中存放页面的bbox等信息"""
    meta: Dict = Field(default_factory=dict)

    def to_dict(self,
                excludes: List[str] = None,
                includes: List[str] = None):
        ret_dict = {}
        for key, val in self.__dict__.items():
            if ((excludes is None or key not in excludes) and
                    (includes is None or (not key.startswith("_") or key in includes))):
                if hasattr(val, "to_dict"):
                    ret_dict[key] = val.to_dict()
                elif isinstance(val, list):
                    ret_dict[key] = [_val.to_dict() if hasattr(_val, "to_dict") else _val for _val in val]
                else:
                    ret_dict[key] = val
        return ret_dict

    def to_json(self,
                excludes: List[str] = None,
                includes: List[str] = None):
        ret_json = {}
        for key, val in self.__dict__.items():
            if ((excludes is None or key not in excludes) and
                    (includes is None or (not key.startswith("_") or key in includes))):
                if hasattr(val, "to_json"):
                    ret_json[key] = val.to_json()
                elif isinstance(val, list):
                    ret_json[key] = [_val.to_json() if hasattr(_val, "to_json") else _val for _val in val]
                elif isinstance(val, bytes):
                    ret_json[key] = bytes2str(val)
                else:
                    ret_json[key] = val
        return ret_json
