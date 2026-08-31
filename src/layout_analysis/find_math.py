from mmdet.apis import init_detector, inference_detector
from paddleocr.paddleocr import check_img
import numpy as np
from layoutparser.elements import Rectangle, Layout
from .analysis_structure import LayoutBlock
from .load_pdf import PDF_base

class MathDetector():
    def __init__(self):
        self.model = init_detector('ICDAR2021_MFD/configs/gfl/gfl_s50_fpn_2x_coco.py',
            '/home/lizichao2022/models/ICDAR2021_MFD/mfd_gfl_s50.pth', device = 'cuda')
        # 上述pth文件下载地址: https://drive.google.com/file/d/1ZG1dLdhAL5h1uLpZVu4CPZXPDTJzwgB-/view?usp=share_link


    def extract_math_expressions(self, img, threshold = 0.6):
        assert isinstance(img, (np.ndarray, list, str, bytes))
        image = check_img(img)
        math_result = inference_detector(self.model, image)  # 这里是BGR格式吗
        isolated_math_blocks = []
        embedded_math_blocks = []
        for bbox in math_result[1]:
            if bbox[4] < threshold:
                continue
            rectangle = Rectangle(bbox[0].item(), bbox[1].item(), bbox[2].item(), bbox[3].item())
            block = LayoutBlock(block = rectangle, score = bbox[4].item(), type = 'isolated_expression')
            isolated_math_blocks.append(block)
        for bbox in math_result[0]:
            if bbox[4] < threshold:
                continue
            rectangle = Rectangle(bbox[0].item(), bbox[1].item(), bbox[2].item(), bbox[3].item())
            block = LayoutBlock(block = rectangle, score = bbox[4].item(), type = 'embedded_expression')
            embedded_math_blocks.append(block)
        return isolated_math_blocks, embedded_math_blocks
    

    def combine_with_pdf(self, pdf_base: PDF_base):
        '''
            完成两件事情:
            - 识别独立公式区块, 将其添入pdf结构中
            - 识别内嵌公式区块, 把内嵌公式区块内的token视为数学类合并
        '''
        for page_id in pdf_base.used_pages:
            page_img = pdf_base.page_images[page_id]
            page_lines = pdf_base.page_texts[page_id]
            page_layout = pdf_base.page_structures[page_id]
            isolated_math_blocks, embedded_math_blocks = self.extract_math_expressions(page_img)
            # 首先将isolated_math_blocks加入
            for block in isolated_math_blocks:
                block.id = len(page_layout._blocks)
                page_layout._blocks.append(block)
            # 然后处理embedded_math_blocks, 顺便处理无法识别的文字
            for line_block in page_lines:
                # 1 识别
                for word_block in line_block.word_list:
                    flag = False
                    if '(cid:' in word_block.text:
                        flag = True
                    for math_block in embedded_math_blocks:
                        if word_block.is_in(math_block,soft_margin={"top": 2, "bottom": 2, "left": 2, "right": 2}, center = True):
                            flag = True
                            break
                    word_block.is_symbol = flag
                new_word_list = []
                # 2 合并
                for word_block in line_block.word_list:
                    if word_block.is_symbol is False:
                        new_word_list.append(word_block)
                    elif len(new_word_list) > 0 and new_word_list[-1].is_symbol is True:
                        new_word_list[-1].text += ' ' + word_block.text
                        new_word_list[-1].block = new_word_list[-1].block.union(word_block.block)
                    else:
                        new_word_list.append(word_block)
                line_block.word_list = new_word_list

