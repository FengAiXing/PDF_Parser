# -*- coding: utf-8 -*-
"""
文本提取模块

根据字符坐标判断每个字符属于哪个单元格，然后组合成文本
"""

import fitz  # PyMuPDF
from typing import Dict, List
from collections import defaultdict


def get_text_in_cells_by_char(table, page, rows_data: List[Dict] = None) -> Dict:
    """
    根据字符坐标判断每个字符属于哪个单元格，然后组合成文本
    
    Args:
        table: PyMuPDF 的 Table 对象
        page: PyMuPDF 的 Page 对象
        rows_data: 可选的rows_data，如果提供则使用它来构建cell_grid，确保索引一致
        
    Returns:
        字典，key为(row_idx, col_idx)，value为组合后的文本内容
    """
    # 如果提供了rows_data，直接使用它来构建cell_grid，确保索引一致
    if rows_data:
        cell_grid = {}  # {(row_idx, col_idx): (x0, y0, x1, y1)}
        for row in rows_data:
            row_idx = row['row_index']
            for cell in row['cells']:
                col_idx = cell['col_index']
                cell_grid[(row_idx, col_idx)] = (
                    cell['x_start'], cell['y_start'], 
                    cell['x_end'], cell['y_end']
                )
    else:
        # 如果没有提供rows_data，则使用原来的逻辑
        if not hasattr(table, 'cells'):
            return {}
        
        cells = table.cells
        if not cells:
            return {}
        
        # 提取单元格坐标
        cell_coords = []
        for cell in cells:
            if isinstance(cell, tuple) and len(cell) >= 4:
                x0, y0, x1, y1 = cell[0], cell[1], cell[2], cell[3]
                cell_coords.append((x0, y0, x1, y1))
        
        if not cell_coords:
            return {}
        
        # 按行组织单元格（用于匹配文本）
        tolerance = 2.0
        row_y_coords = set()
        for (x0, y0, x1, y1) in cell_coords:
            row_y_coords.add(round(y0, 1))
        
        sorted_row_y = sorted(row_y_coords)
        cell_grid = {}  # {(row_idx, col_idx): (x0, y0, x1, y1)}
        
        for row_idx, row_y0 in enumerate(sorted_row_y):
            row_cells = []
            for (x0, y0, x1, y1) in cell_coords:
                if abs(y0 - row_y0) < tolerance:
                    row_cells.append((x0, y0, x1, y1))
            
            if row_cells:
                row_cells_sorted = sorted(row_cells, key=lambda c: c[0])
                for col_idx, (x0, y0, x1, y1) in enumerate(row_cells_sorted):
                    cell_grid[(row_idx, col_idx)] = (x0, y0, x1, y1)
    
    # 获取页面文本块（带坐标）- 使用 rawdict 获取每个字符的精确坐标
    text_dict = page.get_text("rawdict")
    text_blocks = text_dict.get("blocks", [])
    
    # 计算整个表格的外接框，用于提前过滤不在表格范围内的字符
    if cell_grid:
        xs0, ys0, xs1, ys1 = zip(*cell_grid.values())
        table_bbox = (
            min(xs0),
            min(ys0),
            max(xs1),
            max(ys1)
        )
        # 允许的微小缓冲，避免边框贴边的文字被误剔除
        min_cell_height = min(ys1[i] - ys0[i] for i in range(len(ys0)))
        safety_margin = min(2.0, max(0.5, min_cell_height * 0.1))
    else:
        table_bbox = None
        safety_margin = 0.0
    
    # 存储每个单元格的字符（按位置排序）
    cell_chars = defaultdict(list)  # {(row_idx, col_idx): [{'char': str, 'x': float, 'y': float, 'x0': float, 'y0': float}]}
    
    # 遍历所有文本块，提取每个字符
    for block in text_blocks:
        if block.get("type") != 0:  # 只处理文本块
            continue
        
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                # 使用 rawdict 格式，直接获取每个字符的精确坐标
                chars = span.get("chars", [])
                
                if not chars:
                    continue
                
                # 遍历每个字符，获取其精确坐标
                for char_info in chars:
                    char_text = char_info.get("c", "")
                    char_bbox = char_info.get("bbox", [])
                    
                    if not char_text or len(char_bbox) < 4:
                        continue
                    
                    # 如果字符整体落在表格外侧，则直接跳过，避免页码/脚注被吸入表格
                    if table_bbox:
                        tb_x0, tb_y0, tb_x1, tb_y1 = table_bbox
                        if not (tb_x0 - safety_margin <= char_bbox[0] <= tb_x1 + safety_margin and
                                tb_x0 - safety_margin <= char_bbox[2] <= tb_x1 + safety_margin and
                                tb_y0 - safety_margin <= char_bbox[1] <= tb_y1 + safety_margin and
                                tb_y0 - safety_margin <= char_bbox[3] <= tb_y1 + safety_margin):
                            continue
                    
                    # 获取字符的精确边界框坐标
                    char_x0, char_y0, char_x1, char_y1 = char_bbox[0], char_bbox[1], char_bbox[2], char_bbox[3]
                    char_center_x = (char_x0 + char_x1) / 2
                    char_center_y = (char_y0 + char_y1) / 2
                    
                    # 构建字符信息字典（用于存储和排序）
                    char_data = {
                        'char': char_text,
                        'x': char_center_x,
                        'y': char_center_y,
                        'x0': char_x0,
                        'y0': char_y0
                    }
                    
                    # 找到包含这个字符的单元格
                    # 优先使用边界框重叠匹配，如果失败则使用中心点匹配
                    matched = False
                    for (row_idx, col_idx), (cell_x0, cell_y0, cell_x1, cell_y1) in cell_grid.items():
                        # 检查字符的边界框是否与单元格有重叠
                        if (char_x0 < cell_x1 and char_x1 > cell_x0 and 
                            char_y0 < cell_y1 and char_y1 > cell_y0):
                            cell_chars[(row_idx, col_idx)].append(char_data)
                            matched = True
                            break
                    
                    # 如果边界框匹配失败，尝试使用中心点匹配（向后兼容）
                    if not matched:
                        for (row_idx, col_idx), (cell_x0, cell_y0, cell_x1, cell_y1) in cell_grid.items():
                            if (cell_x0 <= char_center_x <= cell_x1 and 
                                cell_y0 <= char_center_y <= cell_y1):
                                cell_chars[(row_idx, col_idx)].append(char_data)
                                break
    
    # 对每个单元格的字符进行排序并组合，根据纵坐标判断是否需要换行
    cell_texts = {}
    threshold = 2.0  # 纵坐标容差阈值，用于判断是否属于同一行
    
    for (row_idx, col_idx), chars in cell_chars.items():
        if not chars:
            cell_texts[(row_idx, col_idx)] = ""
            continue
        
        # 按 y 坐标分组，判断哪些字符属于同一行
        # 先按 y0 坐标排序
        chars_sorted = sorted(chars, key=lambda c: (c['y0'], c['x']))
        
        # 按 y 坐标分组
        lines = []  # 每一行的字符列表
        current_line = [chars_sorted[0]]
        current_y = chars_sorted[0]['y0']
        
        for char_info in chars_sorted[1:]:
            char_y = char_info['y0']
            # 如果纵坐标差值小于阈值，视为同一行
            if abs(char_y - current_y) < threshold:
                current_line.append(char_info)
            else:
                # 纵坐标不同，开始新的一行
                # 对当前行的字符按 x 坐标排序
                current_line_sorted = sorted(current_line, key=lambda c: c['x'])
                lines.append(current_line_sorted)
                current_line = [char_info]
                current_y = char_y
        
        # 添加最后一行
        if current_line:
            current_line_sorted = sorted(current_line, key=lambda c: c['x'])
            lines.append(current_line_sorted)
        
        # 组合文本：每行内的字符直接连接，行与行之间用<br>分隔
        text_parts = []
        for line_chars in lines:
            line_text = ''.join(c['char'] for c in line_chars)
            text_parts.append(line_text)
        
        text = '<br>'.join(text_parts)
        cell_texts[(row_idx, col_idx)] = text.strip()
    
    return cell_texts

