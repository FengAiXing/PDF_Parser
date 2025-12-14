# -*- coding: utf-8 -*-
"""
表格处理模块 - table

提供表格相关功能：
- CrossPageTableDetector: 跨页表格检测器
- CrossPageTableMerger: 跨页表格合并器
- table_utils: 表格工具函数

注意：TableParser 已移动到 parsers 模块
"""

from .cross_page_table_detector import CrossPageTableDetector
from .cross_page_table_merger import CrossPageTableMerger

# 导出工具函数（供外部使用）
from .table_utils import (
    crop_table_image,
    bbox_overlap_ratio,
    detect_rectangular_boxes,
    has_real_table_lines,
    is_valid_table,
    merge_vertical_lines,
    extract_table_rows_and_data_with_pymupdf,
    parse_single_table_with_pymupdf
)

__all__ = [
    'CrossPageTableDetector', 
    'CrossPageTableMerger',
    'crop_table_image',
    'bbox_overlap_ratio',
    'detect_rectangular_boxes',
    'has_real_table_lines',
    'is_valid_table',
    'merge_vertical_lines',
    'extract_table_rows_and_data_with_pymupdf',
    'parse_single_table_with_pymupdf'
]

