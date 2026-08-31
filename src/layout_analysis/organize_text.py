import unicodedata

import fitz
import numpy as np
from layoutparser.elements import TextBlock, Rectangle, Layout
from paddleocr import PaddleOCR

from .analysis_structure import LayoutBlock
from .detect_order import sort_layout_by_cut
from .extract_words_digital import extract_words_from_fitz, extract_words_from_pdfplumber
from .modified_pdfplumber.page import Page

ocr_engine = PaddleOCR(use_angle_cls=False, lang="ch")

ocr_engine_2 = PaddleOCR(use_angle_cls=False, lang="en")


class WordBlock(TextBlock):
    '''
        除了block, id, text之外, 特殊的属性在于：
        - line_id: 所属的line_block的id值
        - is_symbol: 是否为嵌入行内数学公式或无法表示的符号等
        - (deleted) layout_id: 所属的layout_block的id值
        - (deleted) layout_type: 所属的layout_block的类型
    '''

    def __init__(self, block, text="", id=None, type=None, parent=None, next=None, score=None, line_id=-1, font_size=7,
                 font_name=''):
        super().__init__(block, text, id, type, parent, next, score)
        self.line_id = line_id
        # self.layout_id = -1
        # self.layout_type = 'text'
        self.is_symbol = 'False'
        self.font_size = font_size
        self.font_name = font_name


class LineBlock(TextBlock):
    '''
        除了block, id, text之外, 特殊的属性在于：
        - layout_id: 所属的layout_block的id值
        - layout_type: 所属的layout_block的类型
        - word_list: 所包含的word_block的列表
    '''

    def __init__(self, block, text="", id=None, type=None, parent=None, next=None, score=None):
        super().__init__(block, text, id, type, parent, next, score)
        self.layout_id = -1
        self.layout_type = 'text'
        self.word_list = []

    @property
    def font_size(self):
        if len(self.word_list) == 0:
            return 7
        font_size_list = [word.font_size for word in self.word_list]
        return max(font_size_list, key=font_size_list.count)

    @property
    def font_name(self):
        if len(self.word_list) == 0:
            return ''
        font_name_list = [word.font_name for word in self.word_list]
        return max(font_name_list, key=font_name_list.count)


def extract_lines_from_ocr(img, min_column_width=50, engine='paddle', word2line_x_tolerance=1000,
                           word2line_y_overlap_rate=0.5):
    # 输入可以是:图像（图像路径，np.ndarray，bytes）
    assert isinstance(img, (np.ndarray, list, str, bytes))
    # if type(img) is Image:
    #     img = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
    ocr_result = ocr_engine.ocr(img, cls=False)[0]
    blocks = []
    for line in ocr_result:
        rectangle = Rectangle((line[0][0][0] + line[0][3][0]) / 2, (line[0][0][1] + line[0][1][1]) / 2,
                              (line[0][1][0] + line[0][2][0]) / 2, (line[0][3][1] + line[0][2][1]) / 2)
        block = WordBlock(rectangle, text=line[1][0], score=line[1][1])
        blocks.append(block)
    sorted_word_blocks = sort_layout_by_cut(blocks, min_column_width)  # 依据规则排序
    for idx in range(len(sorted_word_blocks)):
        sorted_word_blocks[idx].id = idx
    line_blocks = group_word_into_line(sorted_word_blocks, x_tolerance=word2line_x_tolerance,
                                       y_overlap_rate=word2line_y_overlap_rate)  # 赋予line_id，相同line_id的token合并为line_block
    return Layout(sorted_word_blocks), Layout(line_blocks)


