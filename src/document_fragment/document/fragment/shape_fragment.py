from typing import Union

from .base import BaseFragment, FragmentType


class ShapeFragment(BaseFragment):
    type: str = FragmentType.SHAPE

    blob: Union[bytes, None]
    suffix: str
    caption: str

