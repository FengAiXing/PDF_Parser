# -*- coding: utf-8 -*-
"""
边框线检测模块

通过检测边框线来手动构建表格
"""

import fitz  # PyMuPDF
from typing import List


def detect_tables_from_borders(page) -> List:
    """
    通过检测边框线来手动构建表格
    
    Args:
        page: PyMuPDF 的 Page 对象
        
    Returns:
        表格对象列表（模拟PyMuPDF Table对象）
    """
    # 获取页面上的所有绘图路径（包括线条）
    drawings = page.get_drawings()
    
    # 收集所有水平和垂直线条
    horizontal_lines = []  # [(x0, y, x1, y)]
    vertical_lines = []    # [(x, y0, x, y1)]
    
    threshold = 2.0  # 线条容差
    
    for drawing in drawings:
        if 'items' in drawing:
            for item in drawing['items']:
                if item[0] == 'l':  # 直线
                    x0, y0 = item[1]
                    x1, y1 = item[2]
                    
                    # 判断是水平线还是垂直线
                    if abs(y1 - y0) < threshold:  # 水平线
                        y = (y0 + y1) / 2
                        horizontal_lines.append((min(x0, x1), y, max(x0, x1), y))
                    elif abs(x1 - x0) < threshold:  # 垂直线
                        x = (x0 + x1) / 2
                        vertical_lines.append((x, min(y0, y1), x, max(y0, y1)))
                elif item[0] == 're':  # 矩形
                    rect = item[1]  # (x0, y0, x1, y1)
                    x0, y0, x1, y1 = rect
                    # 将矩形转换为4条线
                    horizontal_lines.append((x0, y0, x1, y0))  # 上边
                    horizontal_lines.append((x0, y1, x1, y1))  # 下边
                    vertical_lines.append((x0, y0, x0, y1))    # 左边
                    vertical_lines.append((x1, y0, x1, y1))    # 右边
    
    if not horizontal_lines or not vertical_lines:
        return []
    
    # 合并相近的线条
    def merge_lines(lines, is_horizontal=True):
        """合并相近的线条"""
        if not lines:
            return []
        
        # 按坐标排序
        if is_horizontal:
            lines_sorted = sorted(lines, key=lambda l: l[1])  # 按y坐标排序
        else:
            lines_sorted = sorted(lines, key=lambda l: l[0])  # 按x坐标排序
        
        merged = [lines_sorted[0]]
        for line in lines_sorted[1:]:
            last_line = merged[-1]
            if is_horizontal:
                # 水平线：如果y坐标相近，合并
                if abs(line[1] - last_line[1]) < threshold:
                    # 合并：取x范围更大的
                    merged[-1] = (min(last_line[0], line[0]), last_line[1], 
                                 max(last_line[2], line[2]), last_line[3])
                else:
                    merged.append(line)
            else:
                # 垂直线：如果x坐标相近，合并
                if abs(line[0] - last_line[0]) < threshold:
                    # 合并：取y范围更大的
                    merged[-1] = (last_line[0], min(last_line[1], line[1]),
                                 last_line[2], max(last_line[3], line[3]))
                else:
                    merged.append(line)
        
        return merged
    
    horizontal_lines = merge_lines(horizontal_lines, is_horizontal=True)
    vertical_lines = merge_lines(vertical_lines, is_horizontal=False)
    
    # 找出能形成封闭矩形的线条组合
    # 简化处理：找出所有横线和竖线的交点，形成单元格
    
    # 收集所有唯一的x和y坐标
    x_coords = set()
    y_coords = set()
    
    for line in horizontal_lines:
        y_coords.add(round(line[1], 1))
    for line in vertical_lines:
        x_coords.add(round(line[0], 1))
    
    sorted_x = sorted(x_coords)
    sorted_y = sorted(y_coords)
    
    # 如果至少有2条横线和2条竖线，可以形成表格
    if len(sorted_x) >= 2 and len(sorted_y) >= 2:
        # 创建单元格
        cells = []
        for i in range(len(sorted_y) - 1):
            for j in range(len(sorted_x) - 1):
                x0 = sorted_x[j]
                y0 = sorted_y[i]
                x1 = sorted_x[j + 1]
                y1 = sorted_y[i + 1]
                cells.append((x0, y0, x1, y1))
        
        # 创建模拟的Table对象
        class ManualTable:
            def __init__(self, cells, bbox):
                self.cells = cells
                self.bbox = bbox
            
            def extract(self):
                # 返回空数据，实际内容会通过字符匹配获取
                return [[""] * (len(sorted_x) - 1) for _ in range(len(sorted_y) - 1)]
        
        # 计算表格边界框
        bbox = (sorted_x[0], sorted_y[0], sorted_x[-1], sorted_y[-1])
        table = ManualTable(cells, bbox)
        
        return [table]
    
    return []

