from layoutparser.elements import TextBlock, Quadrilateral, Rectangle, Layout
from paddleocr import PPStructure
import numpy as np
from .detect_order import sort_layout_by_cut
from typing import List
import cv2
from PIL import Image
from .table_post_process import overlaps

ch_structure_engine = PPStructure(table=False, ocr=False, show_log=False, lang = 'ch', layout_score_threshold = 0.5)
# 中文结构引擎识别单元类别：文字、标题、图片、图片标题、表格、表格标题、页眉、页脚、引用、公式
# 基于CDLA数据集
en_structure_engine = PPStructure(table=False, ocr=False, show_log=False, lang = 'en', layout_score_threshold = 0.5)
# 英文结构引擎识别单元类别：文字、标题、表格、图片以及列表
# 基于PubLayNet数据集



class LayoutBlock(TextBlock):
    '''
        除了block, id, text之外, 特殊的属性在于：
        - line_ids: 所包含的line_block的列表
    '''
    def __init__(self, block, text="", id=None, type=None, parent=None, next=None, score=None):
        super().__init__(block, text, id, type, parent, next, score)
        self.line_list = []
        self.heuristic_group = False

    @property
    def font_size(self):
        if len(self.line_list) == 0:
            return 7
        font_size_list = [line.font_size for line in self.line_list]
        return max(font_size_list, key = font_size_list.count)
    
    @property
    def font_name(self):
        if len(self.line_list) == 0:
            return ''
        font_name_list = [line.font_name for line in self.line_list]
        return max(font_name_list, key = font_name_list.count)


def extract_layout_from_cv(img, lang = 'ch', keep_types : List = ['figure', 'table', 'header', 'footer'], table_transformer = None):
    # assert isinstance(img, (np.ndarray, list, str, bytes))
    if lang == 'ch':
        structure_result = ch_structure_engine(img)
    else:  # 基本上通用
        structure_result = en_structure_engine(img)
    blocks = []
    structure_result = [result for result in structure_result if result['type'] in keep_types]
    if table_transformer is not None and 'table' in keep_types:
        structure_result = [result for result in structure_result if result['type'] != 'table']
        PIL_image = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        outputs = table_transformer.detect(PIL_image)
        """这里的条件可能有问题"""
        for output in outputs:
            structure_result = [early_result for early_result in structure_result if early_result['type'] != 'figure' or not overlaps(output['bbox'], early_result['bbox'])]

        structure_result.extend([{'bbox': output['bbox'], 'type': 'table'} for output in outputs if output['label'] == 'table' and output['score'] >= 0.5])

    for element_id in range(len(structure_result)):
        element = structure_result[element_id]
        rectangle = Rectangle(element['bbox'][0], element['bbox'][1], element['bbox'][2], element['bbox'][3])
        block = LayoutBlock(block = rectangle, type = element['type'], id = element_id, text = '')
        blocks.append(block)


    return Layout(blocks)




