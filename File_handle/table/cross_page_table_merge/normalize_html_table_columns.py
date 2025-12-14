from typing import Any, List


def normalize_html_table_columns(merger: Any, html_rows: List[str], expected_cols: int) -> List[str]:
    """
    标准化HTML表格行，去除rowspan占位位置的单元格

    策略：
    1. 跟踪每列的rowspan状态
    2. 如果某行有rowspan占位，去除占位位置的单元格（这些单元格在原始HTML中可能不存在）
    3. 不添加任何新的空单元格，只去除rowspan占位位置的单元格
    4. 保留原始存在的单元格

    Args:
        merger: CrossPageTableMerger 实例
        html_rows: HTML行列表
        expected_cols: 期望的列数（此参数保留以保持接口兼容性，但不使用）

    Returns:
        标准化后的HTML行列表（只去除rowspan占位，不添加任何单元格）
    """
    import re

    if not html_rows:
        return html_rows

    normalized_rows = []

    # 跟踪每列的rowspan状态（用于识别rowspan占位位置的单元格）
    active_rowspans = []  # 每列剩余的rowspan高度

    for i, row in enumerate(html_rows):
        # 提取所有<td>标签（包括属性和内容）
        cell_matches = re.findall(r"<td([^>]*)>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)

        if not cell_matches:
            # 没有单元格，保留原样
            normalized_rows.append(row)
            # 递减rowspan
            for j in range(len(active_rowspans)):
                if active_rowspans[j] > 0:
                    active_rowspans[j] -= 1
            continue

        # 收集非rowspan占位位置的单元格
        cells_to_keep = []  # 保存需要保留的单元格（属性，内容）

        # 计算每列的rowspan占位，并过滤掉rowspan占位位置的单元格
        col_idx = 0
        for attrs, content in cell_matches:
            # 检查当前列是否被rowspan占用
            if col_idx < len(active_rowspans) and active_rowspans[col_idx] > 0:
                # 当前列被rowspan占用，跳过这个单元格（不保留）
                col_idx += 1
                continue

            # 检查是否有colspan和rowspan属性
            colspan_match = re.search(r"colspan\s*=\s*['\"]?(\d+)['\"]?", attrs, re.IGNORECASE)
            rowspan_match = re.search(r"rowspan\s*=\s*['\"]?(\d+)['\"]?", attrs, re.IGNORECASE)

            # 更新rowspan占位
            if rowspan_match:
                rowspan_value = int(rowspan_match.group(1))
                colspan_value = int(colspan_match.group(1)) if colspan_match else 1
                # 确保active_rowspans长度足够
                need_len = col_idx + colspan_value
                if len(active_rowspans) < need_len:
                    active_rowspans.extend([0] * (need_len - len(active_rowspans)))
                # 标记rowspan占位（从下一行开始）
                # rowspan_value 表示总共占用多少行（包括当前行）
                # 设置为rowspan_value，这样在后续rowspan_value-1行中都会被正确跳过
                for w in range(colspan_value):
                    target_col = col_idx + w
                    active_rowspans[target_col] = max(active_rowspans[target_col], rowspan_value)

            # 保留这个单元格
            cells_to_keep.append((attrs, content))
            col_idx += int(colspan_match.group(1)) if colspan_match else 1

        # 行结束，递减rowspan
        for j in range(len(active_rowspans)):
            if active_rowspans[j] > 0:
                active_rowspans[j] -= 1

        # 重建行，只包含非rowspan占位位置的单元格（不添加任何新单元格）
        if cells_to_keep:
            def _fmt_td(a, c):
                a_clean = a.strip()
                prefix = f" {a_clean}" if a_clean else ""
                return f"<td{prefix}>{c}</td>"
            cells_html_parts = []
            for attrs, content in cells_to_keep:
                cells_html_parts.append(_fmt_td(attrs, content))
            normalized_row = f"<tr>{''.join(cells_html_parts)}</tr>"
            normalized_rows.append(normalized_row)
        else:
            # 所有单元格都被rowspan占用，保留原样（可能是空行）
            normalized_rows.append(row)

    return normalized_rows

