# -*- coding: utf-8 -*-
"""
文本合并器 - TextMerger

合并不同来源的解析结果：
- 合并PDF文本和图片OCR结果
- 按页码组织内容
- 生成最终的文本文件
- 支持自定义合并策略
"""

import os
import logging
from typing import Dict, List, Tuple, Optional


class TextMerger:
    """文本合并器 - 合并粗解析和精确解析的结果"""
    
    def __init__(self):
        """初始化文本合并器"""
        self.logger = logging.getLogger(__name__)
    
    def merge_pdf_text_and_images(self, 
                                  pdf_text_by_page: List[Tuple[int, str]],
                                  ocr_results_by_page: Dict[int, List[Tuple[str, str]]],
                                  merge_strategy: str = 'append') -> str:
        """
        合并PDF文本和图片OCR结果
        
        Args:
            pdf_text_by_page: PDF文本内容，列表元素为 (页码, 文本)
            ocr_results_by_page: OCR结果，字典键为页码，值为 [(图片路径, OCR文本), ...]
            merge_strategy: 合并策略
                - 'append': 将OCR结果追加到文本后面（默认）
                - 'replace': 如果页面文本较少，使用OCR结果替换
                - 'interleave': 交错插入OCR结果
            
        Returns:
            合并后的文本内容
        """
        try:
            merged_content = []
            
            for page_num, page_text in pdf_text_by_page:
                # 添加页面标题
                merged_content.append(f"==第{page_num}页==")
                
                # 处理页面文本
                if merge_strategy == 'replace':
                    # 如果文本很少，优先使用OCR结果
                    if len(page_text.strip()) < 50 and page_num in ocr_results_by_page:
                        merged_content.append("[使用图片OCR结果]")
                        for img_path, ocr_text in ocr_results_by_page[page_num]:
                            merged_content.append(f"\n[图片: {os.path.basename(img_path)}]")
                            merged_content.append(ocr_text)
                    else:
                        merged_content.append(page_text)
                        
                        # 如果还有OCR结果，也追加
                        if page_num in ocr_results_by_page:
                            merged_content.append("\n[图片OCR结果]")
                            for img_path, ocr_text in ocr_results_by_page[page_num]:
                                merged_content.append(f"\n[图片: {os.path.basename(img_path)}]")
                                merged_content.append(ocr_text)
                
                elif merge_strategy == 'interleave':
                    # 交错插入
                    if page_text.strip():
                        merged_content.append(page_text)
                    
                    if page_num in ocr_results_by_page:
                        for img_path, ocr_text in ocr_results_by_page[page_num]:
                            merged_content.append(f"\n[图片: {os.path.basename(img_path)}]")
                            merged_content.append(ocr_text)
                
                else:  # 'append' (默认)
                    # 先添加文本内容
                    if page_text.strip():
                        merged_content.append(page_text)
                    
                    # 再添加OCR结果
                    if page_num in ocr_results_by_page:
                        merged_content.append("\n[图片OCR结果]")
                        for img_path, ocr_text in ocr_results_by_page[page_num]:
                            merged_content.append(f"\n[图片: {os.path.basename(img_path)}]")
                            merged_content.append(ocr_text)
                
                merged_content.append("")  # 添加空行分隔
            
            result = "\n".join(merged_content)
            self.logger.info(f"文本合并完成: 共{len(pdf_text_by_page)}页, 策略={merge_strategy}")
            return result
            
        except Exception as e:
            self.logger.error(f"文本合并失败: 错误: {e}")
            return ""
    
    def merge_simple(self, 
                    text_content: str, 
                    ocr_results: Dict[str, str]) -> str:
        """
        简单合并：将OCR结果追加到文本内容后面
        
        Args:
            text_content: 原始文本内容
            ocr_results: OCR结果，字典键为图片路径，值为OCR文本
            
        Returns:
            合并后的文本内容
        """
        try:
            merged_content = []
            
            # 添加原始文本
            if text_content:
                merged_content.append(text_content)
                merged_content.append("")
            
            # 添加OCR结果
            if ocr_results:
                merged_content.append("=" * 50)
                merged_content.append("图片OCR识别结果")
                merged_content.append("=" * 50)
                merged_content.append("")
                
                for img_path, ocr_text in ocr_results.items():
                    merged_content.append(f"[图片: {os.path.basename(img_path)}]")
                    merged_content.append(ocr_text)
                    merged_content.append("")
            
            result = "\n".join(merged_content)
            self.logger.info(f"简单合并完成: 文本长度={len(text_content)}, OCR结果数={len(ocr_results)}")
            return result
            
        except Exception as e:
            self.logger.error(f"简单合并失败: 错误: {e}")
            return text_content if text_content else ""
    
    def save_to_file(self, content: str, output_path: str) -> bool:
        """
        保存合并后的内容到文件
        
        Args:
            content: 要保存的内容
            output_path: 输出文件路径
            
        Returns:
            是否保存成功
        """
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"保存文件成功: {output_path}, 大小={len(content)}字节")
            return True
            
        except Exception as e:
            self.logger.error(f"保存文件失败: {output_path}, 错误: {e}")
            return False
    
    def merge_with_sections(self, sections: Dict[str, str]) -> str:
        """
        按章节合并内容
        
        Args:
            sections: 章节内容字典，键为章节标题，值为内容
            
        Returns:
            合并后的文本内容
        """
        try:
            merged_content = []
            
            for section_title, section_content in sections.items():
                # 添加章节标题
                merged_content.append("=" * 50)
                merged_content.append(section_title)
                merged_content.append("=" * 50)
                merged_content.append("")
                
                # 添加章节内容
                merged_content.append(section_content)
                merged_content.append("")
            
            result = "\n".join(merged_content)
            self.logger.info(f"按章节合并完成: 共{len(sections)}个章节")
            return result
            
        except Exception as e:
            self.logger.error(f"按章节合并失败: 错误: {e}")
            return ""
    
    def merge_multiple_files(self, 
                           file_contents: Dict[str, str],
                           add_separators: bool = True) -> str:
        """
        合并多个文件的内容
        
        Args:
            file_contents: 文件内容字典，键为文件名，值为内容
            add_separators: 是否添加分隔符
            
        Returns:
            合并后的文本内容
        """
        try:
            merged_content = []
            
            for file_name, content in file_contents.items():
                if add_separators:
                    merged_content.append("=" * 60)
                    merged_content.append(f"文件: {file_name}")
                    merged_content.append("=" * 60)
                    merged_content.append("")
                
                merged_content.append(content)
                merged_content.append("")
            
            result = "\n".join(merged_content)
            self.logger.info(f"多文件合并完成: 共{len(file_contents)}个文件")
            return result
            
        except Exception as e:
            self.logger.error(f"多文件合并失败: 错误: {e}")
            return ""
    
    def format_with_metadata(self, 
                           content: str, 
                           metadata: Dict[str, any]) -> str:
        """
        添加元数据到内容
        
        Args:
            content: 原始内容
            metadata: 元数据字典
            
        Returns:
            包含元数据的文本内容
        """
        try:
            formatted_content = []
            
            # 添加元数据
            formatted_content.append("=" * 60)
            formatted_content.append("文件元数据")
            formatted_content.append("=" * 60)
            
            for key, value in metadata.items():
                formatted_content.append(f"{key}: {value}")
            
            formatted_content.append("=" * 60)
            formatted_content.append("")
            
            # 添加内容
            formatted_content.append(content)
            
            result = "\n".join(formatted_content)
            self.logger.info(f"添加元数据完成: {len(metadata)}个字段")
            return result
            
        except Exception as e:
            self.logger.error(f"添加元数据失败: 错误: {e}")
            return content
    
    def merge_with_page_info(self, 
                            content_by_page: Dict[int, str],
                            add_page_numbers: bool = True) -> str:
        """
        按页码合并内容
        
        Args:
            content_by_page: 页码到内容的映射
            add_page_numbers: 是否添加页码标记
            
        Returns:
            合并后的文本内容
        """
        try:
            merged_content = []
            
            # 按页码排序
            sorted_pages = sorted(content_by_page.items())
            
            for page_num, page_content in sorted_pages:
                if add_page_numbers:
                    merged_content.append(f"==第{page_num}页==")
                
                merged_content.append(page_content)
                merged_content.append("")
            
            result = "\n".join(merged_content)
            self.logger.info(f"按页码合并完成: 共{len(content_by_page)}页")
            return result
            
        except Exception as e:
            self.logger.error(f"按页码合并失败: 错误: {e}")
            return ""
    
    def clean_content(self, content: str) -> str:
        """
        清理内容（去除多余空行等）
        
        Args:
            content: 原始内容
            
        Returns:
            清理后的内容
        """
        try:
            lines = content.split('\n')
            cleaned_lines = []
            prev_empty = False
            
            for line in lines:
                is_empty = len(line.strip()) == 0
                
                # 避免连续多个空行
                if is_empty and prev_empty:
                    continue
                
                cleaned_lines.append(line)
                prev_empty = is_empty
            
            result = '\n'.join(cleaned_lines)
            self.logger.info(f"内容清理完成: {len(lines)}行 -> {len(cleaned_lines)}行")
            return result
            
        except Exception as e:
            self.logger.error(f"内容清理失败: 错误: {e}")
            return content

