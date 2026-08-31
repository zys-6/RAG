from pathlib import Path
from typing import IO, List, Union

from pydantic import BaseModel, Field, ConfigDict

from .fragment.base import FragmentLevel, BaseFragment


class BaseDocument(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    filepath: Union[str, bytes, IO, Path]

    temp_directory: Union[str, Path] = str(Path("static/tmp"))

    lazy: bool = False
    picture: bool = True
    table: bool = True
    fragment_level: str = FragmentLevel.PARAGRAPH
    formula: bool = True
    shape: bool = True  # 需要依赖外部工具
    chart: bool = True  # 目前还不支持解析
    doc: bool = False  # 需要依赖外部工具

    fragments: List[BaseFragment] = Field(default_factory=list)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._content = self.read_file(self.filepath)

    @classmethod
    def read_file(cls, filepath: Union[str, Path, bytes, IO]) -> bytes:
        if isinstance(filepath, bytes):
            return filepath
        elif isinstance(filepath, str) or isinstance(filepath, Path):
            with open(filepath, "rb") as fin:
                _content = fin.read()
            return _content
        elif isinstance(filepath, IO):
            _content = filepath.read()
            return _content
        else:
            raise TypeError(f"Can't read file from type `{type(filepath)}`")

    def _convert_to_fragments(self):
        raise NotImplementedError("Please use WordDocument or PdfDocument.")

    @property
    def content_catalog(self):
        """正文目录"""
        pass

    @property
    def table_catalog(self):
        """表目录"""
        pass

    @property
    def picture_catalog(self):
        """图目录"""
        pass

    @property
    def formula_catalog(self):
        """公式目录"""
        pass
