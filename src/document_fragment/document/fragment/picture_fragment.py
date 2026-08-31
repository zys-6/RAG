from typing import List, Union

from .base import BaseFragment, FragmentType
from .utils import bytes2str


class PictureFragment(BaseFragment):
    type: str = FragmentType.PICTURE

    blob: Union[bytes, None]
    caption: str
    suffix: str

    def to_json(self,
                excludes: List[str] = None,
                includes: List[str] = None):
        ret_json = {}
        for key, val in self.__dict__.items():
            if ((excludes is None or key not in excludes) and
                    (includes is None or (not key.startswith("_") or key in includes))):
                if hasattr(val, "to_json"):
                    ret_json[key] = val.to_json()
                elif isinstance(val, bytes):
                    ret_json[key] = bytes2str(val)
                else:
                    ret_json[key] = val
        return ret_json
