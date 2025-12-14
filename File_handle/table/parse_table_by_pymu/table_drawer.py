# -*- coding: utf-8 -*-
"""
表格绘制模块

绘制ASCII艺术表格
"""

from typing import List, Dict


def draw_table_simple(rows_data: List[Dict], table_data: List[List] = None) -> str:
    """
    简化版表格绘制（正确处理合并单元格，包括rowspan）
    
    Args:
        rows_data: 按行组织的单元格坐标数据
        table_data: 可选的表格数据
        
    Returns:
        绘制好的表格字符串
    """
    if not rows_data:
        return "（空表格）"
    
    # 收集所有唯一的 x 坐标（列边界）和 y 坐标（行边界）
    x_coords = set()
    y_coords = set()
    
    for row in rows_data:
        y_coords.add(round(row['y_start'], 1))
        y_coords.add(round(row['y_end'], 1))
        for cell in row['cells']:
            x_coords.add(round(cell['x_start'], 1))
            x_coords.add(round(cell['x_end'], 1))
    
    sorted_x = sorted(x_coords)
    sorted_y = sorted(y_coords)
    
    # 创建坐标到索引的映射
    x_to_idx = {x: i for i, x in enumerate(sorted_x)}
    y_to_idx = {y: i for i, y in enumerate(sorted_y)}
    
    # 计算列数和行数
    num_cols = len(sorted_x) - 1
    num_rows = len(sorted_y) - 1
    
    # 创建一个网格来存储单元格信息
    # grid[row][col] = {'text': '', 'colspan': 1, 'rowspan': 1, 'used': False}
    grid = [[{'text': '', 'colspan': 1, 'rowspan': 1, 'used': False} 
             for _ in range(num_cols)] for _ in range(num_rows)]
    
    # 填充网格 - 遍历所有行的所有单元格
    for row_data_idx, row in enumerate(rows_data):
        for cell in row['cells']:
            # 找到单元格在网格中的位置
            x_start = round(cell['x_start'], 1)
            x_end = round(cell['x_end'], 1)
            y_start = round(cell['y_start'], 1)
            y_end = round(cell['y_end'], 1)
            
            col_start_idx = x_to_idx.get(x_start, -1)
            col_end_idx = x_to_idx.get(x_end, -1)
            row_start_idx = y_to_idx.get(y_start, -1)
            row_end_idx = y_to_idx.get(y_end, -1)
            
            if (col_start_idx >= 0 and col_end_idx > col_start_idx and 
                row_start_idx >= 0 and row_end_idx > row_start_idx and
                row_start_idx < num_rows and col_start_idx < num_cols):
                
                # 获取单元格内容
                cell_text = ""
                if table_data and row_data_idx < len(table_data):
                    row_data = table_data[row_data_idx]
                    if cell['col_index'] < len(row_data):
                        cell_text = str(row_data[cell['col_index']]) if row_data[cell['col_index']] else ""
                
                # 计算 colspan 和 rowspan
                colspan = col_end_idx - col_start_idx
                rowspan = row_end_idx - row_start_idx
                
                # 存储到网格（只存储左上角位置）
                if not grid[row_start_idx][col_start_idx]['used']:
                    grid[row_start_idx][col_start_idx] = {
                        'text': cell_text,
                        'colspan': colspan,
                        'rowspan': rowspan,
                        'used': True
                    }
    
    # 计算每列的最大宽度
    col_widths = [10] * num_cols
    for row in grid:
        col_idx = 0
        while col_idx < num_cols:
            cell = row[col_idx]
            if cell['used']:
                # 计算这个单元格占用的总宽度
                cell_width = sum(col_widths[col_idx + i] for i in range(min(cell['colspan'], num_cols - col_idx)))
                text_width = len(cell['text']) + 2
                if text_width > cell_width:
                    # 需要增加宽度
                    extra = text_width - cell_width
                    per_col = extra // cell['colspan'] + 1
                    for i in range(min(cell['colspan'], num_cols - col_idx)):
                        col_widths[col_idx + i] = max(col_widths[col_idx + i], per_col)
                col_idx += cell['colspan']
            else:
                col_idx += 1
    
    # 确保最小宽度
    col_widths = [max(w, 8) for w in col_widths]
    
    result = []
    
    # 绘制顶部边框
    top_line = "┌"
    for i in range(num_cols):
        top_line += "─" * col_widths[i]
        if i < num_cols - 1:
            top_line += "┬"
    top_line += "┐"
    result.append(top_line)
    
    # 绘制每一行
    for row_idx, row in enumerate(grid):
        # 内容行
        content_line = "│"
        separator_parts = []
        
        col_idx = 0
        while col_idx < num_cols:
            # 检查这个位置是否被上面的rowspan占用
            occupied_by = None
            for check_row_idx in range(row_idx):
                if col_idx < num_cols:
                    check_cell = grid[check_row_idx][col_idx]
                    if (check_cell['used'] and 
                        check_cell['rowspan'] > 1 and
                        check_row_idx + check_cell['rowspan'] > row_idx):
                        occupied_by = check_cell
                        break
            
            if occupied_by:
                # 这个位置被上面的单元格占用（rowspan）
                cell_width = sum(col_widths[col_idx + i] for i in range(min(occupied_by['colspan'], num_cols - col_idx)))
                # 绘制空内容（跨行单元格在后续行不显示内容）
                content_line += " " * cell_width
                if col_idx + occupied_by['colspan'] < num_cols:
                    content_line += "│"
                separator_parts.append((" " * cell_width, col_idx + occupied_by['colspan'] < num_cols))
                col_idx += occupied_by['colspan']
            elif row[col_idx]['used']:
                # 当前单元格
                cell = row[col_idx]
                cell_text = cell['text']
                cell_width = sum(col_widths[col_idx + i] for i in range(min(cell['colspan'], num_cols - col_idx)))
                
                # 截断过长的文本
                if len(cell_text) > cell_width - 2:
                    cell_text = cell_text[:cell_width - 5] + "..."
                
                # 居中显示
                padded_text = cell_text.center(cell_width)
                content_line += padded_text
                
                # 分隔符
                if col_idx + cell['colspan'] < num_cols:
                    content_line += "│"
                
                # 分隔行部分
                separator_parts.append(("─" * cell_width, col_idx + cell['colspan'] < num_cols))
                
                col_idx += cell['colspan']
            else:
                # 空单元格
                content_line += " " * col_widths[col_idx] + "│"
                separator_parts.append(("─" * col_widths[col_idx], col_idx + 1 < num_cols))
                col_idx += 1
        
        content_line += "│"
        result.append(content_line)
        
        # 分隔行（最后一行用底部边框）
        if row_idx < num_rows - 1:
            # 构建分隔行，需要考虑rowspan
            separator_line = "├"
            col_idx = 0
            while col_idx < num_cols:
                # 检查这个位置是否被上面的rowspan占用
                occupied_by = None
                for check_row_idx in range(row_idx + 1):
                    if col_idx < num_cols:
                        check_cell = grid[check_row_idx][col_idx]
                        if (check_cell['used'] and 
                            check_cell['rowspan'] > 1 and
                            check_row_idx + check_cell['rowspan'] > row_idx + 1):
                            occupied_by = check_cell
                            break
                
                if occupied_by:
                    # rowspan继续，使用空格（不绘制横线）
                    cell_width = sum(col_widths[col_idx + i] for i in range(min(occupied_by['colspan'], num_cols - col_idx)))
                    separator_line += " " * cell_width
                    if col_idx + occupied_by['colspan'] < num_cols:
                        separator_line += "│"  # 使用竖线分隔
                    col_idx += occupied_by['colspan']
                else:
                    # 正常分隔符
                    separator_line += "─" * col_widths[col_idx]
                    if col_idx < num_cols - 1:
                        separator_line += "┼"
                    col_idx += 1
            
            separator_line = separator_line.rstrip("│").rstrip(" ") + "┤"
            result.append(separator_line)
    
    # 绘制底部边框
    bottom_line = "└"
    for i in range(num_cols):
        bottom_line += "─" * col_widths[i]
        if i < num_cols - 1:
            bottom_line += "┴"
    bottom_line += "┘"
    result.append(bottom_line)
    
    return "\n".join(result)

