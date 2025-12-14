# -*- coding: utf-8 -*-
"""
PDF处理器 - PDFHandler

提供PDF文件的基本操作功能：
- 获取PDF信息（页数、元数据等）
- 提取PDF文本内容（逐页）
- 检测PDF类型（文本PDF、扫描PDF、混合PDF）
- 分析PDF结构（表格、图片、文本块分布）
"""

import os
import logging
import fitz  # PyMuPDF
from typing import Dict, List, Optional, Tuple
from collections import Counter


class PDFHandler:
    """PDF文件处理器 - 提供基础PDF操作功能"""
    
    def __init__(self):
        """初始化PDF处理器"""
        self.logger = logging.getLogger(__name__)
    
    def get_pdf_info(self, pdf_path: str) -> Dict[str, any]:
        """
        获取PDF文件基本信息
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            包含PDF信息的字典：
            - page_count: 页数
            - file_size: 文件大小（字节）
            - metadata: 元数据
            - pdf_type: PDF类型（text/scanned/mixed）
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            
            info = {
                'page_count': len(doc),
                'file_size': os.path.getsize(pdf_path),
                'metadata': doc.metadata,
                'pdf_type': self.detect_pdf_type(pdf_path)
            }
            
            doc.close()
            self.logger.info(f"成功获取PDF信息: {pdf_path}")
            return info
            
        except Exception as e:
            self.logger.error(f"获取PDF信息失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return {}
    
    def detect_pdf_type(self, pdf_path: str) -> str:
        """
        检测PDF类型：文本PDF、扫描PDF或混合PDF
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            PDF类型: "text"（文本PDF）, "scanned"（扫描PDF）, "mixed"（混合PDF）
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            
            # 检查前几页来确定PDF类型
            text_pages = 0
            image_pages = 0
            total_pages = min(len(doc), 3)  # 只检查前3页
            
            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                
                # 获取文本内容
                text = page.get_text()
                
                # 获取图片数量
                image_list = page.get_images()
                
                if len(text.strip()) > 100:
                    # 有足够的文本内容
                    text_pages += 1
                elif len(image_list) > 0:
                    # 有图片但文本很少，可能是扫描件
                    image_pages += 1
            
            doc.close()
            
            # 根据统计结果判断PDF类型
            if text_pages > image_pages:
                return "text"
            elif image_pages > text_pages:
                return "scanned"
            else:
                return "mixed"
                
        except Exception as e:
            self.logger.error(f"PDF类型检测失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            # 检测失败时，默认按混合类型处理
            return "mixed"
    
    def extract_text_from_pdf(self, pdf_path: str) -> List[Tuple[int, str]]:
        """
        从PDF中提取文本内容（逐页）
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            列表，每个元素为 (页码, 文本内容)
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            result = []
            
            for page_num in range(len(doc)):
                try:
                    page = doc.load_page(page_num)
                    text = page.get_text()
                    result.append((page_num + 1, text))
                except Exception as e:
                    self.logger.warning(f"提取第{page_num + 1}页文本失败: {e}")
                    result.append((page_num + 1, ""))
            
            doc.close()
            self.logger.info(f"成功提取PDF文本: {pdf_path}, 共{len(result)}页")
            return result
            
        except Exception as e:
            self.logger.error(f"提取PDF文本失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return []
    
    def analyze_pdf_structure(self, pdf_path: str) -> Dict[str, any]:
        """
        分析PDF文件结构
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            包含结构分析结果的字典：
            - total_pages: 总页数
            - has_tables: 是否包含表格
            - has_images: 是否包含图片
            - text_density: 每页文本密度列表
            - page_types: 每页的类型（text/table/image/mixed）
            - table_pages: 包含表格的页码列表
            - image_pages: 包含图片的页码列表
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            
            analysis = {
                'total_pages': len(doc),
                'has_tables': False,
                'has_images': False,
                'text_density': [],
                'page_types': [],
                'table_pages': [],
                'image_pages': []
            }
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # 检查是否有表格
                tables = page.find_tables()
                if tables:
                    analysis['has_tables'] = True
                    analysis['table_pages'].append(page_num + 1)
                
                # 检查是否有图片
                images = page.get_images(full=True)
                if images:
                    analysis['has_images'] = True
                    analysis['image_pages'].append(page_num + 1)
                
                # 计算文本密度
                text = page.get_text()
                text_density = len(text) / (page.rect.width * page.rect.height) if page.rect.width and page.rect.height else 0
                analysis['text_density'].append(text_density)
                
                # 判断页面类型
                if tables and images:
                    page_type = 'mixed'
                elif tables:
                    page_type = 'table'
                elif images:
                    page_type = 'image'
                else:
                    page_type = 'text'
                analysis['page_types'].append(page_type)
            
            doc.close()
            self.logger.info(f"PDF结构分析完成: {pdf_path}")
            return analysis
            
        except Exception as e:
            self.logger.error(f"PDF结构分析失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return {}
    
    def extract_tables_info(self, pdf_path: str) -> List[Dict[str, any]]:
        """
        提取PDF中的表格信息
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            表格信息列表，每个元素包含：
            - page: 页码
            - bbox: 边界框
            - data: 表格数据
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            tables = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_tables = page.find_tables()
                
                for table in page_tables:
                    tables.append({
                        'page': page_num + 1,
                        'bbox': table.bbox,
                        'data': table.extract()
                    })
            
            doc.close()
            self.logger.info(f"成功提取表格信息: {pdf_path}, 共{len(tables)}个表格")
            return tables
            
        except Exception as e:
            self.logger.error(f"提取表格信息失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return []
    
    def get_page_image_info(self, pdf_path: str) -> Dict[int, List[Dict]]:
        """
        获取PDF每页的图片信息
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            字典，键为页码，值为该页的图片信息列表
            每个图片信息包含：xref, width, height
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            page_images = {}
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                image_list = page.get_images(full=True)
                
                images_info = []
                for img in image_list:
                    xref = img[0]
                    try:
                        image_bytes = doc.extract_image(xref)
                        images_info.append({
                            'xref': xref,
                            'width': img[2],
                            'height': img[3],
                            'ext': image_bytes.get('ext', 'unknown')
                        })
                    except:
                        pass
                
                if images_info:
                    page_images[page_num + 1] = images_info
            
            doc.close()
            self.logger.info(f"成功获取图片信息: {pdf_path}")
            return page_images
            
        except Exception as e:
            self.logger.error(f"获取图片信息失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return {}
    
    def is_valid_pdf(self, pdf_path: str) -> bool:
        """
        检查是否为有效的PDF文件
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            是否为有效PDF
        """
        doc = None
        try:
            if not os.path.exists(pdf_path):
                return False
            
            doc = fitz.open(pdf_path)
            is_valid = len(doc) > 0
            doc.close()
            return is_valid
            
        except Exception as e:
            self.logger.error(f"PDF验证失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return False

