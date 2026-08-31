import logging

from bs4 import BeautifulSoup
from mdtex2html import convert

from .base import BaseFragment, FragmentType
from .utils import replace_escape

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class FormulaFragment(BaseFragment):
    type: str = FragmentType.FORMULA

    latex: str
    tag: str = ""
    inline: bool = False

    @staticmethod
    def convert_latex_to_mathml(latex: str):
        try:
            """转移替换"""
            # latex = replace_escape(latex)
            if not latex.startswith("$"):
                latex = "${}$".format(latex)
            mathml = convert(latex)
            mathml = BeautifulSoup(mathml, "lxml").find("math").decode()
        except Exception as e:
            logger.error("convert_latex_to_mathml: {}".format(e))
            mathml = latex
        return mathml
