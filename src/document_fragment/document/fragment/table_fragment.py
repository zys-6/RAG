from typing import List

from pydantic import Field

from .base import BaseFragment, FragmentType


class TableFragment(BaseFragment):
    type: str = FragmentType.TABLE

    data: List[List[str]]
    caption: str = ""

    merge_cell: List = Field(default_factory=list)
    delete_cell: List = Field(default_factory=list)
    width: List[float] = Field(default_factory=list)

    def to_picture(self) -> bytes:
        """尝试调用chrome"""
        pass

    def to_html(self) -> str:
        pass
