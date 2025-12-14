from typing import Any, List


def absorb_empty_rowspan_cells(merger: Any, rows: List[str]) -> List[str]:
    """
    将跨页后半段中"空内容且带rowspan的单元格"吸收到前一段对应列的锚点单元格里，避免重复空列并累加rowspan。

    规则与流程：
    1) 解析每行<td>，记录rowspan/colspan，逐行进行列布局模拟（考虑上方rowspan占位），得到每个单元格的起始列索引start_col。
    2) 锚点：同列最近的"有内容"或"rowspan>1"的单元格。
    3) 如果某单元格内容为空、rowspan>1、且无colspan扩展，并且对应列已有锚点，则：
       - 将其rowspan累加到锚点的rowspan；
       - 当前单元格标记为删除。
    4) 重建HTML行，更新rowspan/colspan属性，移除被吸收的单元格。
    """
    import re

    self = merger
    if not rows:
        return rows

    parsed_rows: List[List[dict]] = []
    for row_html in rows:
        cells = re.findall(r"<td([^>]*)>(.*?)</td>", row_html, re.DOTALL | re.IGNORECASE)
        parsed = []
        for attrs, content in cells:
            rowspan_match = re.search(r"rowspan\s*=\s*['\"]?(\d+)['\"]?", attrs, re.IGNORECASE)
            colspan_match = re.search(r"colspan\s*=\s*['\"]?(\d+)['\"]?", attrs, re.IGNORECASE)
            parsed.append(
                {
                    "attrs": attrs,
                    "content": content,
                    "rowspan": int(rowspan_match.group(1)) if rowspan_match else 1,
                    "colspan": int(colspan_match.group(1)) if colspan_match else 1,
                    "remove": False,
                    "start_col": None,  # 计算出的起始列索引
                }
            )
        parsed_rows.append(parsed)

    # 列布局模拟：处理rowspan占位，给每个单元格分配start_col
    active_spans: List[int] = []  # 每列剩余的rowspan高度
    anchors = {}  # col_idx -> (row_idx, cell_idx)

    for r_idx, row in enumerate(parsed_rows):
        col_idx = 0

        def next_free_col(start: int) -> int:
            idx = start
            while idx < len(active_spans) and active_spans[idx] > 0:
                idx += 1
            return idx

        for c_idx, cell in enumerate(row):
            # 对于"空内容+rowspan>1+无colspan"的单元格，如果当前列被上方rowspan占用，
            # 不要跳过这一列（否则会错位），直接对齐当前列以便后续吸收。
            is_empty_rowspan = (
                (not cell["content"].strip()) and cell["rowspan"] > 1 and cell["colspan"] == 1
            )
            if is_empty_rowspan and col_idx < len(active_spans) and active_spans[col_idx] > 0:
                cell["start_col"] = col_idx
            else:
                col_idx = next_free_col(col_idx)
                cell["start_col"] = col_idx

            span_w = cell["colspan"]
            span_h = cell["rowspan"]

            # 确保active_spans长度
            need_len = cell["start_col"] + span_w
            if len(active_spans) < need_len:
                active_spans.extend([0] * (need_len - len(active_spans)))

            # 标记rowspan占位；对于待吸收的空rowspan且其列已被占用，不再重复占位
            # span_h 表示总共占用多少行（包括当前行）
            # 设置为span_h，这样在后续span_h-1行中都会被正确处理
            for w in range(span_w):
                target_col = cell["start_col"] + w
                if span_h > 1 and not (is_empty_rowspan and target_col < len(active_spans) and active_spans[target_col] > 0):
                    active_spans[target_col] = max(active_spans[target_col], span_h)
            col_idx = cell["start_col"] + span_w

            content_stripped = cell["content"].strip()
            has_rowspan = cell["rowspan"] > 1
            has_colspan = cell["colspan"] > 1

            # 吸收空rowspan单元格（仅吸收到"已经有rowspan>1"或"本身为空内容的锚点"上，避免把正常单元格拉长）
            if (not content_stripped) and has_rowspan and (not has_colspan) and cell["start_col"] in anchors:
                a_r, a_c = anchors[cell["start_col"]]
                anchor_cell = parsed_rows[a_r][a_c]
                anchor_has_span = anchor_cell["rowspan"] > 1
                anchor_is_empty = not anchor_cell["content"].strip()
                if anchor_has_span or anchor_is_empty:
                    anchor_cell["rowspan"] += cell["rowspan"]
                    cell["remove"] = True
                    continue

            # 更新锚点：优先保留/更新"带rowspan的锚点"；普通有内容单元格仅在该列无锚点时设置
            existing = anchors.get(cell["start_col"])
            if has_rowspan:
                if not existing:
                    anchors[cell["start_col"]] = (r_idx, c_idx)
                else:
                    a_r, a_c = existing
                    anchor_cell = parsed_rows[a_r][a_c]
                    # 用更大的rowspan作为锚点
                    if cell["rowspan"] > anchor_cell["rowspan"]:
                        anchors[cell["start_col"]] = (r_idx, c_idx)
            elif content_stripped:
                if not existing:
                    anchors[cell["start_col"]] = (r_idx, c_idx)

        # 行结束，递减占位高度
        for i in range(len(active_spans)):
            if active_spans[i] > 0:
                active_spans[i] -= 1

    # 重建HTML
    new_rows = []
    for row in parsed_rows:
        parts = []
        for cell in row:
            if cell["remove"]:
                continue
            attrs = cell["attrs"]
            # 更新rowspan
            if cell["rowspan"] > 1:
                if re.search(r'rowspan\s*=\s*["\']?\d+["\']?', attrs, re.IGNORECASE):
                    attrs = re.sub(r'rowspan\s*=\s*["\']?\d+["\']?', f'rowspan="{cell["rowspan"]}"', attrs, flags=re.IGNORECASE)
                else:
                    attrs = (attrs + ' rowspan="{0}"').format(cell["rowspan"])
            else:
                attrs = re.sub(r'rowspan\s*=\s*["\']?\d+["\']?', "", attrs, flags=re.IGNORECASE)
            # 更新colspan
            if cell["colspan"] > 1:
                if re.search(r'colspan\s*=\s*["\']?\d+["\']?', attrs, re.IGNORECASE):
                    attrs = re.sub(r'colspan\s*=\s*["\']?\d+["\']?', f'colspan="{cell["colspan"]}"', attrs, flags=re.IGNORECASE)
                else:
                    attrs = (attrs + ' colspan="{0}"').format(cell["colspan"])
            else:
                attrs = re.sub(r'colspan\s*=\s*["\']?\d+["\']?', "", attrs, flags=re.IGNORECASE)

            attrs = attrs.strip()
            if attrs and not attrs.startswith(" "):
                attrs = " " + attrs
            attrs_clean = attrs.strip()
            prefix = f" {attrs_clean}" if attrs_clean else ""
            parts.append(f'<td{prefix}>{cell["content"]}</td>' if attrs or attrs_clean else f'<td>{cell["content"]}</td>')
        new_rows.append("<tr>" + "".join(parts) + "</tr>")

    return new_rows

