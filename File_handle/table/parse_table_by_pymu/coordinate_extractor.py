# -*- coding: utf-8 -*-
"""
表格坐标提取模块

提取表格的详细坐标信息，包括行、列的边框线坐标
"""

from typing import Dict, List


def get_table_detailed_coordinates(table) -> Dict:
    """
    获取表格的详细坐标信息
    
    Args:
        table: PyMuPDF 的 Table 对象（通过 page.find_tables() 获取）
        
    Returns:
        包含详细坐标信息的字典：
        - rows: 按行组织的单元格坐标列表
        - cols: 按列组织的单元格坐标列表
        - row_col_counts: 每行的列数 {row_index: col_count}
        - col_row_counts: 每列的行数 {col_index: row_count}
    """
    if not hasattr(table, 'cells'):
        return {
            'rows': [],
            'cols': [],
            'row_col_counts': {},
            'col_row_counts': {}
        }
    
    cells = table.cells
    
    if not cells:
        return {
            'rows': [],
            'cols': [],
            'row_col_counts': {},
            'col_row_counts': {}
        }
    
    # 注意：table.cells 返回的是元组列表，每个元组是 (x0, y0, x1, y1)
    # 提取所有单元格的坐标
    cell_coords = []
    for cell in cells:
        if isinstance(cell, tuple) and len(cell) >= 4:
            x0, y0, x1, y1 = cell[0], cell[1], cell[2], cell[3]
            cell_coords.append((x0, y0, x1, y1))
        elif hasattr(cell, 'bbox'):
            # 兼容处理：如果是对象，尝试获取 bbox
            bbox = cell.bbox
            if isinstance(bbox, tuple):
                x0, y0, x1, y1 = bbox[0], bbox[1], bbox[2], bbox[3]
            else:
                x0, y0, x1, y1 = bbox.x0, bbox.y0, bbox.x1, bbox.y1
            cell_coords.append((x0, y0, x1, y1))
    
    if not cell_coords:
        return {
            'rows': [],
            'cols': [],
            'row_col_counts': {},
            'col_row_counts': {}
        }
    
    tolerance = 2.0  # 坐标容差（像素）
    
    # ========== 按行组织单元格 ==========
    # 收集所有唯一的 y0 坐标（行的起始位置）
    row_y_coords = set()
    for (x0, y0, x1, y1) in cell_coords:
        row_y_coords.add(round(y0, 1))
    
    sorted_row_y = sorted(row_y_coords)
    
    # 将单元格按行分组
    rows_data = []
    for row_idx, row_y0 in enumerate(sorted_row_y):
        # 找到 y0 接近 row_y0 的所有单元格（属于同一行）
        row_cells = []
        for (x0, y0, x1, y1) in cell_coords:
            if abs(y0 - row_y0) < tolerance:
                row_cells.append((x0, y0, x1, y1))
        
        if row_cells:
            # 按 x 坐标排序，确定列索引
            row_cells_sorted = sorted(row_cells, key=lambda c: c[0])
            
            # 计算行的 y_end（取该行所有单元格的最大 y1）
            row_y1 = max(y1 for (x0, y0, x1, y1) in row_cells_sorted)
            
            cells_info = []
            for col_idx, (x0, y0, x1, y1) in enumerate(row_cells_sorted):
                cells_info.append({
                    'col_index': col_idx,
                    'x_start': round(x0, 2),
                    'y_start': round(y0, 2),
                    'x_end': round(x1, 2),
                    'y_end': round(y1, 2),
                    'width': round(x1 - x0, 2),
                    'height': round(y1 - y0, 2)
                })
            
            rows_data.append({
                'row_index': row_idx,
                'y_start': round(row_y0, 2),
                'y_end': round(row_y1, 2),
                'height': round(row_y1 - row_y0, 2),
                'col_count': len(cells_info),
                'cells': cells_info
            })
    
    # ========== 按列组织单元格 ==========
    # 收集所有唯一的 x0 坐标（列的起始位置）
    col_x_coords = set()
    for (x0, y0, x1, y1) in cell_coords:
        col_x_coords.add(round(x0, 1))
    
    sorted_col_x = sorted(col_x_coords)
    
    # 将单元格按列分组
    cols_data = []
    for col_idx, col_x0 in enumerate(sorted_col_x):
        # 找到 x0 接近 col_x0 的所有单元格（属于同一列）
        col_cells = []
        for (x0, y0, x1, y1) in cell_coords:
            if abs(x0 - col_x0) < tolerance:
                col_cells.append((x0, y0, x1, y1))
        
        if col_cells:
            # 按 y 坐标排序，确定行索引
            col_cells_sorted = sorted(col_cells, key=lambda c: c[1])
            
            # 计算列的 x_end（取该列所有单元格的最大 x1）
            col_x1 = max(x1 for (x0, y0, x1, y1) in col_cells_sorted)
            
            cells_info = []
            for row_idx, (x0, y0, x1, y1) in enumerate(col_cells_sorted):
                cells_info.append({
                    'row_index': row_idx,
                    'x_start': round(x0, 2),
                    'y_start': round(y0, 2),
                    'x_end': round(x1, 2),
                    'y_end': round(y1, 2),
                    'width': round(x1 - x0, 2),
                    'height': round(y1 - y0, 2)
                })
            
            cols_data.append({
                'col_index': col_idx,
                'x_start': round(col_x0, 2),
                'x_end': round(col_x1, 2),
                'width': round(col_x1 - col_x0, 2),
                'row_count': len(cells_info),
                'cells': cells_info
            })
    
    # ========== 统计信息 ==========
    row_col_counts = {row['row_index']: row['col_count'] for row in rows_data}
    col_row_counts = {col['col_index']: col['row_count'] for col in cols_data}
    
    return {
        'rows': rows_data,
        'cols': cols_data,
        'row_col_counts': row_col_counts,
        'col_row_counts': col_row_counts
    }

