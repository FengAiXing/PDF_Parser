# -*- coding: utf-8 -*-
"""
表格提取模块

从PDF中提取表格及其详细坐标信息
"""

import fitz  # PyMuPDF
from typing import List, Dict

from .coordinate_extractor import get_table_detailed_coordinates
from .text_extractor import get_text_in_cells_by_char
from .html_converter import convert_table_to_html
from .table_drawer import draw_table_simple
from .border_detector import detect_tables_from_borders


def extract_tables_with_detailed_coords(pdf_path: str) -> List[Dict]:
    """
    从 PDF 中提取表格及其详细坐标信息
    
    Args:
        pdf_path: PDF 文件路径
        
    Returns:
        表格列表，每个表格包含：
        - page: 页码
        - table_index: 表格索引
        - bbox: 表格边界框
        - data: 表格数据
        - rows: 按行组织的单元格坐标
        - cols: 按列组织的单元格坐标
        - row_col_counts: 每行的列数
        - col_row_counts: 每列的行数
    """
    doc = fitz.open(pdf_path)
    all_tables = []
    
    try:
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # 查找表格，尝试不同的参数以提高识别率
            table_finder = None
            tables = []
            
            # 方法1：使用默认参数
            try:
                table_finder = page.find_tables()
                if table_finder and table_finder.tables:
                    tables = table_finder.tables
            except Exception as e:
                print(f"  第 {page_num + 1} 页，默认方法失败: {e}")
            
            # 如果默认方法没找到，尝试其他策略
            if not tables:
                try:
                    # 方法2：使用线条检测策略
                    table_finder = page.find_tables(
                        strategy="lines",
                        vertical_strategy="lines",
                        horizontal_strategy="lines"
                    )
                    if table_finder and table_finder.tables:
                        tables = table_finder.tables
                except Exception as e:
                    print(f"  第 {page_num + 1} 页，线条策略失败: {e}")
            
            # 如果还没找到，尝试文本检测策略
            if not tables:
                try:
                    table_finder = page.find_tables(
                        strategy="text",
                        vertical_strategy="text",
                        horizontal_strategy="text"
                    )
                    if table_finder and table_finder.tables:
                        tables = table_finder.tables
                except Exception as e:
                    print(f"  第 {page_num + 1} 页，文本策略失败: {e}")
            
            # 如果还没找到，尝试基于边框线的手动检测
            if not tables:
                try:
                    manual_tables = detect_tables_from_borders(page)
                    if manual_tables:
                        tables = manual_tables
                        print(f"  第 {page_num + 1} 页，边框线检测找到 {len(tables)} 个表格")
                except Exception as e:
                    print(f"  第 {page_num + 1} 页，边框线检测失败: {e}")
            
            if tables:
                for table_idx, table in enumerate(tables):
                    # 获取详细坐标信息
                    detailed_coords = get_table_detailed_coordinates(table)
                    
                    # 根据字符坐标判断每个字符属于哪个单元格，然后组合成文本
                    # 传入rows_data确保索引一致
                    cell_texts = get_text_in_cells_by_char(table, page, detailed_coords['rows'])
                    
                    table_info = {
                        'page': page_num + 1,
                        'table_index': table_idx + 1,
                        'bbox': table.bbox,  # (x0, y0, x1, y1)
                        'data': table.extract(),  # 表格数据
                        'rows': detailed_coords['rows'],
                        'cols': detailed_coords['cols'],
                        'row_col_counts': detailed_coords['row_col_counts'],
                        'col_row_counts': detailed_coords['col_row_counts'],
                        'cell_texts': cell_texts  # 根据坐标匹配的文本
                    }
                    
                    all_tables.append(table_info)
                    
                    # 打印详细信息
                    print(f"\n{'='*80}")
                    print(f"第 {page_num + 1} 页，表格 {table_idx + 1}")
                    print(f"{'='*80}")
                    print(f"表格边界框: {table.bbox}")
                    print(f"\n【行信息】")
                    print(f"  总行数: {len(detailed_coords['rows'])}")
                    print(f"  每行的列数: {detailed_coords['row_col_counts']}")
                    
                    for row in detailed_coords['rows']:
                        print(f"\n  行 {row['row_index']} (y={row['y_start']:.2f} ~ {row['y_end']:.2f}, 高度={row['height']:.2f}, 列数={row['col_count']}):")
                        for cell in row['cells']:
                            print(f"    列 {cell['col_index']}: x={cell['x_start']:.2f}~{cell['x_end']:.2f}, y={cell['y_start']:.2f}~{cell['y_end']:.2f}")
                    
                    print(f"\n【列信息】")
                    print(f"  总列数: {len(detailed_coords['cols'])}")
                    print(f"  每列的行数: {detailed_coords['col_row_counts']}")
                    
                    for col in detailed_coords['cols']:
                        print(f"\n  列 {col['col_index']} (x={col['x_start']:.2f} ~ {col['x_end']:.2f}, 宽度={col['width']:.2f}, 行数={col['row_count']}):")
                        for cell in col['cells']:
                            print(f"    行 {cell['row_index']}: x={cell['x_start']:.2f}~{cell['x_end']:.2f}, y={cell['y_start']:.2f}~{cell['y_end']:.2f}")
                    
                    # 显示根据字符坐标匹配的文本
                    if cell_texts:
                        print(f"\n【根据字符坐标匹配的文本】")
                        for (row_idx, col_idx), text in sorted(cell_texts.items()):
                            print(f"  单元格 ({row_idx}, {col_idx}): '{text}'")
                    
                    # 只绘制表格框架（不填充文本）
                    print(f"\n{'='*80}")
                    print(f"【绘制的表格框架】")
                    print(f"{'='*80}")
                    
                    # 不传入表格数据，只绘制空表格框架
                    table_drawing = draw_table_simple(detailed_coords['rows'], None)
                    print(table_drawing)
                    
                    # 转换为HTML格式（使用坐标匹配的文本填充）
                    print(f"\n{'='*80}")
                    print(f"【HTML格式的表格（使用坐标匹配的文本）】")
                    print(f"{'='*80}")
                    
                    # 构建表格数据（使用坐标匹配的文本）
                    # 将cell_texts转换为按rows_data索引的格式
                    table_data_from_coords = []
                    for row in detailed_coords['rows']:
                        row_data = []
                        for cell in row['cells']:
                            # cell_texts的key是(row_idx, col_idx)，对应rows_data的row_index和cell的col_index
                            key = (row['row_index'], cell['col_index'])
                            text = cell_texts.get(key, "")
                            row_data.append(text)
                        table_data_from_coords.append(row_data)
                    
                    # 使用坐标匹配的文本填充HTML表格
                    html_table = convert_table_to_html(detailed_coords['rows'], table_data_from_coords)
                    print(html_table)
    
    finally:
        doc.close()
    
    return all_tables