# def extract_words_from_digital(page, x_tolerance, y_tolerance, word2line_x_tolerance, word2line_y_overlap_rate = 0.5):  旧版本
def extract_lines_from_digital(page, x_tolerance_rate=0.15, y_tolerance=1.2, word2line_x_tolerance=1000,
                               word2line_y_overlap_rate=0.5):
    # pdfplumber中的page类
    assert isinstance(page, (Page, fitz.Page))
    if type(page) is Page:
        words = extract_words_from_pdfplumber(page, x_tolerance_rate, y_tolerance)
    else:
        words = extract_words_from_fitz(page, x_tolerance_rate, y_tolerance)
    blocks = []
    idx = 0
    for word in words:
        if word['upright'] == False:
            continue
        rectangle = Rectangle(word['x0'], word['top'], word['x1'], word['bottom'])
        block = WordBlock(rectangle, text=unicodedata.normalize("NFKC", word['text'].strip()),
                          font_size=max(1, int(word['size'])), font_name=word['fontname'])
        # block.font = word['fontname'] + f"-{int(word['size'])}"
        block.id = idx
        idx += 1
        blocks.append(block)
    # 已通过text_flow排序
    line_blocks = group_word_into_line(blocks, x_tolerance=word2line_x_tolerance,
                                       y_overlap_rate=word2line_y_overlap_rate)  # 赋予line_id，相同line_id的token合并为line_block
    return Layout(blocks), Layout(line_blocks)


def group_word_into_line(words_layout, x_tolerance=1000, y_overlap_rate=0.5):
    """Get text segments from the current page.
    It will automatically add new lines for
    1) line breaks
    2) big horizontal gaps
    """
    # prev_y = None
    prev_y1 = None
    prev_y2 = None
    prev_len = 0
    prev_x = None

    n = 0
    line_id = 0
    temp_line_block = None
    line_block_list = []
    for token in words_layout:
        # cur_y = token.block.center[1]   # 用(y1+y2)/2
        cur_y1 = token.coordinates[1]  # top
        cur_y2 = token.coordinates[3]  # bottom
        cur_x = token.coordinates[0]  # 用x1 left
        if prev_y1 is None or prev_y2 is None:
            prev_x = cur_x
            prev_y2 = cur_y2
            prev_y1 = cur_y1

        if (cur_y1 < prev_y2 and cur_y2 > prev_y1 and min(cur_y2 - prev_y1, prev_y2 - cur_y1) >= y_overlap_rate * min(
                cur_y2 - cur_y1, prev_y2 - prev_y1)) and cur_x - prev_x <= x_tolerance:
            token.line_id = line_id
            if temp_line_block == None:
                temp_line_block = LineBlock(token.block, token.text, id=line_id)
                temp_line_block.word_list.append(token)
            else:
                temp_line_block.block = temp_line_block.block.union(token.block, strict=False)
                temp_line_block.text += ' ' + token.text
                temp_line_block.word_list.append(token)
            if n == 0:
                prev_y1 = cur_y1
                prev_y2 = cur_y2
            else:
                prev_y1 = (prev_y1 * prev_len + len(token.text) * cur_y1) / (prev_len + len(token.text))
                prev_y2 = (prev_y2 * prev_len + len(token.text) * cur_y2) / (prev_len + len(token.text))
                # prev_y1 = temp_line_block.coordinates[1]
                # prev_y2 = temp_line_block.coordinates[3]
            n += 1
            prev_len += len(token.text)
        else:
            line_id += 1
            token.line_id = line_id
            line_block_list.append(temp_line_block)
            temp_line_block = LineBlock(token.block, token.text, id=line_id)
            temp_line_block.word_list.append(token)
            n = 1
            prev_y1 = cur_y1
            prev_y2 = cur_y2
            prev_len = len(token.text)
        prev_x = token.coordinates[2]
    if temp_line_block != None:
        line_block_list.append(temp_line_block)
    return line_block_list


