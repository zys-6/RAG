import logging
import os
import re
from argparse import Namespace
from multiprocessing.pool import ThreadPool as Pool
from typing import List, Dict, IO, Union

import cv2
import fitz
import numpy as np
from PIL import Image
from layoutparser.elements import Rectangle, Layout
from paddleocr.ppstructure.table.predict_structure import TableStructurer

from .analysis_structure import extract_layout_from_cv, LayoutBlock
from .detect_order import sort_layout_by_cut, sort_layout_by_digital
from .modified_pdfplumber import open as plumber_open
from .organize_text import extract_lines_from_digital, extract_lines_from_ocr, group_line_into_layout
from .resolve_table import analysis_table_content
from .table_post_process import iob
from .table_transformer import TableExtractionPipeline

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class PDF_base:
    '''
     初始化输入:
        - pdf_path,       PDF文件路径或数据流
        - used_pages,     选取页面列表(从0开始计数,若不设置则选择所有页面)
        - lang,           默认为ch (通常来讲,ch模型也能处理en内容)
        - digital_engine, PDF源码流解析引擎,默认为'fitz'即PyMuPDF
        - constraint,     默认无限制,若为'ocr'或'digital'则限制文本来源
        - layout_config,  结构化参数Dict
        - cv_keep_types,  布局分析模型需要保留的类别区块
        - table_tool,     Paddle表格识别模型路径，默认为None
        - table_transformer
        - max_threads

     可配置结构化参数(layout_config):
        - char -> word,         char2word_x_tolerance_rate选项和char2word_y_tolerance选项
        - word -> line,         word2line_y_overlap_rate选项和word2line_x_tolerance选项(可选)
        - line -> layout,       line2block_y_gap_rate选项和line2block_h_diff_rate选项和line2block_x_align_rate选项(可选)
        # 这些结构化参数也可以设置成绝对值形式, 后续支持两种情况的配置

     可供调用的属性包括: 
        - pdf_path,       PDF文件路径
        - page_images,    每页扫描图像的列表 
        - scale_rates,    每页的缩放比例 (相比于原PDF页面尺寸)
        - page_sizes,     每页尺寸 (字典对象,包含'width'与'height'键值)
        - page_objects,   每页的页面对象 (fitz.Page对象或pdfplumber.page.Page对象的列表)
        - page_num,       页面数量
        - used_pages,     使用页面列表，从0开始计数
        - page_words,     每页文本词 (layoutparser.elements.Layout对象的列表)
        - page_texts,     每页文本行 (layoutparser.elements.Layout对象的列表)
        - page_sources,   每页文本来源 ('ocr'或'digital')
        - page_structures 每页结构 (layoutparser.elements.Layout对象的列表)
    '''

    def __init__(self, pdf_path: Union[str, IO],
                 used_pages: List[int] = None,
                 lang='ch',
                 digital_engine: str = None,
                 constraint: str = None,
                 layout_config: Dict = None,
                 cv_keep_types: List[str] = None,
                 table_tool=None,
                 table_transformer=None,
                 max_threads=12):
        self.pdf_path = pdf_path
        self.digital_engine = digital_engine if digital_engine else 'fitz'
        self.constraint = constraint if constraint else ""
        self.layout_config = layout_config if layout_config else {}
        self.cv_keep_types = cv_keep_types if cv_keep_types else ['figure', 'table', 'header', 'footer',
                                                                  'figure_caption', 'table_caption']
        self.table_tool = table_tool if table_tool else None
        self.table_transformer = table_transformer if table_transformer else None
        self.max_threads = max_threads if max_threads else 12
        self.used_pages = used_pages if used_pages else None
        self.lang = lang

        if self.digital_engine == 'fitz':
            if isinstance(pdf_path, str):
                pdf = fitz.open(pdf_path)
            elif isinstance(pdf_path, IO):
                pdf = fitz.open(stream=pdf_path, filetype='pdf')
            else:
                raise NotImplementedError(pdf_path)
            self.page_objects = [pdf.load_page(i) for i in range(pdf.pageCount)]
            self.page_num = pdf.pageCount
        else:
            pdf = plumber_open(pdf_path)
            self.page_objects = pdf.pages
            self.page_num = len(self.page_objects)

        print(f'this PDF file contains {self.page_num} pages')

        if self.used_pages is not None:
            # self.page_num = len(used_pages)
            print(f"we only use the {used_pages} pages")
        else:
            used_pages = [i for i in range(self.page_num)]
            print(f'we use every page...')

        # set table parsing tool
        if self.table_tool is not None:
            table_char_dict_path = self.table_tool['table_char_dict_path']
            table_model_dir = self.table_tool['table_model_dir']
            args = Namespace(alpha=1.0, benchmark=False, beta=1.0, enable_mkldnn=False, fourier_degree=5, gpu_mem=500,
                             help='==SUPPRESS==', image_dir=None, image_orientation=False, ir_optim=True,
                             max_batch_size=10, max_text_length=25, merge_no_span_structure=True, mode='structure',
                             ocr=False, page_num=0, precision='fp32', process_id=0, scales=[8, 16, 32], show_log=True,
                             structure_version='PP-Structurev2', table=True, table_algorithm='TableAttn',
                             table_char_dict_path=table_char_dict_path, table_max_len=488,
                             table_model_dir=table_model_dir, total_process_num=1, type='ocr', use_angle_cls=False,
                             use_dilation=False, use_gpu=False, use_mp=False, use_npu=False, use_onnx=False,
                             use_pdf2docx_api=False, use_pdserving=False, use_space_char=True, use_tensorrt=False,
                             use_visual_backbone=True, use_xpu=False, warmup=False)
            self.table_engine = TableStructurer(args)

        if self.table_transformer is not None:
            det_model_path = self.table_transformer['det_model_path']
            det_device = self.table_transformer['det_device']
            str_device = self.table_transformer['str_device']
            str_model_path = self.table_transformer['str_model_path']
            self.table_transformer_engine = TableExtractionPipeline(det_device, str_device, det_model_path,
                                                                    str_model_path)

        print('transforming each page to image...')
        self.page_images, self.scale_rates, self.page_sizes = self.generate_imgs(pdf_path)

        self.char2word_x_tolerance_rate = layout_config[
            'char2word_x_tolerance_rate'] if 'char2word_x_tolerance_rate' in layout_config else 0.15
        self.char2word_y_tolerance = layout_config[
            'char2word_y_tolerance'] if 'char2word_y_tolerance' in layout_config else 1.2
        self.word2line_y_overlap_rate = layout_config[
            'word2line_y_overlap_rate'] if 'word2line_y_overlap_rate' in layout_config else 0.5
        self.word2line_x_tolerance = layout_config[
            'word2line_x_tolerance'] if 'word2line_x_tolerance' in layout_config else 1000
        self.line2block_y_gap_rate = layout_config[
            'line2block_y_gap_rate'] if 'line2block_y_gap_rate' in layout_config else 0.6
        self.line2block_h_diff_rate = layout_config[
            'line2block_h_diff_rate'] if 'line2block_h_diff_rate' in layout_config else 0.5
        self.line2block_x_align_rate = layout_config[
            'line2block_x_align_rate'] if 'line2block_x_align_rate' in layout_config else 0.5

        print("generating each page's text")
        self.page_words = [None] * self.page_num
        self.page_texts = [None] * self.page_num
        self.page_sources = ['none'] * self.page_num
        pool = Pool(processes=self.max_threads)
        for page_id in range(self.page_num):
            self.generate_text(page_id)
            # pool.apply_async(self.generate_text, [page_id])
        pool.close()
        pool.join()
        # self.page_words, self.page_texts, self.page_sources = self.generate_texts()  # 此处的文本按行组织

        print("analysing each page's structure")
        self.page_structures = [None] * self.page_num
        pool = Pool(processes=self.max_threads)
        for page_id in range(self.page_num):
            self.generate_structure(page_id, cv_keep_types)
            # pool.apply_async(self.generate_structure, args = (page_id, cv_keep_types))
        pool.close()
        pool.join()
        # self.page_structures = self.generate_structures(cv_keep_types)
        # print("Aligning each page's structure & text")
        # self.align_text_structure()

    def generate_imgs(self, pdf_path):
        imgs = []
        sizes = []
        scale_rates = []
        if type(pdf_path) is str:
            pdf = fitz.open(pdf_path)
        else:
            pdf = fitz.open(stream=pdf_path, file_type='pdf')
        # with fitz.open(pdf_path) as pdf:
        for page_id in range(self.page_num):
            if page_id not in self.used_pages:
                sizes.append(None)
                imgs.append(None)
                scale_rates.append(None)
                continue
            print(f"transforming {page_id + 1}-th page to image")
            page = pdf[page_id]
            page_rate = 2
            mat = fitz.Matrix(page_rate, page_rate)
            pm = page.getPixmap(matrix=mat, alpha=False)
            # if width or height > 2000 pixels, don't enlarge the image
            if pm.width > 2000 or pm.height > 2000:
                page_rate = 1
                pm = page.getPixmap(matrix=fitz.Matrix(1, 1), alpha=False)
            img = Image.frombytes("RGB", [pm.width, pm.height], pm.samples)
            img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            scale_rates.append(page_rate)
            imgs.append(img)
            sizes.append({'width': pm.width, 'height': pm.height})
        return imgs, scale_rates, sizes

    def generate_text(self, page_id):

        if page_id in self.used_pages:
            print(f"generating {page_id + 1}-th page's text")
            digital_words, digital_lines = extract_lines_from_digital(self.page_objects[page_id],
                                                                      self.char2word_x_tolerance_rate,
                                                                      self.char2word_y_tolerance,
                                                                      self.word2line_x_tolerance,
                                                                      self.word2line_y_overlap_rate)
            # 旧版本参数 digital_words, digital_lines = extract_lines_from_digital(self.page_objects[page_id], self.char2word_x_tolerance, self.char2word_y_tolerance, self.word2line_x_tolerance, self.word2line_y_overlap_rate)
            if len(digital_words._blocks) != 0 and self.constraint.lower() != 'ocr':
                if self.scale_rates[page_id] != 1:
                    digital_words = digital_words.scale(self.scale_rates[page_id])
                    digital_lines = digital_lines.scale(self.scale_rates[page_id])
                    for line in digital_lines:
                        line.word_list = [word.scale(self.scale_rates[page_id]) for word in line.word_list]
                self.page_texts[page_id] = digital_lines
                self.page_words[page_id] = digital_words
                self.page_sources[page_id] = 'digital'

            elif self.constraint.lower() != 'digital':
                ocr_words, ocr_lines = extract_lines_from_ocr(self.page_images[page_id], min_column_width=int(
                    0.2 * self.page_sizes[page_id]['width']), word2line_x_tolerance=self.word2line_x_tolerance,
                                                              word2line_y_overlap_rate=self.word2line_y_overlap_rate)
                self.page_texts[page_id] = ocr_lines
                self.page_words[page_id] = ocr_words
                self.page_sources[page_id] = 'ocr'
            else:
                self.page_texts[page_id] = Layout([])
                self.page_words[page_id] = Layout([])
                self.page_sources[page_id] = 'none'

    def generate_structure(self, page_id, keep_types):
        if page_id in self.used_pages:
            print(f"analysing {page_id + 1}-th page's structure")
            if self.table_transformer != None:
                layout = extract_layout_from_cv(self.page_images[page_id], self.lang, keep_types,
                                                self.table_transformer_engine)
            else:
                layout = extract_layout_from_cv(self.page_images[page_id], self.lang, keep_types)

            self.page_structures[page_id] = layout

    def align_text_structure(self):
        for page_id in self.used_pages:
            # 结构区块和文本行
            page_layout = self.page_structures[page_id]
            page_lines = self.page_texts[page_id]
            no_group_lines = []
            # 把位于区块内的文本行放入区块
            for line_block in page_lines:
                if line_block.layout_id != -1:
                    continue
                for layout_block in page_layout:
                    try:
                        if line_block.is_in(layout_block, soft_margin={"top": 2, "bottom": 2, "left": 2, "right": 2},
                                            center=True) or layout_block.is_in(line_block,
                                                                               soft_margin={"top": 2, "bottom": 2,
                                                                                            "left": 2, "right": 2},
                                                                               center=True):
                            if line_block.layout_id == -1 or layout_block.type != 'text':  # 还未赋值或类别特别 有待商榷
                                line_block.layout_id = layout_block.id
                                line_block.layout_type == layout_block.type
                    except AssertionError:
                        continue
                if line_block.layout_id != -1:
                    page_layout._blocks[line_block.layout_id].line_list.append(line_block)
                if line_block.layout_id == -1:
                    no_group_lines.append(line_block)
            # 处理不在任何区块内的文本行，产生新的结构区块
            add_layout_blocks = group_line_into_layout(no_group_lines, self.line2block_y_gap_rate,
                                                       self.line2block_h_diff_rate, self.line2block_x_align_rate,
                                                       begin_idx=len(page_layout._blocks))
            page_layout._blocks.extend(add_layout_blocks)
            # 对layout_block进行排序
            page_layout = sort_layout_by_cut(page_layout, 0.2 * self.page_sizes[page_id]['width'])
            if self.page_sources[page_id] == 'digital':  # 若为digital，则根据数字信息精细排序
                page_layout = sort_layout_by_digital(page_layout)

    def table_2_html(self, layout_block, page_id):
        layout_block.text = ''
        assert layout_block.type == 'table'
        if self.table_transformer != None:
            table_region = layout_block.block.pad(left=10, right=10, top=20, bottom=10)

            def crop_image(ori_img: np.ndarray, rectangle: Rectangle):
                x1, y1, x2, y2 = int(rectangle.x_1), int(rectangle.y_1), int(rectangle.x_2), int(rectangle.y_2)
                cropped_img = ori_img[y1:y2, x1:x2, :]
                return cropped_img

            PIL_image = Image.fromarray(
                cv2.cvtColor(crop_image(self.page_images[page_id], table_region), cv2.COLOR_BGR2RGB))
            tokens = [{'bbox': list(token.block.coordinates), 'text': token.text} for token in self.page_words[page_id]]
            table_tokens = [token for token in tokens if iob(token['bbox'], list(table_region.coordinates)) >= 0.5]
            for token in table_tokens:
                token['bbox'] = [token['bbox'][0] - table_region.x_1, token['bbox'][1] - table_region.y_1,
                                 token['bbox'][2] - table_region.x_1, token['bbox'][3] - table_region.y_1]

            layout_block.text = ' '.join(self.table_transformer_engine.recognize(PIL_image, table_tokens))
        elif self.table_tool != None:
            _, table_html, _1 = analysis_table_content(self.page_images[page_id], layout_block.block,
                                                       self.page_words[page_id], self.table_engine)
            layout_block.text = table_html

        layout_block.text = layout_block.text.strip()

    def export_structured_content(self):
        print("Aligning each page's structure & text")
        self.align_text_structure()
        content = []
        content_idx = 0
        # generate text of every layout block
        pool = Pool(processes=self.max_threads)
        for page_id in self.used_pages:
            page_layout = self.page_structures[page_id]
            for layout_block in page_layout:
                layout_block.text = ''
                if layout_block.type == 'table' and (self.table_transformer != None or self.table_tool != None):
                    self.table_2_html(layout_block, page_id)
                    # pool.apply_async(self.table_2_html, args = (layout_block, page_id))
                else:
                    for line_block in layout_block.line_list:
                        if len(line_block.text.strip()) > 0:
                            layout_block.text += line_block.text.strip() + ' '
                    layout_block.text = layout_block.text.strip()
        pool.close()
        pool.join()
        for page_id in self.used_pages:
            print(f'exporting {page_id + 1}-th page to structured content')
            page_layout = self.page_structures[page_id]
            for layout_block in page_layout:
                if layout_block.type != 'figure' and layout_block.type != 'table' and layout_block.text.strip() == '':
                    continue
                if layout_block.heuristic_group == True:
                    layout_type = 'other'
                else:
                    layout_type = layout_block.type
                new_coordinates = [coord / self.scale_rates[page_id] for coord in layout_block.coordinates]
                new_width = self.page_sizes[page_id]['width'] / self.scale_rates[page_id]
                new_height = self.page_sizes[page_id]['height'] / self.scale_rates[page_id]
                display = [
                    {'page_no': page_id, 'page_width': new_width, 'page_height': new_height, 'top': new_coordinates[1],
                     'bottom': new_coordinates[3], 'left': new_coordinates[0], 'right': new_coordinates[2]}]
                json_block = {'content_id': content_idx, 'type': layout_type, 'display': display,
                              'text': layout_block.text.strip()}
                content_idx += 1
                content.append(json_block)
        return content

    def exported_connected_result(self, resource_dir=None):
        self.align_text_structure()
        # generate text of every layout block
        pool = Pool(processes=self.max_threads)
        for page_id in self.used_pages:
            page_layout = self.page_structures[page_id]
            for layout_block in page_layout:
                layout_block.text = ''
                if layout_block.type == 'table' and (self.table_transformer != None or self.table_tool != None):
                    self.table_2_html(layout_block, page_id)
                    # pool.apply_async(self.table_2_html, args = (layout_block, page_id))
                else:
                    for line_block in layout_block.line_list:
                        if len(line_block.text.strip()) > 0:
                            layout_block.text += line_block.text.strip() + ' '
                    layout_block.text = layout_block.text.strip()
        pool.close()
        pool.join()
        mid_results = []  # 存储中间结果
        flag_0 = False  # 标记上一个区块是否可能和该区块相连
        for page_id in self.used_pages:  # 遍历每个页面
            page_layout_blocks = self.page_structures[page_id]._blocks
            page_size = self.page_sizes[page_id]
            line_heights = sorted([line.height for line in self.page_texts[page_id] if
                                   line.layout_type in ['text', 'title', 'reference', 'equation', 'list']])
            line_widths = sorted([line.width for line in self.page_texts[page_id] if
                                  line.layout_type in ['text', 'title', 'reference', 'equation', 'list']])
            # 计算平均宽度
            if 0 < len(line_widths) < 5:
                average_median_width = sum(line_widths) / len(line_widths)
            elif len(line_widths) == 0:
                average_median_width = 0
            else:
                average_median_width = (line_widths[int(len(line_widths) / 2) - 2] + line_widths[
                    int(len(line_widths) / 2) - 1]
                                        + line_widths[int(len(line_widths) / 2)] + line_widths[
                                            int(len(line_widths) / 2) + 1] + line_widths[
                                            int(len(line_widths) / 2) + 2]) / 5
            # 遍历该页面的所有区块
            for block_order in range(len(page_layout_blocks)):
                layout_block = page_layout_blocks[block_order]
                # 确定new_type
                layout_block.new_type = layout_block.type
                if layout_block.coordinates[3] < 0.1 * page_size['height']:
                    layout_block.new_type = 'header'
                elif layout_block.coordinates[1] > 0.92 * page_size['height']:
                    layout_block.new_type = 'footer'
                elif re.match('(Fig)|(FIG)', layout_block.text) is not None:
                    layout_block.new_type = 'figure_caption'
                elif re.match('(Table)|(TABLE)', layout_block.text) is not None:
                    layout_block.new_type = 'table_caption'
                elif len(line_heights) >= 5:  # >=5时才有footnote存在的必要
                    average_median_height = (line_heights[int(len(line_heights) / 2) - 2] + line_heights[
                        int(len(line_heights) / 2) - 1] +
                                             line_heights[int(len(line_heights) / 2)] + line_heights[
                                                 int(len(line_heights) / 2) + 1] + line_heights[
                                                 int(len(line_heights) / 2) + 2]) / 5

                    def is_mini(l_b: LayoutBlock):
                        for line in l_b.line_list:
                            if line.coordinates[3] - line.coordinates[1] > 0.925 * average_median_height:
                                return False
                        return True

                    if layout_block.type in ['title', 'text', 'reference', 'equation', 'list']:
                        if layout_block.coordinates[1] > 0.75 * page_size['height']:
                            flag_mini = is_mini(layout_block)
                            if flag_mini is True:
                                for layout_block_other in page_layout_blocks:
                                    if layout_block_other.coordinates[1] > 0.92 * page_size['height'] or \
                                            layout_block_other.coordinates[3] < 0.1 * page_size[
                                        'height'] or layout_block_other.type in ['header', 'footer']:
                                        continue
                                    if layout_block_other.coordinates[1] > layout_block.coordinates[1] and \
                                            layout_block_other.coordinates[0] < layout_block.coordinates[2] and \
                                            layout_block.coordinates[0] < layout_block_other.coordinates[2]:
                                        if not is_mini(layout_block_other):
                                            flag_mini = False
                                            break
                            if flag_mini is True:
                                layout_block.new_type = 'footnote'
                # 生成放缩之前的坐标
                new_coordinates = [coord / self.scale_rates[page_id] for coord in layout_block.coordinates]
                new_width = self.page_sizes[page_id]['width'] / self.scale_rates[page_id]
                new_height = self.page_sizes[page_id]['height'] / self.scale_rates[page_id]
                # 如果不是需要考虑拼接的区块
                if layout_block.new_type in ['header', 'footer', 'table', 'figure', 'figure_caption', 'table_caption',
                                             'footnote']:
                    mid_results.append({'display': [
                        {'page_no': page_id, 'page_width': new_width, 'page_height': new_height,
                         'top': new_coordinates[1], 'bottom': new_coordinates[3], 'left': new_coordinates[0],
                         'right': new_coordinates[2]}],
                        'content_id': len(mid_results), 'type': layout_block.type,
                        'new_type': layout_block.new_type, 'text': layout_block.text})
                    if layout_block.new_type in ['figure', 'table'] and resource_dir != None:  # don't save table image
                        page_image = Image.fromarray(cv2.cvtColor(self.page_images[page_id], cv2.COLOR_BGR2RGB))
                        crop_box = tuple(
                            [max(layout_block.coordinates[0] - 2, 0), max(layout_block.coordinates[1] - 2, 0),
                             min(layout_block.coordinates[2] + 2, self.page_sizes[page_id]['width']),
                             min(layout_block.coordinates[3] + 2, self.page_sizes[page_id]['height'])])
                        img = page_image.crop(crop_box)
                        if img.size[0] == 0 or img.size[1] == 0:
                            img = Image.new('RGB', (1, 1), (255, 255, 255))
                        img.save(os.path.join(resource_dir, str(len(mid_results) - 1) + '.jpg'), quality=95)
                        mid_results[-1]['file_path'] = os.path.join(resource_dir, str(len(mid_results)) + '.jpg')
                    if layout_block.heuristic_group == True:
                        mid_results[-1]['type'] = 'other'
                    continue
                # 如果是需要考虑拼接的文本区块
                elif len(layout_block.line_list) > 0:
                    flag_1 = False
                    for result_id in range(len(mid_results) - 1, -2, -1):
                        if result_id < 0:
                            break
                        result_other = mid_results[result_id]
                        if result_other['new_type'] in ['table', 'figure', 'figure_caption', 'table_caption',
                                                        'footnote']:
                            flag_1 = True  # 标记中间相隔上述区块之一
                        elif result_other['new_type'] not in ['header', 'footer']:
                            break
                    if result_id < 0:  # 如果没有可以连接的区块
                        mid_results.append({'display': [
                            {'page_no': page_id, 'page_width': new_width, 'page_height': new_height,
                             'top': new_coordinates[1], 'bottom': new_coordinates[3], 'left': new_coordinates[0],
                             'right': new_coordinates[2]}],
                            'content_id': len(mid_results), 'type': layout_block.type,
                            'new_type': layout_block.new_type, 'text': layout_block.text})
                        if layout_block.heuristic_group == True:
                            mid_results[-1]['type'] = 'other'
                    else:
                        result_other = mid_results[result_id]
                        flag_2 = False  # 标记是否与其他区块相连
                        if result_other['display'][-1]['page_no'] != page_id or new_coordinates[1] < \
                                result_other['display'][-1]['bottom'] - 6 or flag_1 == True:
                            if flag_0 == True and result_other['text'] != '' and result_other['text'][
                                -1] not in '。！？”）.!"…?)':
                                if result_other['type'] == 'other' or result_other[
                                    'type'] == layout_block.type or layout_block.heuristic_group == True:
                                    result_other['display'].append(
                                        {'page_no': page_id, 'page_width': new_width, 'page_height': new_height,
                                         'top': new_coordinates[1], 'bottom': new_coordinates[3],
                                         'left': new_coordinates[0], 'right': new_coordinates[2]})
                                    result_other['text'] += ' ' + layout_block.text
                                    if layout_block.heuristic_group == False:
                                        result_other['type'] = layout_block.type
                                    if result_other['type'] != 'other':
                                        result_other['new_type'] = result_other['type']
                                    flag_2 = True
                        if flag_2 == False:
                            mid_results.append({'display': [
                                {'page_no': page_id, 'page_width': new_width, 'page_height': new_height,
                                 'top': new_coordinates[1], 'bottom': new_coordinates[3], 'left': new_coordinates[0],
                                 'right': new_coordinates[2]}],
                                'content_id': len(mid_results), 'type': layout_block.type,
                                'new_type': layout_block.new_type, 'text': layout_block.text})
                            if layout_block.heuristic_group == True:
                                mid_results[-1]['type'] = 'other'
                    if layout_block.line_list[-1].width < 0.9 * average_median_width:
                        flag_0 = False
                    else:
                        flag_0 = True
        return mid_results
