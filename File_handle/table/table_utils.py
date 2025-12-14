# -*- coding: utf-8 -*-
"""
表格工具函数 - table_utils

提供表格解析所需的各种辅助函数：
- 表格图片裁剪
- bbox重叠计算
- 矩形框检测
- 表格有效性验证
- 表格数据提取
"""

import os
import logging
import tempfile
from typing import List, Tuple, Optional

import fitz  # PyMuPDF

from .parse_table_by_pymu import (
    get_table_detailed_coordinates,
    get_text_in_cells_by_char,
    convert_table_to_html,
    extract_text_from_bbox_to_html
)


def crop_table_image(page, bbox: Tuple, output_dir: str, filename: str, 
                     save_to_disk: bool = True, config=None, logger=None) -> str:
    """
    裁剪表格区域为图片
    
    Args:
        page: PyMuPDF页面对象
        bbox: 边界框 (x0, y0, x1, y1)
        output_dir: 输出目录
        filename: 文件名（不含扩展名）
        save_to_disk: 是否保存到磁盘
        config: Config对象（用于检查是否需要保存）
        logger: 日志对象
        
    Returns:
        图片文件路径（如果 save_to_disk=False，返回临时路径）
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        # 添加边距（扩大2像素）
        x0, y0, x1, y1 = bbox
        margin = 2
        
        # 确保不超出页面边界
        page_rect = page.rect
        x0 = max(0, x0 - margin)
        y0 = max(0, y0 - margin)
        x1 = min(page_rect.width, x1 + margin)
        y1 = min(page_rect.height, y1 + margin)
        
        # 创建裁剪矩形
        clip_rect = fitz.Rect(x0, y0, x1, y1)
        
        # 使用较高分辨率渲染（提高OCR识别率）
        mat = fitz.Matrix(3.0, 3.0)  # 3倍缩放
        pix = page.get_pixmap(matrix=mat, clip=clip_rect)
        
        # 根据 config 决定是否保存到磁盘
        should_save = save_to_disk
        if config is not None:
            should_save = save_to_disk and config.should_save_table_images()
        
        if should_save:
            image_path = os.path.join(output_dir, f"{filename}.png")
            pix.save(image_path)
            logger.debug(f"表格图片已保存: {image_path}")
            return image_path
        else:
            # 不保存到磁盘时，使用临时文件（用于后续处理）
            temp_path = os.path.join(tempfile.gettempdir(), f"{filename}.png")
            pix.save(temp_path)
            return temp_path
        
    except Exception as e:
        logger.error(f"裁剪表格图片失败: {e}")
        return None


def bbox_overlap_ratio(bbox1: tuple, bbox2: tuple) -> float:
    """
    计算两个bbox的重叠率（重叠面积 / 较小bbox的面积）
    
    Args:
        bbox1: (x0, y0, x1, y1)
        bbox2: (x0, y0, x1, y1)
        
    Returns:
        重叠率 (0.0-1.0)
    """
    # 计算交集
    x_left = max(bbox1[0], bbox2[0])
    y_top = max(bbox1[1], bbox2[1])
    x_right = min(bbox1[2], bbox2[2])
    y_bottom = min(bbox1[3], bbox2[3])
    
    if x_right < x_left or y_bottom < y_top:
        return 0.0  # 没有交集
    
    # 交集面积
    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    
    # 两个bbox的面积
    area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
    area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
    
    # 相对于较小bbox的重叠率
    smaller_area = min(area1, area2)
    if smaller_area == 0:
        return 0.0
    
    return intersection_area / smaller_area


def detect_rectangular_boxes(page, logger=None) -> list:
    """
    检测页面中由绘图元素组成的矩形框（通常是只有外框的"表格"）
    
    Args:
        page: PyMuPDF页面对象
        logger: 日志对象
        
    Returns:
        矩形框列表，每个元素是一个bbox元组(x0, y0, x1, y1)
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        drawings = page.get_drawings()
        if not drawings:
            return []
        
        # 提取所有线条
        horizontal_lines = []  # (y, x0, x1)
        vertical_lines = []    # (x, y0, y1)
        
        for drawing in drawings:
            if drawing.get('type') == 's':  # stroke线条
                rect = drawing.get('rect')
                if not rect:
                    continue
                
                # 判断是水平线还是垂直线
                if abs(rect.y1 - rect.y0) < 2:  # 水平线
                    horizontal_lines.append((rect.y0, rect.x0, rect.x1))
                elif abs(rect.x1 - rect.x0) < 2:  # 垂直线
                    vertical_lines.append((rect.x0, rect.y0, rect.y1))
        
        # 尝试组合成矩形
        boxes = []
        tolerance = 5  # 位置容差
        
        # 对于每一对水平线，尝试找到对应的垂直线组成矩形
        for i, (y_top, x_top_left, x_top_right) in enumerate(horizontal_lines):
            for j, (y_bottom, x_bottom_left, x_bottom_right) in enumerate(horizontal_lines):
                if i >= j:  # 避免重复和自己跟自己比
                    continue
                
                # 检查两条水平线是否对齐（X坐标接近）
                if abs(x_top_left - x_bottom_left) > tolerance or abs(x_top_right - x_bottom_right) > tolerance:
                    continue
                
                # 检查是否有对应的左右垂直线
                has_left = False
                has_right = False
                
                for x_vert, y_vert_top, y_vert_bottom in vertical_lines:
                    # 左边框
                    if abs(x_vert - x_top_left) < tolerance:
                        if abs(y_vert_top - y_top) < tolerance and abs(y_vert_bottom - y_bottom) < tolerance:
                            has_left = True
                    # 右边框
                    if abs(x_vert - x_top_right) < tolerance:
                        if abs(y_vert_top - y_top) < tolerance and abs(y_vert_bottom - y_bottom) < tolerance:
                            has_right = True
                
                # 如果四条边都找到了，就是一个矩形框
                if has_left and has_right:
                    bbox = (x_top_left, y_top, x_top_right, y_bottom)
                    
                    # 检查尺寸是否合理
                    width = bbox[2] - bbox[0]
                    height = bbox[3] - bbox[1]
                    
                    if width > 50 and height > 20:  # 最小尺寸要求
                        # 避免重复添加
                        is_duplicate = False
                        for existing_box in boxes:
                            if (abs(existing_box[0] - bbox[0]) < tolerance and
                                abs(existing_box[1] - bbox[1]) < tolerance and
                                abs(existing_box[2] - bbox[2]) < tolerance and
                                abs(existing_box[3] - bbox[3]) < tolerance):
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            boxes.append(bbox)
        
        return boxes
        
    except Exception as e:
        logger.warning(f"矩形框检测失败: {e}")
        return []


