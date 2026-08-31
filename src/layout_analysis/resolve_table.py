from layoutparser.elements import Rectangle, Layout, TextBlock
import numpy as np
from argparse import Namespace
from paddleocr.ppstructure.table.predict_structure import TableStructurer
from typing import List, Union
import cv2

'''
1 先crop_image 得到表格区域图像
2 再对表格区域图像进行侦查 得到表格结构
3 对齐
'''

def analysis_table_content(ori_img : np.ndarray, table_rectangle : Rectangle = None, word_blocks : Union[Layout, List[TextBlock]] = [], table_engine : TableStructurer = None):
    if table_rectangle != None:
        cropped_img = crop_image(ori_img, table_rectangle)
    else:
        cropped_img = ori_img.copy()
    
    resized_img = cv2.resize(cropped_img, (int(cropped_img.shape[1] / 2), int(cropped_img.shape[0] / 2)))
    x_rate = cropped_img.shape[0] / int(cropped_img.shape[0] / 2)
    y_rate = cropped_img.shape[1] / int(cropped_img.shape[1] / 2)

    structure_res, elapse = table_engine(resized_img)
    structure_mark_list, structure_bbox_list = structure_res
    structure_bbox_list[:,0::2] *= x_rate
    structure_bbox_list[:,1::2] *= y_rate
    if table_rectangle != None:
        structure_bbox_list[:,0::2] += int(table_rectangle.x_1)
        structure_bbox_list[:,1::2] += int(table_rectangle.y_1)
    structure_block_list = []
    for bbox in structure_bbox_list:
        if len(bbox) == 8:
            rectangle = Rectangle((bbox[0] + bbox[6]) / 2, (bbox[1] + bbox[3]) / 2, (bbox[2] + bbox[4]) / 2, (bbox[5] + bbox[7]) / 2)
        else:
            rectangle = Rectangle(bbox[0], bbox[1], bbox[2], bbox[3])
        structure_block_list.append(TextBlock(rectangle, ''))
    # 进行对齐
    match_result(structure_block_list, word_blocks)
    result_html = get_pred_html(structure_mark_list, structure_block_list)
    return structure_block_list, result_html, cropped_img
    

def crop_image(ori_img : np.ndarray, rectangle : Rectangle):
    x1, y1, x2, y2 = int(rectangle.x_1), int(rectangle.y_1), int(rectangle.x_2), int(rectangle.y_2)
    cropped_img = ori_img[y1:y2, x1:x2, :]
    return cropped_img

def distance(block1, block2):
    x1, y1, x2, y2 = block1.coordinates
    x3, y3, x4, y4 = block2.coordinates
    dis = abs(x3 - x1) + abs(y3 - y1) + abs(x4 - x2) + abs(y4 - y2)
    dis_2 = abs(x3 - x1) + abs(y3 - y1)
    dis_3 = abs(x4 - x2) + abs(y4 - y2)
    return dis + min(dis_2, dis_3)

def compute_iou(block1, block2):
    """
    computing IoU
    :param rec1: (y0, x0, y1, x1), which reflects
            (top, left, bottom, right)
    :param rec2: (y0, x0, y1, x1)
    :return: scala value of IoU
    """
    x1, y1, x2, y2 = block1.coordinates
    x3, y3, x4, y4 = block2.coordinates
    # computing area of each rectangles
    S_rec1 = (y2 - y1) * (x2 - x1)
    S_rec2 = (y4 - y3) * (x4 - x3)

    # computing the sum_area
    sum_area = S_rec1 + S_rec2

    # find the each edge of intersect rectangle
    left_line = max(x1, x3)
    right_line = min(x2, x4)
    top_line = max(y1, y3)
    bottom_line = min(y2, y4)

    # judge if there is an intersect
    if left_line >= right_line or top_line >= bottom_line:
        return 0.0
    else:
        intersect = (right_line - left_line) * (bottom_line - top_line)
        return (intersect / (sum_area - intersect)) * 1.0


def match_result(structure_blocks, word_blocks):
    # matched = {}
    for word_block in word_blocks:
        distances = []
        for structure_block in structure_blocks:
            if compute_iou(word_block, structure_block) != 0.0:
                distances.append((1. - compute_iou(word_block, structure_block), distance(word_block, structure_block), structure_block))
        sorted_distances = sorted(distances, key=lambda item: (item[0], item[1]))
        if len(sorted_distances) > 0:
            sorted_distances[0][2].text += word_block.text + ' '


def get_pred_html(pred_structures, structure_blocks):
    end_html = []
    td_index = 0
    for tag in pred_structures:
        if '</td>' in tag:
            if '<td></td>' == tag:
                end_html.extend('<td>')
            if structure_blocks[td_index].text.strip() != '':
                end_html.extend(structure_blocks[td_index].text.strip())
            if '<td></td>' == tag:
                end_html.append('</td>')
            else:
                end_html.append(tag)
            td_index += 1
        else:
            end_html.append(tag)
    return ''.join(end_html)

def to_excel(html_table, excel_path):
    from tablepyxl import tablepyxl
    tablepyxl.document_to_xl(html_table, excel_path)