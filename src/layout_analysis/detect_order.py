# modified from https://github.com/Sanster/xy-cut

from layoutparser.elements import TextBlock, Quadrilateral, Rectangle, Layout
import numpy as np
from typing import List, Union

def sort_layout_by_digital(layout : Union[Layout, List[TextBlock]]):
    if type(layout) == Layout:
        blocks = layout._blocks
    else:
        blocks = layout
    sorted_blocks = []
    for block in blocks:
        idx = 0
        if len(block.line_list) == 0:
            sorted_blocks.append(block)
            continue
        for idx in range(len(sorted_blocks) + 1):
            if idx == len(sorted_blocks):
                break
            if len(sorted_blocks[idx].line_list) == 0:
                continue
            if sorted_blocks[idx].line_list[0].id > block.line_list[0].id:
                break
        sorted_blocks.insert(idx, block)
    if type(layout) == Layout:
        layout._blocks = sorted_blocks
    else:
        layout = sorted_blocks
    return layout

        

def sort_layout_by_cut(layout : Union[Layout, List[TextBlock]], min_column_width = 50):
    if type(layout) == Layout:
        blocks = layout._blocks
    else:
        blocks = layout
    if len(blocks) == 0:
        return layout
    boxes = np.array([block.coordinates for block in blocks], dtype = int)
    order = new_recursive_cut(boxes, np.arange(len(blocks)), min_column_width)
    if type(layout) == Layout:
        layout._blocks = [blocks[i] for i in order]
    else:
        layout = [blocks[i] for i in order]
    return layout



def new_recursive_cut(boxes: np.ndarray, indices: np.ndarray, min_column_width = 50):
    """
    Args:
        boxes: (N, 4)
        indices: 递归过程中始终表示 box 在原始数据中的索引
    Returns:
        res: 保存排序结果
    """
    res = []
    if len(indices) <= 1 or np.min(boxes) < 0:  # 新的改动
        return [i for i in indices]
    assert len(boxes) == len(indices)
    # 在x轴方向上投影。首先依据x0进行排序
    _indices = boxes[:, 0].argsort()
    x_sorted_boxes = boxes[_indices]
    x_sorted_indices = indices[_indices]
    # 获取x轴方向上的投影直方图
    x_projection = projection_by_bboxes(boxes=x_sorted_boxes, axis=0)
    # 合并直方图区块
    pos_x = split_projection_profile(x_projection, min_value = 0, min_gap = 1)
    if not pos_x:  # 没有任何有效区块
        return [i for i in x_sorted_indices]
    arr_x0, arr_x1 = pos_x
    # 先进行竖直切分（最多切一下）
    flag = False
    for i in range(1, len(arr_x0)):
        if arr_x1[i] - arr_x0[i] > min_column_width:
            flag = True
    if len(arr_x0) > 1 and arr_x1[0] - arr_x0[0] > min_column_width and flag == True:   # 能竖直切割的话，首先竖直切割，再考虑两边区块的分别排序
        left_indices = (arr_x0[0] <= x_sorted_boxes[:, 0]) & (x_sorted_boxes[:, 0] < arr_x1[0])
        right_indices = ~left_indices
        _indices_list = [left_indices, right_indices]
        for _indices in _indices_list:
            x_sorted_boxes_trunk = x_sorted_boxes[_indices]
            x_sorted_indices_trunk = x_sorted_indices[_indices]
            res.extend(new_recursive_cut(x_sorted_boxes_trunk, x_sorted_indices_trunk, min_column_width))
    else:
        _indices = boxes[:, 1].argsort()
        y_sorted_boxes = boxes[_indices]
        y_sorted_indices = indices[_indices]
        # 获取y轴方向上的投影直方图
        y_projection = projection_by_bboxes(boxes=y_sorted_boxes, axis=1)
        # 合并直方图区块
        pos_y = split_projection_profile(y_projection, min_value = 0, min_gap = 1)
        if not pos_y:
            return [i for i in y_sorted_indices]
        arr_y0, arr_y1 = pos_y
        if len(arr_y0) > 1:   # 可水平切分
            _indices_list = [((arr_y0[arr_idx] <= y_sorted_boxes[:, 1]) & (y_sorted_boxes[:, 1] < arr_y1[arr_idx])) for arr_idx in range(len(arr_y0))]
            temp_boxes = np.empty([0,4], dtype = int)  # []
            temp_indices = np.empty(0, dtype = int) #[]
            for arr_idx in range(len(_indices_list)):
                temp_indices = np.concatenate((temp_indices, y_sorted_indices[_indices_list[arr_idx]]), axis = 0)
                temp_boxes = np.concatenate((temp_boxes, y_sorted_boxes[_indices_list[arr_idx]]), axis = 0)
                # 看这些temp区块能否进行竖直切分
                _indices = temp_boxes[:, 0].argsort()
                temp_x_sorted_boxes = temp_boxes[_indices]
                x_projection = projection_by_bboxes(boxes = temp_x_sorted_boxes, axis=0)
                pos_x = split_projection_profile(x_projection, min_value = 0, min_gap = 1)
                if not pos_x:  # 没有任何有效区块
                    break
                arr_x0, arr_x1 = pos_x
                if len(arr_x0) == 1 or not (arr_x1[0] - arr_x0[0] > min_column_width and (arr_x1[-1] - arr_x0[1] > min_column_width)):
                    break
            arr_idx_split = [range(max(1, arr_idx)), range(max(1, arr_idx), len(_indices_list))]
            for arr_idx_range in arr_idx_split:
                temp_boxes = np.empty([0,4], dtype = int)  # []
                temp_indices = np.empty(0, dtype = int) #[]
                for new_arr_idx in arr_idx_range:
                    temp_indices = np.concatenate((temp_indices, y_sorted_indices[_indices_list[new_arr_idx]]), axis = 0)
                    temp_boxes = np.concatenate((temp_boxes, y_sorted_boxes[_indices_list[new_arr_idx]]), axis = 0)
                
                res.extend(new_recursive_cut(temp_boxes, temp_indices, min_column_width))
        
        else:  # 水平、竖直均无法切分
            if len(arr_x0) > 1:
                left_indices = (arr_x0[0] <= x_sorted_boxes[:, 0]) & (x_sorted_boxes[:, 0] < arr_x1[0])
                right_indices = ~left_indices
                _indices_list = [left_indices, right_indices]
                for _indices in _indices_list:
                    x_sorted_boxes_trunk = x_sorted_boxes[_indices]
                    x_sorted_indices_trunk = x_sorted_indices[_indices]
                    res.extend(new_recursive_cut(x_sorted_boxes_trunk, x_sorted_indices_trunk, min_column_width))
                # return [i for i in x_sorted_indices]
            else:
                return [i for i in y_sorted_indices]
    return res
                