def has_real_table_lines(page, bbox: tuple, logger=None) -> bool:
    """
    检查表格区域是否有真实的表格线（排除文本对齐误识别）
    
    Args:
        page: PyMuPDF页面对象
        bbox: 表格边界框
        logger: 日志对象
        
    Returns:
        是否有真实表格线
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        drawings = page.get_drawings()
        if not drawings:
            return False
        
        # 表格区域，稍微扩展一点容差
        tolerance = 5
        table_x0, table_y0, table_x1, table_y1 = bbox
        table_x0 -= tolerance
        table_y0 -= tolerance
        table_x1 += tolerance
        table_y1 += tolerance
        
        # 统计表格区域内的线条
        lines_in_table = 0
        
        for drawing in drawings:
            if drawing.get('type') == 's':  # stroke线条
                rect = drawing.get('rect')
                if not rect:
                    continue
                
                # 线条的中心点
                line_x = (rect.x0 + rect.x1) / 2
                line_y = (rect.y0 + rect.y1) / 2
                
                # 判断线条是否在表格区域内
                if (table_x0 <= line_x <= table_x1 and table_y0 <= line_y <= table_y1):
                    lines_in_table += 1
        
        # 至少需要3条线（通常表格至少有上下边框+一条分隔线）
        return lines_in_table >= 3
        
    except Exception as e:
        logger.warning(f"检查表格线失败: {e}")
        return True  # 出错时保守处理，认为是有效表格


def is_valid_table(table_data, col_count: int, row_count: int, bbox: tuple, 
                   strict_mode: bool = True, logger=None) -> bool:
    """
    验证是否为有效表格（过滤假表格）
    
    Args:
        table_data: 表格数据
        col_count: 列数
        row_count: 行数
        bbox: 边界框
        strict_mode: 严格模式。False时更宽松，允许单列表格（用于可能是跨页延续的情况）
        logger: 日志对象
        
    Returns:
        是否为有效表格
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # 1. 检查行数：至少要有1行
    if row_count < 1:
        logger.info(f"    ❌ 过滤原因: 行数为0")
        return False
    
    # 2. 检查列数：严格模式下至少要有2列，宽松模式下允许1列（可能是跨页表格延续）
    if strict_mode and col_count < 2:
        logger.info(f"    ❌ 过滤原因: 列数过少({col_count}列)")
        return False
    
    # 3. 检查表格大小
    if bbox:
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        
        # 宽松模式下进一步降低限制（可能是跨页表格延续）
        if strict_mode:
            # 严格模式：正常限制
            if width < 80:
                logger.info(f"    ❌ 过滤原因: 宽度过小({width:.1f}像素)")
                return False
            
            if height < 20:
                logger.info(f"    ❌ 过滤原因: 高度过小({height:.1f}像素)")
                return False
            
            # 只过滤明显是单行文本的情况：1-2列 + 1行 + 很宽
            if row_count == 1 and col_count <= 2 and width > 400:
                logger.info(f"    ❌ 过滤原因: 单行文本({col_count}列,{width:.1f}px宽)")
                return False
        else:
            # 宽松模式：极低限制（可能是跨页延续）
            if width < 30:  # 只过滤极小的宽度
                logger.info(f"    ❌ 过滤原因: 宽度极小({width:.1f}像素)")
                return False
            
            if height < 10:  # 只过滤极小的高度
                logger.info(f"    ❌ 过滤原因: 高度极小({height:.1f}像素)")
                return False
    
    # 4. 不再过滤内容过少的表格，保留所有检测到的表格
    return True


