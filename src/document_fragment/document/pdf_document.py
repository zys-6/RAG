import io
import logging
import re
from multiprocessing import Pool
from pathlib import Path
from typing import List, Union, IO, Dict, Tuple

import cv2
import fitz
import numpy as np
import requests
from PIL import Image
from layoutparser.elements import Rectangle, TextBlock

from .base import BaseDocument
from .fragment import PictureFragment, ContentFragment, TableFragment
from .layout.config import LayoutConfig
from .layout.model import get_table_extraction_pipeline, get_structure_engine, get_ocr_engine
from .layout.page import Page, Char, Word, Line, Text, Structure, LocalLayout, PageImage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PdfDocument(BaseDocument):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._url = kwargs.get("url", None)
        self._devices = kwargs.get("devices", [])
        self._max_threads = kwargs.get("max_threads", None)
        self._pdf = self._convert_to_pdf(self.filepath)
        self._page_count = self._pdf.page_count
        self._pages = self._convert_to_pages(self._pdf)
        self._start = int(kwargs.get("start", 0))
        self._end = int(kwargs.get("end", self._page_count))
        self._lang = kwargs.get("lang", "zh")
        self._layout_config = kwargs.get("layout_config", LayoutConfig())
        self._texts = []
        self._layouts = []
        self.fragments = self._convert_to_fragments()

    @classmethod
    def _convert_to_pdf(cls, file_path: Union[str, Path, bytes, IO]):
        if isinstance(file_path, (str, Path)):
            return fitz.open(file_path)
        elif isinstance(file_path, (bytes, IO)):
            return fitz.open("pdf", file_path)
        else:
            raise NotImplementedError

    @classmethod
    def _convert_to_pages(cls, pdf, start=0, end=None):
        if end is None:
            end = pdf.page_count
        pages = [pdf.load_page(i) for i in range(start, end)]
        page_images = cls._convert_pages_to_images(pages)
        pages = [Page(fitz_page=page, image=page_image) for page, page_image in zip(pages, page_images)]
        return pages

    def _get_fragments_from_url(self):
        fragments = []
        resp = requests.post(self._url, files={"file": ("pdf_file.pdf", self._content)})
        if resp.status_code == 200 and resp.json()['status_code'] == 200:
            result = resp.json()
            for item in result['data']:
                if item['type'] == 'figure':
                    img = self.cut_figure(item)
                    b = io.BytesIO()
                    img.save(b, "png")
                    b.seek(0)
                    fragments.append(PictureFragment(
                        blob=b.read(),
                        caption="",
                        suffix=".png"
                    ))
                    b.close()
                elif item['type'] in ("text", "reference", "figure_caption", "table_caption", "other"):
                    fragments.append(ContentFragment(
                        text=item['text']
                    ))
                elif item['type'] == "title":
                    fragments.append(ContentFragment(
                        text=item['text'],
                        outline=1
                    ))
                elif item['type'] == "table":
                    table = convert_html_to_list(item['text'])
                    if table:
                        merge_info, del_info = get_merge_del_info(table)
                        fragments.append(TableFragment(
                            data=table,
                            merge_cell=merge_info,
                            delete_cell=del_info,
                            width=[]
                        ))
                else:
                    logger.warning("Passing : {}".format(item['type'], item.get("text", "")))
        return fragments

    def cut_figure(self, page_data):
        with fitz.open('pdf', self._content) as pdf:
            page_data = page_data['display'][0]
            page = pdf[page_data['page_no']]
            page_rate = 2
            mat = fitz.Matrix(page_rate, page_rate)
            pm = page.get_pixmap(matrix=mat, alpha=False)
            if pm.width > 2000 or pm.height > 2000:
                page_rate = 1
                mat = fitz.Matrix(page_rate, page_rate)
                pm = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pm.width, pm.height], pm.samples)
            img = cv2.cvtColor(np.array(img), cv2.COLOR_BGR2RGB)
            img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            crop_box = (max(int(page_data['left'] * page_rate), 0),
                        max(int(page_data['top'] * page_rate), 0),
                        min(int(page_data['right'] * page_rate), pm.width),
                        min(int(page_data['bottom'] * page_rate), pm.height))
            img = img.crop(crop_box)
        return img

    @classmethod
    def _get_average_length(cls, width_list: List[float]) -> float:
        length = len(width_list)
        if length == 0:
            average_width = 0
        elif length < 5:
            average_width = sum(width_list) / length
        else:
            average_width = (width_list[length // 2 - 2] +
                             width_list[length // 2 - 1] +
                             width_list[length // 2] +
                             width_list[length // 2 + 1] +
                             width_list[length // 2 + 2]
                             ) / 5
        return average_width

    @classmethod
    def _convert_layouts_to_fragments(cls, page_list: List[Page], layout_list: List[LocalLayout]):
        fragments = []

        for page, layout in zip(page_list, layout_list):
            width_list = sorted([line.block.width for structure in layout.structure_list
                                 for line in structure.line_list if structure.type not in ("figure", "table")])
            height_list = sorted([line.block.height for structure in layout.struture_list
                                  for line in structure.line_list if structure.type not in ("figure", "table")])
            average_width = cls._get_average_length(width_list)
            for structure in layout.structure_list:
                block = structure.block_from_line_list
                if block is None:
                    block = structure.block
                if block is None:
                    continue

    @classmethod
    def _convert_table_html_to_fragment(cls, table_html: str, meta) -> TableFragment:
        return TableFragment(data=[], meta=meta)

    @classmethod
    def _is_connected(cls, last: Structure, current: Structure) -> bool:
        """
        判断两个文本是否应该相连，存在以下情况：

        1. last的最后一行和current的第一行的行高和宽度相似
        2. current的第一行较短（一般为句号等）和last最后一行（一般不为句号等）
        """

        # def _is_same_paragraph(line: Line, paragraph: List[Line]) -> bool:
        #     width_list = [(_line.block.coordinates[2] - _line.block.coordinates[0]) / 2 for _line in paragraph]
        #     width = (line.block.coordinates[2] - line.block.coordinates[0]) / 2
        #     mean = np.mean(width_list)
        #     std = np.std(width_list) + 10
        #     upper_bound = mean + 3 * std
        #     lower_bound = mean - 3 * std
        #     return lower_bound <= width <= upper_bound
        #
        last_line = last.line_list[-1]
        first_line = current.line_list[0]
        # if last.text.startswith("服务未来"):
        #     print(last)
        #
        # flag1 = re.search("[。.：:！!？?]$", first_line.text.strip()) and last_line is not None and \
        #         first_line.block.width < last_line.block.width
        # flag2 = _is_same_paragraph(first_line, [last_line])
        #
        # return (not flag1) or flag2

        last_coords = list(last_line.block.coordinates)
        first_coords = list(first_line.block.coordinates)
        """转换为同一坐标系下"""
        last_coords = [0, 0, last_coords[2] - last_coords[0], last_coords[3] - last_coords[1]]
        first_coords = [0, 0, first_coords[2] - first_coords[0], first_coords[3] - first_coords[1]]

        # if re.search("[。！？.!?]$", first_line.text.strip()) is not None and \
        #         re.search("[。！？.!?]$", last_line.text.strip()) is None:
        #     return True

        if re.search("[。.：:！!？?)）\"”'‘]$", last_line.text.strip()) is None:
            if abs(last_coords[2] - first_coords[2]) <= 0.15 * min(last_coords[2], first_coords[2]):
                return True
            else:
                if re.search("[。.：:！!？?)）\"”'‘]$", first_line.text.strip()) is not None:
                    return True

        return False

    @classmethod
    def _merge_lines_into_structure(cls, lines: List[Line], type: str, page: dict) -> Tuple[Structure, dict]:
        structure = Structure(bbox=[], text="", line_list=lines, type=type)
        block = structure.block_from_line_list
        structure.bbox = block.coordinates
        structure.text = block.text
        meta = {
            "blocks": [{
                "bbox": structure.bbox,
                "type": type,
                "page": page
            }]
        }
        return structure, meta

    @classmethod
    def _split_reference_structure(cls, structure: Structure, page) -> List[Tuple[Structure, dict]]:

        ret = []
        to_merge = []
        for line in structure.line_list:
            if re.search("^\[[0-9 ]+\]|[0-9]+\.", line.text.strip()) and to_merge:
                ret.append(cls._merge_lines_into_structure(to_merge, "reference", page))
                to_merge = []
            to_merge.append(line)
        if to_merge:
            ret.append(cls._merge_lines_into_structure(to_merge, "reference", page))
        return ret

    @classmethod
    def _merge_text_structures_into_content_fragment(cls, text_list: List[Tuple[Structure, Dict]]) -> ContentFragment:
        text = re.sub("\s+", " ", " ".join([_structure.text for _structure, _ in text_list]))
        meta = {
            "blocks": []
        }
        for _, _meta in text_list:
            meta['blocks'].extend(_meta['blocks'])
        return ContentFragment(text=text, meta=meta)

    @classmethod
    def _get_last_content_fragment(cls, fragments: List):
        for fragment in fragments[::-1]:
            if isinstance(fragment, ContentFragment):
                return fragment

    @classmethod
    def _get_type_from_meta(cls, meta):
        for block in meta['blocks']:
            return block['type']

    @classmethod
    def _get_outline_of_title(cls, text: str):
        matched = re.search("^([0-9.]+)", text)
        if matched is not None:
            return matched.group(1).count(".") + 1
        else:
            return 1

    @classmethod
    def _aggregate_layouts_into_fragments(cls, layout_list: List[LocalLayout]):
        """自己实现的段落连接"""
        fragments = []
        text_merge = []
        reference_merge = []
        last_text_structure = None
        need_plus_one = False
        footer_appended = False
        last_reference_structure = None

        for page_idx, layout in enumerate(layout_list):
            header_merge = []
            foot_merge = []
            header_insert_idx = len(fragments) + (1 if need_plus_one else 0)
            for structure in layout.structure_list:
                meta = {
                    "blocks": [{
                        "bbox": structure.bbox,
                        "page": {
                            "index": page_idx,
                            "width": layout.width,
                            "height": layout.height
                        },
                        "type": structure.type
                    }]
                }
                if structure.type == "figure":
                    fragments.append(PictureFragment(
                        blob=structure.content,
                        caption="",
                        suffix=".png",
                        meta=meta
                    ))
                elif structure.type == "table":
                    fragments.append(cls._convert_table_html_to_fragment(structure.text, meta=meta))
                elif structure.type == "header":
                    header_merge.append((structure, meta))
                elif structure.type == "footer":
                    foot_merge.append((structure, meta))
                elif structure.type in ("figure_caption", "table_caption"):
                    fragments.append(ContentFragment(
                        text=structure.text,
                        alignment="CENTER",
                        meta=meta
                    ))
                elif structure.type == "title":
                    if structure.text.strip() == '':
                        continue
                    if text_merge:
                        _fragment = cls._merge_text_structures_into_content_fragment(text_merge)
                        if fragments:
                            last_content_fragment = cls._get_last_content_fragment(fragments)

                            if last_content_fragment and cls._get_type_from_meta(last_content_fragment.meta) == 'footer' \
                                    and not footer_appended:
                                fragments.insert(-1, _fragment)
                                footer_appended = True
                            else:
                                fragments.append(_fragment)

                        else:
                            fragments.append(_fragment)
                        text_merge = []
                    fragments.append(ContentFragment(
                        text=structure.text,
                        outline=cls._get_outline_of_title(structure.text),
                        meta=meta
                    ))
                    last_text_structure = None
                elif structure.type == "reference":
                    if structure.text == "":
                        continue
                    _references = cls._split_reference_structure(structure, meta['blocks'][0]['page'])
                    if len(_references) == 0: continue
                    reference = _references[0]
                    if re.search("^\[[0-9 ]+\]", reference[0].text.strip()):
                        reference_merge.extend(_references)
                    elif reference_merge:
                        """和上一个进行连接"""
                        last_reference = reference_merge.pop(-1)
                        reference_merge.append(cls._merge_lines_into_structure(last_reference[0].line_list+reference[0].line_list,
                                                        "reference", meta['blocks'][0]['page']))
                        if _references[1:]:
                            reference_merge.extend(_references[1:])
                    else:
                        """直接放入"""
                        fragments.extend([ContentFragment(text=_ref[0].text, meta=_ref[1]) for _ref in _references])
                elif structure.type == "text":
                    if structure.text == "":
                        continue
                    """只针对跨页进行切分"""
                    if text_merge and last_text_structure and not cls._is_connected(last_text_structure, structure):
                        _fragment = cls._merge_text_structures_into_content_fragment(text_merge)
                        if fragments:
                            last_content_fragment = cls._get_last_content_fragment(fragments)
                            if last_content_fragment and cls._get_type_from_meta(last_content_fragment.meta) == 'footer' \
                                    and not footer_appended:
                                fragments.insert(-1, _fragment)
                                footer_appended = True
                            else:
                                fragments.append(_fragment)
                        else:
                            fragments.append(_fragment)
                        text_merge = []
                    text_merge.append((structure, meta))
                    last_text_structure = structure
                elif structure.type == "equation":
                    """TODO: pix2tex将公式转换为latex"""
                    if text_merge:
                        _fragment = cls._merge_text_structures_into_content_fragment(text_merge)
                        if fragments:
                            last_content_fragment = cls._get_last_content_fragment(fragments)

                            if last_content_fragment and cls._get_type_from_meta(last_content_fragment.meta) == 'footer' \
                                    and not footer_appended:
                                fragments.insert(-1, _fragment)
                                footer_appended = True
                            else:
                                fragments.append(_fragment)

                        else:
                            fragments.append(_fragment)
                        text_merge = []
                    fragments.append(PictureFragment(
                        blob=structure.content,
                        caption="",
                        suffix=".png",
                        meta=meta
                    ))
                    last_text_structure = None
                else:
                    raise ValueError(structure.type)

            if header_merge:
                fragments.insert(header_insert_idx, cls._merge_text_structures_into_content_fragment(header_merge))
                if text_merge:
                    need_plus_one = True
                else:
                    need_plus_one = False
            if foot_merge:
                fragments.append(cls._merge_text_structures_into_content_fragment(foot_merge))
                footer_appended = False

        if text_merge:
            fragments.append(cls._merge_text_structures_into_content_fragment(text_merge))

        if reference_merge:
            fragments.extend([ContentFragment(text=_ref[0].text, meta=_ref[1]) for _ref in reference_merge])

        """去除多余空格"""
        for fragment in fragments:
            if fragment.type == 'content':
                fragment.text = cls._remove_space(fragment.text)

        return fragments

    def _get_fragments_from_local(self):
        if self._max_threads is None:
            layout_list = self.sync_layout_analysis(self._start, self._end, self._lang)
        else:
            layout_list = self.layout_analysis(self._start, self._end, self._lang, self._max_threads)
        """将layout_list转换为fragments"""
        fragments = self._aggregate_layouts_into_fragments(layout_list)
        """\uD800至\uDFFF"""
        for fragment in fragments:
            if isinstance(fragment, ContentFragment):
                fragment.text = re.sub('[\uD800-\uDFFF]', "", fragment.text)
        return fragments

    @classmethod
    def _remove_space(cls, text):
        ret = []
        idx = 0
        text = re.sub("\s+", " ", text)
        while idx < len(text):
            curr = text[idx]
            if curr == " ":
                """判断前后是否都为英文"""
                if idx - 1 >= 0 and idx + 1 < len(text) and re.search("[a-zA-Z0-9]", text[idx - 1]) and \
                        re.search("[a-zA-Z0-9]", text[idx + 1]):
                    ret.append(curr)
            else:
                ret.append(curr)
            idx += 1
        return "".join(ret)

    def _convert_to_fragments(self):
        fragments = []
        if self._url is not None:
            fragments += self._get_fragments_from_url()
        else:
            fragments += self._get_fragments_from_local()
        return fragments

    @classmethod
    def _convert_pages_to_images(cls, pages: List[fitz.Page]) -> List[PageImage]:
        images = []
        for page in pages:
            scale = max(2000 // int(max(page.rect.width, page.rect.height)), 1)
            matrix = fitz.Matrix(scale, scale)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = PageImage(content=pixmap.samples,
                              width=pixmap.width,
                              height=pixmap.height,
                              scale=scale)
            images.append(image)
        return images

    @classmethod
    def _extract_chars_from_page(cls,
                                 page: Page) -> List[Char]:
        text_page = page.fitz_page.get_textpage()
        raw_dict = text_page.extractRAWDICT()
        char_list = []
        for block in raw_dict['blocks']:
            if block['type'] != 0:
                continue
            for line in block['lines']:
                """0: 水平, 1: 竖直"""
                if line['wmode'] == 0:
                    pass
                for span in line['spans']:
                    font = span['font']
                    size = span['size']
                    ascender = span['ascender']
                    descender = span['descender']
                    for char in span['chars']:
                        bottom = char['origin'][1] - size * descender / (ascender - descender)
                        top = bottom - size
                        char_list.append(Char(
                            text=char['c'],
                            horizontal=line['wmode'] == 0,
                            font_name=font,
                            font_size=size,
                            left=char['bbox'][0],
                            right=char['bbox'][2],
                            top=top,
                            bottom=bottom
                        ))
        return char_list

    @classmethod
    def __iter_chars_to_words(cls,
                              char_list: List[Char]):
        _chars = []

        for char in char_list:
            if char.text.isspace():
                if _chars:
                    yield _chars
                _chars = []
            else:
                _chars.append(char)

    @classmethod
    def __should_split(cls,
                       prev_char: Union[Char, None],
                       curr_char: Char,
                       layout_config: LayoutConfig) -> bool:
        if prev_char is not None and curr_char.text.isspace():
            return True
        elif prev_char is not None and prev_char.horizontal != curr_char.horizontal:
            return True
        elif prev_char is not None and prev_char.font_size != curr_char.font_size:
            return True
        elif prev_char is not None:
            inter_tol = layout_config.char2word_y_tolerance
            """为什么加入height？"""
            intra_tol = layout_config.char2word_x_tolerance_rate * max(
                curr_char.width, curr_char.height, prev_char.width, prev_char.height
            )
            if curr_char.horizontal:
                return (curr_char.left - prev_char.right > intra_tol) or (
                        abs(curr_char.top - prev_char.top) > inter_tol)
            else:
                return (curr_char.top - prev_char.bottom > intra_tol) or (
                        abs(curr_char.left - prev_char.left) > inter_tol)
                # """是否需要进行翻转"""
                # return (curr_char.top - prev_char.bottom > inter_tol) or
                # (abs(curr_char.left - prev_char.left) > intra_tol)
        else:
            return False

    @classmethod
    def _aggregate_chars_to_words(cls,
                                  char_list: List[Char],
                                  layout_config: LayoutConfig,
                                  scale: float = 1.0) -> List[Word]:
        """聚合策略
        """
        word_list = []
        _chars = []
        prev_char = None
        for curr_char in char_list:
            if cls.__should_split(prev_char, curr_char, layout_config):
                word_list.append(Word(char_list=_chars, scale=scale))
                _chars = []
            # if not curr_char.text.isspace():
            #     prev_char = curr_char
            # else:
            #     prev_char = None
            prev_char = curr_char
            """这里的空格需不需要加入"""

            _chars.append(curr_char)
        if _chars:
            word_list.append(Word(char_list=_chars, scale=scale))
        return word_list

    @classmethod
    def _extract_words_from_page(cls,
                                 page: Page,
                                 layout_config: LayoutConfig) -> List[Word]:
        chars = cls._extract_chars_from_page(page)
        """aggregate_char_into_word"""
        words = cls._aggregate_chars_to_words(chars, layout_config)
        return words

    @classmethod
    def _aggregate_words_to_lines(cls,
                                  word_list: List[Word],
                                  layout_config: LayoutConfig,
                                  scale: float = 1.0):
        class Item:
            def __init__(self, top, bottom, left):
                self.top = top
                self.bottom = bottom
                self.left = left

            def is_none(self):
                return self.top is None or self.bottom is None or self.left is None

        def get_words_length(words: List[Word]) -> int:
            return sum([len(word.text) for word in words])

        line_list = []
        _words = []
        prev = Item(None, None, None)
        for word in word_list:
            if prev.is_none():
                prev = Item(word.top, word.bottom, word.left)
                _words.append(word)
            elif word.in_same_line(prev, layout_config):
                _words_length = get_words_length(_words)
                prev.top = (prev.top * _words_length + len(word.text) * word.top) / (_words_length + len(word.text))
                prev.bottom = (prev.bottom * _words_length + len(word.text) * word.bottom) / (
                        _words_length + len(word.text))
                prev.left = word.left
                _words.append(word)
            else:
                """生成行"""
                line_list.append(Line(word_list=_words, scale=scale, index=len(line_list)))
                _words = [word]
                prev = Item(word.top, word.bottom, word.left)
        if _words:
            line_list.append(Line(word_list=_words, scale=scale, index=len(line_list)))

        return line_list

    @classmethod
    def _extract_lines_from_page(cls,
                                 page: Page,
                                 layout_config: LayoutConfig):
        words = cls._extract_words_from_page(page, layout_config)
        lines = cls._aggregate_words_to_lines(words, layout_config,
                                              scale=page.image.scale)
        return lines

    @classmethod
    def _extract_lines_from_page_by_ocr(cls,
                                        page: Page,
                                        layout_config: LayoutConfig,
                                        lang: str = "zh"):
        img = page.image.image_cv2
        ocr_engine = get_ocr_engine(lang=lang)
        ocr_result = ocr_engine.ocr(img, cls=False)[0]
        if ocr_result is None:
            return []
        lines = []
        for line_idx, (bbox, (text, score)) in enumerate(ocr_result):
            rect = Rectangle((bbox[0][0] + bbox[3][0]) / 2, (bbox[0][1] + bbox[1][1]) / 2,
                             (bbox[1][0] + bbox[2][0]) / 2, (bbox[3][1] + bbox[2][1]) / 2)
            lines.append(Line(word_list=[Word(char_list=[Char(text=text, horizontal=False,
                                                              font_name="",
                                                              font_size=7,
                                                              left=rect.coordinates[0],
                                                              right=rect.coordinates[2],
                                                              top=rect.coordinates[1],
                                                              bottom=rect.coordinates[3])])],
                              index=line_idx))

        return lines

    @classmethod
    def _extract_text_from_page(cls,
                                content: bytes,
                                page_idx: int,
                                layout_config: LayoutConfig):
        """首先尝试进行数据流格式读取"""
        pdf = cls._convert_to_pdf(content)
        page = cls._convert_to_pages(pdf, start=page_idx, end=page_idx + 1)[0]
        line_list = []
        if not layout_config.constraint or layout_config.constraint == 'digital':
            logger.info(f"Try extract text from page {page_idx} by digital")
            try:
                line_list += cls._extract_lines_from_page(page, layout_config)
            except Exception as e:
                logger.error(f"_extract_text_from_page: {e}")

        if (layout_config.constraint and layout_config.constraint == 'ocr') or not line_list:
            logger.info(f"Try extract text from page {page_idx} by ocr")
            line_list += cls._extract_lines_from_page_by_ocr(page, layout_config)
        logger.info("Extracted text from page {}".format(page_idx))
        return Text(line_list=line_list, scale=page.image.scale)

    @classmethod
    def _merge_table_into_structure(cls, table_result, structure_result, overlap_threshold=0.1, score_threshold=0.5):
        def _overlap(bbox_a, bbox_b, threshold=0.5):
            rect_a = fitz.Rect(list(bbox_a))
            rect_b = fitz.Rect(list(bbox_b))
            area_a = rect_a.get_area()
            if area_a == 0:
                return False
            return rect_a.intersect(rect_b).get_area() / area_a >= threshold

        def _overlaps(bbox, bbox_list, threshold=0.5):
            rect = fitz.Rect(list(bbox))
            area = 0
            if rect.get_area() == 0:
                return False
            for _bbox in bbox_list:
                rect = fitz.Rect(list(bbox))
                _rect = fitz.Rect(list(_bbox))
                _area = rect.intersect(_rect).get_area()
                area += _area
            return area / fitz.Rect(list(bbox)).get_area() >= threshold

        result = []
        for table in table_result:
            if not _overlaps(table['bbox'], [_structure['bbox'] for _structure in structure_result],
                             threshold=overlap_threshold):
                result.append(table)
        return structure_result + [{"bbox": table['bbox'], "type": "table"} for table in result]

    @classmethod
    def _cleaning_structures(cls, structures):
        """过滤overlap的structure， 去掉table结构"""
        ret = []
        rects = [Rectangle(*list(structure['bbox'])) for structure in structures]
        for i in range(len(structures)):
            not_in = True
            for j in range(len(structures)):
                if i == j: continue
                if TextBlock(rects[i]).is_in(TextBlock(rects[j]),
                                             soft_margin={"top": 3, "left": 3, "bottom": 3, "right": 3}):
                    not_in = False
                    break
            if not_in:
                ret.append(structures[i])

        return ret

    @classmethod
    def _extract_layout_from_page(cls,
                                  content: bytes,
                                  page_idx: int,
                                  lang: str):
        logger.info("Extracting layout from page {}".format(page_idx))
        pdf = cls._convert_to_pdf(content)
        page = cls._convert_to_pages(pdf, start=page_idx, end=page_idx + 1)[0]
        structure_engine = get_structure_engine(lang=lang)
        structure_result = structure_engine(page.image.image_cv2)
        structure_result = [structure for structure in structure_result if structure['type'] != 'table']
        table_engine = get_table_extraction_pipeline()
        table_result = table_engine.detect(page.image.image)
        if table_result:
            table_result = cls._cleaning_structures(table_result)
            result = cls._merge_table_into_structure(table_result, structure_result)
        else:
            result = structure_result
        """将result转换为structure_list"""
        structure_list = []
        for structure in result:
            structure_list.append(Structure(
                bbox=structure['bbox'],
                type=structure['type'],
            ))
            if structure['type'] in ('figure', 'equation'):
                structure_list[-1].content = cv2.imencode(".png", np.array(structure['img']))[1].tostring()
        logger.info("Extracted layout from page {}".format(page_idx))
        return LocalLayout(structure_list=structure_list, width=page.image.width, height=page.image.height)

    @classmethod
    def _aggregate_lines_into_structures(cls, lines: List[Line], layout_config: LayoutConfig):
        line_id_to_strucutre = dict()
        new_layout_blocks = []
        _blocks = [line.block for line in lines]
        for line_index in range(len(_blocks)):
            before_layout_block = None
            before_line_index = line_index - 1
            if before_line_index >= 0:
                if lines[before_line_index].is_neighbor(lines[line_index], layout_config):
                    before_layout_block = line_id_to_strucutre[before_line_index]
                    if len(before_layout_block.line_list) <= 1 or lines[before_line_index].is_aligned(
                            lines[line_index], layout_config
                    ):
                        before_layout_block.line_list.append(lines[line_index])
                    elif _blocks[before_line_index].coordinates[0] < _blocks[line_index].coordinates[0] and \
                            _blocks[before_line_index].coordinates[2] > _blocks[line_index].coordinates[2]:
                        before_layout_block.line_list.append(lines[line_index])
                    elif _blocks[before_line_index].coordinates[0] > _blocks[line_index].coordinates[0] and \
                            _blocks[before_line_index].coordinates[2] > _blocks[line_index].coordinates[2]:
                        before_layout_block.line_list.append(lines[line_index])
                    else:
                        before_layout_block = None

            if before_layout_block is None:
                before_layout_block = Structure(text=lines[line_index].text,
                                                type="text",
                                                bbox=[])
                new_layout_blocks.append(before_layout_block)
                before_layout_block.line_list.append(lines[line_index])
            line_id_to_strucutre[line_index] = before_layout_block

        for structure in new_layout_blocks:
            if structure is not None:
                structure.heuristic_group = True
                structure.bbox = list(structure.block_from_line_list.coordinates)
        return new_layout_blocks

    @classmethod
    def _split_projection_profile(cls, arr_values: np.ndarray, min_value: float, min_gap: float):
        # 投影值超过min_value的index列表
        arr_index = np.where(arr_values > min_value)[0]
        if not len(arr_index):
            return

        # find zero intervals between adjacent projections
        # |  |                    ||
        # ||||<- zero-interval -> |||||
        arr_diff = arr_index[1:] - arr_index[0:-1]
        arr_diff_index = np.where(arr_diff > min_gap)[0]
        arr_zero_intvl_start = arr_index[arr_diff_index]
        arr_zero_intvl_end = arr_index[arr_diff_index + 1]

        # convert to index of projection range:
        # the start index of zero interval is the end index of projection
        arr_start = np.insert(arr_zero_intvl_end, 0, arr_index[0])
        arr_end = np.append(arr_zero_intvl_start, arr_index[-1])
        arr_end += 1  # end index will be excluded as index slice

        return arr_start, arr_end

    @classmethod
    def _projection_by_bboxes(cls, boxes: np.array, axis: int) -> np.ndarray:
        assert axis in [0, 1]
        length = np.max(boxes[:, axis::2])  # 双引号：从双引号前的数开始，以双引号后面的数为间隔
        res = np.zeros(length, dtype=int)
        for start, end in boxes[:, axis::2]:
            res[start:end] += 1
        return res

    @classmethod
    def _recursive_cut(cls, boxes: np.ndarray, indices: np.ndarray, min_column_width):
        res = []
        if len(indices) <= 1 or np.min(boxes) < 0:  # 新的改动
            return [i for i in indices]
        assert len(boxes) == len(indices)
        # 在x轴方向上投影。首先依据x0进行排序
        _indices = boxes[:, 0].argsort()
        x_sorted_boxes = boxes[_indices]
        x_sorted_indices = indices[_indices]
        # 获取x轴方向上的投影直方图
        x_projection = cls._projection_by_bboxes(boxes=x_sorted_boxes, axis=0)
        # 合并直方图区块
        pos_x = cls._split_projection_profile(x_projection, min_value=0, min_gap=1)
        if not pos_x:  # 没有任何有效区块
            return [i for i in x_sorted_indices]
        arr_x0, arr_x1 = pos_x
        # 先进行竖直切分（最多切一下）
        flag = False
        for i in range(1, len(arr_x0)):
            if arr_x1[i] - arr_x0[i] > min_column_width:
                flag = True
        if len(arr_x0) > 1 and arr_x1[0] - arr_x0[0] > min_column_width and flag == True:  # 能竖直切割的话，首先竖直切割，再考虑两边区块的分别排序
            left_indices = (arr_x0[0] <= x_sorted_boxes[:, 0]) & (x_sorted_boxes[:, 0] < arr_x1[0])
            right_indices = ~left_indices
            _indices_list = [left_indices, right_indices]
            for _indices in _indices_list:
                x_sorted_boxes_trunk = x_sorted_boxes[_indices]
                x_sorted_indices_trunk = x_sorted_indices[_indices]
                res.extend(cls._recursive_cut(x_sorted_boxes_trunk, x_sorted_indices_trunk, min_column_width))
        else:
            _indices = boxes[:, 1].argsort()
            y_sorted_boxes = boxes[_indices]
            y_sorted_indices = indices[_indices]
            # 获取y轴方向上的投影直方图
            y_projection = cls._projection_by_bboxes(boxes=y_sorted_boxes, axis=1)
            # 合并直方图区块
            pos_y = cls._split_projection_profile(y_projection, min_value=0, min_gap=1)
            if not pos_y:
                return [i for i in y_sorted_indices]
            arr_y0, arr_y1 = pos_y
            if len(arr_y0) > 1:  # 可水平切分
                _indices_list = [((arr_y0[arr_idx] <= y_sorted_boxes[:, 1]) & (y_sorted_boxes[:, 1] < arr_y1[arr_idx]))
                                 for arr_idx in range(len(arr_y0))]
                temp_boxes = np.empty([0, 4], dtype=int)  # []
                temp_indices = np.empty(0, dtype=int)  # []
                for arr_idx in range(len(_indices_list)):
                    temp_indices = np.concatenate((temp_indices, y_sorted_indices[_indices_list[arr_idx]]), axis=0)
                    temp_boxes = np.concatenate((temp_boxes, y_sorted_boxes[_indices_list[arr_idx]]), axis=0)
                    # 看这些temp区块能否进行竖直切分
                    _indices = temp_boxes[:, 0].argsort()
                    temp_x_sorted_boxes = temp_boxes[_indices]
                    x_projection = cls._projection_by_bboxes(boxes=temp_x_sorted_boxes, axis=0)
                    pos_x = cls._split_projection_profile(x_projection, min_value=0, min_gap=1)
                    if not pos_x:  # 没有任何有效区块
                        break
                    arr_x0, arr_x1 = pos_x
                    if len(arr_x0) == 1 or not (
                            arr_x1[0] - arr_x0[0] > min_column_width and (arr_x1[-1] - arr_x0[1] > min_column_width)):
                        break
                arr_idx_split = [range(max(1, arr_idx)), range(max(1, arr_idx), len(_indices_list))]
                for arr_idx_range in arr_idx_split:
                    temp_boxes = np.empty([0, 4], dtype=int)  # []
                    temp_indices = np.empty(0, dtype=int)  # []
                    for new_arr_idx in arr_idx_range:
                        temp_indices = np.concatenate((temp_indices, y_sorted_indices[_indices_list[new_arr_idx]]),
                                                      axis=0)
                        temp_boxes = np.concatenate((temp_boxes, y_sorted_boxes[_indices_list[new_arr_idx]]), axis=0)

                    res.extend(cls._recursive_cut(temp_boxes, temp_indices, min_column_width))

            else:  # 水平、竖直均无法切分
                if len(arr_x0) > 1:
                    left_indices = (arr_x0[0] <= x_sorted_boxes[:, 0]) & (x_sorted_boxes[:, 0] < arr_x1[0])
                    right_indices = ~left_indices
                    _indices_list = [left_indices, right_indices]
                    for _indices in _indices_list:
                        x_sorted_boxes_trunk = x_sorted_boxes[_indices]
                        x_sorted_indices_trunk = x_sorted_indices[_indices]
                        res.extend(cls._recursive_cut(x_sorted_boxes_trunk, x_sorted_indices_trunk, min_column_width))
                    # return [i for i in x_sorted_indices]
                else:
                    return [i for i in y_sorted_indices]
        return res

    @classmethod
    def _sort_layout(cls, layout: LocalLayout):
        sorted_structure_list = []
        for structure in layout.structure_list:
            idx = 0
            if len(structure.line_list) == 0:
                sorted_structure_list.append(structure)
            else:
                for idx in range(len(sorted_structure_list) + 1):
                    if idx == len(sorted_structure_list):
                        break
                    if len(sorted_structure_list[idx].line_list) == 0:
                        continue
                    if sorted_structure_list[idx].line_list[0].index > structure.line_list[0].index:
                        break
                sorted_structure_list.insert(idx, structure)
        layout.structure_list = sorted_structure_list
        return layout

    @classmethod
    def _recursive_sort_layout(cls, layout: LocalLayout, width: float):
        blocks = [block for block in layout.layout]
        if len(blocks) == 0:
            return layout
        boxes = np.array([block.coordinates for block in blocks], dtype=int)
        order = cls._recursive_cut(boxes, np.arange(len(blocks)), width)
        structure_list = [layout.structure_list[i] for i in order]
        layout.structure_list = structure_list
        return layout

    @classmethod
    def _is_overlap(cls, bbox_a, bbox_b, threshold: float = 0.5):
        rect_a = fitz.Rect(bbox_a)
        area_a = rect_a.get_area()
        if area_a == 0:
            return False
        rect_b = fitz.Rect(bbox_b)
        return rect_a.intersect(rect_b).get_area() / area_a >= threshold

    @classmethod
    def _split_text_structure(cls, structure: Structure) -> List[Structure]:
        """将文本块按照一定的规则拆分为多个块，一般按照段落"""

        def _merge_lines_into_structure(lines: List[Line]) -> Structure:
            _structure = Structure(bbox=[], type="text", line_list=lines)
            _structure.bbox = list(_structure.block_from_line_list.coordinates)
            _structure.text = _structure.block_from_line_list.text
            return _structure

        def _get_spacing_between_lines(line_a, line_b) -> float:
            return abs(line_a.block.coordinates[3] - line_b.block.coordinates[1])

        def _get_average_line_spacing(lines: List[Line]) -> float:
            assert len(lines) >= 2
            space_list = [_get_spacing_between_lines(lines[idx], lines[idx + 1])
                          for idx in range(0, len(lines) - 1)]
            return sum(space_list) / len(space_list)

        def _is_same_paragraph(line: Line, paragraph: List[Line]) -> bool:
            width_list = [(_line.block.coordinates[0] + _line.block.coordinates[2]) / 2 for _line in paragraph]
            width = (line.block.coordinates[0] + line.block.coordinates[2]) / 2
            mean = np.mean(width_list)
            std = np.std(width_list) + 10
            upper_bound = mean + 3 * std
            lower_bound = mean - 3 * std
            return lower_bound <= width <= upper_bound

        ret = []
        paragraph = []
        last_line = None
        for line in structure.line_list:
            # if line.text.strip().startswith("体 "):
            #     print(line)
            if re.search("[。.：:！!？?)）\"”;；'‘]$", line.text.strip()) and last_line is not None and \
                    line.block.width < last_line.block.width:
                """新段落"""
                paragraph.append(line)
                ret.append(_merge_lines_into_structure(paragraph))
                paragraph = []
                last_line = None
            elif paragraph and not _is_same_paragraph(line, paragraph):
                ret.append(_merge_lines_into_structure(paragraph))
                paragraph = [line]
                last_line = None
            elif last_line is not None and len(paragraph) >= 2 and \
                    _get_average_line_spacing(paragraph) * 3 < _get_spacing_between_lines(last_line, line):
                ret.append(_merge_lines_into_structure(paragraph))
                paragraph = [line]
                last_line = None
            else:
                paragraph.append(line)
                last_line = line
        if paragraph:
            ret.append(_merge_lines_into_structure(paragraph))
        return ret

    @classmethod
    def _align_text_structure(cls,
                              text: Text,
                              layout: LocalLayout,
                              width: float,
                              layout_config: LayoutConfig,
                              soft_top: float = 3, soft_bottom: float = 3,
                              soft_left: float = 3.0, soft_right: float = 3.0):
        """将Text结构合并到Structure结构中"""
        soft_margin = {"top": soft_top,
                       "bottom": soft_bottom,
                       "left": soft_left,
                       "right": soft_right}
        no_group_lines = []
        for line in text.line_list:
            line_block = line.block
            grouped = False
            for structure in layout.structure_list:
                """应该需要给structure_list进行排序"""
                if structure.type in ("figure",):
                    continue
                structure_block = structure.block
                try:
                    if cls._is_overlap(list(line_block.coordinates), list(structure_block.coordinates),
                                       threshold=0.5) or \
                            cls._is_overlap(list(structure_block.coordinates), list(line_block.coordinates),
                                            threshold=0.5):
                        # if line_block.is_in(structure_block, soft_margin=soft_margin, center=True) or \
                        #         structure_block.is_in(line_block, soft_margin=soft_margin, center=True):
                        structure.line_list.append(line)
                        line.type = structure.type
                        grouped = True
                        break
                except Exception as e:
                    logger.error("_align_text_structure: {}".format(e))
                    continue
            if not grouped:
                no_group_lines.append(line)
        if no_group_lines:
            added_structures = cls._aggregate_lines_into_structures(no_group_lines, layout_config)
            layout.structure_list.extend(added_structures)
        """排序layout"""
        layout = cls._recursive_sort_layout(layout, 0.2 * width)
        """该排序的意义不明"""
        # layout = cls._sort_layout(layout)
        """对页面中的文本区块进行细粒度拆分"""
        structure_list = []
        for structure in layout.structure_list:
            if structure.type == "text":
                structure_list += cls._split_text_structure(structure)
            else:
                structure_list.append(structure)
        layout.structure_list = structure_list
        return layout

    @classmethod
    def _crop_image(cls, img: np.ndarray, rect: Rectangle):
        x1, y1, x2, y2 = int(rect.x_1), int(rect.y_1), int(rect.x_2), int(rect.y_2)
        cropped_img = img[y1:y2, x1:x2, :]
        return cropped_img

    @classmethod
    def _iob(cls, bbox_a, bbox_b):
        intersection = fitz.Rect(bbox_a).intersect(bbox_b)

        bbox_a_area = fitz.Rect(bbox_a).get_area()
        if bbox_a_area > 0:
            return intersection.get_area() / bbox_a_area
        return 0

    @classmethod
    def _convert_table_to_html(cls,
                               content: bytes,
                               structure: Structure,
                               page_idx: int,
                               soft_left=10,
                               soft_right=10,
                               soft_top=20,
                               soft_bottom=10):
        pdf = cls._convert_to_pdf(content)
        page = cls._convert_to_pages(pdf, page_idx, page_idx + 1)[0]
        table_extraction_pipeline = get_table_extraction_pipeline()
        table_region = structure.block.pad(left=soft_left, right=soft_right, top=soft_top, bottom=soft_bottom)
        cropped_img = Image.fromarray(
            cv2.cvtColor(cls._crop_image(page.image.image_cv2, table_region.block), cv2.COLOR_BGR2RGB))
        tokens = []
        for line in structure.line_list:
            for word in line.word_list:
                bbox = list(word.block.coordinates)
                if cls._iob(bbox, list(table_region.coordinates)) >= 0.5:
                    tokens.append({"bbox": [
                        bbox[0] - table_region.block.x_1, bbox[1] - table_region.block.y_1,
                        bbox[2] - table_region.block.x_1, bbox[3] - table_region.block.y_1
                    ], "text": word.text})
        for idx, token in enumerate(tokens):
            if not 'span_num' in token:
                token['span_num'] = idx
            if not 'line_num' in token:
                token['line_num'] = 0
            if not 'block_num' in token:
                token['block_num'] = 0
        structure.text = " ".join(table_extraction_pipeline.recognize(cropped_img, tokens)).strip()
        return structure

    @classmethod
    def _adjust_line2block_y_gap_rate(cls, texts: List[Text]) -> float:
        """根据抽取的页面调整line2block_y_gap_rate"""
        y_gap_rate_list = []
        for text in texts:
            before_line_block = None
            for line in text.line_list:
                line_block = line.block
                if before_line_block is not None and min(line_block.block.height, before_line_block.block.height) > 0:
                    y_gap_rate_list.append(min(abs(line_block.coordinates[1] - before_line_block.coordinates[3]),
                                               abs(line_block.coordinates[3] - before_line_block.coordinates[1])) / min(
                        line_block.height,
                        before_line_block.height))
                before_line_block = line.block
        if len(y_gap_rate_list) > 0 and sorted(y_gap_rate_list)[len(y_gap_rate_list) // 2] < 0.6:
            return 0.8
        return None

    def layout_analysis(self,
                        start: int = 0,
                        end: int = None,
                        lang: str = 'zh',
                        max_threads: int = None,
                        ):
        layout_config = self._layout_config
        end = end if end else self._page_count

        pool = Pool(max(max_threads, 1))
        text_list = []
        layout_list = []
        logger.info("Extracting text and layout")

        for page_idx in range(start, end):
            """generate_text"""
            text_list.append(pool.apply_async(self.__class__._extract_text_from_page,
                                              args=(self._content, page_idx, self._layout_config)))
            """extract_structure"""
            layout_list.append(pool.apply_async(self.__class__._extract_layout_from_page,
                                                args=(self._content, page_idx, lang,)))

        pool.close()
        pool.join()
        text_list = [text.get() for text in text_list]
        layout_list = [layout.get() for layout in layout_list]

        y_gap_rate = self._adjust_line2block_y_gap_rate(text_list)
        if y_gap_rate is not None:
            self._layout_config.line2block_y_gap_rate = y_gap_rate

        logger.info("Aligning text and layout")
        """后处理"""
        aligned_layout_list = []
        pool = Pool(processes=max(min(max_threads, end - start), 1))
        for page, text, layout in zip(self._pages[start:end], text_list, layout_list):
            aligned_layout_list.append(pool.apply_async(self.__class__._align_text_structure,
                                                        args=(text, layout, page.image.width, layout_config)))
        pool.close()
        pool.join()

        aligned_layout_list = [layout.get() for layout in aligned_layout_list]
        logger.info("Aggregating layouts to fragments")
        pool = Pool(processes=max(min(max_threads, len(self._pages[start:end])), 1))
        for page_idx in range(start, end):
            for structure in aligned_layout_list[page_idx - start].structure_list:
                if structure.type == "table":
                    pool.apply_async(self.__class__._convert_table_to_html, args=(self._content, structure, page_idx))
                else:
                    if structure.block_from_line_list:
                        structure.text = structure.block_from_line_list.text
        pool.close()
        pool.join()
        return aligned_layout_list

    def sync_layout_analysis(self,
                             start: int = 0,
                             end: int = None,
                             lang: str = 'zh'):
        layout_config = self._layout_config
        end = end if end else self._page_count

        text_list = []
        layout_list = []
        logger.info("Extracting text and layout")

        for page_idx in range(start, end):
            """generate_text"""
            text_list.append(self.__class__._extract_text_from_page(self._content, page_idx, self._layout_config))
            """extract_structure"""
            layout_list.append(self.__class__._extract_layout_from_page(self._content, page_idx, lang, ))

            y_gap_rate = self._adjust_line2block_y_gap_rate(text_list)
            if y_gap_rate is not None:
                self._layout_config.line2block_y_gap_rate = y_gap_rate

        logger.info("Aligning text and layout")
        """后处理"""
        aligned_layout_list = []
        for page, text, layout in zip(self._pages[start:end], text_list, layout_list):
            aligned_layout_list.append(self.__class__._align_text_structure(text,
                                                                            layout,
                                                                            page.image.width,
                                                                            layout_config))

        logger.info("Aggregating layouts to fragments")
        for page_idx in range(start, end):
            for structure in aligned_layout_list[page_idx - start].structure_list:
                if structure.type == "table":
                    self.__class__._convert_table_to_html(self._content, structure, page_idx)
                else:
                    if structure.block_from_line_list:
                        structure.text = structure.block_from_line_list.text

        return aligned_layout_list
