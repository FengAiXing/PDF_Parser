# -*- coding: utf-8 -*-
"""
粗解析器 - CoarseParser

快速提取文件内容，不使用视觉模型：
- PDF文件：使用PyMuPDF提取文本内容
- Excel文件：使用pandas提取表格内容
- 适用于文本PDF和Excel文件的快速解析
- 不处理图片内容（扫描PDF需要使用精确解析）
"""

import os
import logging
import warnings
import fitz  # PyMuPDF
import pandas as pd
from typing import Optional, Dict, List, Tuple
from ..utils import HeaderFooterCleaner

# 抑制 openpyxl 的样式警告
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')


class CoarseParser:
    """粗解析器 - 快速提取文件文本内容（不使用视觉模型）"""
    
    def __init__(self, remove_header_footer: bool = False, 
                 use_smart_removal: bool = True,
                 common_headers: set = None,
                 common_footers: set = None):
        """
        初始化粗解析器
        
        Args:
            remove_header_footer: 是否移除页眉页脚（默认False）
            use_smart_removal: 是否使用智能移除方法（基于位置），否则使用简单方法（基于行数）（默认True）
            common_headers: 预检测的页眉集合（传入后不再重复检测）
            common_footers: 预检测的页脚集合（传入后不再重复检测）
        """
        self.logger = logging.getLogger(__name__)
        self.remove_header_footer = remove_header_footer
        self.use_smart_removal = use_smart_removal
        self.header_footer_cleaner = HeaderFooterCleaner()
        # 使用传入的页眉页脚，避免重复检测
        self.common_headers = common_headers
        self.common_footers = common_footers
        self.supported_formats = {
            'pdf': self._parse_pdf,
            'xlsx': self._parse_excel,
            'xls': self._parse_excel
        }
    
    def parse_file(self, file_path: str) -> Optional[str]:
        """
        粗解析文件内容（自动检测文件类型）
        
        Args:
            file_path: 文件路径
            
        Returns:
            提取的文本内容，失败返回None
        """
        try:
            # 自动检测文件格式
            file_ext = os.path.splitext(file_path)[1].lower().lstrip('.')
            
            if file_ext not in self.supported_formats:
                self.logger.error(f"不支持的文件格式: {file_ext}")
                return None
            
            # 调用对应的解析方法
            parser_func = self.supported_formats[file_ext]
            content = parser_func(file_path)
            
            # 粗解析完成（具体日志在各解析方法中）
            
            return content
            
        except Exception as e:
            self.logger.error(f"粗解析失败: {file_path}, 错误: {e}")
            return None

    async def parse_file_async(self, file_path: str) -> Optional[str]:
        """
        异步封装：在事件循环中将同步解析放入线程池，便于上层流水线并发调度。
        """
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.parse_file, file_path)
    
    def _parse_pdf(self, pdf_path: str) -> Optional[str]:
        """
        粗解析PDF文件（仅提取文本，不处理图片）
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            提取的文本内容
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            text_content = []
            
            # 使用预传入的页眉页脚，避免重复检测
            if self.common_headers is not None and self.common_footers is not None:
                common_headers = self.common_headers
                common_footers = self.common_footers
            elif self.remove_header_footer and self.use_smart_removal:
                # 没有预传入时才自己检测
                try:
                    common_headers, common_footers = self.header_footer_cleaner.detect_common_texts(
                        doc,
                        repeat_threshold=2
                    )
                except Exception as e:
                    self.logger.warning(f"检测通用页眉页脚失败，使用默认逻辑: {e}")
                    common_headers, common_footers = set(), set()
            else:
                common_headers, common_footers = set(), set()
            total_pages = len(doc)  # 保存页数，避免在关闭后访问
            
            for page_num in range(total_pages):
                try:
                    page = doc.load_page(page_num)
                    
                    # 根据配置决定是否移除页眉页脚
                    if self.remove_header_footer:
                        if self.use_smart_removal:
                            page_text = self.header_footer_cleaner.remove_by_position(
                                page,
                                common_headers=common_headers,
                                common_footers=common_footers,
                                remove_page_numbers=True
                            )
                        else:
                            page_text = page.get_text()
                            page_text = self.header_footer_cleaner.remove_simple(page_text)
                    else:
                        page_text = page.get_text()
                    
                    if page_text.strip():
                        text_content.append(f"==第{page_num + 1}页==")
                        text_content.append(page_text.strip())
                        text_content.append("")
                        
                except Exception as e:
                    self.logger.warning(f"处理第{page_num + 1}页时出错: {e}")
                    continue
            
            doc.close()
            
            if text_content:
                result = "\n".join(text_content)
                self.logger.info(f"PDF粗解析完成: {pdf_path}, 共{total_pages}页")
                return result
            else:
                self.logger.warning(f"PDF未提取到文本内容: {pdf_path}")
                return None
                
        except Exception as e:
            self.logger.error(f"PDF粗解析失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return None
    
    def _parse_excel(self, excel_path: str) -> Optional[str]:
        """
        粗解析Excel文件
        
        Args:
            excel_path: Excel文件路径
            
        Returns:
            提取的文本内容
        """
        try:
            # 根据文件扩展名确定引擎
            file_ext = os.path.splitext(excel_path)[1].lower()
            
            if file_ext == '.xlsx':
                engine = 'openpyxl'
            elif file_ext == '.xls':
                engine = 'xlrd'
            else:
                engine = None
            
            # 使用上下文管理器确保文件正确关闭
            with pd.ExcelFile(excel_path, engine=engine) as excel_file:
                content_parts = []
                
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)
                    
                    # 添加工作表标题
                    content_parts.append(f"=== 工作表: {sheet_name} ===")
                    
                    # 将DataFrame转换为文本
                    if not df.empty:
                        text_content = df.to_string(index=True, header=True, na_rep='')
                        content_parts.append(text_content)
                    else:
                        content_parts.append("(空工作表)")
                    
                    content_parts.append("")  # 添加空行分隔
                
                result = "\n".join(content_parts)
                self.logger.info(f"Excel粗解析完成: {excel_path}, 共{len(excel_file.sheet_names)}个工作表")
                return result
                
        except Exception as e:
            self.logger.error(f"Excel粗解析失败: {excel_path}, 错误: {e}")
            return None
    
    def parse_pdf_with_details(self, pdf_path: str) -> Dict[str, any]:
        """
        粗解析PDF并返回详细信息
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            包含解析结果和元数据的字典：
            - content: 文本内容
            - page_count: 页数
            - pages: 每页内容列表
            - has_text: 是否包含文本
            - metadata: PDF元数据
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            
            pages = []
            all_text = []
            total_pages = len(doc)
            metadata = doc.metadata  # 保存元数据
            
            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                page_text = page.get_text()
                
                pages.append({
                    'page_num': page_num + 1,
                    'text': page_text,
                    'has_text': len(page_text.strip()) > 0
                })
                
                if page_text.strip():
                    all_text.append(f"==第{page_num + 1}页==")
                    all_text.append(page_text.strip())
                    all_text.append("")
            
            doc.close()
            
            result = {
                'content': "\n".join(all_text) if all_text else None,
                'page_count': total_pages,
                'pages': pages,
                'has_text': any(p['has_text'] for p in pages),
                'metadata': metadata
            }
            
            self.logger.info(f"PDF粗解析（详细）完成: {pdf_path}")
            return result
            
        except Exception as e:
            self.logger.error(f"PDF粗解析（详细）失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return {}
    
    def parse_excel_with_details(self, excel_path: str) -> Dict[str, any]:
        """
        粗解析Excel并返回详细信息
        
        Args:
            excel_path: Excel文件路径
            
        Returns:
            包含解析结果和元数据的字典：
            - content: 文本内容
            - sheet_count: 工作表数量
            - sheets: 每个工作表的详细信息
        """
        try:
            file_ext = os.path.splitext(excel_path)[1].lower()
            engine = 'openpyxl' if file_ext == '.xlsx' else 'xlrd'
            
            with pd.ExcelFile(excel_path, engine=engine) as excel_file:
                sheets = []
                all_content = []
                
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)
                    
                    sheet_info = {
                        'name': sheet_name,
                        'rows': len(df),
                        'columns': len(df.columns),
                        'is_empty': df.empty,
                        'column_names': df.columns.tolist()
                    }
                    
                    sheets.append(sheet_info)
                    
                    # 添加到总内容
                    all_content.append(f"=== 工作表: {sheet_name} ===")
                    if not df.empty:
                        all_content.append(df.to_string(index=True, header=True, na_rep=''))
                    else:
                        all_content.append("(空工作表)")
                    all_content.append("")
                
                result = {
                    'content': "\n".join(all_content),
                    'sheet_count': len(excel_file.sheet_names),
                    'sheets': sheets
                }
                
                self.logger.info(f"Excel粗解析（详细）完成: {excel_path}")
                return result
                
        except Exception as e:
            self.logger.error(f"Excel粗解析（详细）失败: {excel_path}, 错误: {e}")
            return {}
    
    def check_if_needs_vision_parsing(self, pdf_path: str) -> bool:
        """
        检查PDF是否需要视觉模型解析
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            True表示需要视觉解析（扫描PDF或有大量图片），False表示文本PDF
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            
            # 检查前几页
            text_pages = 0
            image_pages = 0
            total_pages = min(len(doc), 3)
            
            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                text = page.get_text()
                images = page.get_images()
                
                if len(text.strip()) > 100:
                    text_pages += 1
                elif len(images) > 0:
                    image_pages += 1
            
            doc.close()
            
            # 如果图片页多于文本页，建议使用视觉解析
            needs_vision = image_pages > text_pages
            
            if needs_vision:
                self.logger.info(f"PDF建议使用视觉解析: {pdf_path} (图片页:{image_pages}, 文本页:{text_pages})")
            else:
                self.logger.info(f"PDF可使用粗解析: {pdf_path} (图片页:{image_pages}, 文本页:{text_pages})")
            
            return needs_vision
            
        except Exception as e:
            self.logger.error(f"检查PDF类型失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            # 检测失败时，建议使用视觉解析
            return True
    
    def batch_parse_files(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """
        批量粗解析文件
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            文件路径到解析结果的映射
        """
        results = {}
        
        for file_path in file_paths:
            try:
                content = self.parse_file(file_path)
                results[file_path] = content
            except Exception as e:
                self.logger.error(f"批量粗解析失败: {file_path}, 错误: {e}")
                results[file_path] = None
        
        self.logger.info(f"批量粗解析完成: 共{len(file_paths)}个文件")
        return results