def merge_vertical_lines(lines: List[float], threshold: float = 2.0) -> List[float]:
    """合并相近的纵向边框线坐标（容差像素）。"""
    if not lines:
        return []
    sorted_coords = sorted(set(round(x, 1) for x in lines))
    merged = [sorted_coords[0]]
    for coord in sorted_coords[1:]:
        if coord - merged[-1] >= threshold:
            merged.append(coord)
        else:
            merged[-1] = (merged[-1] + coord) / 2
    return merged


def extract_table_rows_and_data_with_pymupdf(
    pdf_path: str, page_num: int, bbox: tuple, logger=None
) -> tuple:
    """
    提取单个表格的行坐标和文本内容。
    返回 (rows_data, table_data_from_coords, fallback_html)。
    
    Args:
        pdf_path: PDF文件路径
        page_num: 页码（从0开始）
        bbox: 边界框
        logger: 日志对象
        
    Returns:
        (rows_data, table_data_from_coords, fallback_html)
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_num)
        
        # 尝试在页面中查找表格
        table_finder = None
        tables = []
        
        try:
            table_finder = page.find_tables()
            if table_finder and table_finder.tables:
                tables = table_finder.tables
        except Exception as e:
            logger.debug(f"第 {page_num + 1} 页，默认方法失败: {e}")
        
        if not tables:
            try:
                table_finder = page.find_tables(
                    strategy="lines",
                    vertical_strategy="lines",
                    horizontal_strategy="lines"
                )
                if table_finder and table_finder.tables:
                    tables = table_finder.tables
            except Exception as e:
                logger.debug(f"第 {page_num + 1} 页，线条策略失败: {e}")
        
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
                logger.debug(f"第 {page_num + 1} 页，文本策略失败: {e}")
        
        matched_table = None
        min_distance = float('inf')
        
        for table in tables:
            table_bbox_raw = table.bbox
            if hasattr(table_bbox_raw, 'x0'):
                table_bbox_tuple = (table_bbox_raw.x0, table_bbox_raw.y0, table_bbox_raw.x1, table_bbox_raw.y1)
            else:
                table_bbox_tuple = table_bbox_raw
            
            table_center_x = (table_bbox_tuple[0] + table_bbox_tuple[2]) / 2
            table_center_y = (table_bbox_tuple[1] + table_bbox_tuple[3]) / 2
            bbox_center_x = (bbox[0] + bbox[2]) / 2
            bbox_center_y = (bbox[1] + bbox[3]) / 2
            
            distance = ((table_center_x - bbox_center_x) ** 2 + 
                       (table_center_y - bbox_center_y) ** 2) ** 0.5
            
            overlap_ratio = bbox_overlap_ratio(
                table_bbox_tuple,
                bbox
            )
            
            if overlap_ratio > 0.3 or distance < 50:
                if distance < min_distance:
                    min_distance = distance
                    matched_table = table
        
        if not matched_table:
            try:
                html_table = extract_text_from_bbox_to_html(page, bbox, logger=logger)
                doc.close()
                
                if html_table:
                    return None, None, html_table
                else:
                    logger.warning(f"第 {page_num + 1} 页从 bbox 区域提取文本失败")
                    return None, None, None
                    
            except Exception as e:
                logger.error(f"第 {page_num + 1} 页从 bbox 区域提取文本失败: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                doc.close()
                return None, None, None
        
        detailed_coords = get_table_detailed_coordinates(matched_table)
        cell_texts = get_text_in_cells_by_char(matched_table, page, detailed_coords['rows'])
        
        table_data_from_coords = []
        for row in detailed_coords['rows']:
            row_data = []
            for cell in row['cells']:
                key = (row['row_index'], cell['col_index'])
                text = cell_texts.get(key, "")
                row_data.append(text)
            table_data_from_coords.append(row_data)
        
        doc.close()
        return detailed_coords['rows'], table_data_from_coords, None
        
    except Exception as e:
        logger.error(f"使用PyMuPDF解析表格失败 (第{page_num + 1}页): {e}")
        if 'doc' in locals():
            try:
                doc.close()
            except:
                pass
        return None, None, None


def parse_single_table_with_pymupdf(
    pdf_path: str, page_num: int, bbox: tuple, 
    merged_vertical_lines: List[float] = None, logger=None
) -> Optional[str]:
    """
    使用 PyMuPDF 解析单个表格并生成 HTML，可选传入跨页合并后的纵向边框线坐标用于精准colspan
    
    Args:
        pdf_path: PDF文件路径
        page_num: 页码（从0开始）
        bbox: 边界框
        merged_vertical_lines: 合并后的垂直线坐标
        logger: 日志对象
        
    Returns:
        HTML表格字符串
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    rows_data, table_data_from_coords, fallback_html = extract_table_rows_and_data_with_pymupdf(
        pdf_path, page_num, bbox, logger
    )
    if fallback_html is not None:
        return fallback_html
    if rows_data and table_data_from_coords:
        return convert_table_to_html(
            rows_data, table_data_from_coords, 
            merged_vertical_lines=merged_vertical_lines, tolerance=2.0
        )
    return None

