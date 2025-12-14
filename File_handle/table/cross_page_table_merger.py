# -*- coding: utf-8 -*-
"""
跨页表格合并器 - CrossPageTableMerger

功能：
- 检测并合并跨页表格
- 合并表格图片
- 合并跨页表格的HTML内容
"""

import os
import logging
from typing import List, Dict
from PIL import Image

from .cross_page_table_detector import CrossPageTableDetector
from .cross_page_table_merge import (
    detect_and_merge_cross_page_tables as detect_and_merge_cross_page_tables_impl,
    merge_table_images as merge_table_images_impl,
    merge_multiple_table_images as merge_multiple_table_images_impl,
    merge_html_tables as merge_html_tables_impl,
    merge_cross_page_rows as merge_cross_page_rows_impl,
    absorb_empty_rowspan_cells as absorb_empty_rowspan_cells_impl,
    normalize_html_table_columns as normalize_html_table_columns_impl,
    should_merge_rows as should_merge_rows_impl,
    compute_display_cols as compute_display_cols_impl,
    get_rowspan_info_from_previous_rows as get_rowspan_info_from_previous_rows_impl,
    merge_rows_with_rowspan as merge_rows_with_rowspan_impl,
    merge_two_rows as merge_two_rows_impl,
    has_key_column_values as has_key_column_values_impl,
)


