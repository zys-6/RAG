from typing import Union
from pydantic import BaseModel


class LayoutConfig(BaseModel):
    char2word_x_tolerance_rate: float = 0.15
    char2word_y_tolerance: float = 1.2
    word2line_y_overlap_rate: float = 0.5
    word2line_x_tolerance: float = 1000
    line2block_y_gap_rate: float = 0.6
    line2block_h_diff_rate: float = 0.5
    line2block_x_align_rate: float = 0.5

    constraint: Union[str, None] = None
