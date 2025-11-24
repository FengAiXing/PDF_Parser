# -*- coding: utf-8 -*-
"""
复杂文件内容合并器
专门处理candidate_bid_files类型文件的内容合并，包含图片OCR结果
"""

import os
import logging
import fitz  # PyMuPDF
import concurrent.futures
from typing import List, Dict, Tuple, Optional
from .pdf_processor import ComplexPDFProcessor
from .ocr_processor import ComplexOCRProcessor


class ComplexContentMerger:
    """复杂文件内容合并器"""
    
    def __init__(self, max_workers: int = 4):
        self.logger = logging.getLogger(__name__)
        self.max_workers = max_workers
        self.pdf_processor = ComplexPDFProcessor()
        self.ocr_processor = ComplexOCRProcessor()
    
    def cleanup_temp_files(self, output_image_dir: str = None, output_txt_path: str = None):
        """
        清理临时文件
        
        Args:
            output_image_dir: 临时图片目录
            output_txt_path: 临时文本文件路径
        """
        try:
            # 清理临时图片目录
            if output_image_dir and os.path.exists(output_image_dir):
                try:
                    import shutil
                    shutil.rmtree(output_image_dir)
                    logging.info(f"清理临时图片目录: {output_image_dir}")
                except Exception as e:
                    logging.warning(f"清理临时图片目录失败: {e}")
            
            # 清理临时文本文件
            if output_txt_path and os.path.exists(output_txt_path):
                try:
                    os.remove(output_txt_path)
                    logging.info(f"清理临时文本文件: {output_txt_path}")
                except Exception as e:
                    logging.warning(f"清理临时文本文件失败: {e}")
                    
        except Exception as e:
            logging.warning(f"清理临时文件时发生错误: {e}")
    
    async def process_pdf_file(self, pdf_path: str, output_dir: str = None) -> Optional[str]:
        """
        处理复杂PDF文件的完整流程：提取文本、提取图片、OCR识别、内容合并
        专门针对candidate_bid_files类型，支持真正的异步并发处理
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            
        Returns:
            生成的TXT文件路径
        """
        if output_dir is None:
            output_dir = os.path.dirname(pdf_path)

        pdf_filename = os.path.basename(pdf_path)
        pdf_name = os.path.splitext(pdf_filename)[0]
        output_image_dir = os.path.join(output_dir, "images", pdf_name)

        try:
            # 打开PDF文件
            pdf = fitz.open(pdf_path)
            num_pages = len(pdf)
            result = []  # 用于存储每页文本和图片文字

            # 1. 提取图片
            image_paths = self.pdf_processor.extract_images_from_pdf(pdf_path, output_image_dir)
            logging.info(f"复杂文件处理 - 成功提取 {len(image_paths)} 张有效图片")
            
            # 如果没有提取到图片，记录详细信息
            if len(image_paths) == 0:
                logging.info(f"复杂文件处理 - 未提取到图片，可能原因：1)PDF中没有图片 2)图片被过滤 3)图片尺寸过小")

            # 2. 处理图片 OCR - 使用真正的异步并发处理
            image_texts = {}
            if image_paths:
                # 使用新的异步批量OCR处理方法
                image_paths_list = [img_path for img_path, _ in image_paths]
                image_texts = await self.ocr_processor.batch_extract_text_async(
                    image_paths_list, 
                    max_workers=20  # 增加并发数
                )

            # 3. 处理每一页文本和图片文字
            for page_num in range(num_pages):
                page = pdf[page_num]
                page_text = page.get_text()
                
                # 添加图片文字 - 使用投标文件专用格式
                page_images = [img for img in image_paths if img[1] == page_num + 1]
                image_content = ""
                for i, (image_path, _) in enumerate(page_images):
                    if image_path in image_texts:
                        image_title = f"【【投标文件图片{i + 1}】】: 【【{image_texts[image_path]}】】\n"
                        image_content += image_title
                
                # 只有当页面有文本内容或图片内容时才添加页面
                if page_text.strip() or image_content.strip():
                    page_result = f"[当前页码: {page_num + 1}]\n{page_text}"
                    if image_content:
                        page_result += image_content
                    result.append(page_result)
                else:
                    logging.warning(f"复杂文件第 {page_num + 1} 页无任何内容，跳过")

            pdf.close()

            # 4. 写入 TXT 文件
            output_txt_path = os.path.join(output_dir, f"{pdf_name}_complex.txt")
            with open(output_txt_path, "w", encoding="utf-8") as f:
                # 使用更智能的合并方式，避免多余空白行
                content_parts = []
                for page_content in result:
                    if page_content.strip():  # 只添加非空内容
                        content_parts.append(page_content.strip())
                
                # 使用单个换行符连接，避免多余空白
                f.write("\n".join(content_parts))

            # 记录处理结果统计
            total_content_length = sum(len(page_result) for page_result in result)
            logging.info(f"复杂文件处理完成: {pdf_filename} -> {os.path.basename(output_txt_path)}")
            logging.info(f"处理统计 - 总页数: {num_pages}, 图片数量: {len(image_paths)}, 内容长度: {total_content_length} 字符")
            return output_txt_path

        except Exception as e:
            logging.error(f"处理复杂PDF文件失败: {pdf_path}, 错误: {e}")
            # 清理临时文件
            self.cleanup_temp_files(output_image_dir, None)
            return None
    
    def process_pdf_with_images_only(self, pdf_path: str, output_dir: str = None) -> Dict[str, str]:
        """
        仅处理PDF中的图片OCR - 专门针对candidate_bid_files
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            
        Returns:
            图片路径到OCR结果的映射
        """
        try:
            if output_dir is None:
                output_dir = os.path.dirname(pdf_path)
            
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            output_image_dir = os.path.join(output_dir, "images", pdf_name)
            
            # 提取图片
            image_paths = self.pdf_processor.extract_images_from_pdf(pdf_path, output_image_dir)
            
            # OCR处理 - 使用专门的投标文件OCR处理器
            image_texts = self.ocr_processor.batch_extract_text(
                [img_path for img_path, _ in image_paths],
                max_workers=self.max_workers
            )
            
            return image_texts
            
        except Exception as e:
            self.logger.error(f"处理复杂PDF图片失败: {e}")
            # 清理临时文件
            self.cleanup_temp_files(output_image_dir, None)
            return {}
    
    def merge_content(self, pdf_texts: List[str], image_texts: Dict[str, str], 
                     image_paths: List[Tuple[str, int]]) -> List[str]:
        """
        合并PDF文本和图片OCR结果 - 专门针对candidate_bid_files
        
        Args:
            pdf_texts: PDF文本列表
            image_texts: 图片OCR结果字典
            image_paths: 图片路径和页码列表
            
        Returns:
            合并后的内容列表
        """
        result = []
        
        for page_num, page_text in enumerate(pdf_texts):
            # 添加图片文字 - 使用投标文件专用格式
            page_images = [img for img in image_paths if img[1] == page_num + 1]
            image_content = ""
            for i, (image_path, _) in enumerate(page_images):
                if image_path in image_texts:
                    image_title = f"【【投标文件图片{i + 1}】】: 【【{image_texts[image_path]}】】\n"
                    image_content += image_title
            
            # 只有当页面有文本内容或图片内容时才添加页面
            if page_text.strip() or image_content.strip():
                page_result = f"[当前页码: {page_num + 1}]\n{page_text}"
                if image_content:
                    page_result += image_content
                result.append(page_result)
        
        return result
    
    def process_bid_specific_content(self, pdf_path: str, output_dir: str = None) -> Dict[str, any]:
        """
        专门处理投标文件的特定内容
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            
        Returns:
            包含投标文件特定内容的字典
        """
        try:
            if output_dir is None:
                output_dir = os.path.dirname(pdf_path)
            
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            output_image_dir = os.path.join(output_dir, "images", pdf_name)
            
            # 提取投标文件特定元素
            bid_elements = self.pdf_processor.extract_bid_specific_elements(pdf_path)
            
            # 分析投标文件结构
            structure_analysis = self.pdf_processor.analyze_bid_structure(pdf_path)
            
            # 处理图片OCR
            image_paths = self.pdf_processor.extract_images_from_pdf(pdf_path, output_image_dir)
            image_texts = self.ocr_processor.batch_extract_text(
                [img_path for img_path, _ in image_paths],
                max_workers=self.max_workers
            )
            
            # 提取文本内容
            pdf_texts = self.pdf_processor.extract_text_from_pdf(pdf_path)
            
            # 合并内容
            merged_content = self.merge_content(pdf_texts, image_texts, image_paths)
            
            return {
                'merged_content': merged_content,
                'bid_elements': bid_elements,
                'structure_analysis': structure_analysis,
                'image_texts': image_texts,
                'pdf_texts': pdf_texts
            }
            
        except Exception as e:
            self.logger.error(f"处理投标文件特定内容失败: {e}")
            return {}
    
    def extract_bid_key_information(self, pdf_path: str) -> Dict[str, any]:
        """
        提取投标文件关键信息
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            投标文件关键信息字典
        """
        try:
            # 获取PDF基本信息
            pdf_info = self.pdf_processor.get_pdf_info(pdf_path)
            
            # 分析投标文件结构
            structure_analysis = self.pdf_processor.analyze_bid_structure(pdf_path)
            
            # 提取投标文件特定元素
            bid_elements = self.pdf_processor.extract_bid_specific_elements(pdf_path)
            
            return {
                'pdf_info': pdf_info,
                'structure_analysis': structure_analysis,
                'bid_elements': bid_elements,
                'has_tables': len(bid_elements.get('tables', [])) > 0,
                'has_images': len(bid_elements.get('images', [])) > 0,
                'total_pages': pdf_info.get('page_count', 0)
            }
            
        except Exception as e:
            self.logger.error(f"提取投标文件关键信息失败: {e}")
            return {}
