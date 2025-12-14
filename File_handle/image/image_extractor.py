# -*- coding: utf-8 -*-
"""
图片提取器 - ImageExtractor

从PDF文件中提取图片，支持：
- 提取所有图片并保存到指定目录
- 过滤重复尺寸的图片（如页眉页脚）
- 过滤过小的图片
- 返回图片路径和页码映射
"""

import os
import logging
import tempfile
import fitz  # PyMuPDF
from collections import Counter
from typing import List, Tuple, Dict, Optional

from ..config import Config


class ImageExtractor:
    """图片提取器 - 从PDF中提取图片"""
    
    def __init__(self, 
                 min_size: int = 14,
                 repetition_threshold: float = 0.8):
        """
        初始化图片提取器
        
        Args:
            min_size: 图片最小边长（像素），小于此值的图片将被过滤
            repetition_threshold: 重复尺寸阈值，超过PDF页数此比例的相同尺寸图片将被过滤
        """
        self.logger = logging.getLogger(__name__)
        self.min_size = min_size
        self.repetition_threshold = repetition_threshold
    
    def extract_images_from_pdf(self, 
                               pdf_path: str, 
                               output_dir: str,
                               filter_repetitive: bool = True,
                               filter_small: bool = True) -> List[Tuple[str, int]]:
        """
        从PDF中提取图片
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 图片输出目录
            filter_repetitive: 是否过滤重复尺寸的图片
            filter_small: 是否过滤过小的图片
            
        Returns:
            图片信息列表，每个元素为 (图片路径, 页码)
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            pdf_page_count = len(doc)
            
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            # 第一阶段：提取所有图片并统计
            all_images = []
            size_counter = Counter()
            total_count = 0
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                image_list = page.get_images(full=True)
                
                for image_index, img in enumerate(image_list, start=1):
                    total_count += 1
                    xref = img[0]
                    
                    try:
                        image_bytes = doc.extract_image(xref)["image"]
                        image_ext = doc.extract_image(xref)["ext"]
                        image_filename = f"page_{page_num + 1}_img_{image_index}.{image_ext}"
                        image_path = os.path.join(output_dir, image_filename)
                        
                        # 保存图片
                        with open(image_path, "wb") as img_file:
                            img_file.write(image_bytes)
                        
                        # 获取图片尺寸
                        img_doc = fitz.open(image_path)
                        width, height = img_doc[0].rect.width, img_doc[0].rect.height
                        img_doc.close()
                        
                        image_size = (int(width), int(height))
                        all_images.append({
                            'path': image_path,
                            'page': page_num + 1,
                            'size': image_size,
                            'width': int(width),
                            'height': int(height)
                        })
                        size_counter[image_size] += 1
                        
                    except Exception as e:
                        self.logger.warning(f"提取图片失败: page {page_num + 1}, img {image_index}, 错误: {e}")
                        continue
            
            doc.close()
            
            # 第二阶段：根据规则过滤图片
            filtered_images = []
            removed_count = 0
            
            # 计算需要删除的重复尺寸
            threshold = int(pdf_page_count * self.repetition_threshold)
            sizes_to_delete = {size: count for size, count in size_counter.items() 
                             if count > threshold} if filter_repetitive else {}
            
            for img_info in all_images:
                should_remove = False
                remove_reason = ""
                
                # 检查是否过小
                if filter_small and min(img_info['width'], img_info['height']) < self.min_size:
                    should_remove = True
                    remove_reason = f"尺寸过小 ({img_info['width']}x{img_info['height']})"
                
                # 检查是否重复尺寸
                if filter_repetitive and img_info['size'] in sizes_to_delete:
                    should_remove = True
                    remove_reason = f"重复尺寸 ({img_info['size']}, 出现{size_counter[img_info['size']]}次)"
                
                if should_remove:
                    try:
                        os.remove(img_info['path'])
                        removed_count += 1
                        # self.logger.debug(f"删除图片: {os.path.basename(img_info['path'])}, 原因: {remove_reason}")
                    except Exception as e:
                        self.logger.warning(f"删除图片失败: {img_info['path']}, 错误: {e}")
                else:
                    filtered_images.append((img_info['path'], img_info['page']))
            
            # 统计信息
            self.logger.info(f"图片提取完成: {pdf_path}")
            self.logger.info(f"总图片数: {total_count}, 保留: {len(filtered_images)}, 删除: {removed_count}")
            if sizes_to_delete:
                self.logger.info(f"重复尺寸过滤: {len(sizes_to_delete)}种尺寸被过滤")
            
            return filtered_images
            
        except Exception as e:
            self.logger.error(f"提取图片失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return []
    
    def extract_images_with_metadata(self, 
                                    pdf_path: str, 
                                    output_dir: str,
                                    filter_repetitive: bool = True,
                                    filter_small: bool = True,
                                    save_to_disk: bool = True) -> List[Dict[str, any]]:
        """
        从PDF中提取图片（包含详细元数据）
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 图片输出目录
            filter_repetitive: 是否过滤重复尺寸的图片
            filter_small: 是否过滤过小的图片
            save_to_disk: 是否保存到磁盘（由 Config 控制）
            
        Returns:
            图片信息列表，每个元素包含：
            - path: 图片路径
            - page: 页码
            - width: 宽度
            - height: 高度
            - size: 尺寸元组
            - format: 图片格式
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            pdf_page_count = len(doc)
            
            # 根据 Config 决定是否保存到磁盘
            should_save = save_to_disk and Config.should_save_extracted_images()
            
            # 确保输出目录存在（即使不保存也需要临时目录）
            if should_save:
                os.makedirs(output_dir, exist_ok=True)
                actual_output_dir = output_dir
            else:
                actual_output_dir = tempfile.mkdtemp(prefix="images_temp_")
            
            # 提取所有图片
            all_images = []
            size_counter = Counter()
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                image_list = page.get_images(full=True)
                
                for image_index, img in enumerate(image_list, start=1):
                    xref = img[0]
                    
                    try:
                        image_data = doc.extract_image(xref)
                        image_bytes = image_data["image"]
                        image_ext = image_data["ext"]
                        image_filename = f"page_{page_num + 1}_img_{image_index}.{image_ext}"
                        image_path = os.path.join(actual_output_dir, image_filename)
                        
                        # 保存图片（用于后续处理，可能是临时目录）
                        with open(image_path, "wb") as img_file:
                            img_file.write(image_bytes)
                        
                        # 获取图片尺寸
                        img_doc = fitz.open(image_path)
                        width, height = img_doc[0].rect.width, img_doc[0].rect.height
                        img_doc.close()
                        
                        # 获取图片在页面中的位置（bbox）
                        image_bbox = None
                        image_y0 = 0  # 默认 y 坐标
                        try:
                            rects = page.get_image_rects(xref)
                            if rects:
                                # 取第一个矩形作为图片位置
                                rect = rects[0]
                                image_bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
                                image_y0 = rect.y0
                        except Exception:
                            pass
                        
                        image_size = (int(width), int(height))
                        image_info = {
                            'path': image_path,
                            'page': page_num + 1,
                            'width': int(width),
                            'height': int(height),
                            'size': image_size,
                            'format': image_ext,
                            'xref': xref,
                            'bbox': image_bbox,
                            'y0': image_y0
                        }
                        
                        all_images.append(image_info)
                        size_counter[image_size] += 1
                        
                    except Exception as e:
                        self.logger.warning(f"提取图片失败: page {page_num + 1}, img {image_index}, 错误: {e}")
                        continue
            
            doc.close()
            
            # 过滤图片
            threshold = int(pdf_page_count * self.repetition_threshold)
            sizes_to_delete = {size: count for size, count in size_counter.items() 
                             if count > threshold} if filter_repetitive else {}
            
            filtered_images = []
            for img_info in all_images:
                should_remove = False
                
                # 检查是否过小
                if filter_small and min(img_info['width'], img_info['height']) < self.min_size:
                    should_remove = True
                
                # 检查是否重复尺寸
                if filter_repetitive and img_info['size'] in sizes_to_delete:
                    should_remove = True
                
                if should_remove:
                    try:
                        os.remove(img_info['path'])
                    except:
                        pass
                else:
                    filtered_images.append(img_info)
            
            self.logger.info(f"提取图片完成（含元数据）: {pdf_path}, 保留{len(filtered_images)}张图片")
            return filtered_images
            
        except Exception as e:
            self.logger.error(f"提取图片失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return []
    
    def render_pages_as_images(self, 
                                pdf_path: str, 
                                output_dir: str,
                                dpi: int = 150,
                                pages: List[int] = None) -> List[Dict[str, any]]:
        """
        将PDF页面渲染为图片（用于扫描版PDF）
        
        当PDF是扫描版（无法提取文本）时，将每页渲染为图片进行OCR识别。
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 图片输出目录
            dpi: 渲染分辨率（默认150，可根据需要调整）
            pages: 要渲染的页码列表（从1开始），None表示全部页面
            
        Returns:
            图片信息列表，每个元素包含：
            - path: 图片路径
            - page: 页码
            - width: 宽度
            - height: 高度
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            os.makedirs(output_dir, exist_ok=True)
            
            # 计算缩放比例（72是PDF的默认DPI）
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            
            rendered_images = []
            
            # 确定要渲染的页面
            if pages is None:
                page_nums = range(len(doc))
            else:
                page_nums = [p - 1 for p in pages if 0 < p <= len(doc)]
            
            for page_num in page_nums:
                page = doc.load_page(page_num)
                
                # 渲染页面为图片
                pix = page.get_pixmap(matrix=mat)
                
                image_filename = f"page_{page_num + 1}_rendered.png"
                image_path = os.path.join(output_dir, image_filename)
                
                pix.save(image_path)
                
                # 渲染的页面图片覆盖整个页面，y0=0
                page_rect = page.rect
                image_info = {
                    'path': image_path,
                    'page': page_num + 1,
                    'width': pix.width,
                    'height': pix.height,
                    'size': (pix.width, pix.height),
                    'format': 'png',
                    'is_rendered': True,  # 标记为渲染的页面
                    'bbox': (page_rect.x0, page_rect.y0, page_rect.x1, page_rect.y1),
                    'y0': 0  # 渲染图片从页面顶部开始
                }
                
                rendered_images.append(image_info)
            
            doc.close()
            
            # 页面渲染日志已移除
            return rendered_images
            
        except Exception as e:
            self.logger.error(f"渲染页面失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return []
    
    def extract_images_smart(self, 
                            pdf_path: str, 
                            output_dir: str,
                            filter_repetitive: bool = True,
                            filter_small: bool = True,
                            save_to_disk: bool = True,
                            render_empty_pages: bool = True,
                            render_dpi: int = 150) -> List[Dict[str, any]]:
        """
        智能提取图片（自动处理扫描版PDF）
        
        1. 首先尝试提取嵌入的图片
        2. 对于没有图片也没有文本的页面，将其渲染为图片
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 图片输出目录
            filter_repetitive: 是否过滤重复尺寸的图片
            filter_small: 是否过滤过小的图片
            save_to_disk: 是否保存到磁盘
            render_empty_pages: 是否将空页面（无文本无图片）渲染为图片
            render_dpi: 渲染分辨率
            
        Returns:
            图片信息列表
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            pdf_page_count = len(doc)
            
            # 根据 Config 决定是否保存到磁盘
            should_save = save_to_disk and Config.should_save_extracted_images()
            
            if should_save:
                os.makedirs(output_dir, exist_ok=True)
                actual_output_dir = output_dir
            else:
                actual_output_dir = tempfile.mkdtemp(prefix="images_temp_")
            
            # 记录每页的状态
            pages_with_images = set()
            pages_with_text = set()
            
            # 第一阶段：检查每页的内容
            for page_num in range(pdf_page_count):
                page = doc.load_page(page_num)
                
                # 检查是否有图片
                if page.get_images(full=True):
                    pages_with_images.add(page_num)
                
                # 检查是否有文本
                text = page.get_text().strip()
                if text:
                    pages_with_text.add(page_num)
            
            doc.close()
            
            # 第二阶段：提取嵌入的图片
            extracted_images = self.extract_images_with_metadata(
                pdf_path, actual_output_dir, 
                filter_repetitive=filter_repetitive,
                filter_small=filter_small,
                save_to_disk=True  # 临时保存
            )
            
            # 记录已提取图片的页面
            pages_with_extracted_images = set(img['page'] for img in extracted_images)
            
            # 第三阶段：对于没有提取到图片且没有文本的页面，渲染为图片
            if render_empty_pages:
                empty_pages = []
                for page_num in range(pdf_page_count):
                    page_1based = page_num + 1
                    # 如果该页没有提取到图片，且没有文本
                    if page_1based not in pages_with_extracted_images and page_num not in pages_with_text:
                        empty_pages.append(page_1based)
                
                if empty_pages:
                    self.logger.info(f"检测到{len(empty_pages)}个空页面（无图片无文本），将渲染为图片")
                    rendered_images = self.render_pages_as_images(
                        pdf_path, actual_output_dir, 
                        dpi=render_dpi, 
                        pages=empty_pages
                    )
                    extracted_images.extend(rendered_images)
            
            # 按页码排序
            extracted_images.sort(key=lambda x: x['page'])
            
            # 智能提取日志已移除
            return extracted_images
            
        except Exception as e:
            self.logger.error(f"智能提取图片失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return []
    
    def get_image_statistics(self, pdf_path: str) -> Dict[str, any]:
        """
        获取PDF中的图片统计信息（不保存图片）
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            统计信息字典：
            - total_images: 总图片数
            - pages_with_images: 包含图片的页数
            - size_distribution: 尺寸分布
            - avg_width: 平均宽度
            - avg_height: 平均高度
        """
        doc = None
        try:
            doc = fitz.open(pdf_path)
            
            total_images = 0
            pages_with_images = 0
            size_counter = Counter()
            widths = []
            heights = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                image_list = page.get_images(full=True)
                
                if image_list:
                    pages_with_images += 1
                    total_images += len(image_list)
                    
                    for img in image_list:
                        width = img[2]
                        height = img[3]
                        size_counter[(width, height)] += 1
                        widths.append(width)
                        heights.append(height)
            
            doc.close()
            
            stats = {
                'total_images': total_images,
                'pages_with_images': pages_with_images,
                'size_distribution': dict(size_counter),
                'avg_width': sum(widths) / len(widths) if widths else 0,
                'avg_height': sum(heights) / len(heights) if heights else 0,
                'unique_sizes': len(size_counter)
            }
            
            self.logger.info(f"图片统计完成: {pdf_path}, 共{total_images}张图片")
            return stats
            
        except Exception as e:
            self.logger.error(f"获取图片统计信息失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return {}

