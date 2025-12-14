# -*- coding: utf-8 -*-
"""
文档组装器 - DocumentAssembler

智能组织和合并文档内容：
- 按页组织文本、表格、图片内容
- 处理跨页表格，避免重复显示
- 智能选择显示内容（表格优先，图片其次，文本最后）
- 生成结构化的完整文档
"""

import os
import re
import logging
import fitz  # PyMuPDF
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from .header_footer_cleaner import HeaderFooterCleaner


class DocumentAssembler:
    """文档组装器 - 智能组织和合并文档内容"""
    
    def __init__(self, pdf_path: str = None,
                 common_headers=None,
                 common_footers=None):
        """
        初始化文档组装器
        
        Args:
            pdf_path: PDF文件路径（用于根据表格bbox提取文本）
        """
        self.logger = logging.getLogger(__name__)
        self.pdf_path = pdf_path
        self.header_footer_cleaner = HeaderFooterCleaner()
        self.common_headers = common_headers or set()
        self.common_footers = common_footers or set()
    
    def parse_page_number(self, page_str: str) -> int:
        """
        解析页码字符串，处理跨页表格的情况
        
        Args:
            page_str: 页码字符串，如 "13" 或 "13-26"
            
        Returns:
            起始页码
        """
        page_str = str(page_str)
        if '-' in page_str:
            # 跨页表格，如 "13-26"
            start_page = int(page_str.split('-')[0])
            return start_page
        else:
            return int(page_str)
    
    def parse_text_by_page(self, text_content: str) -> Dict[int, str]:
        """
        按页分割粗解析文本
        
        Args:
            text_content: 完整的文本内容（包含页码标记）
            
        Returns:
            页码到页面文本的映射
        """
        page_texts = {}
        
        if not text_content:
            return page_texts
        
        # 按页分割内容
        page_pattern = r'==第(\d+)页=='
        page_splits = re.split(page_pattern, text_content)
        
        # page_splits格式: ['开头内容', '1', '第1页内容', '2', '第2页内容', ...]
        for i in range(1, len(page_splits), 2):
            if i+1 < len(page_splits):
                page_num = int(page_splits[i])
                page_text = page_splits[i+1].strip()
                page_texts[page_num] = page_text
        
        self.logger.info(f"文本按页分割完成: {len(page_texts)}页")
        return page_texts

    def _clean_text(self, text: str) -> str:
        """移除首尾页码行及重复页眉/页脚行。"""
        if not text:
            return text
        text = self.header_footer_cleaner.strip_edge_page_numbers(text)
        lines = text.splitlines()
        cleaned = []
        page_num_pattern = re.compile(r"^\s*(?:第\s*\d+\s*页|\d+)\s*$")
        for line in lines:
            if page_num_pattern.fullmatch(line):
                continue
            if line in self.common_headers or line in self.common_footers:
                continue
            cleaned.append(line)
        return "\n".join(cleaned).strip()
    
    def organize_tables_by_page(self, tables: List[Dict]) -> Dict[int, List[Dict]]:
        """
        按页组织表格
        
        Args:
            tables: 表格列表
            
        Returns:
            页码到表格列表的映射
        """
        page_tables = defaultdict(list)
        
        if not tables:
            return page_tables
        
        for table in tables:
            page_num = self.parse_page_number(table['page'])
            page_tables[page_num].append(table)
        
        self.logger.info(f"表格按页组织完成: {len(page_tables)}页有表格")
        return dict(page_tables)
    
    def get_text_blocks_with_positions(self, page_num: int) -> List[Tuple[float, str]]:
        """
        获取页面中所有文本块及其 y0 坐标
        
        Args:
            page_num: 页码（从1开始）
            
        Returns:
            文本块列表: [(y0, text), ...]
        """
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            return []
        
        try:
            doc = fitz.open(self.pdf_path)
            if page_num < 1 or page_num > len(doc):
                doc.close()
                return []
            
            page = doc.load_page(page_num - 1)
            blocks = page.get_text("dict")["blocks"]
            
            text_blocks = []
            for block in blocks:
                if block.get("type") != 0:  # 只处理文本块
                    continue
                bbox = block.get("bbox")
                if not bbox:
                    continue
                y0 = bbox[1]
                
                # 提取该块中的所有文本
                block_text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        block_text += span.get("text", "")
                
                block_text = block_text.strip()
                if block_text:
                    # 检查是否是页眉页脚
                    if block_text in self.common_headers or block_text in self.common_footers:
                        continue
                    text_blocks.append((y0, block_text))
            
            doc.close()
            
            # 按 y0 排序
            text_blocks.sort(key=lambda x: x[0])
            return text_blocks
            
        except Exception as e:
            self.logger.error(f"获取文本块位置失败（第{page_num}页）: {e}")
            return []
    
    def extract_text_excluding_tables(self, page_num: int, table_bboxes: List[Tuple]) -> Tuple[str, str, List[Tuple[float, str]]]:
        """
        从PDF页面中提取文本，但排除表格区域，并区分表格前和表格后的文本
        同时返回按y坐标排序的文本块列表，用于在多个表格之间插入文本
        
        Args:
            page_num: 页码（从1开始）
            table_bboxes: 表格bbox列表，每个bbox为(x0, y0, x1, y1)
            
        Returns:
            (表格前的文本, 表格后的文本, 按y坐标排序的文本块列表) 元组
            文本块列表格式: [(y0, text), ...]
        """
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            self.logger.warning(f"PDF路径无效，无法排除表格区域: {self.pdf_path}")
            return "", ""
        
        try:
            doc = fitz.open(self.pdf_path)
            if page_num < 1 or page_num > len(doc):
                doc.close()
                return "", ""
            
            page = doc.load_page(page_num - 1)
            page_rect = page.rect
            
            # 如果没有表格，直接提取所有文本作为"表格前文本"
            if not table_bboxes:
                text = page.get_text()
                doc.close()
                return text.strip(), ""
            
            # 按y坐标排序所有表格bbox
            sorted_table_bboxes = sorted(table_bboxes, key=lambda bbox: bbox[1])
            top_table_y0 = sorted_table_bboxes[0][1]  # 最上面的表格顶部
            bottom_table_y1 = sorted_table_bboxes[-1][3]  # 最下面的表格底部
            
            # 获取所有文本块
            blocks = page.get_text("dict")["blocks"]
            
            # 收集不在表格区域内的文本块，并按Y坐标排序
            text_blocks = []
            for block in blocks:
                if "bbox" not in block:
                    continue
                
                block_bbox = block["bbox"]
                block_x0, block_y0, block_x1, block_y1 = block_bbox
                
                # 检查文本块是否与任何表格区域重叠
                is_in_table = False
                for table_bbox in table_bboxes:
                    table_x0, table_y0, table_x1, table_y1 = table_bbox
                    
                    # 检查文本块是否在表格区域内（允许一些容差）
                    tolerance = 5  # 5像素容差
                    if (block_x0 >= table_x0 - tolerance and 
                        block_y0 >= table_y0 - tolerance and
                        block_x1 <= table_x1 + tolerance and
                        block_y1 <= table_y1 + tolerance):
                        is_in_table = True
                        break
                
                # 如果文本块不在表格区域内，收集文本内容和位置
                if not is_in_table:
                    block_text = ""
                    if "lines" in block:
                        for line in block["lines"]:
                            if "spans" in line:
                                for span in line["spans"]:
                                    if "text" in span:
                                        block_text += span["text"]
                        if block_text.strip():
                            text_blocks.append((block_y0, block_text))  # 使用Y坐标用于排序
            
            doc.close()
            
            # 按Y坐标排序
            text_blocks.sort(key=lambda x: x[0])
            
            # 分离表格前和表格后的文本
            # 对于多个表格之间的文本，也归入"表格后"文本，因为会在显示时按顺序插入
            text_before = []
            text_after = []
            
            for y0, text in text_blocks:
                # 如果文本块在第一个表格上方，属于表格前文本
                if y0 < top_table_y0:
                    text_before.append(text)
                # 如果文本块在最后一个表格下方，或者在表格之间，都属于表格后文本
                # （表格之间的文本会在显示时根据表格位置正确插入）
                else:
                    text_after.append(text)
            
            return "\n".join(text_before).strip(), "\n".join(text_after).strip(), text_blocks
            
        except Exception as e:
            self.logger.error(f"提取排除表格区域的文本失败（第{page_num}页）: {e}")
            return "", "", []
    
    def organize_images_by_page(self, ocr_results_by_page: Dict[int, List]) -> Dict[int, List[Dict]]:
        """
        按页组织图片OCR结果，按 y0 坐标排序
        
        Args:
            ocr_results_by_page: 页码到OCR结果列表的映射
                格式: {page_num: [(image_path, ocr_text, y0), ...]}
                其中 y0 是可选的，用于按位置排序
            
        Returns:
            页码到图片信息列表的映射（按 y0 排序）
                格式: {page_num: [{'image': filename, 'text': ocr_text, 'y0': y0}, ...]}
        """
        page_images = {}
        
        if not ocr_results_by_page:
            return page_images
        
        for page_num, ocr_list in ocr_results_by_page.items():
            images = []
            for item in ocr_list:
                img_path = item[0]
                ocr_text = item[1]
                y0 = item[2] if len(item) > 2 else 0
                
                if ocr_text:
                    images.append({
                        'image': os.path.basename(img_path),
                        'text': ocr_text,
                        'y0': y0
                    })
            
            # 按 y0 坐标排序（从上到下）
            images.sort(key=lambda x: x.get('y0', 0))
            
            if images:
                page_images[page_num] = images
        
        self.logger.info(f"图片按页组织完成: {len(page_images)}页有图片")
        return page_images
    
    def identify_cross_page_covered_pages(self, page_tables: Dict[int, List[Dict]]) -> Dict[int, Tuple[int, Dict]]:
        """
        识别被跨页表格覆盖的页面
        
        Args:
            page_tables: 页码到表格列表的映射
            
        Returns:
            被覆盖页码到(起始页, 表格信息)的映射
        """
        cross_page_covered = {}
        
        for page_num, tables in page_tables.items():
            for table in tables:
                if table.get('is_cross_page'):
                    # 解析页码范围
                    page_range = str(table['page'])
                    if '-' in page_range:
                        start_page, end_page = map(int, page_range.split('-'))
                        # 后续页（非起始页）都被覆盖
                        for p in range(start_page + 1, end_page + 1):
                            cross_page_covered[p] = (start_page, table)
        
        if cross_page_covered:
            self.logger.info(f"识别到{len(cross_page_covered)}页被跨页表格覆盖")
        
        return cross_page_covered
    
    def _load_table_content_from_file(self, table: Dict, single_table_results_dir: str) -> Optional[str]:
        """
        从文件中读取表格内容（当recognized_content为空时使用）
        
        Args:
            table: 表格信息字典
            single_table_results_dir: 单张表格识别结果目录
            
        Returns:
            表格HTML内容，如果读取失败返回None
        """
        try:
            table_id = table.get('id')
            is_cross_page = table.get('is_cross_page', False)
            
            if is_cross_page:
                # 跨页表格：读取所有部分的文件并合并
                original_image_paths = table.get('original_image_paths', [])
                original_tables = table.get('original_tables', [])
                
                if not original_image_paths or not original_tables:
                    return None
                
                html_parts = []
                for idx, img_path in enumerate(original_image_paths):
                    if idx < len(original_tables):
                        orig_table = original_tables[idx]
                        page_num = orig_table.get('page', '?')
                        
                        # 构建文件名
                        filename = f"table_{table_id}_part{idx+1}_page_{page_num}.txt"
                        filepath = os.path.join(single_table_results_dir, filename)
                        
                        if os.path.exists(filepath):
                            with open(filepath, 'r', encoding='utf-8') as f:
                                content = f.read()
                                # 提取HTML表格部分（跳过文件头部的元数据）
                                html_match = re.search(r'<table>.*?</table>', content, re.DOTALL)
                                if html_match:
                                    html_parts.append(html_match.group(0))
                
                if html_parts:
                    # 合并HTML部分：提取所有<tr>行，合并到一个<table>中
                    all_rows = []
                    for html_part in html_parts:
                        # 提取所有<tr>行
                        rows = re.findall(r'<tr>.*?</tr>', html_part, re.DOTALL)
                        all_rows.extend(rows)
                    
                    if all_rows:
                        # 组合成完整的HTML表格
                        merged_html = '<table>\n' + '\n'.join(all_rows) + '\n</table>'
                        return merged_html
            else:
                # 单页表格：直接读取文件
                page_num = table.get('page', '?')
                filename = f"table_{table_id}_page_{page_num}.txt"
                filepath = os.path.join(single_table_results_dir, filename)
                
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # 提取HTML表格部分（跳过文件头部的元数据）
                        html_match = re.search(r'<table>.*?</table>', content, re.DOTALL)
                        if html_match:
                            return html_match.group(0)
            
            return None
        except Exception as e:
            self.logger.warning(f"从文件读取表格{table_id}内容失败: {e}")
            return None
    
    def assemble_document(self, 
                         page_texts: Dict[int, str],
                         page_tables: Dict[int, List[Dict]],
                         page_images: Dict[int, List[Dict]] = None,
                         pdf_filename: str = "文档",
                         single_table_results_dir: str = None) -> str:
        """
        组装完整文档
        
        Args:
            page_texts: 页码到文本的映射
            page_tables: 页码到表格列表的映射
            page_images: 页码到图片列表的映射（可选）
            pdf_filename: PDF文件名（用于标题）
            single_table_results_dir: 单张表格识别结果目录（可选，用于读取表格内容）
            
        Returns:
            组装好的完整文档内容
        """
        if page_images is None:
            page_images = {}
        
        # 识别被跨页表格覆盖的页面
        cross_page_covered = self.identify_cross_page_covered_pages(page_tables)
        
        # 获取所有页码
        all_pages = sorted(set(
            list(page_texts.keys()) + 
            list(page_tables.keys()) + 
            list(page_images.keys())
        ))
        
        # 组装文档
        final_lines = []
        
        for page_num in all_pages:
            # 检查该页是否被跨页表格覆盖
            is_cross_page_covered = page_num in cross_page_covered
            
            if is_cross_page_covered:
                # 对于跨页表格的后续页，检查是否有表格外的内容
                # 但如果该页同时也是某个跨页表格的起始页，应该显示该表格
                start_page, table_info = cross_page_covered[page_num]
                
                # 检查该页是否是某个跨页表格的起始页，或者是否有单页表格
                is_start_page = False
                has_single_page_table = False
                if page_num in page_tables:
                    for table in page_tables[page_num]:
                        if table.get('is_cross_page'):
                            page_range = str(table.get('page', ''))
                            if '-' in page_range:
                                table_start_page = int(page_range.split('-')[0])
                                if table_start_page == page_num:
                                    is_start_page = True
                                    break
                        else:
                            # 单页表格，应该显示
                            has_single_page_table = True
                
                # 如果该页是某个跨页表格的起始页，或者有单页表格，显示该表格
                # 否则，不显示表格（避免重复显示）
                has_table = is_start_page or has_single_page_table
                has_image = page_num in page_images
                
                # 收集该页所有表格的bbox（用于提取排除表格区域的文本）
                table_bboxes = []
                original_tables = table_info.get('original_tables', [])
                # 查找该页对应的原始表格（来自覆盖该页的跨页表格）
                for orig_table in original_tables:
                    if orig_table.get('page') == page_num:
                        bbox = orig_table.get('bbox')
                        if bbox:
                            table_bboxes.append(bbox)
                            break
                
                # 如果该页有表格（起始页的跨页表格或单页表格），也需要收集该页所有表格的bbox
                if has_table and page_num in page_tables:
                    for table in page_tables[page_num]:
                        if table.get('is_cross_page'):
                            page_range = str(table.get('page', ''))
                            if '-' in page_range:
                                table_start_page = int(page_range.split('-')[0])
                                if table_start_page == page_num:
                                    bbox = table.get('bbox')
                                    if bbox:
                                        table_bboxes.append(bbox)
                        else:
                            # 单页表格，收集其bbox
                            bbox = table.get('bbox')
                            if bbox:
                                table_bboxes.append(bbox)
                
                # 获取排除表格区域的文本（区分表格前后）
                text_before_table = ""
                text_after_table = ""
                
                if table_bboxes and self.pdf_path:
                    # 使用新方法获取排除表格区域的文本（区分前后）
                    text_before_table, text_after_table, text_blocks = self.extract_text_excluding_tables(page_num, table_bboxes)
                elif page_num in page_texts:
                    # 如果无法排除表格区域，使用粗解析文本
                    text_after_table = page_texts[page_num].strip()
                    text_blocks = []
                
                # 清理文本后再检查是否为空（移除页码、页眉页脚等）
                cleaned_before = self._clean_text(text_before_table) if text_before_table else ""
                cleaned_after = self._clean_text(text_after_table) if text_after_table else ""
                
                # 如果该页没有任何表格外的有效内容（没有文本、没有图片），跳过该页
                if not cleaned_before and not cleaned_after and not has_image:
                    continue  # 跳过该页，不显示
            else:
                # 判断该页是否有表格或图片
                has_table = page_num in page_tables
                has_image = page_num in page_images
                
                # 收集该页所有表格的bbox（用于提取排除表格区域的文本）
                table_bboxes = []
                if has_table:
                    tables = page_tables[page_num]
                    for table in tables:
                        bbox = table.get('bbox')
                        if bbox:
                            table_bboxes.append(bbox)
                
                # 获取排除表格区域的文本（区分表格前后）
                text_before_table = ""
                text_after_table = ""
                
                if table_bboxes and self.pdf_path:
                    # 使用新方法获取排除表格区域的文本（区分前后）
                    text_before_table, text_after_table, text_blocks = self.extract_text_excluding_tables(page_num, table_bboxes)
                elif page_num in page_texts:
                    # 没有表格，但尝试获取文本块位置（用于与图片混合排序）
                    text_before_table = page_texts[page_num].strip()
                    if self.pdf_path and has_image:
                        # 有图片时，获取文本块位置信息以便混合排序
                        text_blocks = self.get_text_blocks_with_positions(page_num)
                    else:
                        text_blocks = []
            
            # 对于非跨页覆盖页面，需要在这里清理文本
            if not is_cross_page_covered:
                cleaned_before = self._clean_text(text_before_table) if text_before_table else ""
                cleaned_after = self._clean_text(text_after_table) if text_after_table else ""
            
            # 显示该页
            final_lines.append(f"第 {page_num} 页")
            final_lines.append("")
            
            # 判断是否需要按位置混合显示（有图片且有文本块位置信息，且没有表格）
            should_mix_content = has_image and text_blocks and len(text_blocks) > 0 and not has_table
            
            # 按照PDF中的实际顺序显示内容：
            # 1. 先显示表格前的文本（如果有）- 但如果需要混合显示则跳过
            if cleaned_before and not should_mix_content:
                final_lines.append(cleaned_before)
                final_lines.append("")
            
            # 2. 然后显示表格HTML（如果有），按y坐标排序，并在表格之间插入文本
            if has_table:
                tables = page_tables[page_num]
                
                # 过滤表格：如果该页被跨页表格覆盖，只显示该页作为起始页的跨页表格，或者显示单页表格
                filtered_tables = []
                for table in tables:
                    if is_cross_page_covered:
                        if table.get('is_cross_page'):
                            page_range = str(table.get('page', ''))
                            if '-' in page_range:
                                table_start_page = int(page_range.split('-')[0])
                                # 只显示该页作为起始页的跨页表格
                                if table_start_page != page_num:
                                    continue  # 跳过不是起始页的跨页表格
                        # 单页表格：如果该页被跨页表格覆盖，仍然显示（因为单页表格是独立的）
                    filtered_tables.append(table)
                
                # 如果该页被跨页表格覆盖，还需要添加该页对应的原始表格（用于排序和显示）
                if is_cross_page_covered:
                    start_page, table_info = cross_page_covered[page_num]
                    original_tables = table_info.get('original_tables', [])
                    # 查找该页对应的原始表格
                    for orig_table in original_tables:
                        if orig_table.get('page') == page_num:
                            # 创建一个表格字典，用于排序和显示
                            orig_table_dict = {
                                'id': table_info.get('id'),
                                'page': f"{start_page}-{page_num}",  # 跨页表格的页码范围
                                'is_cross_page': True,
                                'bbox': orig_table.get('bbox'),  # 使用原始表格的bbox
                                'original_table_on_this_page': orig_table  # 保存原始表格信息
                            }
                            filtered_tables.append(orig_table_dict)
                            break
                
                # 按y坐标排序表格（使用bbox的y0）
                def get_table_y0(table):
                    bbox = table.get('bbox')
                    if bbox:
                        return bbox[1]  # y0
                    return 0
                
                filtered_tables.sort(key=get_table_y0)
                
                # 如果有文本块列表，按y坐标插入文本
                if text_blocks and len(filtered_tables) > 1:
                    # 对于每个表格，找到它之前和之后的文本块
                    for i, table in enumerate(filtered_tables):
                        table_bbox = table.get('bbox')
                        if not table_bbox:
                            # 没有bbox，直接显示表格
                            self._append_table(final_lines, table, page_num, single_table_results_dir)
                            continue
                        
                        table_y0 = table_bbox[1]
                        table_y1 = table_bbox[3]
                        
                        # 找到表格之前的文本块（从上一個表格的底部到当前表格的顶部）
                        prev_table_y1 = 0
                        if i > 0:
                            prev_bbox = filtered_tables[i-1].get('bbox')
                            if prev_bbox:
                                prev_table_y1 = prev_bbox[3]
                        
                        # 收集表格之前的文本块
                        text_before_this_table = []
                        for y0, text in text_blocks:
                            if y0 > prev_table_y1 and y0 < table_y0:
                                text_before_this_table.append(text)
                        
                        # 显示表格之前的文本
                        if text_before_this_table:
                            text_before = "\n".join(text_before_this_table).strip()
                            cleaned_before = self._clean_text(text_before)
                            if cleaned_before:
                                final_lines.append(cleaned_before)
                                final_lines.append("")
                        
                        # 显示表格
                        self._append_table(final_lines, table, page_num, single_table_results_dir)
                        
                        # 如果是最后一个表格，显示它之后的文本
                        if i == len(filtered_tables) - 1:
                            text_after_this_table = []
                            for y0, text in text_blocks:
                                if y0 > table_y1:
                                    text_after_this_table.append(text)
                            
                            if text_after_this_table:
                                text_after = "\n".join(text_after_this_table).strip()
                                cleaned_after = self._clean_text(text_after)
                                if cleaned_after:
                                    final_lines.append(cleaned_after)
                                    final_lines.append("")
                else:
                    # 没有文本块列表或只有一个表格，使用原来的逻辑
                    for table in filtered_tables:
                        self._append_table(final_lines, table, page_num, single_table_results_dir)
                    
                    # 显示表格后的文本（如果有）
                    if cleaned_after:
                        final_lines.append(cleaned_after)
                        final_lines.append("")
            
            # 3. 如果没有表格，显示表格后的文本（如果有）
            elif cleaned_after:
                final_lines.append(cleaned_after)
                final_lines.append("")
            
            # 4. 显示图片OCR（如果有）
            # 图片按 y0 坐标插入到正确位置
            if has_image:
                images = page_images[page_num]
                
                # 检查是否需要混合显示（没有表格时，将文本和图片按位置混合）
                if should_mix_content:
                    # 将图片和文本块混合排序
                    # 文本块格式: (y0, text)
                    # 图片格式: {'image': ..., 'text': ..., 'y0': ...}
                    
                    # 创建混合列表: (y0, type, content)
                    mixed_content = []
                    
                    # 添加文本块
                    for y0, text in text_blocks:
                        if text and text.strip():
                            mixed_content.append((y0, 'text', text))
                    
                    # 添加图片
                    for img_data in images:
                        img_y0 = img_data.get('y0', 0)
                        img_text = img_data.get('text', '')
                        if img_text and img_text.strip():
                            mixed_content.append((img_y0, 'image', img_text))
                    
                    # 按 y0 排序
                    mixed_content.sort(key=lambda x: x[0])
                    
                    # 按顺序显示所有内容（文本和图片混合）
                    for y0, content_type, content in mixed_content:
                        cleaned_content = self._clean_text(content) if content else ""
                        if cleaned_content:
                            final_lines.append(cleaned_content)
                            final_lines.append("")
                elif text_blocks and len(text_blocks) > 0 and has_table:
                    # 有表格时，文本已在表格前后显示，这里只显示图片
                    for img_data in images:
                        img_text = img_data.get('text', '')
                        if img_text and img_text.strip():
                            cleaned_text = self._clean_text(img_text)
                            if cleaned_text:
                                final_lines.append(cleaned_text)
                                final_lines.append("")
                else:
                    # 没有文本块位置信息，直接显示图片（已按 y0 排序）
                    for img_data in images:
                        image_text = img_data.get('text', '')
                        if image_text and image_text.strip():
                            cleaned_text = self._clean_text(image_text)
                            if cleaned_text:
                                final_lines.append(cleaned_text)
                                final_lines.append("")
            
            # 对于无表格页面，如果没有提取到文本，使用粗解析文本
            if not has_table and page_num not in cross_page_covered:
                if not cleaned_before and page_num in page_texts:
                    page_text = self._clean_text(page_texts[page_num].strip())
                    if page_text:
                        final_lines.append(page_text)
                        final_lines.append("")
            
            final_lines.append("")
        
        self.logger.info(f"文档组装完成: 共{len(all_pages)}页")
        return "\n".join(final_lines)
    
    def _append_table(self, final_lines: List[str], table: Dict, page_num: int, single_table_results_dir: str = None):
        """辅助方法：将表格添加到final_lines中"""
        # 检查是否是跨页表格在该页的原始表格部分
        # 如果是，不显示（因为整个跨页表格已经在起始页显示过了）
        if 'original_table_on_this_page' in table:
            return
        
        if table.get('is_cross_page'):
            # 跨页表格：显示表格（第X-Y页）
            page_range = str(table['page'])
            final_lines.append(f"表格（第{page_range}页）")
        else:
            # 单页表格：显示表格（第X页）
            page_num_str = str(table.get('page', page_num))
            final_lines.append(f"表格（第{page_num_str}页）")
        final_lines.append("")
        
        # 显示表格HTML内容
        content = table.get('recognized_content')
        
        # 如果recognized_content为空，尝试从文件中读取
        if not content and single_table_results_dir and os.path.exists(single_table_results_dir):
            content = self._load_table_content_from_file(table, single_table_results_dir)
        
        if content:
            cleaned_content = self.header_footer_cleaner.strip_edge_page_numbers(content)
            final_lines.append(cleaned_content)
        else:
            final_lines.append('(未能识别)')
        final_lines.append("")