def projection_by_bboxes(boxes: np.array, axis: int) -> np.ndarray:
    """
     通过一组 bbox 获得投影直方图，最后以 per-pixel 形式输出
    Args:
        boxes: [N, 4]
        axis: 0-x坐标向水平方向投影， 1-y坐标向垂直方向投影
    Returns:
        1D 投影直方图，长度为投影方向坐标的最大值(我们不需要图片的实际边长，因为只是要找文本框的间隔)
    """
    assert axis in [0, 1]
    length = np.max(boxes[:, axis::2])   # 双引号：从双引号前的数开始，以双引号后面的数为间隔
    res = np.zeros(length, dtype=int)
    for start, end in boxes[:, axis::2]:
        res[start:end] += 1
    return res


# from: https://dothinking.github.io/2021-06-19-%E9%80%92%E5%BD%92%E6%8A%95%E5%BD%B1%E5%88%86%E5%89%B2%E7%AE%97%E6%B3%95/#:~:text=%E9%80%92%E5%BD%92%E6%8A%95%E5%BD%B1%E5%88%86%E5%89%B2%EF%BC%88Recursive%20XY,%EF%BC%8C%E5%8F%AF%E4%BB%A5%E5%88%92%E5%88%86%E6%AE%B5%E8%90%BD%E3%80%81%E8%A1%8C%E3%80%82
def split_projection_profile(arr_values: np.array, min_value: float, min_gap: float):
    """Split projection profile:
    ```
                              ┌──┐
         arr_values           │  │       ┌─┐───
             ┌──┐             │  │       │ │ |
             │  │             │  │ ┌───┐ │ │min_value
             │  │<- min_gap ->│  │ │   │ │ │ |
         ────┴──┴─────────────┴──┴─┴───┴─┴─┴─┴───
         0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16
    ```
    Args:
        arr_values (np.array): 1-d array representing the projection profile.
        min_value (float): Ignore the profile if `arr_value` is less than `min_value`.
        min_gap (float): Ignore the gap if less than this value.
    Returns:
        tuple: Start indexes and end indexes of split groups.
    """
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



# 新算法
'''
1 找出所有横向切割
2 从上往下，遍历横向块
3 对于每个横向块，找到能向该横向块以下延伸得最深的纵向切割
4 如果没有能延伸的切割，就按横向？顺序排序
5 如果有，就分成了三部分：左，右，下，依次排序
'''

# 动归算法整理  尚未实现
'''
1 找出所有横向切割
2 对于每个横向块，有两种情况：上面没纵向切割线延伸下来，上面有一条纵向切割线延伸下来
3 上面有纵切线，则看能不能接上，能的话有两个选择：继续延伸或者在此断掉
4 
'''