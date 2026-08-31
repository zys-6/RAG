from typing import List

from pydantic import BaseModel, Field

from .base import BaseFragment, FragmentType


class HtmlTag(BaseModel):
    start_offset: int
    end_offset: int
    content: str
    type: str

    def to_json(self):
        return {"start_offset": self.start_offset,
                "end_offset": self.end_offset,
                "content": self.content,
                "type": self.type}


class ContentFragment(BaseFragment):
    type: str = FragmentType.CONTENT

    text: str
    outline: int = 0
    bold: bool = False
    font_size: int = 14
    font_name: str = "黑体"
    alignment: str = "LEFT"
    note_type: List[str] = Field(default_factory=list)

    tags: List[HtmlTag] = Field(default_factory=list)
