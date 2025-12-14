# -*- coding: utf-8 -*-
"""
页眉页脚清理工具

集中管理页眉页脚的判定与清理逻辑，便于在各解析模块复用。
"""

from typing import List, Tuple, Optional, Dict, Set
import logging
import re


class HeaderFooterCleaner:
    """提供页眉页脚判定和文本清理能力。"""

    def __init__(self,
                 header_ratio: float = 0.15,
                 footer_ratio: float = 0.15):
        """
        Args:
            header_ratio: 页眉所占页面高度比例（0-1）
            footer_ratio: 页脚所占页面高度比例（0-1）
        """
        self.logger = logging.getLogger(__name__)
        self.header_ratio = header_ratio
        self.footer_ratio = footer_ratio

    def compute_margins(self, page_height: float) -> Tuple[float, float]:
        """根据页面高度计算页眉、页脚边界位置。"""
        header_margin = page_height * self.header_ratio
        footer_margin = page_height * (1 - self.footer_ratio)
        return header_margin, footer_margin

    def is_in_header_footer(self, bbox: Tuple[float, float, float, float], page_height: float) -> bool:
        """判断给定bbox是否落在页眉或页脚区域内。"""
        _, y0, _, y1 = bbox
        header_margin, footer_margin = self.compute_margins(page_height)
        return y0 < header_margin or y1 > footer_margin

    def extract_region_lines(
        self,
        page,
        top_ratio: Optional[float] = None,
        bottom_ratio: Optional[float] = None
    ) -> Dict[str, List[str]]:
        """
        提取页面顶部/底部区域的文本行，按行维持原样（不跨行拼接）。
        """
        page_rect = page.rect
        page_height = page_rect.height
        header_r = top_ratio if top_ratio is not None else self.header_ratio
        footer_r = bottom_ratio if bottom_ratio is not None else self.footer_ratio
        header_margin = page_height * header_r
        footer_margin = page_height * (1 - footer_r)

        regions = {"header": [], "footer": []}
        blocks = page.get_text("dict").get("blocks", [])

        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                # 使用行内第一个span的位置判断行所处区域，保持逐行判定
                spans = line.get("spans", [])
                if not spans:
                    continue
                first_span = spans[0]
                if "bbox" not in first_span:
                    continue
                _, y0, _, y1 = first_span["bbox"]

                line_text = "".join(span.get("text", "") for span in spans).strip()
                if not line_text:
                    continue

                if y0 < header_margin:
                    regions["header"].append(line_text)
                elif y1 > footer_margin:
                    regions["footer"].append(line_text)

        return regions

    def detect_common_texts(
        self,
        doc,
        repeat_threshold: int = 2,
        top_ratio: Optional[float] = None,
        bottom_ratio: Optional[float] = None
    ) -> Tuple[Set[str], Set[str]]:
        """
        在多个页面顶部/底部区域寻找重复文本，用于判定页眉/页脚。
        仅当同一文本行在至少 repeat_threshold 页中出现时才视为公共内容。
        """
        header_counts: Dict[str, int] = {}
        footer_counts: Dict[str, int] = {}
        total_pages = len(doc)
        header_r = top_ratio if top_ratio is not None else self.header_ratio
        footer_r = bottom_ratio if bottom_ratio is not None else self.footer_ratio

        for page_index in range(total_pages):
            page = doc.load_page(page_index)
            regions = self.extract_region_lines(page, header_r, footer_r)
            # 为避免同一页重复行被多次计数，仅按“每页是否出现”计一次
            unique_header_lines = set(regions["header"])
            unique_footer_lines = set(regions["footer"])

            for text in unique_header_lines:
                header_counts[text] = header_counts.get(text, 0) + 1
            for text in unique_footer_lines:
                footer_counts[text] = footer_counts.get(text, 0) + 1

        common_headers = {t for t, c in header_counts.items() if c >= repeat_threshold}
        common_footers = {t for t, c in footer_counts.items() if c >= repeat_threshold}

        return common_headers, common_footers

    def remove_by_position(
        self,
        page,
        common_headers: Optional[Set[str]] = None,
        common_footers: Optional[Set[str]] = None,
        remove_page_numbers: bool = True,
        top_ratio: Optional[float] = None,
        bottom_ratio: Optional[float] = None
    ) -> str:
        """
        基于位置和字体大小移除页眉页脚。
        """
        try:
            page_rect = page.rect
            page_height = page_rect.height
            blocks = page.get_text("dict")["blocks"]
            header_r = top_ratio if top_ratio is not None else self.header_ratio
            footer_r = bottom_ratio if bottom_ratio is not None else self.footer_ratio
            header_margin = page_height * header_r
            footer_margin = page_height * (1 - footer_r)

            content_lines: List[str] = []

            for block in blocks:
                if block.get("type") != 0:  # 只处理文本块
                    continue
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    if not spans:
                        continue
                    first_span = spans[0]
                    if "bbox" not in first_span:
                        continue
                    _, y0, _, y1 = first_span["bbox"]

                    line_text = "".join(span.get("text", "") for span in spans).strip()
                    if not line_text:
                        continue

                    in_header = y0 < header_margin
                    in_footer = y1 > footer_margin

                    # 页眉：移除公共行；同时移除页码样式行
                    if in_header:
                        if common_headers and line_text in common_headers:
                            continue
                        if remove_page_numbers and re.fullmatch(r"^\s*(?:第\s*\d+\s*页|\d+)\s*$", line_text):
                            continue

                    # 页脚：移除公共行以及页码格式（递增页码）
                    if in_footer:
                        if common_footers and line_text in common_footers:
                            continue
                        if remove_page_numbers and re.fullmatch(r"^\s*(?:第\s*\d+\s*页|\d+)\s*$", line_text):
                            continue

                    content_lines.append(line_text)

            return "\n".join(content_lines)
        except Exception as e:
            self.logger.warning(f"基于位置移除页眉页脚失败，回退原文: {e}")
            return page.get_text()

    @staticmethod
    def strip_edge_page_numbers(text: str) -> str:
        """
        移除文本首尾的页码行（纯数字或“第X页”），避免 OCR 表格中夹带的页码。
        仅去除首尾，降低误删表格数字的风险。
        """
        if not text:
            return text

        lines = text.splitlines()
        page_num_pattern = re.compile(r"^\s*(?:第\s*\d+\s*页|\d+)\s*$")

        while lines and page_num_pattern.fullmatch(lines[0]):
            lines.pop(0)
        while lines and page_num_pattern.fullmatch(lines[-1]):
            lines.pop()

        return "\n".join(lines)

    def remove_simple(self, text: str,
                      header_lines: int = 2,
                      max_page_number_length: int = 4) -> str:
        """
        简单方法移除页眉页脚（按行数规则）。
        """
        if not text:
            return text

        lines = text.split('\n')
        if len(lines) <= header_lines + 1:
            return text

        start_idx = header_lines

        # 检查页码行
        if start_idx < len(lines):
            first_line = lines[start_idx].strip()
            if first_line.isdigit() and len(first_line) <= max_page_number_length:
                start_idx += 1

        end_idx = len(lines)
        for i in range(len(lines) - 1, start_idx - 1, -1):
            if lines[i].strip():
                end_idx = i + 1
                break

        return '\n'.join(lines[start_idx:end_idx]).strip()

    def filter_blocks_excluding_header_footer(
        self,
        blocks: List[dict],
        page_height: float,
        tolerance: float = 0
    ) -> List[Tuple[float, str]]:
        """
        过滤掉页眉页脚区域的文本块，返回按y坐标收集的文本。
        """
        text_blocks: List[Tuple[float, str]] = []
        header_margin, footer_margin = self.compute_margins(page_height)

        for block in blocks:
            bbox = block.get("bbox")
            if not bbox:
                continue
            x0, y0, x1, y1 = bbox
            if y0 < header_margin - tolerance or y1 > footer_margin + tolerance:
                continue

            block_text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    block_text += span.get("text", "")
            if block_text.strip():
                text_blocks.append((y0, block_text.strip()))

        return text_blocks

