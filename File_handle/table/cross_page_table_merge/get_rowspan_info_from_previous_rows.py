from typing import Any, Dict, List
import re


def get_rowspan_info_from_previous_rows(merger: Any, rows: List[str], target_row_idx: int) -> List[Dict]:
    """
    从前面几行获取rowspan信息，重建目标行的完整列结构（包括rowspan占位）。
    """
    self = merger
    if target_row_idx < 0 or target_row_idx >= len(rows):
        return []

    active_rowspans: List[Dict] = []
    target_row = rows[target_row_idx]
    target_cells = re.findall(r'<td([^>]*)>(.*?)</td>', target_row, re.DOTALL | re.IGNORECASE)

    for row_idx in range(target_row_idx):
        row = rows[row_idx]
        cells = re.findall(r'<td([^>]*)>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)

        col_idx = 0
        for attrs, content in cells:
            while col_idx < len(active_rowspans) and active_rowspans[col_idx] is not None:
                col_idx += 1

            colspan_match = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            rowspan_match = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            colspan_val = int(colspan_match.group(1)) if colspan_match else 1
            rowspan_val = int(rowspan_match.group(1)) if rowspan_match else 1

            need_len = col_idx + colspan_val
            if len(active_rowspans) < need_len:
                active_rowspans.extend([None] * (need_len - len(active_rowspans)))

            if rowspan_val > 1:
                remaining_rows = rowspan_val - 1
                for c in range(colspan_val):
                    target_col = col_idx + c
                    if active_rowspans[target_col] is None or active_rowspans[target_col]['remaining'] < remaining_rows:
                        active_rowspans[target_col] = {
                            'remaining': remaining_rows,
                            'attrs': attrs,
                            'content': content,
                            'start_row': row_idx,
                            'original_rowspan': rowspan_val
                        }

            col_idx += colspan_val

        is_last_row_before_target = (row_idx == target_row_idx - 1)
        for i in range(len(active_rowspans)):
            if active_rowspans[i] is not None:
                active_rowspans[i]['remaining'] -= 1
                if active_rowspans[i]['remaining'] < 0:
                    active_rowspans[i] = None
                elif not is_last_row_before_target and active_rowspans[i]['remaining'] <= 0:
                    active_rowspans[i] = None


    all_rows_up_to_target = rows[:target_row_idx + 1]
    display_cols = self.compute_display_cols(all_rows_up_to_target)
    expected_cols = display_cols[-1] if display_cols else 4

    target_total_cols = 0
    for attrs, _ in target_cells:
        colspan_match = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
        colspan_val = int(colspan_match.group(1)) if colspan_match else 1
        target_total_cols += colspan_val

    total_cols = max(expected_cols, len(active_rowspans), target_total_cols)
    if len(active_rowspans) < total_cols:
        active_rowspans.extend([None] * (total_cols - len(active_rowspans)))

    full_structure: List[Dict] = []
    target_cell_idx = 0
    col_idx = 0
    while col_idx < total_cols:
        has_rowspan = (
            col_idx < len(active_rowspans)
            and active_rowspans[col_idx] is not None
            and active_rowspans[col_idx].get('remaining', -1) >= 0
        )
        has_target_cell = target_cell_idx < len(target_cells)

        if has_rowspan:
            remaining = active_rowspans[col_idx]['remaining']
            full_structure.append({
                'attrs': active_rowspans[col_idx]['attrs'],
                'content': active_rowspans[col_idx]['content'],
                'is_rowspan_placeholder': True,
                'remaining_rows': remaining,
                'original_rowspan': active_rowspans[col_idx].get('original_rowspan', 1),
                'start_row': active_rowspans[col_idx].get('start_row', -1)
            })
            col_idx += 1
        else:
            if has_target_cell:
                attrs, content = target_cells[target_cell_idx]
                colspan_match = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
                colspan_val = int(colspan_match.group(1)) if colspan_match else 1

                for c in range(colspan_val):
                    full_structure.append({
                        'attrs': attrs if c == 0 else '',
                        'content': content if c == 0 else '',
                        'is_rowspan_placeholder': False
                    })
                    col_idx += 1
                target_cell_idx += 1
            else:
                full_structure.append({
                    'attrs': '',
                    'content': '',
                    'is_rowspan_placeholder': False
                })
                col_idx += 1

    return full_structure

