#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PDF内容筛选器
使用pymupdf进行粗解析，然后通过正则表达式匹配关键位置，截取指定范围的PDF页面
"""

import os
import re
import fitz  # PyMuPDF
import logging
from typing import Tuple, Optional, List

logger = logging.getLogger(__name__)

class PDFContentFilter:
    """PDF内容筛选器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def clean_text(self, text: str) -> str:
        """
        清理文本，去除所有标点符号、空格、换行符等
        只保留中文字符和数字
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清理后的文本
        """
        # 去除所有非中文字符和非数字的字符
        cleaned = re.sub(r'[^\u4e00-\u9fff0-9]', '', text)
        return cleaned
    
    def find_qualification_section(self, text: str) -> List[Tuple[int, int]]:
        """
        查找所有"资格审查资料"的位置
        
        Args:
            text: 文本内容
            
        Returns:
            List[Tuple[int, int]]: 找到的位置列表，每个元素为(开始位置, 结束位置)
        """
        positions = []
        pattern = r'资格审查资料'
        
        for match in re.finditer(pattern, text):
            start = match.start()
            end = match.end()
            positions.append((start, end))
            self.logger.info(f"找到资格审查资料位置: {start}-{end}")
        
        return positions
    
    def find_basic_info_table_near_position(self, text: str, position: int, search_range: int = 50) -> Optional[int]:
        """
        在指定位置后搜索"基本情况表"
        
        Args:
            text: 文本内容
            position: 资格审查资料位置
            search_range: 搜索范围（字符数）
            
        Returns:
            Optional[int]: 找到的位置，未找到返回None
        """
        # 从资格审查资料位置后开始搜索
        search_start = position + len("资格审查资料")
        search_end = min(len(text), search_start + search_range)
        
        # 确保搜索窗口不会跨越到其他"资格审查资料"位置
        # 查找搜索范围内是否有其他"资格审查资料"
        search_content = text[search_start:search_end]
        other_qualification_pos = search_content.find("资格审查资料")
        if other_qualification_pos != -1:
            # 如果找到其他"资格审查资料"，截断搜索范围
            search_end = search_start + other_qualification_pos
            search_window = text[search_start:search_end]
        else:
            search_window = search_content
        
        self.logger.info(f"在位置 {position} 前后 {search_range} 字符内搜索基本情况表")
        self.logger.info(f"搜索窗口: '{search_window}'")
        
        # 清理搜索窗口
        cleaned_window = self.clean_text(search_window)
        self.logger.info(f"清理后搜索窗口: '{cleaned_window}'")
        
        # 清理目标字符串
        target_patterns = [
            '基本情况表'
        ]
        
        for target in target_patterns:
            cleaned_target = self.clean_text(target)
            self.logger.info(f"清理后目标: '{cleaned_target}'")
            
            # 在清理后的窗口中查找目标
            if cleaned_target in cleaned_window:
                # 找到匹配，需要计算原始位置
                match_pos = cleaned_window.find(cleaned_target)
                # 将清理后的位置映射回原始位置
                original_pos = self._map_cleaned_position_to_original(search_window, match_pos)
                if original_pos != -1:
                    actual_pos = search_start + original_pos
                    self.logger.info(f"找到基本情况表: 位置 {actual_pos}")
                    return actual_pos
        
        return None
    
    def find_tech_file_section(self, text: str) -> List[Tuple[int, int]]:
        """
        查找所有"第三部分"的位置，并验证前后20字符内是否有"技术文件"
        
        Args:
            text: 文本内容
            
        Returns:
            List[Tuple[int, int]]: 找到的位置列表，每个元素为(开始位置, 结束位置)
        """
        positions = []
        pattern = r'第三部分'
        
        for match in re.finditer(pattern, text):
            start = match.start()
            end = match.end()
            
            # 在前后20字符内搜索"技术文件"
            if self._find_tech_file_near_position(text, start, 20):
                positions.append((start, end))
                self.logger.info(f"找到第三部分位置: {start}-{end}")
            else:
                self.logger.info(f"第三部分位置 {start}-{end} 附近未找到技术文件，跳过")
        
        return positions
    
    def _find_tech_file_near_position(self, text: str, position: int, search_range: int = 20) -> bool:
        """
        在指定位置前后搜索"技术文件"
        
        Args:
            text: 文本内容
            position: 搜索中心位置
            search_range: 搜索范围（字符数）
            
        Returns:
            bool: 是否找到
        """
        # 计算搜索范围
        start_pos = max(0, position - search_range)
        end_pos = min(len(text), position + search_range)
        search_window = text[start_pos:end_pos]
        
        # 清理搜索窗口
        cleaned_window = self.clean_text(search_window)
        
        # 清理目标字符串
        target_patterns = [
            '技术文件',
            '第三部分技术文件',
            '技术'
        ]
        
        for target in target_patterns:
            cleaned_target = self.clean_text(target)
            if cleaned_target in cleaned_window:
                self.logger.info(f"在位置 {position} 附近找到技术文件")
                return True
        
        return False
    
    def _map_cleaned_position_to_original(self, original_text: str, cleaned_pos: int) -> int:
        """
        将清理后文本的位置映射回原始文本的位置
        
        Args:
            original_text: 原始文本
            cleaned_pos: 清理后文本中的位置
            
        Returns:
            int: 原始文本中的位置，映射失败返回-1
        """
        if cleaned_pos < 0:
            return -1
        
        # 计算清理后的文本
        cleaned_text = self.clean_text(original_text)
        
        if cleaned_pos >= len(cleaned_text):
            return -1
        
        # 找到清理后文本中指定位置的字符
        target_char = cleaned_text[cleaned_pos]
        
        # 在原始文本中找到对应的位置
        original_pos = 0
        cleaned_index = 0
        
        for i, char in enumerate(original_text):
            if re.match(r'[\u4e00-\u9fff0-9]', char):
                if cleaned_index == cleaned_pos:
                    return i
                cleaned_index += 1
        
        return -1
    
    def extract_pdf_pages(self, pdf_path: str, start_page: int, end_page: int, output_path: str) -> bool:
        """
        从PDF中提取指定页面范围
        
        Args:
            pdf_path: 原始PDF路径
            start_page: 开始页码（从0开始）
            end_page: 结束页码（从0开始）
            output_path: 输出PDF路径
            
        Returns:
            bool: 是否成功
        """
        try:
            # 打开原始PDF
            doc = fitz.open(pdf_path)
            
            # 创建新的PDF文档
            new_doc = fitz.open()
            
            # 提取指定页面范围
            for page_num in range(start_page, min(end_page + 1, len(doc))):
                page = doc[page_num]
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                # self.logger.info(f"提取第 {page_num + 1} 页")
            
            # 保存新的PDF
            new_doc.save(output_path)
            new_doc.close()
            doc.close()
            
            self.logger.info(f"成功提取页面 {start_page + 1}-{end_page + 1} 到 {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"提取PDF页面失败: {e}")
            return False
    
    def find_text_in_pdf_pages(self, pdf_path: str, text: str) -> List[Tuple[int, int]]:
        """
        在PDF中查找文本所在的页面位置
        
        Args:
            pdf_path: PDF文件路径
            text: 要查找的文本
            
        Returns:
            List[Tuple[int, int]]: 找到的位置列表，每个元素为(页码, 位置)
        """
        positions = []
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                
                # 在页面文本中查找目标文本
                for match in re.finditer(re.escape(text), page_text):
                    positions.append((page_num, match.start()))
                    self.logger.info(f"在第 {page_num + 1} 页找到文本: {text}")
            
            doc.close()
            
        except Exception as e:
            self.logger.error(f"在PDF中查找文本失败: {e}")
        
        return positions
    
    def remove_pages_2_to_10(self, pdf_path: str, temp_pdf_path: str) -> bool:
        """
        去除PDF的第2到第10页，创建临时文件
        
        Args:
            pdf_path: 原始PDF路径
            temp_pdf_path: 临时PDF路径
            
        Returns:
            bool: 是否成功
        """
        try:
            self.logger.info(f"开始去除第2到第10页: {pdf_path}")
            
            # 打开原始PDF
            doc = fitz.open(pdf_path)
            
            # 创建新的PDF文档
            new_doc = fitz.open()
            
            # 添加第1页
            new_doc.insert_pdf(doc, from_page=0, to_page=0)
            self.logger.info("保留第1页")
            
            # 添加第11页及以后的页面
            for page_num in range(10, len(doc)):  # 从第11页开始（索引10）
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                # self.logger.info(f"保留第{page_num + 1}页")
            
            # 保存临时PDF
            new_doc.save(temp_pdf_path)
            new_doc.close()
            doc.close()
            
            self.logger.info(f"成功去除第2到第10页，临时文件保存到: {temp_pdf_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"去除页面失败: {e}")
            return False

    def filter_pdf_content(self, pdf_path: str, output_path: str) -> bool:
        """
        筛选PDF内容，先去除第2到第10页，然后提取资格审查资料到第三部分之间的内容
        
        Args:
            pdf_path: 原始PDF路径
            output_path: 输出PDF路径
            
        Returns:
            bool: 是否成功
        """
        try:
            self.logger.info(f"开始筛选PDF内容: {pdf_path}")
            
            # 1. 先去除第2到第10页，创建临时文件
            temp_pdf_path = pdf_path.replace('.pdf', '_temp_no_pages_2_10.pdf')
            if not self.remove_pages_2_to_10(pdf_path, temp_pdf_path):
                self.logger.error("去除第2到第10页失败")
                return False
            
            # 2. 使用修改后的PDF进行pymupdf解析获取文本
            doc = fitz.open(temp_pdf_path)
            full_text = ""
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                full_text += f"\n=== 第{page_num + 1}页 ===\n{page_text}"
            
            doc.close()
            
            self.logger.info(f"修改后PDF文本解析完成，总长度: {len(full_text)} 字符")
            
            # 2. 查找资格审查资料位置
            qualification_positions = self.find_qualification_section(full_text)
            if not qualification_positions:
                self.logger.error("未找到资格审查资料")
                return False
            
            # 3. 查找基本情况表
            qualification_page = None
            for pos_start, pos_end in qualification_positions:
                basic_info_pos = self.find_basic_info_table_near_position(full_text, pos_start, 50)
                if basic_info_pos is not None:
                    # 找到匹配的位置，确定页码
                    qualification_page = self._find_page_for_position(full_text, pos_start)
                    self.logger.info(f"找到匹配的资格审查资料，在第 {qualification_page + 1} 页")
                    break
            
            if qualification_page is None:
                self.logger.error("未找到包含基本情况表的资格审查资料")
                return False
            
            # 4. 查找第三部分位置（必须在资格审查资料之后）
            tech_positions = self.find_tech_file_section(full_text)
            if not tech_positions:
                self.logger.error("未找到第三部分")
                return False
            
            # 找到资格审查资料在文本中的位置
            qualification_text_pos = None
            for pos_start, pos_end in qualification_positions:
                if self.find_basic_info_table_near_position(full_text, pos_start, 50) is not None:
                    qualification_text_pos = pos_start
                    break
            
            if qualification_text_pos is None:
                self.logger.error("未找到有效的资格审查资料位置")
                return False
            
            # 找到资格审查资料之后的第三部分
            tech_page = None
            for tech_pos_start, tech_pos_end in tech_positions:
                if tech_pos_start > qualification_text_pos:  # 第三部分必须在资格审查资料之后
                    tech_page = self._find_page_for_position(full_text, tech_pos_start)
                    self.logger.info(f"找到第三部分，在第 {tech_page + 1} 页")
                    break
            
            if tech_page is None:
                self.logger.error("未找到资格审查资料之后的第三部分")
                return False
            
            # 5. 提取页面范围（第1页 + 资格审查资料到第三部分）
            if qualification_page is not None and tech_page is not None:
                # 使用临时文件进行页面提取
                doc = fitz.open(temp_pdf_path)
                new_doc = fitz.open()
                
                # 1. 添加第1页（如果不在提取范围内）
                if qualification_page > 0:
                    self.logger.info(f"添加第1页")
                    new_doc.insert_pdf(doc, from_page=0, to_page=0)
                
                # 2. 添加资格审查资料到第三部分的页面
                self.logger.info(f"添加页面范围: {qualification_page + 1} 到 {tech_page + 1}")
                for page_num in range(qualification_page, min(tech_page + 1, len(doc))):
                    new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                    # self.logger.info(f"提取第 {page_num + 1} 页")
                
                # 保存新的PDF
                new_doc.save(output_path)
                new_doc.close()
                doc.close()
                
                # 6. 清理临时文件
                try:
                    import os
                    os.remove(temp_pdf_path)
                    self.logger.info(f"已清理临时文件: {temp_pdf_path}")
                except Exception as cleanup_error:
                    self.logger.warning(f"清理临时文件失败: {cleanup_error}")
                
                self.logger.info(f"成功提取页面到 {output_path}")
                return True
            else:
                # 清理临时文件
                try:
                    import os
                    os.remove(temp_pdf_path)
                    self.logger.info(f"已清理临时文件: {temp_pdf_path}")
                except Exception as cleanup_error:
                    self.logger.warning(f"清理临时文件失败: {cleanup_error}")
                
                self.logger.error("无法确定页面范围")
                return False
                
        except Exception as e:
            # 清理临时文件
            try:
                import os
                if 'temp_pdf_path' in locals():
                    os.remove(temp_pdf_path)
                    self.logger.info(f"已清理临时文件: {temp_pdf_path}")
            except Exception as cleanup_error:
                self.logger.warning(f"清理临时文件失败: {cleanup_error}")
            
            self.logger.error(f"筛选PDF内容失败: {e}")
            return False
    
    def _find_page_for_position(self, full_text: str, position: int) -> int:
        """
        根据文本位置找到对应的页码
        
        Args:
            full_text: 完整文本
            position: 文本位置
            
        Returns:
            int: 页码（从0开始）
        """
        # 查找位置之前的页面标记
        page_markers = []
        for match in re.finditer(r'=== 第(\d+)页 ===', full_text):
            page_num = int(match.group(1)) - 1  # 转换为从0开始的页码
            page_markers.append((match.start(), page_num))
        
        # 找到位置所在的页面
        for i, (marker_pos, page_num) in enumerate(page_markers):
            if position >= marker_pos:
                if i + 1 < len(page_markers):
                    next_marker_pos = page_markers[i + 1][0]
                    if position < next_marker_pos:
                        return page_num
                else:
                    # 最后一个页面
                    return page_num
        
        return 0  # 默认返回第一页


def main():
    """测试函数"""
    import sys
    import os
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 测试文件路径
    test_pdf = "C:/Users/gf133/Desktop/变量提取文件/工程_测试文件/一--（改版）投标文件2024.12.10.pdf"
    output_pdf = "test_output/filtered_pdf.pdf"
    
    if not os.path.exists(test_pdf):
        print(f"测试文件不存在: {test_pdf}")
        return
    
    # 创建筛选器
    filter_obj = PDFContentFilter()
    
    # 执行筛选
    success = filter_obj.filter_pdf_content(test_pdf, output_pdf)
    
    if success:
        print(f"PDF筛选成功，结果保存到: {output_pdf}")
    else:
        print("PDF筛选失败")


if __name__ == "__main__":
    main()
