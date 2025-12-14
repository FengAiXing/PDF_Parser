# -*- coding: utf-8 -*-
"""
PyMuPDF 表格解析模块

提供表格提取、坐标分析、HTML转换等功能
"""

from .text_extractor import get_text_in_cells_by_char
from .coordinate_extractor import get_table_detailed_coordinates
from .html_converter import convert_table_to_html
from .table_drawer import draw_table_simple
from .border_detector import detect_tables_from_borders
from .table_extractor import extract_tables_with_detailed_coords
from .simple_table_extractor import extract_text_from_bbox_to_html

__all__ = [
    'get_text_in_cells_by_char',
    'get_table_detailed_coordinates',
    'convert_table_to_html',
    'draw_table_simple',
    'detect_tables_from_borders',
    'extract_tables_with_detailed_coords',
    'extract_text_from_bbox_to_html'
]