class CrossPageTableMerger:
    """跨页表格合并器"""
    
    def __init__(self, logger: logging.Logger = None, detector: CrossPageTableDetector = None):
        """
        初始化跨页表格合并器
        
        Args:
            logger: 日志记录器，如果为None则创建新的
            detector: 跨页表格识别器，如果为None则创建新的
        """
        self.logger = logger or logging.getLogger(__name__)
        self.detector = detector or CrossPageTableDetector(logger=self.logger)
    
    def detect_and_merge_cross_page_tables(self, tables: List[Dict], pdf_path: str, 
                                           output_dir: str, is_valid_table_func=None,
                                           save_images: bool = True) -> List[Dict]:
        """
        检测并合并跨页表格（支持连续多页跨页）
        
        Args:
            tables: 表格列表
            pdf_path: PDF文件路径
            output_dir: 输出目录
            is_valid_table_func: 验证表格有效性的函数（可选）
            save_images: 是否保存合并后的表格图片
            
        Returns:
            合并后的表格列表
        """
        return detect_and_merge_cross_page_tables_impl(
            self, tables, pdf_path, output_dir, is_valid_table_func, save_images
        )
    
    def merge_table_images(self, image_path1: str, image_path2: str, 
                           output_dir: str, filename: str) -> str:
        """
        合并两个表格图片（垂直拼接）
        
        Args:
            image_path1: 第一个表格图片路径
            image_path2: 第二个表格图片路径
            output_dir: 输出目录
            filename: 输出文件名
            
        Returns:
            合并后的图片路径
        """
        return merge_table_images_impl(self, image_path1, image_path2, output_dir, filename)
    
    def merge_multiple_table_images(self, image_paths: List[str], 
                                     output_dir: str, filename: str) -> str:
        """
        合并多个表格图片（垂直拼接，支持2张以上）
        
        Args:
            image_paths: 表格图片路径列表
            output_dir: 输出目录
            filename: 输出文件名
            
        Returns:
            合并后的图片路径
        """
        return merge_multiple_table_images_impl(self, image_paths, output_dir, filename)
    
    def merge_html_tables(self, tables: List[Dict]) -> List[Dict]:
        """
        合并跨页表格的HTML内容（从原始图片的识别结果中提取）
        
        Args:
            tables: 表格列表（包含original_results）
            
        Returns:
            合并后的表格列表
        """
        return merge_html_tables_impl(self, tables)
    
    def normalize_html_table_columns(self, html_rows: List[str], expected_cols: int) -> List[str]:
        """
        标准化HTML表格行，去除rowspan占位位置的单元格
        
        策略：
        1. 跟踪每列的rowspan状态
        2. 如果某行有rowspan占位，去除占位位置的单元格（这些单元格在原始HTML中可能不存在）
        3. 不添加任何新的空单元格，只去除rowspan占位位置的单元格
        4. 保留原始存在的单元格
        
        Args:
            html_rows: HTML行列表
            expected_cols: 期望的列数（此参数保留以保持接口兼容性，但不使用）
            
        Returns:
            标准化后的HTML行列表（只去除rowspan占位，不添加任何单元格）
        """
        return normalize_html_table_columns_impl(self, html_rows, expected_cols)
    
    def compute_display_cols(self, rows: List[str]) -> List[int]:
        """
        计算每行的"展示列数"（从上往下，考虑rowspan占位和colspan）
        
        规则：
        1. 第一行：直接统计<td>数量，每个colspan的单元格贡献colspan值的列数
        2. 后续行：统计实际<td>数量（考虑colspan）+ 上方rowspan占位的列数
        3. rowspan占位：如果上一行某单元格有rowspan=N，则后续N-1行该位置被占位
        
        例如：
        - 第一行：<td rowspan="4">A</td><td rowspan="4">B</td><td>C</td><td>D</td>
          列数 = 4（4个<td>，其中2个有rowspan，但不影响第一行的列数计算）
        - 第二行：<td>E</td><td>F</td>
          列数 = 2（实际<td>）+ 2（rowspan占位）= 4
        - 第三行：<td>G</td><td>H</td>
          列数 = 2（实际<td>）+ 2（rowspan占位）= 4
        """
        return compute_display_cols_impl(self, rows)
    
    def get_rowspan_info_from_previous_rows(self, rows: List[str], target_row_idx: int) -> List[Dict]:
        """
        从前面几行获取rowspan信息，重建目标行的完整列结构（包括rowspan占位）
        
        Args:
            rows: 所有行的列表
            target_row_idx: 目标行的索引（最后一行的索引）
            
        Returns:
            完整列结构列表，每个元素包含 {'attrs': str, 'content': str, 'is_rowspan_placeholder': bool}
        """
        return get_rowspan_info_from_previous_rows_impl(self, rows, target_row_idx)
    
    def merge_rows_with_rowspan(self, row1_full: List[Dict], row2: str, prev_rows: List[str] = None) -> tuple:
        """
        合并两行，考虑rowspan占位
        
        Args:
            row1_full: 第一行的完整列结构（包括rowspan占位）
            row2: 第二行的HTML
            prev_rows: 第二行所在页面的前面所有行（用于获取rowspan信息）
            
        Returns:
            (是否合并, 合并后的行HTML)
        """
        return merge_rows_with_rowspan_impl(self, row1_full, row2, prev_rows)
    
    def merge_two_rows(self, row1: str, row2: str) -> tuple:
        """
        尝试合并两行（仅用于上一页最后一行与下一页第一行）
        返回 (是否合并, 合并后的行)
        """
        return merge_two_rows_impl(self, row1, row2)
    
    def merge_cross_page_rows(self, all_html_parts: List[str]) -> List[str]:
        """
        严格顺序的跨页合并策略：
        - 只比较"上一页最后一行"与"下一页第一行"。
        - 每页的中间行绝不跨页合并，保持原顺序。
        - 如果一页只有一行，则这行同时作为首行和尾行参与跨页判断。
        """
        return merge_cross_page_rows_impl(self, all_html_parts)
    
    def absorb_empty_rowspan_cells(self, rows: List[str]) -> List[str]:
        """
        将跨页后半段中"空内容且带rowspan的单元格"吸收到前一段对应列的锚点单元格里，避免重复空列并累加rowspan。
        
        规则与流程：
        1) 解析每行<td>，记录rowspan/colspan，逐行进行列布局模拟（考虑上方rowspan占位），得到每个单元格的起始列索引start_col。
        2) 锚点：同列最近的"有内容"或"rowspan>1"的单元格。
        3) 如果某单元格内容为空、rowspan>1、且无colspan扩展，并且对应列已有锚点，则：
           - 将其rowspan累加到锚点的rowspan；
           - 当前单元格标记为删除。
        4) 重建HTML行，更新rowspan/colspan属性，移除被吸收的单元格。
        """
        return absorb_empty_rowspan_cells_impl(self, rows)
    
    def has_key_column_values(self, row_html: str) -> bool:
        """
        检查行的关键列（第一列，序号列）是否有值
        
        Args:
            row_html: 行的HTML
            
        Returns:
            如果第一列有值，返回True；否则返回False
        """
        return has_key_column_values_impl(self, row_html)
    
    def should_merge_rows(self, row1: str, row2: str, original_has_key_values: bool = None, has_next_new_row: bool = False) -> tuple:
        """
        判断两行是否应该合并，并返回合并后的行
        
        Args:
            row1: 前一页的最后一行HTML（可能是跨页延续，关键列可能为空）
            row2: 后一页的第一行HTML
            original_has_key_values: 原始行的关键列是否有值（用于判断row1是否是跨页延续）
            has_next_new_row: row2后面是否有新行（完整行，关键列有值）
            
        Returns:
            (是否合并, 合并后的行HTML)
        """

        return should_merge_rows_impl(self, row1, row2, original_has_key_values, has_next_new_row)
