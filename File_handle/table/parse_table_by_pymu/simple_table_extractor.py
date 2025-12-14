# -*- coding: utf-8 -*-
"""
简单表格提取模块

从 bbox 区域直接提取文本并生成 HTML 表格（适用于矩形框检测到的表格）
"""

import fitz  # PyMuPDF
from typing import Optional, Tuple, List
import logging


def escape_html(text: str) -> str:
    """
    转义 HTML 特殊字符，但保留 <br> 标签
    
    Args:
        text: 要转义的文本
        
    Returns:
        转义后的文本
    """
    if not text:
        return ""
    # 先保护 <br> 标签
    text = text.replace('<br>', '___BR_TAG___')
    # 转义其他 HTML 特殊字符
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    # 恢复 <br> 标签
    text = text.replace('___BR_TAG___', '<br>')
    return text


def extract_text_from_bbox_to_html(page: fitz.Page, bbox: Tuple[float, float, float, float], 
                                   logger: Optional[logging.Logger] = None) -> Optional[str]:
    """
    从 bbox 区域提取文本并生成 HTML 表格（单列表格）
    
    Args:
        page: PyMuPDF 页面对象
        bbox: 表格边界框 (x0, y0, x1, y1)
        logger: 日志记录器（可选）
        
    Returns:
        HTML格式的表格字符串，如果提取失败返回None
    """
    try:
        # 从 bbox 区域提取文本（使用 dict 格式获取带坐标的文本）
        rect = fitz.Rect(bbox)
        text_dict = page.get_text("dict", clip=rect)
        
        if not text_dict or not text_dict.get("blocks"):
            # 如果 dict 格式失败，尝试 text 格式
            text_in_box = page.get_text("text", clip=rect).strip()
            if text_in_box:
                # 简单处理：将整个文本作为一个单元格
                html_table = f"<table>\n  <tr><td>{escape_html(text_in_box)}</td></tr>\n</table>"
                if logger:
                    logger.info("从 bbox 区域提取文本成功（单单元格）")
                return html_table
            else:
                if logger:
                    logger.warning("bbox 区域内无文本内容")
                return None
        
        # 使用坐标信息按行组织文本
        blocks = text_dict.get("blocks", [])
        text_lines = []  # [(y, text, height)]
        
        for block in blocks:
            if block.get("type") != 0:  # 只处理文本块
                continue
            
            for line in block.get("lines", []):
                line_text_parts = []
                line_y = None
                line_height = None
                
                for span in line.get("spans", []):
                    span_text = span.get("text", "").strip()
                    if span_text:
                        bbox_span = span.get("bbox", [])
                        if len(bbox_span) >= 4:
                            if line_y is None:
                                # 使用行的 y 坐标（取第一个 span 的 y0）
                                line_y = bbox_span[1]  # y0
                                line_height = bbox_span[3] - bbox_span[1]  # height
                            line_text_parts.append(span_text)
                
                if line_text_parts and line_y is not None:
                    line_text = " ".join(line_text_parts)
                    text_lines.append((line_y, line_text, line_height or 10))
        
        if not text_lines:
            # 如果坐标提取失败，使用简单方法
            text_in_box = page.get_text("text", clip=rect).strip()
            if text_in_box:
                html_table = f"<table>\n  <tr><td>{escape_html(text_in_box)}</td></tr>\n</table>"
                if logger:
                    logger.info("从 bbox 区域提取文本成功（单单元格，坐标提取失败）")
                return html_table
            return None
        
        # 按 y 坐标排序
        text_lines.sort(key=lambda x: x[0])
        
        # 将所有文本放在同一个单元格内，根据 y 坐标差值决定是否添加 <br>
        y_threshold = 2.0  # y 坐标差值阈值（像素），超过此值用 <br> 分隔
        
        cell_parts = []  # 单元格内容片段列表
        prev_line_y = None
        
        for line_y, line_text, line_height in text_lines:
            if prev_line_y is None:
                # 第一行，直接添加
                cell_parts.append(line_text)
                prev_line_y = line_y
            else:
                # 计算与上一行的 y 坐标差值
                y_diff = line_y - prev_line_y
                
                # 如果 y 坐标差值大于阈值，认为是换行，用 <br> 分隔
                if y_diff > y_threshold:
                    cell_parts.append("<br>" + line_text)
                else:
                    # 同一行，直接拼接（不添加 <br>）
                    cell_parts.append(" " + line_text)
                
                prev_line_y = line_y
        
        if cell_parts:
            # 生成 HTML 表格：所有文本在一个单元格内
            cell_text = "".join(cell_parts)
            escaped_text = escape_html(cell_text)
            html_table = f"<table>\n  <tr><td>{escaped_text}</td></tr>\n</table>"
            
            return html_table
        else:
            if logger:
                logger.warning("bbox 区域内无有效文本行")
            return None
            
    except Exception as e:
        if logger:
            logger.error(f"从 bbox 区域提取文本失败: {e}")
        return None

