from .base import BaseFragment, FragmentType


class ChartFragment(BaseFragment):
    type: str = FragmentType.CHART

    xml: str

    caption: str = ""
