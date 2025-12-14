# -*- coding: utf-8 -*-
"""
HTML转换模块

将表格转换为HTML格式（table/tr/td标签）
"""

from typing import List, Dict, Optional


def convert_table_to_html(
    rows_data: List[Dict],
    table_data: List[List] = None,
    merged_vertical_lines: Optional[List[float]] = None,
    tolerance: float = 2.0,
) -> str:
    """
    将表格转换为HTML格式（table/tr/td标签）
    直接按照rows_data的顺序填充，处理rowspan时跳过被占用的列
    
    Args:
        rows_data: 按行组织的单元格坐标数据
        table_data: 可选的表格数据
        
    Returns:
        HTML格式的表格字符串
    """
    if not rows_data:
        return "<table></table>"
    
    # 收集所有唯一的 x 和 y 坐标
    x_coords = set()
    y_coords = set()
    
    for row in rows_data:
        y_coords.add(round(row['y_start'], 1))
        y_coords.add(round(row['y_end'], 1))
        for cell in row['cells']:
            x_coords.add(round(cell['x_start'], 1))
            x_coords.add(round(cell['x_end'], 1))
    
    sorted_y = sorted(y_coords)
    
    # 对坐标进行去重：如果两个坐标的差值小于阈值，则视为同一条线
    def merge_close_coords(coords_list, threshold):
        """合并相近的坐标"""
        if not coords_list:
            return []
        
        sorted_coords = sorted(set(coords_list))
        merged = [sorted_coords[0]]
        
        for coord in sorted_coords[1:]:
            # 如果当前坐标与已合并的最后一个坐标的差值小于阈值，则视为同一条线
            if coord - merged[-1] >= threshold:
                merged.append(coord)
            else:
                merged[-1] = (merged[-1] + coord) / 2
        
        return merged
    
    # 纵向边框线：优先使用跨页合并后的坐标；否则按当前表格自身坐标
    all_x_coords_list = []
    for row in rows_data:
        for cell in row['cells']:
            all_x_coords_list.append(round(cell['x_start'], 1))
            all_x_coords_list.append(round(cell['x_end'], 1))

    if merged_vertical_lines:
        merged_lines = merge_close_coords([round(x, 1) for x in merged_vertical_lines], tolerance)
        local_lines = merge_close_coords(all_x_coords_list, tolerance)
        # 避免跨页合并线过少导致列数变小：取列线数量更多的那组
        sorted_x_coords = merged_lines if len(merged_lines) >= len(local_lines) else local_lines
    else:
        sorted_x_coords = merge_close_coords(all_x_coords_list, tolerance)
    
    sorted_y_coords = merge_close_coords(list(y_coords), tolerance)  # 去重后的横边框线坐标
    
    # 创建坐标到索引的映射（纵坐标使用近邻匹配，容差=tolerance）
    x_to_idx = {x: i for i, x in enumerate(sorted_x_coords)}
    y_to_idx = {y: i for i, y in enumerate(sorted_y)}
    
    def find_nearest_idx(val: float, coords: List[float], tol: float) -> int:
        """在容差范围内找到最接近的坐标索引；未找到返回-1。"""
        best_idx = -1
        best_diff = tol
        for i, c in enumerate(coords):
            diff = abs(c - val)
            if diff < best_diff:
                best_diff = diff
                best_idx = i
        return best_idx
    
    # 简化逻辑：直接按照rows_data顺序填充，处理rowspan时跳过被占用的列
    html_lines = ["<table>"]
    
    # 第一遍：计算每个单元格的rowspan和colspan，并记录哪些列被rowspan占用
    # row_occupied_cols[row_data_idx] = set of column indices occupied by rowspan from previous rows
    row_occupied_cols = [set() for _ in range(len(rows_data))]
    cell_info = {}  # {(row_data_idx, col_index): {'rowspan': ..., 'colspan': ...}}
    
    for row_data_idx, row in enumerate(rows_data):
        for cell in row['cells']:
            x_start = round(cell['x_start'], 1)
            x_end = round(cell['x_end'], 1)
            y_start = round(cell['y_start'], 1)
            y_end = round(cell['y_end'], 1)
            
            col_start_idx = find_nearest_idx(x_start, sorted_x_coords, tolerance)
            col_end_idx = find_nearest_idx(x_end, sorted_x_coords, tolerance)
            
            if col_start_idx >= 0 and col_end_idx > col_start_idx:
                # 计算colspan：在x_start到x_end之间有多少条纵边框线（不包括起始和结束的）
                # 使用阈值判断，避免因坐标精度问题导致误判
                colspan = 1
                for x_coord in sorted_x_coords:
                    if x_start + tolerance < x_coord < x_end - tolerance:
                        colspan += 1
                
                # 计算rowspan：在y_start到y_end之间有多少条横边框线（不包括起始和结束的）
                # 使用阈值判断，避免因坐标精度问题导致误判
                rowspan = 1
                for y_coord in sorted_y_coords:
                    if y_start + tolerance < y_coord < y_end - tolerance:
                        rowspan += 1
                
                # 确保colspan和rowspan至少为1（单个单元格的情况）
                colspan = max(1, colspan)
                rowspan = max(1, rowspan)
                
                cell_info[(row_data_idx, cell['col_index'])] = {
                    'rowspan': rowspan,
                    'colspan': colspan,
                    'col_start_idx': col_start_idx,
                    'col_end_idx': col_end_idx
                }
                
                # 如果rowspan > 1，标记后续行中被占用的列
                if rowspan > 1:
                    # 找到这个单元格跨越了哪些逻辑行
                    # 从当前行开始，找到rowspan个逻辑行
                    for affected_row_idx in range(row_data_idx + 1, min(row_data_idx + rowspan, len(rows_data))):
                        for col_offset in range(colspan):
                            row_occupied_cols[affected_row_idx].add(col_start_idx + col_offset)
    
    # 第二遍：生成HTML，按行填充
    for row_data_idx, row in enumerate(rows_data):
        html_lines.append("  <tr>")
        
        # 按x坐标排序单元格，确保顺序正确
        row_cells_sorted = sorted(row['cells'], key=lambda c: c['x_start'])
        
        # 当前列位置（用于填充空列）
        current_col_idx = 0
        
        for cell in row_cells_sorted:
            x_start = round(cell['x_start'], 1)
            # 优先用预先计算的start_idx；否则用近邻匹配，避免跨页列线差异导致落不到索引
            info = cell_info.get((row_data_idx, cell['col_index']), {})
            col_start_idx = info.get('col_start_idx', x_to_idx.get(x_start, -1))
            if col_start_idx < 0:
                col_start_idx = find_nearest_idx(x_start, sorted_x_coords, tolerance)
            
            # 填充当前列到cell起始列之间的空列（如果不在rowspan占用范围内）
            while current_col_idx < col_start_idx:
                if current_col_idx not in row_occupied_cols[row_data_idx]:
                    html_lines.append("    <td></td>")
                current_col_idx += 1
            
            if col_start_idx >= 0:
                # 获取单元格信息
                rowspan = info.get('rowspan', 1)
                colspan = info.get('colspan', 1)
                
                # 获取单元格内容
                cell_text = ""
                if table_data is not None and row_data_idx < len(table_data):
                    row_data = table_data[row_data_idx]
                    if cell['col_index'] < len(row_data):
                        cell_text = str(row_data[cell['col_index']]) if row_data[cell['col_index']] else ""
                
                # 构建td标签属性
                attrs = []
                if colspan > 1:
                    attrs.append(f'colspan="{colspan}"')
                if rowspan > 1:
                    attrs.append(f'rowspan="{rowspan}"')
                
                attr_str = ' ' + ' '.join(attrs) if attrs else ''
                
                # 转义HTML特殊字符，但保留<br>标签
                # 先保护<br>标签
                cell_text = cell_text.replace('<br>', '___BR_TAG___')
                # 转义其他HTML特殊字符
                cell_text = cell_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
                # 恢复<br>标签
                cell_text = cell_text.replace('___BR_TAG___', '<br>')
                
                html_lines.append(f"    <td{attr_str}>{cell_text}</td>")
                current_col_idx = info.get('col_end_idx', col_start_idx + 1)
        
        # 补齐行尾缺失的空列，确保列数与纵向边框线一致
        total_cols = max(0, len(sorted_x_coords) - 1)
        while current_col_idx < total_cols:
            if current_col_idx not in row_occupied_cols[row_data_idx]:
                html_lines.append("    <td></td>")
            current_col_idx += 1
        
        html_lines.append("  </tr>")
    
    html_lines.append("</table>")
    return "\n".join(html_lines)

