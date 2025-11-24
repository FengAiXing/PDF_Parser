# -*- coding: utf-8 -*-
"""
复杂文件处理服务
专门处理candidate_bid_files类型的文件，使用pymupdf提取第一页和第二页的投标人名称
"""

import logging
import fitz  # PyMuPDF
import os
import tempfile
import asyncio
from typing import Dict, List, Any, Optional
from common.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ComplexFileService:
    """复杂文件处理服务类"""
    
    def __init__(self):
        """初始化服务"""
        self.llm_client = LLMClient()
    
    async def extract_bidder_name_from_cover_page(self, pdf_path: str) -> Optional[str]:
        """
        从PDF第一页和第二页提取投标人名称
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            Optional[str]: 投标人名称，如果提取失败返回None
        """
        try:
            # 使用pymupdf打开PDF
            doc = fitz.open(pdf_path)
            
            if len(doc) == 0:
                logger.warning(f"PDF文件为空: {pdf_path}")
                doc.close()
                return None
            
            # 提取第一页文本
            first_page = doc[0]
            first_page_text = first_page.get_text()
            
            # 提取第二页文本（如果存在）
            second_page_text = ""
            has_second_page = len(doc) > 1
            if has_second_page:
                second_page = doc[1]
                second_page_text = second_page.get_text()
            
            doc.close()
            
            # 检查第一页和第二页是否需要使用OCR（视觉模型）处理
            # 如果某页直接提取不到文本，说明可能是图片，需要使用视觉模型
            need_ocr_first = not first_page_text or not first_page_text.strip()
            need_ocr_second = has_second_page and (not second_page_text or not second_page_text.strip())
            
            # 如果任何一页需要OCR处理，使用视觉模型处理
            if need_ocr_first or need_ocr_second:
                logger.info(f"检测到需要OCR处理: 第一页={need_ocr_first}, 第二页={need_ocr_second}, 文件: {pdf_path}")
                ocr_text = await self._extract_first_and_second_pages_with_ocr(
                    pdf_path, 
                    need_ocr_first=need_ocr_first, 
                    need_ocr_second=need_ocr_second,
                    first_page_text=first_page_text if not need_ocr_first else None,
                    second_page_text=second_page_text if not need_ocr_second else None
                )
                
                if ocr_text:
                    cover_text = ocr_text
                else:
                    # 如果OCR失败，使用直接提取的文本（如果有）
                    cover_text = first_page_text if first_page_text else ""
                    if second_page_text:
                        cover_text = f"{cover_text}\n\n{second_page_text}" if cover_text else second_page_text
            else:
                # 两页都能直接提取到文本，直接合并
                cover_text = first_page_text
                if second_page_text:
                    cover_text = f"{first_page_text}\n\n{second_page_text}"
            
            # 如果最终还是没有文本，返回None
            if not cover_text or not cover_text.strip():
                logger.warning(f"最终未能提取到文本: {pdf_path}")
                return None
            
            # 使用LLM从第一页和第二页内容中提取投标人名称
            prompt_template = """
请从以下投标文件第一页和第二页内容中提取投标人名称（投标公司名称）。

要求：
1. 提取完整的公司名称，包括公司类型后缀（如：有限公司、股份有限公司等）
2. 如果有多家公司，提取主要的投标人名称
3. 如果找不到明确的投标人名称，请返回"未找到"

第一页和第二页内容：
$content

请直接返回投标人名称，不要包含其他文字。
"""
            
            # 限制内容长度（因为现在包含两页，适当增加长度限制）
            cover_text_limited = cover_text[:4000]
            result = await self.llm_client.call_llm(prompt_template, cover_text_limited, model_type="gemini")
            
            if result:
                # 清理结果，去除多余的空格和换行
                bidder_name = result.strip()
                # 如果结果包含引号，去除引号
                if bidder_name.startswith('"') and bidder_name.endswith('"'):
                    bidder_name = bidder_name[1:-1]
                if bidder_name.startswith("'") and bidder_name.endswith("'"):
                    bidder_name = bidder_name[1:-1]
                
                logger.info(f"成功提取投标人名称: {bidder_name}")
                return bidder_name
            else:
                logger.warning(f"LLM未返回投标人名称: {pdf_path}")
                return None
                
        except Exception as e:
            logger.error(f"提取投标人名称失败: {pdf_path}, 错误: {e}")
            return None
    
    async def _extract_first_and_second_pages_with_ocr(
        self, 
        pdf_path: str,
        need_ocr_first: bool = True,
        need_ocr_second: bool = True,
        first_page_text: Optional[str] = None,
        second_page_text: Optional[str] = None
    ) -> Optional[str]:
        """
        使用OCR工具（视觉模型）提取PDF第一页和第二页的文本内容
        
        Args:
            pdf_path: PDF文件路径
            need_ocr_first: 是否需要使用OCR处理第一页
            need_ocr_second: 是否需要使用OCR处理第二页
            first_page_text: 第一页直接提取的文本（如果不需要OCR）
            second_page_text: 第二页直接提取的文本（如果不需要OCR）
            
        Returns:
            Optional[str]: 提取的文本内容（合并第一页和第二页），失败返回None
        """
        try:
            import tempfile
            from src.utils.complex_file.ocr_processor import ComplexOCRProcessor
            
            # 打开PDF文件
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                logger.warning(f"PDF文件为空，无法进行OCR: {pdf_path}")
                doc.close()
                return None
            
            # 创建临时目录保存图片
            temp_dir = tempfile.mkdtemp()
            ocr_processor = ComplexOCRProcessor()
            
            all_text_parts = []
            has_second_page = len(doc) > 1
            
            # 处理第一页
            if need_ocr_first:
                first_page = doc[0]
                first_image_path = os.path.join(temp_dir, "first_page.png")
                
                # 将第一页渲染为图片（使用较高的分辨率）
                mat = fitz.Matrix(2.0, 2.0)  # 2倍缩放，提高OCR识别率
                pix = first_page.get_pixmap(matrix=mat)
                pix.save(first_image_path)
                
                # 使用视觉模型（OCR处理器）提取第一页文本
                logger.info(f"使用视觉模型处理第一页: {pdf_path}")
                first_text, _ = ocr_processor.extract_text_from_image(first_image_path)
                if first_text and not first_text.startswith("ERROR"):
                    all_text_parts.append(first_text)
                    logger.info(f"视觉模型成功提取第一页文本，长度: {len(first_text)} 字符")
                else:
                    logger.warning(f"视觉模型提取第一页文本失败或返回错误: {pdf_path}")
            else:
                # 使用直接提取的文本
                if first_page_text:
                    all_text_parts.append(first_page_text)
                    logger.info(f"第一页使用直接提取的文本，长度: {len(first_page_text)} 字符")
            
            # 处理第二页（如果存在）
            second_image_path = None
            if has_second_page:
                if need_ocr_second:
                    second_page = doc[1]
                    second_image_path = os.path.join(temp_dir, "second_page.png")
                    
                    # 将第二页渲染为图片
                    mat = fitz.Matrix(2.0, 2.0)  # 2倍缩放，提高OCR识别率
                    pix = second_page.get_pixmap(matrix=mat)
                    pix.save(second_image_path)
                    
                    # 使用视觉模型（OCR处理器）提取第二页文本
                    logger.info(f"使用视觉模型处理第二页: {pdf_path}")
                    second_text, _ = ocr_processor.extract_text_from_image(second_image_path)
                    if second_text and not second_text.startswith("ERROR"):
                        all_text_parts.append(second_text)
                        logger.info(f"视觉模型成功提取第二页文本，长度: {len(second_text)} 字符")
                    else:
                        logger.warning(f"视觉模型提取第二页文本失败或返回错误: {pdf_path}")
                else:
                    # 使用直接提取的文本
                    if second_page_text:
                        all_text_parts.append(second_page_text)
                        logger.info(f"第二页使用直接提取的文本，长度: {len(second_page_text)} 字符")
            
            doc.close()
            
            # 清理临时文件
            try:
                if need_ocr_first:
                    first_image_path = os.path.join(temp_dir, "first_page.png")
                    if os.path.exists(first_image_path):
                        os.remove(first_image_path)
                if need_ocr_second and second_image_path and os.path.exists(second_image_path):
                    os.remove(second_image_path)
                os.rmdir(temp_dir)
            except Exception as cleanup_error:
                logger.warning(f"清理临时文件失败: {cleanup_error}")
            
            # 合并所有页面的文本
            if all_text_parts:
                combined_text = "\n\n".join(all_text_parts)
                logger.info(f"成功提取第一页和第二页文本，总长度: {len(combined_text)} 字符")
                return combined_text
            else:
                logger.warning(f"未能提取到文本: {pdf_path}")
                return None
                
        except Exception as e:
            logger.error(f"OCR提取第一页和第二页文本失败: {pdf_path}, 错误: {e}")
            return None
    
    async def process_complex_files(
        self,
        file_urls: List[str],
        project_id: str,
        merged_contents: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        处理多个复杂文件，提取每个文件的投标人名称（并发处理）
        
        Args:
            file_urls: 文件URL列表
            project_id: 项目ID
            merged_contents: 已解析的文件内容（可选，用于获取已下载的文件路径）
            
        Returns:
            List[Dict[str, Any]]: 处理结果列表，每个元素包含：
                - file_url: 文件URL
                - bidder_name: 投标人名称
        """
        import asyncio
        
        # 从merged_contents中获取已下载的文件路径
        file_path_map = {}
        if merged_contents and 'candidate_bid_files' in merged_contents:
            candidate_files_data = merged_contents['candidate_bid_files']
            if isinstance(candidate_files_data, dict) and 'files' in candidate_files_data:
                files_dict = candidate_files_data['files']
                for file_key, file_info in files_dict.items():
                    file_url = file_info.get('file_url')
                    file_path = file_info.get('file_path')
                    if file_url and file_path:
                        file_path_map[file_url] = file_path
        
        # 创建临时目录（如果需要）
        temp_dir = None
        
        # 定义单个文件处理函数
        async def process_single_file(file_url: str) -> Dict[str, Any]:
            """处理单个复杂文件"""
            try:
                # 优先使用已下载的文件路径
                file_path = file_path_map.get(file_url)
                
                # 如果文件路径不存在或文件已被删除，则重新下载
                if not file_path or not os.path.exists(file_path):
                    if file_path:
                        logger.warning(f"文件路径已不存在，重新下载: {file_url}, 原路径: {file_path}")
                    else:
                        logger.info(f"未找到已下载的文件路径，开始下载: {file_url}")
                    
                    # 重新下载文件
                    nonlocal temp_dir
                    if temp_dir is None:
                        temp_dir = tempfile.mkdtemp()
                    file_path = await self._download_file(file_url, temp_dir)
                
                if not file_path or not os.path.exists(file_path):
                    logger.error(f"文件下载失败或路径不存在: {file_url}, 路径: {file_path}")
                    return {
                        "file_url": file_url,
                        "bidder_name": None,
                        "error": "文件路径不存在"
                    }
                
                # 提取投标人名称
                bidder_name = await self.extract_bidder_name_from_cover_page(file_path)
                
                return {
                    "file_url": file_url,
                    "bidder_name": bidder_name,
                    "file_path": file_path
                }
                
            except Exception as e:
                logger.error(f"处理复杂文件失败: {file_url}, 错误: {e}")
                return {
                    "file_url": file_url,
                    "bidder_name": None,
                    "error": str(e)
                }
        
        # 并发处理所有文件
        tasks = [process_single_file(file_url) for file_url in file_urls]
        results = await asyncio.gather(*tasks)
        
        return list(results)
    
    async def _download_file(self, file_url: str, temp_dir: str) -> Optional[str]:
        """
        下载文件到临时目录
        
        Args:
            file_url: 文件URL
            temp_dir: 临时目录
            
        Returns:
            Optional[str]: 下载后的文件路径，失败返回None
        """
        try:
            # 检查是否为本地文件
            if os.path.exists(file_url):
                logger.info(f"检测到本地文件，直接使用: {file_url}")
                return file_url
            
            # 使用AsyncFileProcessor下载文件
            from src.utils.async_file_process import AsyncFileProcessor
            file_processor = AsyncFileProcessor()
            
            success, result = await file_processor.download_file(file_url, temp_dir)
            
            if success:
                file_path = result.split(',')[0]  # 取第一个文件路径
                logger.info(f"文件下载成功: {file_path}")
                return file_path
            else:
                logger.error(f"文件下载失败: {file_url}")
                return None
                        
        except Exception as e:
            logger.error(f"下载文件异常: {file_url}, 错误: {e}")
            return None

