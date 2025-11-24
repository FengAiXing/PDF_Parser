# -*- coding: utf-8 -*-
"""
复杂文件PDF处理器
专门处理candidate_bid_files类型的PDF文件，包含图片等难以解析的内容
"""

import logging
import os
from collections import Counter
import fitz  # PyMuPDF
from typing import List, Tuple, Optional, Dict


class ComplexPDFProcessor:
    """复杂文件PDF处理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # 图片过滤相关配置
        pass
    
    
    def extract_images_from_pdf(self, pdf_path: str, output_image_dir: str) -> List[Tuple[str, int]]:
        """
        从PDF中提取图片并过滤重复尺寸的图片 - 专门针对candidate_bid_files
        
        Args:
            pdf_path: PDF文件路径
            output_image_dir: 输出图片目录
            
        Returns:
            过滤后的图片路径列表 [(图片路径, 页码), ...]
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            pdf_page_count = len(doc)
            image_paths = []
            size_counter = Counter()  # 统计尺寸出现次数

            # 确保输出目录存在
            os.makedirs(output_image_dir, exist_ok=True)

            # 1. 提取并保存所有图片，统计尺寸
            total_count = 0     # 统计总图片数量
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images(full=True)

                for image_index, img in enumerate(image_list, start=1):
                    total_count += 1
                    xref = img[0]
                    image_bytes = doc.extract_image(xref)["image"]
                    image_ext = doc.extract_image(xref)["ext"]
                    image_filename = f"page_{page_num + 1}_img_{image_index}.{image_ext}"
                    image_path = os.path.join(output_image_dir, image_filename)

                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)

                    # 获取图片尺寸
                    img_doc = fitz.open(image_path)
                    width, height = img_doc[0].rect.width, img_doc[0].rect.height
                    img_doc.close()

                    # 过滤最小边 < 14 像素的图片（服务端会报 InvalidParameter）
                    if min(int(width), int(height)) < 14:
                        try:
                            os.remove(image_path)
                        except Exception as remove_err:
                            logging.warning(f"删除过小图片失败: {image_path}, 错误: {remove_err}")
                        # logging.info(f"跳过过小图片: {os.path.basename(image_path)} (尺寸: {(int(width), int(height))})")
                        continue

                    image_size = (width, height)  # 使用宽高元组作为尺寸标识
                    image_paths.append((image_path, page_num + 1, image_size))
                    size_counter[image_size] += 1

            doc.close()

            # 2. 计算需要删除的尺寸 - 针对投标文件调整阈值
            threshold = int(pdf_page_count * 0.8)  # 投标文件可能有很多重复的页眉页脚，但不要过度过滤
            sizes_to_delete = {size: count for size, count in size_counter.items() if count > threshold}

            # 3. 删除超过阈值尺寸的图片
            filtered_image_paths = []
            for path, page, size in image_paths:
                if size in sizes_to_delete:
                    os.remove(path)
                    # logging.info(f"删除重复尺寸图片: {os.path.basename(path)} (尺寸: {size})")
                else:
                    filtered_image_paths.append((path, page))

            # 4. 打印统计信息
            logging.info(f"复杂文件处理 - 图片过滤统计: 总图片数 {total_count}, 保留 {len(filtered_image_paths)} 张")
            logging.info(f"过滤标准: 仅基于重复尺寸过滤（超过PDF总页数80%的尺寸）")
            
            if sizes_to_delete:
                logging.info(f"复杂文件处理 - 发现 {len(sizes_to_delete)} 种尺寸的图片超过pdf总页数的80%阈值。")
                for size, count in sizes_to_delete.items():
                    logging.info(f"- 尺寸 {size}: {count} 张")

            return filtered_image_paths
            
        except Exception as e:
            logging.error(f"从复杂PDF {pdf_path} 提取图片时出错: {e}")
            # 确保PDF文档被关闭
            if doc:
                try:
                    doc.close()
                    logging.info(f"关闭PDF文档: {pdf_path}")
                except Exception as close_error:
                    logging.warning(f"关闭PDF文档失败: {close_error}")
            # 清理临时图片文件
            if 'output_image_dir' in locals() and os.path.exists(output_image_dir):
                try:
                    import shutil
                    shutil.rmtree(output_image_dir)
                    logging.info(f"清理临时图片目录: {output_image_dir}")
                except Exception as cleanup_error:
                    logging.warning(f"清理临时图片目录失败: {cleanup_error}")
            return []
    
    def extract_text_from_pdf(self, pdf_path: str) -> List[str]:
        """
        从PDF中提取文本内容 - 专门针对candidate_bid_files
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            每页文本内容列表
        """
        pdf = None
        try:
            pdf = fitz.open(pdf_path)
            num_pages = len(pdf)
            result = []

            for page_num in range(num_pages):
                page = pdf[page_num]
                text = page.get_text()
                result.append(text)

            pdf.close()
            pdf = None  # 标记已关闭
            return result
            
        except Exception as e:
            logging.error(f"从复杂PDF {pdf_path} 提取文本时出错: {e}")
            # 确保PDF文档被关闭
            if pdf:
                try:
                    pdf.close()
                    logging.info(f"异常时关闭PDF文档: {pdf_path}")
                except Exception as close_error:
                    logging.warning(f"异常时关闭PDF文档失败: {close_error}")
            return []
    
    def get_pdf_info(self, pdf_path: str) -> dict:
        """
        获取PDF文件信息
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            PDF信息字典
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            info = {
                'page_count': len(doc),
                'metadata': doc.metadata,
                'file_size': os.path.getsize(pdf_path)
            }
            doc.close()
            doc = None  # 标记已关闭
            return info
        except Exception as e:
            self.logger.error(f"获取复杂PDF信息失败: {e}")
            # 确保PDF文档被关闭
            if doc:
                try:
                    doc.close()
                    logging.info(f"异常时关闭PDF文档: {pdf_path}")
                except Exception as close_error:
                    logging.warning(f"异常时关闭PDF文档失败: {close_error}")
            return {}
    
    def extract_bid_specific_elements(self, pdf_path: str) -> Dict[str, List]:
        """
        专门提取投标文件中的特定元素
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            包含投标文件特定元素的字典
        """
        try:
            doc = fitz.open(pdf_path)
            result = {
                'tables': [],
                'images': [],
                'text_blocks': []
            }
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # 提取表格
                tables = page.find_tables()
                for table in tables:
                    result['tables'].append({
                        'page': page_num + 1,
                        'bbox': table.bbox,
                        'data': table.extract()
                    })
                
                # 提取图片
                image_list = page.get_images(full=True)
                for img_index, img in enumerate(image_list):
                    result['images'].append({
                        'page': page_num + 1,
                        'index': img_index,
                        'xref': img[0]
                    })
                
                # 提取文本块
                text_dict = page.get_text("dict")
                for block in text_dict["blocks"]:
                    if "lines" in block:
                        result['text_blocks'].append({
                            'page': page_num + 1,
                            'bbox': block['bbox'],
                            'lines': block['lines']
                        })
            
            doc.close()
            return result
            
        except Exception as e:
            self.logger.error(f"提取投标文件特定元素失败: {e}")
            return {'tables': [], 'images': [], 'text_blocks': []}
    
    def analyze_bid_structure(self, pdf_path: str) -> Dict[str, any]:
        """
        分析投标文件结构
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            投标文件结构分析结果
        """
        try:
            doc = fitz.open(pdf_path)
            analysis = {
                'total_pages': len(doc),
                'has_tables': False,
                'has_images': False,
                'text_density': [],
                'page_types': []
            }
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # 检查是否有表格
                tables = page.find_tables()
                if tables:
                    analysis['has_tables'] = True
                
                # 检查是否有图片
                images = page.get_images(full=True)
                if images:
                    analysis['has_images'] = True
                
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
            return analysis
            
        except Exception as e:
            self.logger.error(f"分析投标文件结构失败: {e}")
            return {}
