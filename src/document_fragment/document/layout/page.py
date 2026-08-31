import copy
import re
import unicodedata
from typing import List

import cv2
import fitz
import numpy as np
from PIL import Image
from layoutparser.elements import TextBlock, Rectangle, Layout
from pydantic import BaseModel, Field, ConfigDict

from document_fragment.document.layout.config import LayoutConfig


class PageImage(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    content: bytes
    width: float
    height: float
    scale: float

    @property
    def size(self):
        return (int(self.width), int(self.height))

    @property
    def image(self):
        img = Image.frombytes("RGB", self.size, self.content)
        return img

    @property
    def image_cv2(self):
        img = self.image
        img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        return img


class Char(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    text: str
    horizontal: bool
    font_name: str
    font_size: float
    left: float
    right: float
    top: float
    bottom: float

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top


class Word(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    char_list: List[Char]
    scale: float = 1.0

    @property
    def block(self):
        rectangle = Rectangle(self.left, self.top, self.right, self.bottom)
        return TextBlock(block=rectangle,
                         text=self.text)

    @property
    def text(self):
        text = "".join([char.text for char in self.char_list])
        return unicodedata.normalize("NFKC", text)

    @property
    def left(self):
        return min(char.left for char in self.char_list)

    @property
    def right(self):
        return max(char.right for char in self.char_list)

    @property
    def top(self):
        return min(char.top for char in self.char_list)

    @property
    def bottom(self):
        return max(char.bottom for char in self.char_list)

    @property
    def font_name(self):
        font_name_list = [char.font_name for char in self.char_list]
        if font_name_list:
            return max(font_name_list, key=font_name_list.count)
        else:
            return ""

    @property
    def font_size(self):
        font_size_list = [char.font_size for char in self.char_list]
        if font_size_list:
            return max(font_size_list, key=font_size_list.count)
        else:
            return 7

    @property
    def horizontal(self):
        return self.char_list[0].horizontal

    def in_same_line(self, word, layout_config: LayoutConfig) -> bool:
        return (self.top < word.bottom and self.bottom > word.top and
                min(self.bottom - word.top, word.bottom - self.top) >=
                layout_config.word2line_y_overlap_rate * min(self.bottom - self.top, word.bottom - word.top)) and \
            abs(self.left - word.left) <= layout_config.word2line_x_tolerance


class Line(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    word_list: List[Word]
    scale: float = 1.0
    type: str = "text"
    index: int

    @property
    def font_size(self):
        font_size_list = [word.font_size for word in self.word_list]
        if font_size_list:
            return max(font_size_list, key=font_size_list.count)
        else:
            return 7

    @property
    def text(self):
        return re.sub("\s+", " ", " ".join([word.text for word in self.word_list]))

    @property
    def block(self) -> TextBlock:
        if self.word_list:
            block = copy.deepcopy(self.word_list[0].block)
            block.type = self.type
            for word in self.word_list[1:]:
                block = block.union(word.block, strict=False)
            block.text = self.text
            return block.scale(self.scale)


    @property
    def words_layout(self):
        blocks = [word.block for word in self.word_list if word.horizontal]
        for idx in range(len(blocks)):
            blocks[idx].id = idx
            blocks[idx] = blocks[idx].scale(self.scale)
        return Layout(blocks)

    @property
    def font_name(self):
        font_name_list = [word.font_name for word in self.word_list]
        if font_name_list:
            return max(font_name_list, key=font_name_list.count)
        else:
            return ""

    def is_neighbor(self, other: "Line", layout_config: LayoutConfig) -> bool:
        self_block = self.block
        other_block = other.block
        if self_block.coordinates[0] < other_block.coordinates[2] and \
                other_block.coordinates[0] < self_block.coordinates[2]:
            if abs(self_block.height - other_block.height) <= layout_config.line2block_h_diff_rate * min(
                    self_block.height,
                    other_block.height):
                if (self_block.coordinates[1] < other_block.coordinates[3] and
                        other_block.coordinates[1] < self_block.coordinates[3]):
                    return True
                if layout_config.line2block_y_gap_rate * min(self_block.height, other_block.height) > min(
                        abs(other_block.coordinates[1] - self_block.coordinates[3]),
                        abs(other_block.coordinates[3] - self_block.coordinates[1])
                ):
                    return True
        return False

    def is_aligned(self, other: "Line", layout_config: LayoutConfig) -> bool:
        self_block = self.block
        other_block = other.block
        x_align_tol = layout_config.line2block_x_align_rate * min(self_block.height, other_block.height)
        if abs(self_block.coordinates[0] - other_block.coordinates[0]) < x_align_tol:
            return True
        if abs(self_block.coordinates[2] - other_block.coordinates[2]) < x_align_tol:
            return True
        if abs(self_block.coordinates[2] + self_block.coordinates[0] - other_block.coordinates[2] -
               other_block.coordinates[0]) < 2 * x_align_tol:
            return True
        return False


class Text(BaseModel):
    line_list: List[Line]
    scale: float = 1.0

    @property
    def layout(self):
        blocks = []
        for line in self.line_list:
            blocks.append(line.block)
        return Layout(blocks)


class Structure(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    bbox: List[float]
    type: str
    line_list: List[Line] = Field(default_factory=list)
    text: str = ""
    heuristic_group: bool = False
    content: bytes = None

    @property
    def block(self) -> TextBlock:
        if self.heuristic_group:
            return self.block_from_line_list
        else:
            rect = Rectangle(self.bbox[0],
                             self.bbox[1],
                             self.bbox[2],
                             self.bbox[3])
            block = TextBlock(rect, type=self.type, text=self.text)
            return block

    @property
    def block_from_line_list(self) -> TextBlock:
        if self.line_list:
            block = copy.deepcopy(self.line_list[0].block)
            for line in self.line_list[1:]:
                block = block.union(line.block, strict=False)
                block.text += " " + line.text
            block.type = self.type
            return block


class LocalLayout(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    structure_list: List[Structure]
    width: float
    height: float

    @property
    def layout(self):
        blocks = []
        for idx in range(len(self.structure_list)):
            block = self.structure_list[idx].block
            block.id = idx
            blocks.append(block)
        return Layout(blocks)


class Page(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    fitz_page: fitz.Page
    image: PageImage
    text: Text = Field(default=None)
    layout: LocalLayout = Field(default=None)

