# -*- coding: utf-8 -*-
"""
复杂文件主处理器
专门处理candidate_bid_files类型的文件，整合PDF处理、OCR识别、内容合并的完整流程
"""

import logging
from typing import Optional, Dict, List, Tuple
from .pdf_processor import ComplexPDFProcessor
from .ocr_processor import ComplexOCRProcessor
from .content_merger import ComplexContentMerger


class ComplexFileProcessor:
    """复杂文件主处理器 - 专门处理candidate_bid_files类型"""
    
    def __init__(self, max_workers: int = 4):
        self.logger = logging.getLogger(__name__)
        self.max_workers = max_workers
        
        # 初始化各个处理器
        self.pdf_processor = ComplexPDFProcessor()
        self.ocr_processor = ComplexOCRProcessor()
        self.content_merger = ComplexContentMerger(max_workers=max_workers)
    
    async def process_candidate_bid_file(self, pdf_path: str, output_dir: str = None) -> Optional[str]:
        """
        处理candidate_bid_files类型的PDF文件完整流程
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            
        Returns:
            生成的TXT文件路径
        """
        try:
            result = await self.content_merger.process_pdf_file(pdf_path, output_dir)
            return result
        except Exception as e:
            self.logger.error(f"处理candidate_bid_file失败: {pdf_path}, 错误: {e}")
            raise e
    
    def process_candidate_bid_file_with_images_only(self, pdf_path: str, output_dir: str = None) -> Dict[str, str]:
        """
        仅处理candidate_bid_files中的图片OCR
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            
        Returns:
            图片路径到OCR结果的映射
        """
        return self.content_merger.process_pdf_with_images_only(pdf_path, output_dir)
    
    def extract_text_from_image(self, image_path: str, prompt: str = None) -> Tuple[Optional[str], str]:
        """
        从单张图片提取文字 - 专门针对candidate_bid_files
        
        Args:
            image_path: 图片路径
            prompt: 自定义提示词
            
        Returns:
            (识别结果, 图片路径)
        """
        return self.ocr_processor.extract_text_from_image(image_path, prompt)
    
    def extract_stamp_from_image(self, image_path: str) -> Tuple[Optional[str], str]:
        """
        从图片中提取印章和签名信息
        
        Args:
            image_path: 图片路径
            
        Returns:
            (识别结果, 图片路径)
        """
        return self.ocr_processor.extract_stamp_from_image(image_path)
    
    def get_pdf_info(self, pdf_path: str) -> dict:
        """
        获取PDF文件信息
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            PDF信息字典
        """
        return self.pdf_processor.get_pdf_info(pdf_path)
    
    def analyze_bid_file_structure(self, pdf_path: str) -> Dict[str, any]:
        """
        分析投标文件结构
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            投标文件结构分析结果
        """
        return self.pdf_processor.analyze_bid_structure(pdf_path)
    
    def extract_bid_specific_elements(self, pdf_path: str) -> Dict[str, List]:
        """
        提取投标文件中的特定元素
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            包含投标文件特定元素的字典
        """
        return self.pdf_processor.extract_bid_specific_elements(pdf_path)
    
    def process_bid_specific_content(self, pdf_path: str, output_dir: str = None) -> Dict[str, any]:
        """
        专门处理投标文件的特定内容
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            
        Returns:
            包含投标文件特定内容的字典
        """
        return self.content_merger.process_bid_specific_content(pdf_path, output_dir)
    
    def extract_bid_key_information(self, pdf_path: str) -> Dict[str, any]:
        """
        提取投标文件关键信息
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            投标文件关键信息字典
        """
        return self.content_merger.extract_bid_key_information(pdf_path)
    
    def batch_process_candidate_bid_files(self, pdf_paths: List[str], output_dir: str = None) -> Dict[str, str]:
        """
        批量处理candidate_bid_files类型的PDF文件
        
        Args:
            pdf_paths: PDF文件路径列表
            output_dir: 输出目录
            
        Returns:
            文件路径到处理结果的映射
        """
        results = {}
        
        for pdf_path in pdf_paths:
            try:
                result_path = self.process_candidate_bid_file(pdf_path, output_dir)
                if result_path:
                    results[pdf_path] = result_path
                    self.logger.info(f"成功处理candidate_bid_file: {pdf_path}")
                else:
                    self.logger.error(f"处理candidate_bid_file失败: {pdf_path}")
            except Exception as e:
                self.logger.error(f"处理candidate_bid_file异常: {pdf_path}, 错误: {e}")
        
        return results
    
    def extract_bid_specific_content_from_image(self, image_path: str) -> Dict[str, str]:
        """
        专门提取投标文件中的特定内容
        
        Args:
            image_path: 图片路径
            
        Returns:
            包含各种投标文件信息的字典
        """
        return self.ocr_processor.extract_bid_specific_content(image_path)
    
    def get_processing_statistics(self, pdf_path: str) -> Dict[str, any]:
        """
        获取处理统计信息
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            处理统计信息字典
        """
        try:
            # 获取PDF基本信息
            pdf_info = self.get_pdf_info(pdf_path)
            
            # 分析投标文件结构
            structure_analysis = self.analyze_bid_file_structure(pdf_path)
            
            # 提取投标文件特定元素
            bid_elements = self.extract_bid_specific_elements(pdf_path)
            
            return {
                'pdf_info': pdf_info,
                'structure_analysis': structure_analysis,
                'bid_elements': bid_elements,
                'processing_summary': {
                    'total_pages': pdf_info.get('page_count', 0),
                    'has_tables': len(bid_elements.get('tables', [])) > 0,
                    'has_images': len(bid_elements.get('images', [])) > 0,
                    'table_count': len(bid_elements.get('tables', [])),
                    'image_count': len(bid_elements.get('images', [])),
                    'text_block_count': len(bid_elements.get('text_blocks', []))
                }
            }
            
        except Exception as e:
            self.logger.error(f"获取处理统计信息失败: {e}")
            return {}
