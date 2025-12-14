# -*- coding: utf-8 -*-
"""
主解析器 - MainParser

统一调用接口，提供完整的文件解析流程：
- 粗解析：快速提取文本内容（不使用视觉模型）
- 精确解析：提取图片并使用视觉模型识别
- 完整解析：粗解析 + 精确解析的合并结果
"""

import os
import logging
import asyncio
from typing import Optional, Dict, List, Tuple

from .parsers import CoarseParser, VisionParser
from .image import ImageExtractor
from .utils import PDFHandler, ExcelHandler, TextMerger


class MainParser:
    """主解析器 - 统一文件解析接口"""
    
    def __init__(self, 
                 vision_model: str = "doubao-seed-1-6-vision-250815",
                 vision_detail: str = 'high',
                 max_workers: int = 100):
        """
        初始化主解析器
        
        Args:
            vision_model: 视觉模型名称
            vision_detail: 视觉模型精度 ('high' 或 'low')
            max_workers: 并发处理的最大工作线程数
        """
        self.logger = logging.getLogger(__name__)
        self.max_workers = max_workers
        
        # 初始化各个模块
        self.coarse_parser = CoarseParser()
        self.vision_parser = VisionParser(
            model_name=vision_model,
            detail=vision_detail
        )
        self.pdf_handler = PDFHandler()
        self.excel_handler = ExcelHandler()
        self.image_extractor = ImageExtractor()
        self.text_merger = TextMerger()
        
        self.logger.info(f"主解析器初始化完成: vision_model={vision_model}, max_workers={max_workers}")
    
    def parse_file_coarse(self, file_path: str) -> Optional[str]:
        """
        粗解析文件（不使用视觉模型）
        
        Args:
            file_path: 文件路径
            
        Returns:
            提取的文本内容
        """
        try:
            self.logger.info(f"开始粗解析: {file_path}")
            result = self.coarse_parser.parse_file(file_path)
            
            # 粗解析完成（具体日志在 CoarseParser 中）
            
            return result
            
        except Exception as e:
            self.logger.error(f"粗解析失败: {file_path}, 错误: {e}")
            return None
    
    def parse_pdf_vision_only(self, 
                             pdf_path: str, 
                             output_dir: str = None) -> Dict[str, str]:
        """
        仅对PDF中的图片进行视觉模型解析（不提取文本）
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 图片输出目录（可选）
            
        Returns:
            图片路径到OCR结果的映射
        """
        try:
            self.logger.info(f"开始视觉解析（仅图片）: {pdf_path}")
            
            # 创建临时目录
            if output_dir is None:
                import tempfile
                output_dir = tempfile.mkdtemp(prefix="vision_parse_")
            
            # 提取图片
            images_with_pages = self.image_extractor.extract_images_from_pdf(
                pdf_path, output_dir
            )
            
            if not images_with_pages:
                self.logger.warning(f"未提取到图片: {pdf_path}")
                return {}
            
            # 使用视觉模型解析图片
            image_paths = [img_path for img_path, _ in images_with_pages]
            ocr_results = self.vision_parser.batch_parse_images(
                image_paths, 
                max_workers=self.max_workers
            )
            
            self.logger.info(f"视觉解析完成: {pdf_path}, 处理{len(ocr_results)}张图片")
            return ocr_results
            
        except Exception as e:
            self.logger.error(f"视觉解析失败: {pdf_path}, 错误: {e}")
            return {}
    
    def parse_pdf_complete(self, 
                          pdf_path: str, 
                          output_dir: str = None,
                          merge_strategy: str = 'append') -> Optional[str]:
        """
        完整解析PDF（粗解析 + 视觉解析）
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 图片输出目录（可选）
            merge_strategy: 合并策略 ('append'/'replace'/'interleave')
            
        Returns:
            完整的解析结果
        """
        try:
            self.logger.info(f"开始完整解析: {pdf_path}")
            
            # 1. 粗解析：提取PDF文本
            pdf_text_by_page = self.pdf_handler.extract_text_from_pdf(pdf_path)
            
            # 2. 创建临时目录
            if output_dir is None:
                import tempfile
                output_dir = tempfile.mkdtemp(prefix="complete_parse_")
            
            # 3. 提取图片
            images_with_pages = self.image_extractor.extract_images_from_pdf(
                pdf_path, output_dir
            )
            
            # 4. 视觉解析图片
            ocr_results_by_page = {}
            if images_with_pages:
                ocr_results_by_page = self.vision_parser.parse_images_with_pages(
                    images_with_pages,
                    max_workers=self.max_workers
                )
            
            # 5. 合并结果
            merged_content = self.text_merger.merge_pdf_text_and_images(
                pdf_text_by_page,
                ocr_results_by_page,
                merge_strategy=merge_strategy
            )
            
            self.logger.info(f"完整解析完成: {pdf_path}, 内容长度={len(merged_content)}")
            return merged_content
            
        except Exception as e:
            self.logger.error(f"完整解析失败: {pdf_path}, 错误: {e}")
            return None
    
    async def parse_pdf_complete_async(self, 
                                      pdf_path: str, 
                                      output_dir: str = None,
                                      merge_strategy: str = 'append') -> Optional[str]:
        """
        异步完整解析PDF（粗解析 + 视觉解析）
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 图片输出目录（可选）
            merge_strategy: 合并策略
            
        Returns:
            完整的解析结果
        """
        try:
            self.logger.info(f"开始异步完整解析: {pdf_path}")
            
            # 1. 粗解析：提取PDF文本
            pdf_text_by_page = self.pdf_handler.extract_text_from_pdf(pdf_path)
            
            # 2. 创建临时目录
            if output_dir is None:
                import tempfile
                output_dir = tempfile.mkdtemp(prefix="async_parse_")
            
            # 3. 提取图片
            images_with_pages = self.image_extractor.extract_images_from_pdf(
                pdf_path, output_dir
            )
            
            # 4. 异步视觉解析图片
            ocr_results_by_page = {}
            if images_with_pages:
                ocr_results_by_page = await self.vision_parser.parse_images_with_pages_async(
                    images_with_pages,
                    max_workers=self.max_workers
                )
            
            # 5. 合并结果
            merged_content = self.text_merger.merge_pdf_text_and_images(
                pdf_text_by_page,
                ocr_results_by_page,
                merge_strategy=merge_strategy
            )
            
            self.logger.info(f"异步完整解析完成: {pdf_path}, 内容长度={len(merged_content)}")
            return merged_content
            
        except Exception as e:
            self.logger.error(f"异步完整解析失败: {pdf_path}, 错误: {e}")
            return None
    
    async def parse_images_with_pages_async(self, 
                                           images_with_pages: List[Tuple[str, int]],
                                           max_workers: int = None) -> Dict[int, List[Tuple[str, str]]]:
        """
        异步解析图片并按页码分组（内部辅助方法）
        """
        if max_workers is None:
            max_workers = self.max_workers
        
        # 批量异步解析所有图片
        image_paths = [img_path for img_path, _ in images_with_pages]
        parse_results = await self.vision_parser.batch_parse_images_async(
            image_paths, max_workers
        )
        
        # 按页码分组
        results_by_page = {}
        for img_path, page_num in images_with_pages:
            text = parse_results.get(img_path, "")
            if page_num not in results_by_page:
                results_by_page[page_num] = []
            results_by_page[page_num].append((img_path, text))
        
        return results_by_page
    
    def parse_and_save(self, 
                      file_path: str, 
                      output_path: str,
                      mode: str = 'complete',
                      merge_strategy: str = 'append') -> bool:
        """
        解析文件并保存结果
        
        Args:
            file_path: 输入文件路径
            output_path: 输出文件路径
            mode: 解析模式
                - 'coarse': 仅粗解析
                - 'vision': 仅视觉解析（仅对图片）
                - 'complete': 完整解析（默认）
            merge_strategy: 合并策略（仅在complete模式下有效）
            
        Returns:
            是否保存成功
        """
        try:
            self.logger.info(f"开始解析并保存: {file_path}, 模式={mode}")
            
            # 根据模式选择解析方法
            if mode == 'coarse':
                content = self.parse_file_coarse(file_path)
            elif mode == 'vision':
                ocr_results = self.parse_pdf_vision_only(file_path)
                content = self.text_merger.merge_simple("", ocr_results)
            elif mode == 'complete':
                content = self.parse_pdf_complete(file_path, merge_strategy=merge_strategy)
            else:
                self.logger.error(f"不支持的解析模式: {mode}")
                return False
            
            if not content:
                self.logger.error(f"解析未生成内容: {file_path}")
                return False
            
            # 保存结果
            success = self.text_merger.save_to_file(content, output_path)
            
            if success:
                self.logger.info(f"解析并保存成功: {file_path} -> {output_path}")
            else:
                self.logger.error(f"保存文件失败: {output_path}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"解析并保存失败: {file_path}, 错误: {e}")
            return False
    
    def batch_parse_files(self, 
                         file_paths: List[str],
                         output_dir: str,
                         mode: str = 'complete',
                         merge_strategy: str = 'append') -> Dict[str, bool]:
        """
        批量解析文件
        
        Args:
            file_paths: 文件路径列表
            output_dir: 输出目录
            mode: 解析模式
            merge_strategy: 合并策略
            
        Returns:
            文件路径到处理结果的映射
        """
        results = {}
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        for file_path in file_paths:
            try:
                # 生成输出文件路径
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_path = os.path.join(output_dir, f"{base_name}_parsed.txt")
                
                # 解析并保存
                success = self.parse_and_save(
                    file_path, 
                    output_path, 
                    mode=mode,
                    merge_strategy=merge_strategy
                )
                
                results[file_path] = success
                
            except Exception as e:
                self.logger.error(f"批量解析失败: {file_path}, 错误: {e}")
                results[file_path] = False
        
        success_count = sum(1 for v in results.values() if v)
        self.logger.info(f"批量解析完成: 成功{success_count}/{len(file_paths)}个文件")
        
        return results
    
    def get_file_info(self, file_path: str) -> Dict[str, any]:
        """
        获取文件信息（不解析内容）
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件信息字典
        """
        try:
            file_ext = os.path.splitext(file_path)[1].lower().lstrip('.')
            
            if file_ext == 'pdf':
                info = self.pdf_handler.get_pdf_info(file_path)
                info['file_type'] = 'PDF'
            elif file_ext in ['xlsx', 'xls']:
                sheets_info = self.excel_handler.get_sheet_info(file_path)
                info = {
                    'file_type': 'Excel',
                    'file_size': os.path.getsize(file_path),
                    'sheets': sheets_info,
                    'sheet_count': len(sheets_info)
                }
            else:
                info = {
                    'file_type': 'Unknown',
                    'file_size': os.path.getsize(file_path)
                }
            
            info['file_path'] = file_path
            info['file_name'] = os.path.basename(file_path)
            
            self.logger.info(f"获取文件信息成功: {file_path}")
            return info
            
        except Exception as e:
            self.logger.error(f"获取文件信息失败: {file_path}, 错误: {e}")
            return {}
    
    def check_parse_recommendation(self, pdf_path: str) -> Dict[str, any]:
        """
        检查PDF并推荐解析方式
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            推荐信息字典：
            - recommended_mode: 推荐的解析模式
            - reason: 推荐理由
            - pdf_type: PDF类型
            - has_images: 是否有图片
        """
        try:
            # 获取PDF信息
            pdf_info = self.pdf_handler.get_pdf_info(pdf_path)
            pdf_type = pdf_info.get('pdf_type', 'unknown')
            
            # 分析PDF结构
            structure = self.pdf_handler.analyze_pdf_structure(pdf_path)
            has_images = structure.get('has_images', False)
            
            # 推荐解析模式
            if pdf_type == 'text' and not has_images:
                recommended_mode = 'coarse'
                reason = 'PDF主要包含文本，可使用粗解析快速处理'
            elif pdf_type == 'scanned':
                recommended_mode = 'complete'
                reason = 'PDF为扫描件，建议使用完整解析（视觉模型）'
            else:
                recommended_mode = 'complete'
                reason = 'PDF包含图片或混合内容，建议使用完整解析'
            
            result = {
                'recommended_mode': recommended_mode,
                'reason': reason,
                'pdf_type': pdf_type,
                'has_images': has_images,
                'page_count': pdf_info.get('page_count', 0)
            }
            
            self.logger.info(f"解析推荐完成: {pdf_path}, 推荐={recommended_mode}")
            return result
            
        except Exception as e:
            self.logger.error(f"解析推荐失败: {pdf_path}, 错误: {e}")
            return {
                'recommended_mode': 'complete',
                'reason': '检测失败，默认推荐完整解析',
                'pdf_type': 'unknown',
                'has_images': True
            }

