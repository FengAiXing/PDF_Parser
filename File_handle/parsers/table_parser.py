# -*- coding: utf-8 -*-
"""
表格解析器 - TableParser

功能：
- 识别PDF中的表格
- 检测跨页表格
- 裁剪表格区域为图片
- 合并跨页表格
- 使用视觉模型识别表格内容
"""

import os
import logging
import concurrent.futures
import fitz  # PyMuPDF
from PIL import Image
from typing import List, Dict, Tuple, Optional
import tempfile
from collections import Counter

from ..config import Config

# 导入表格处理模块的组件
from ..table.cross_page_table_detector import CrossPageTableDetector
from ..table.cross_page_table_merger import CrossPageTableMerger

# 导入 PyMuPDF 表格解析模块
from ..table.parse_table_by_pymu import convert_table_to_html

# 导入表格工具函数
from ..table.table_utils import (
    crop_table_image,
    bbox_overlap_ratio,
    detect_rectangular_boxes,
    has_real_table_lines,
    is_valid_table,
    merge_vertical_lines,
    extract_table_rows_and_data_with_pymupdf,
    parse_single_table_with_pymupdf
)


class TableParser:
    """PDF表格解析器 - 支持跨页表格识别"""
    
    def __init__(self, max_workers: int = 100):
        """
        初始化表格解析器
        
        Args:
            max_workers: 并发处理数
        """
        self.logger = logging.getLogger(__name__)
        self.max_workers = max_workers
        
        # 初始化跨页表格识别器和合并器
        self.cross_page_detector = CrossPageTableDetector(logger=self.logger)
        self.cross_page_merger = CrossPageTableMerger(logger=self.logger, detector=self.cross_page_detector)
        
        self.logger.info(f"表格解析器初始化完成: workers={max_workers}")
    
    def extract_tables_from_pdf(self, pdf_path: str, output_dir: str = None) -> List[Dict]:
        """
        从PDF中提取所有表格
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 表格图片输出目录
            
        Returns:
            表格列表，每个表格包含：
            - page: 页码
            - bbox: 边界框
            - image_path: 裁剪的表格图片路径
            - is_cross_page: 是否跨页
        """
        doc = None
        # 根据 Config 决定是否需要保存表格图片
        should_save_images = Config.should_save_table_images()
        
        try:
            doc = fitz.open(pdf_path)
            
            # 只有需要保存时才创建输出目录
            if should_save_images:
                if output_dir is None:
                    output_dir = tempfile.mkdtemp(prefix="tables_")
                os.makedirs(output_dir, exist_ok=True)
                actual_output_dir = output_dir
            else:
                actual_output_dir = None  # 不保存时不需要目录
            
            all_tables = []
            table_id = 0
            
            self.logger.info(f"开始提取表格: {pdf_path}, 共{len(doc)}页")
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # 方法1: 使用PyMuPDF检测表格，采用宽松策略以检测更多表格
                # snap_tolerance: 对齐容差，增加可以检测线条不完全对齐的表格
                # join_tolerance: 连接容差，增加可以检测断开线条的表格  
                # edge_min_length: 最小边长，降低可以检测小表格
                table_finder = page.find_tables(
                    snap_tolerance=5,       # 默认3，提高对齐容差
                    join_tolerance=5,       # 默认3，提高连接容差
                    edge_min_length=3       # 默认5，降低最小边长以检测更多小表格
                )
                
                tables = []
                pymupdf_tables_bboxes = []
                
                # 从TableFinder获取表格
                if table_finder and table_finder.tables:
                    tables = table_finder.tables
                    # 记录PyMuPDF检测到的表格bbox，用于后续去重
                    pymupdf_tables_bboxes = [t.bbox for t in tables]
                
                # 方法2: 检测基于绘图元素的矩形框（只有外框的"表格"）
                box_tables = detect_rectangular_boxes(page, logger=self.logger)
                if box_tables:
                    # 将矩形框作为"伪表格"添加到表格列表中
                    # 注意：需要转换为类似PyMuPDF表格的格式，并且要去重（避免与PyMuPDF表格重叠）
                    for box in box_tables:
                        # 检查这个矩形框是否与已检测的表格重叠
                        is_overlapping = False
                        for existing_bbox in pymupdf_tables_bboxes:
                            if bbox_overlap_ratio(box, existing_bbox) > 0.3:  # 重叠超过30%
                                is_overlapping = True
                                self.logger.debug(f"矩形框与已检测表格重叠，跳过: {box}")
                                break
                        
                        if not is_overlapping:
                            # 创建一个伪表格对象（使用简单的类来模拟）
                            class PseudoTable:
                                def __init__(self, bbox_rect):
                                    self.bbox = bbox_rect
                                def extract(self):
                                    return [[""]]  # 返回一个空单元格
                            
                            tables.append(PseudoTable(box))
                
                if not tables:
                    continue
                
                for table_idx, table in enumerate(tables):
                    # 获取表格边界框
                    bbox_raw = table.bbox
                    # 转换为元组格式 (x0, y0, x1, y1)
                    if hasattr(bbox_raw, 'x0'):
                        bbox = (bbox_raw.x0, bbox_raw.y0, bbox_raw.x1, bbox_raw.y1)
                    else:
                        bbox = bbox_raw
                    
                    # 提取表格数据和列宽信息
                    table_data = table.extract() if hasattr(table, 'extract') else None
                    col_count = 0
                    row_count = 0
                    col_widths = []
                    
                    # 判断是否为矩形框（PseudoTable）
                    is_pseudo_table = hasattr(table, '__class__') and table.__class__.__name__ == 'PseudoTable'
                    
                    # 对于矩形框（PseudoTable），从bbox区域提取文本
                    if is_pseudo_table:
                        # 这是一个矩形框，从bbox区域提取文本内容
                        rect = fitz.Rect(bbox)
                        text_in_box = page.get_text("text", clip=rect).strip()
                        if text_in_box:
                            # 将文本按行分割，每行作为一个单元格
                            lines = [line.strip() for line in text_in_box.split('\n') if line.strip()]
                            table_data = [[line] for line in lines]  # 每行一个单元格（1列）
                            col_count = 1
                            row_count = len(table_data)
                        else:
                            # 空框，跳过
                            self.logger.info(f"  ⚠️ 矩形框为空，跳过")
                            continue
                    elif table_data and len(table_data) > 0:
                        row_count = len(table_data)
                        
                        # 计算列数：考虑rowspan的情况，使用更智能的算法
                        col_counts = []
                        for row in table_data:
                            if row:
                                col_counts.append(len(row))
                        
                        if col_counts:
                            counter = Counter(col_counts)
                            
                            # 策略1：如果所有行的列数都相同，直接使用
                            if len(counter) == 1:
                                col_count = col_counts[0]
                            else:
                                # 策略2：找出最常见的列数
                                most_common_col, most_common_count = counter.most_common(1)[0]
                                
                                # 策略3：找出最大列数（rowspan可能导致某些行列数较少，但最大列数通常是准确的）
                                max_col = max(col_counts)
                                
                                # 如果最常见的列数出现次数超过60%，使用它
                                if most_common_count > len(col_counts) * 0.6:
                                    col_count = most_common_col
                                # 如果最大列数出现次数超过30%，使用最大列数（可能是rowspan导致的）
                                elif counter[max_col] > len(col_counts) * 0.3:
                                    col_count = max_col
                                # 否则，如果最大列数和最常见列数接近（差异<=1），使用最大列数
                                elif abs(max_col - most_common_col) <= 1:
                                    col_count = max_col
                                # 最后，使用最常见的列数
                                else:
                                    col_count = most_common_col
                                
                    
                    # 暂不提取详细列宽（PyMuPDF的cells访问较复杂）
                    # 使用列数和总宽度来判断即可
                    col_widths = []
                    
                    # 【关键检查】验证表格是否有真实的表格线（过滤文本对齐误识别）
                    # 对于PseudoTable（矩形框），已经通过绘图元素检测确认有边框，跳过此检查
                    if not is_pseudo_table:
                        # PyMuPDF检测的表格，需要验证是否有真实表格线
                        if not has_real_table_lines(page, bbox, logger=self.logger):
                            self.logger.info(f"  ⚠️ 跳过无表格线的假表格: 第{page_num + 1}页表格{table_idx + 1} (可能是文本对齐误识别)")
                            continue
                    
                    # 验证表格有效性（使用宽松模式，允许单列表格，可能是跨页延续）
                    if not is_valid_table(table_data, col_count, row_count, bbox, strict_mode=False, logger=self.logger):
                        self.logger.info(f"  ⚠️ 跳过无效表格: 第{page_num + 1}页表格{table_idx + 1}")
                        continue
                    
                    # 验证通过，分配表格ID
                    table_id += 1
                    
                    # 只有需要保存时才裁剪表格图片
                    table_image_path = None
                    if should_save_images and actual_output_dir:
                        table_image_path = crop_table_image(
                            page, bbox, actual_output_dir, f"table_{table_id}_page_{page_num + 1}",
                            save_to_disk=True, config=Config, logger=self.logger
                        )
                    
                    table_info = {
                        'id': table_id,
                        'page': page_num + 1,
                        'bbox': bbox,
                        'image_path': table_image_path,
                        'is_cross_page': False,
                        'table_data': table_data,
                        'col_count': col_count,
                        'row_count': row_count
                    }
                    
                    all_tables.append(table_info)
            
            doc.close()
            
            # 检测并合并跨页表格（传递是否保存图片的标志）
            merged_tables = self.cross_page_merger.detect_and_merge_cross_page_tables(
                all_tables, pdf_path, actual_output_dir, 
                is_valid_table_func=lambda *args, **kwargs: is_valid_table(*args, logger=self.logger, **kwargs),
                save_images=should_save_images
            )
            
            # 表格提取详细日志已移除
            
            return merged_tables
            
        except Exception as e:
            self.logger.error(f"提取表格失败: {pdf_path}, 错误: {e}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return []
    
    def parse_tables_with_vision(self, tables: List[Dict], pdf_path: str) -> List[Dict]:
        """
        使用 PyMuPDF 解析表格内容（替换原来的视觉模型识别）
        
        Args:
            tables: 表格列表（包含page、bbox等信息）
            pdf_path: PDF文件路径
            
        Returns:
            表格列表（添加了recognized_content字段）
        """
        try:
            self.logger.info(f"开始使用PyMuPDF解析{len(tables)}个表格...")
            
            # 处理所有表格（包括跨页表格的原始表格）
            for table in tables:
                if not table.get('is_cross_page', False):
                    # 单页表格：直接解析
                    page_num = table.get('page', 1) - 1  # 转换为从0开始的索引
                    bbox = table.get('bbox')
                    
                    if bbox:
                        html_table = parse_single_table_with_pymupdf(
                            pdf_path, page_num, bbox, logger=self.logger
                        )
                        if html_table:
                            table['recognized_content'] = html_table
                            
                            # 更新列数和行数（从HTML中提取）
                            import re
                            tr_pattern = r'<tr[^>]*>(.*?)</tr>'
                            rows = re.findall(tr_pattern, html_table, re.DOTALL | re.IGNORECASE)
                            if rows:
                                full_rows = [f'<tr>{row}</tr>' for row in rows]
                                col_counts = self.cross_page_merger.compute_display_cols(full_rows)
                                if col_counts:
                                    counter = Counter(col_counts)
                                    detected_max = max(col_counts)
                                    if counter[detected_max] > len(col_counts) * 0.3:
                                        new_col_count = detected_max
                                    else:
                                        most_common_col, _ = counter.most_common(1)[0]
                                        new_col_count = most_common_col
                                    table['col_count'] = new_col_count
                                    table['row_count'] = len(rows)
                            
                        else:
                            table['recognized_content'] = None
                            self.logger.warning(f"表格{table['id']}解析失败")
                    else:
                        table['recognized_content'] = None
                        self.logger.warning(f"表格{table['id']}缺少bbox信息")
                else:
                    # 跨页表格：解析所有原始表格
                    original_image_paths = table.get('original_image_paths', [])
                    original_tables = table.get('original_tables', [])
                    
                    if original_tables:
                        table['original_results'] = {}
                        parsed_parts = []
                        all_vertical_lines = []
                        
                        for idx, orig_table in enumerate(original_tables):
                            page_num = orig_table.get('page', 1) - 1
                            bbox = orig_table.get('bbox')
                            
                            if bbox:
                                rows_data, table_data_from_coords, fallback_html = extract_table_rows_and_data_with_pymupdf(
                                    pdf_path, page_num, bbox, logger=self.logger
                                )
                                parsed_parts.append({
                                    'rows': rows_data,
                                    'table_data': table_data_from_coords,
                                    'fallback_html': fallback_html,
                                })
                                
                                if rows_data:
                                    # 检查是否为1*1表格，若是则不参与列线合并，但后续生成HTML仍会使用合并后的列线
                                    is_1x1_table = (
                                        len(rows_data) == 1 and 
                                        len(rows_data[0].get('cells', [])) == 1
                                    )
                                    if is_1x1_table:
                                        self.logger.info(f"跨页表格{table['id']}第{idx+1}部分是1*1表格，跳过列边框线合并")
                                    else:
                                        for row in rows_data:
                                            for cell in row.get('cells', []):
                                                all_vertical_lines.append(round(cell.get('x_start', 0), 1))
                                                all_vertical_lines.append(round(cell.get('x_end', 0), 1))
                            else:
                                self.logger.warning(f"跨页表格{table['id']}第{idx+1}部分缺少bbox信息")
                                parsed_parts.append({'rows': None, 'table_data': None, 'fallback_html': None})
                        
                        merged_vertical_lines = merge_vertical_lines(all_vertical_lines, threshold=2.0) if all_vertical_lines else None
                        
                        for idx, part in enumerate(parsed_parts):
                            html_table = None
                            if part.get('fallback_html') is not None:
                                html_table = part['fallback_html']
                            elif part.get('rows') and part.get('table_data'):
                                html_table = convert_table_to_html(
                                    part['rows'],
                                    part['table_data'],
                                    merged_vertical_lines=merged_vertical_lines,
                                    tolerance=2.0
                                )
                            
                            if html_table:
                                if idx < len(original_image_paths):
                                    image_path = original_image_paths[idx]
                                    table['original_results'][image_path] = html_table
                                
                                import re
                                tr_pattern = r'<tr[^>]*>(.*?)</tr>'
                                rows = re.findall(tr_pattern, html_table, re.DOTALL | re.IGNORECASE)
                                if rows:
                                    full_rows = [f'<tr>{row}</tr>' for row in rows]
                                    col_counts = self.cross_page_merger.compute_display_cols(full_rows)
                                    if col_counts:
                                        counter = Counter(col_counts)
                                        detected_max = max(col_counts)
                                        if counter[detected_max] > len(col_counts) * 0.3:
                                            new_col_count = detected_max
                                        else:
                                            most_common_col, _ = counter.most_common(1)[0]
                                            new_col_count = most_common_col
                                        orig_table = original_tables[idx]
                                        orig_table['col_count'] = new_col_count
                                        orig_table['row_count'] = len(rows)
                                
                            else:
                                self.logger.warning(f"跨页表格{table['id']}第{idx+1}部分解析失败")
                        
                        # 跨页表格解析完成
                        self.logger.info(f"跨页表格{table['id']}解析完成")
                    else:
                        table['original_results'] = {}
                        self.logger.warning(f"跨页表格{table['id']}没有原始表格信息")
            return tables
            
        except Exception as e:
            self.logger.error(f"表格解析失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return tables
    
    def parse_pdf_tables(self, pdf_path: str, output_dir: str = None, 
                        save_images: bool = True) -> Dict:
        """
        完整解析PDF中的所有表格
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            save_images: 是否保存表格图片
            
        Returns:
            解析结果字典：
            - tables: 表格列表（包含识别内容）
            - total_count: 总表格数
            - cross_page_count: 跨页表格数
        """
        try:
            self.logger.info(f"开始解析PDF表格: {pdf_path}")
            
            # 1. 提取表格
            tables = self.extract_tables_from_pdf(pdf_path, output_dir)
            
            if not tables:
                self.logger.warning("未检测到表格")
                return {
                    'tables': [],
                    'total_count': 0,
                    'cross_page_count': 0
                }
            
            # 2. 使用 PyMuPDF 解析表格内容（替换视觉模型识别）
            tables = self.parse_tables_with_vision(tables, pdf_path)
            
            # 3. 合并跨页表格的HTML内容
            tables = self.cross_page_merger.merge_html_tables(tables)
            
            # 4. 统计信息
            cross_page_count = sum(1 for t in tables if t.get('is_cross_page', False))
            
            result = {
                'tables': tables,
                'total_count': len(tables),
                'cross_page_count': cross_page_count
            }
            
            self.logger.info(f"表格解析完成: 共{len(tables)}个表格, 其中{cross_page_count}个跨页表格")
            
            return result
            
        except Exception as e:
            self.logger.error(f"解析PDF表格失败: {pdf_path}, 错误: {e}")
            return {
                'tables': [],
                'total_count': 0,
                'cross_page_count': 0,
                'error': str(e)
            }

    async def parse_pdf_tables_async(self, pdf_path: str, output_dir: str = None,
                                    save_images: bool = True) -> Dict:
        """
        异步封装：将表格解析放入线程池，便于与其他耗时任务并发。
        """
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.parse_pdf_tables(pdf_path=pdf_path, output_dir=output_dir, save_images=save_images)
        )
    
    def save_tables_to_file(self, tables: List[Dict], output_path: str):
        """
        将表格识别结果保存到文件
        
        Args:
            tables: 表格列表
            output_path: 输出文件路径
        """
        # 根据 Config 决定是否保存
        if not Config.should_save_single_table_results():
            self.logger.info("根据 Config 配置，跳过保存表格结果文件")
            return
            
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("=" * 100 + "\n")
                f.write("PDF表格识别结果\n")
                f.write("=" * 100 + "\n\n")
                
                for table in tables:
                    f.write(f"【表格 {table['id']}】\n")
                    f.write(f"页码: {table['page']}\n")
                    
                    if table.get('is_cross_page'):
                        page_count = table.get('page_count', 2)
                        f.write(f"类型: 跨页表格 (跨{page_count}页)\n")
                        f.write(f"合并自: 表格{table.get('merged_from', [])}\n")
                    else:
                        f.write(f"类型: 单页表格\n")
                    
                    # 添加列数和行数信息
                    col_count = table.get('col_count', 0)
                    row_count = table.get('row_count', 0)
                    if col_count > 0:
                        f.write(f"列数: {col_count}\n")
                    if row_count > 0:
                        f.write(f"行数: {row_count}\n")
                    
                    f.write(f"图片: {table.get('image_path', '无')}\n")
                    f.write("\n识别内容:\n")
                    f.write("-" * 100 + "\n")
                    
                    content = table.get('recognized_content', '未识别')
                    f.write(content if content else '(识别失败)')
                    
                    f.write("\n" + "-" * 100 + "\n\n")
            
            self.logger.info(f"表格结果已保存到: {output_path}")
            
        except Exception as e:
            self.logger.error(f"保存表格结果失败: {e}")

