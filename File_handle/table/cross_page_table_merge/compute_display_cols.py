from typing import Any, List
import re


def compute_display_cols(merger: Any, rows: List[str]) -> List[int]:
    """
    计算每行的展示列数（考虑rowspan占位和colspan，仅以<td>计数列数）。
    """
    self = merger
    display_counts: List[int] = []
    active_spans: List[int] = []  # 每列剩余的rowspan占位行数

    def next_free_col(start: int) -> int:
        """找到下一个未被rowspan占位的列位置。"""
        i = start
        while i < len(active_spans) and active_spans[i] > 0:
            i += 1
        return i

    for row_idx, row_html in enumerate(rows):
        occupied_cols = sum(1 for s in active_spans if s > 0)
        cells = re.findall(r'<td([^>]*)>(.*?)</td>', row_html, re.DOTALL | re.IGNORECASE)

        current_row_cols = 0
        col_idx = 0

        for attrs, _ in cells:
            colspan_match = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            rowspan_match = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            colspan_val = int(colspan_match.group(1)) if colspan_match else 1
            rowspan_val = int(rowspan_match.group(1)) if rowspan_match else 1

            col_idx = next_free_col(col_idx)
            start_col = col_idx
            end_col = start_col + colspan_val

            # 每个<td>按colspan计算列数
            current_row_cols += colspan_val

            if len(active_spans) < end_col:
                active_spans.extend([0] * (end_col - len(active_spans)))

            if rowspan_val > 1:
                for c in range(start_col, end_col):
                    active_spans[c] = max(active_spans[c], rowspan_val)

            col_idx = end_col

        total_cols = occupied_cols + current_row_cols
        display_counts.append(total_cols)

        # 递减rowspan占位计数
        for i in range(len(active_spans)):
            if active_spans[i] > 0:
                active_spans[i] -= 1

    return display_counts

