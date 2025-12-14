# -*- coding: utf-8 -*-
"""
跨页表格识别器 - CrossPageTableDetector

功能：
- 判断两个表格是否为跨页表格
- 检查表格之间是否有文本内容
- 获取行的有效列数
"""

import logging
import fitz  # PyMuPDF
from typing import Dict


class CrossPageTableDetector:
    """跨页表格识别器"""
    
    def __init__(self, logger: logging.Logger = None):
        """
        初始化跨页表格识别器
        
        Args:
            logger: 日志记录器，如果为None则创建新的
        """
        self.logger = logger or logging.getLogger(__name__)
    
    def is_cross_page_table(self, table1: Dict, table2: Dict, pdf_path: str) -> bool:
        """
        判断两个表格是否为跨页表格（不再依赖列数匹配）
        
        判定规则：
        1) 相邻页面
        2) 两表格之间无文本
        3) X 轴对齐（<=20px）
        4) 宽度相似（>=90%）
        
        Args:
            table1: 第一个表格
            table2: 第二个表格
            pdf_path: PDF文件路径
            
        Returns:
            是否为跨页表格
        """
        # 1. 相邻页面
        if table2['page'] - table1['page'] != 1:
            return False
        
        bbox1 = table1['bbox']
        bbox2 = table2['bbox']
        
        # 2. 表格之间无文本
        has_between = self.has_text_between_tables(pdf_path, table1['page'], bbox1, table2['page'], bbox2)
        if has_between:
            return False
        
        # 3. X 轴对齐（容差20px）
        x_diff = abs(bbox1[0] - bbox2[0])
        if x_diff > 20:
            return False
        
        # 4. 宽度相似（>=90%）
        width1 = bbox1[2] - bbox1[0]
        width2 = bbox2[2] - bbox2[0]
        width_ratio = min(width1, width2) / max(width1, width2)
        if width_ratio < 0.90:
            return False
        
        return True
    
    def has_text_between_tables(self, pdf_path: str, page1_num: int, table1_bbox: tuple, 
                                  page2_num: int, table2_bbox: tuple) -> bool:
        """
        检查两个表格之间是否有文本内容（排除页眉页脚）
        
        Args:
            pdf_path: PDF文件路径
            page1_num: 第一个表格所在页码
            table1_bbox: 第一个表格的边界框
            page2_num: 第二个表格所在页码
            table2_bbox: 第二个表格的边界框
            
        Returns:
            是否有文本内容
        """
        try:
            doc = fitz.open(pdf_path)
            has_text = False
            
            # 页眉页脚区域阈值（单位：像素）
            HEADER_MARGIN = 80   # 页眉区域：顶部80像素
            FOOTER_MARGIN = 80   # 页脚区域：底部80像素
            
            # 检查第一页：表格底部到页面底部之间（排除页脚）
            page1 = doc.load_page(page1_num - 1)
            page1_height = page1.rect.height
            
            # 表格底部到页面底部减去页脚区域
            check_y_start = table1_bbox[3]
            check_y_end = page1_height - FOOTER_MARGIN
            
            # 只有当检查区域有效时才检查
            if check_y_end > check_y_start + 10:  # 至少10像素的检查区域
                check_rect1 = fitz.Rect(0, check_y_start, page1.rect.width, check_y_end)
                text_below_table1 = page1.get_text("text", clip=check_rect1).strip()
                
                if text_below_table1:
                    has_text = True
            
            # 检查第二页：页面顶部到表格顶部之间（排除页眉）
            page2 = doc.load_page(page2_num - 1)
            
            # 页面顶部加上页眉区域到表格顶部
            check_y_start2 = HEADER_MARGIN
            check_y_end2 = table2_bbox[1]
            
            # 只有当检查区域有效时才检查
            if check_y_end2 > check_y_start2 + 10:  # 至少10像素的检查区域
                check_rect2 = fitz.Rect(0, check_y_start2, page2.rect.width, check_y_end2)
                text_above_table2 = page2.get_text("text", clip=check_rect2).strip()
                
                if text_above_table2:
                    has_text = True
            
            doc.close()
            return has_text
            
        except Exception as e:
            self.logger.warning(f"  检查表格间文本失败: {e}")
            return False
    
    def get_effective_col_count(self, row: list) -> int:
        """
        获取一行的有效列数（处理合并单元格）
        
        合并单元格的特征：
        - PyMuPDF会返回多个元素，但只有部分单元格有内容，其他都是空的
        - 例如：['标题', '', '', '', '内容', '', '', '', ''] 实际是2列（两个合并单元格）
        
        策略：直接返回非空单元格的数量，因为合并单元格会被解析成多个空单元格
        
        Args:
            row: 表格的一行数据
            
        Returns:
            有效列数（非空单元格数量）
        """
        if not row:
            return 0
        
        # 统计非空单元格的数量
        non_empty_count = 0
        for cell in row:
            if cell and str(cell).strip():
                non_empty_count += 1
        
        # 如果全空，返回原始列数（可能是表格结构行）
        if non_empty_count == 0:
            return len(row)
        
        return non_empty_count