def group_line_into_layout(lines, y_gap_rate=0.6, h_diff_rate=0.5, x_align_rate=0.5, begin_idx=0):
    # 1 水平方向有重合  2 竖直距离小于 0.6 * 行高  3 高度差不大于 0.5 * 行高  4（可选）某种对齐
    line_id_to_layout = dict()
    new_layout_blocks = []
    if type(lines) == Layout:
        _blocks = lines._blocks
    else:
        _blocks = lines
    for line_index in range(len(_blocks)):
        before_layout_block = None
        before_line_index = line_index - 1
        if before_line_index >= 0:
            if is_neighbor_lines(_blocks[before_line_index], _blocks[line_index], y_gap_rate, h_diff_rate):
                before_layout_block = line_id_to_layout[before_line_index]
                if len(before_layout_block.line_list) <= 1 or is_aligned_lines(_blocks[before_line_index],
                                                                               _blocks[line_index],
                                                                               x_align_rate):  # 要求对齐
                    before_layout_block.block = before_layout_block.block.union(_blocks[line_index].block, strict=False)
                elif _blocks[before_line_index].coordinates[0] < _blocks[line_index].coordinates[0] and \
                        _blocks[before_line_index].coordinates[2] > _blocks[line_index].coordinates[2]:
                    # 这个是否使用，有待商榷
                    before_layout_block.block = before_layout_block.block.union(_blocks[line_index].block, strict=False)
                elif _blocks[before_line_index].coordinates[0] > _blocks[line_index].coordinates[0] and \
                        _blocks[before_line_index].coordinates[2] > _blocks[line_index].coordinates[2]:
                    # 这个是否使用，有待商榷
                    before_layout_block.block = before_layout_block.block.union(_blocks[line_index].block, strict=False)
                else:
                    before_layout_block = None
        if before_layout_block == None:
            # 从begin_idx开始
            before_layout_block = LayoutBlock(_blocks[line_index].block, _blocks[line_index].text, id=begin_idx,
                                              type='text')
            new_layout_blocks.append(before_layout_block)
            begin_idx += 1
        '''
        for before_line_index in range(line_index):
            if is_neighbor_lines(_blocks[before_line_index], _blocks[line_index], y_gap_rate, h_diff_rate):
                before_layout_block = line_id_to_layout[before_line_index]
                if len(before_layout_block.line_list) <= 1 or is_aligned_lines(_blocks[before_line_index], _blocks[line_index], x_align_rate): # 要求对齐
                    break
                if _blocks[before_line_index].coordinates[0] < _blocks[line_index].coordinates[0] and _blocks[before_line_index].coordinates[2] > _blocks[line_index].coordinates[2]:
                # 这个是否使用，有待商榷
                    break
                else:
                    before_layout_block = None
        
        if before_layout_block == None:
            # 从begin_idx开始
            before_layout_block = LayoutBlock(_blocks[line_index].block, _blocks[line_index].text, id = begin_idx, type = 'text')
            new_layout_blocks.append(before_layout_block)
            begin_idx += 1
        else:
            before_layout_block.block = before_layout_block.block.union(_blocks[line_index].block, strict = False)
        '''
        line_id_to_layout[line_index] = before_layout_block
        before_layout_block.line_list.append(_blocks[line_index])
        _blocks[line_index].layout_id = before_layout_block.id
    for block in new_layout_blocks:
        if block != None:
            block.heuristic_group = True  # 新增属性 heuristic_group
    return new_layout_blocks  # 返回一个layout列表


def is_neighbor_lines(line_CoordElement1, line_CoordElement2, y_gap_rate, h_diff_rate):
    if line_CoordElement1.coordinates[0] < line_CoordElement2.coordinates[2] and line_CoordElement2.coordinates[0] < \
            line_CoordElement1.coordinates[2]:  # 有重叠
        if abs(line_CoordElement1.height - line_CoordElement2.height) <= h_diff_rate * min(line_CoordElement1.height,
                                                                                           line_CoordElement2.height):  # 高度差
            # if abs(line_CoordElement1.coordinates[0] - line_CoordElement2.coordinates[0])
            if (line_CoordElement1.coordinates[1] < line_CoordElement2.coordinates[3] and
                    line_CoordElement2.coordinates[1] < line_CoordElement1.coordinates[3]):  # 特殊情况

                return True
            if y_gap_rate * min(line_CoordElement1.height, line_CoordElement2.height) > min(
                    abs(line_CoordElement2.coordinates[1] - line_CoordElement1.coordinates[3]),
                    abs(line_CoordElement2.coordinates[3] - line_CoordElement1.coordinates[1])):
                return True
    return False


def is_aligned_lines(line_CoordElement1, line_CoordElement2, x_align_rate):
    x_align_tolerance = x_align_rate * min(line_CoordElement1.height, line_CoordElement2.height)
    if abs(line_CoordElement1.coordinates[0] - line_CoordElement2.coordinates[0]) < x_align_tolerance:
        return True
    if abs(line_CoordElement1.coordinates[2] - line_CoordElement2.coordinates[2]) < x_align_tolerance:
        return True
    if abs(line_CoordElement1.coordinates[2] + line_CoordElement1.coordinates[0] - line_CoordElement2.coordinates[2] -
           line_CoordElement2.coordinates[0]) < 2 * x_align_tolerance:
        return True
    return False
