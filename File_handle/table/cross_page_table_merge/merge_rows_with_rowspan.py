from typing import Any, Dict, List, Tuple
import re


def merge_rows_with_rowspan(merger: Any, row1_full: List[Dict], row2: str, prev_rows: List[str] = None) -> Tuple[bool, str, List[Dict] | None]:
    """
    合并两行，考虑rowspan占位，返回(是否合并, 合并后的行HTML, 需要更新的起始行信息)。
    """
    self = merger

    def fmt_td(attrs: str, content: str) -> str:
        attrs_clean = attrs.strip()
        prefix = f" {attrs_clean}" if attrs_clean else ""
        return f"<td{prefix}>{content}</td>"

    cells2 = re.findall(r'<td([^>]*)>(.*?)</td>', row2, re.DOTALL | re.IGNORECASE)
    row2_full: List[Dict] = []
    row2_cell_idx = 0
    row2_col_pos = 0  # 当前在row2中的列位置

    for i in range(len(row1_full)):
        cell1 = row1_full[i]
        is_placeholder1 = cell1.get('is_rowspan_placeholder', False)

        # 找到row2中对应当前列位置的td
        # 需要跳过已经被colspan占用的列
        while row2_cell_idx < len(cells2):
            attrs2, content2 = cells2[row2_cell_idx]
            colspan_match2 = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs2, re.IGNORECASE)
            colspan_val2 = int(colspan_match2.group(1)) if colspan_match2 else 1

            # 检查这个td是否覆盖当前列位置
            if row2_col_pos <= i < row2_col_pos + colspan_val2:
                # 这个td覆盖当前列位置
                # 只有第一列保留colspan属性，其他列应该是空的
                if i == row2_col_pos:
                    # 第一列，保留完整的attrs和content
                    row2_full.append({
                        'attrs': attrs2,
                        'content': content2,
                        'is_rowspan_placeholder': False
                    })
                else:
                    # 其他列，attrs和content都应该是空的（因为被colspan占位）
                    row2_full.append({
                        'attrs': '',
                        'content': '',
                        'is_rowspan_placeholder': False
                    })
                # 如果这是这个td的最后一列，移动到下一个td
                if i == row2_col_pos + colspan_val2 - 1:
                    row2_col_pos += colspan_val2
                    row2_cell_idx += 1
                break
            else:
                # 这个td不覆盖当前列位置，移动到下一个td
                row2_col_pos += colspan_val2
                row2_cell_idx += 1
        
        # 如果没有找到对应的td，添加空单元格
        if len(row2_full) <= i:
            row2_full.append({
                'attrs': '',
                'content': '',
                'is_rowspan_placeholder': False
            })

    # 如果row2还有剩余的td，添加到row2_full
    while row2_cell_idx < len(cells2):
        attrs2, content2 = cells2[row2_cell_idx]
        colspan_match2 = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs2, re.IGNORECASE)
        colspan_val2 = int(colspan_match2.group(1)) if colspan_match2 else 1
        for _ in range(colspan_val2):
            row2_full.append({
                'attrs': attrs2,
                'content': content2,
                'is_rowspan_placeholder': False
            })
        row2_cell_idx += 1

    if len(row1_full) != len(row2_full):
        return False, None, None

    merged_cells = []
    skip_rowspan_columns = []
    for i in range(len(row1_full)):
        cell1 = row1_full[i]
        cell2 = row2_full[i] if i < len(row2_full) else {'attrs': '', 'content': '', 'is_rowspan_placeholder': False}

        is_placeholder1 = cell1.get('is_rowspan_placeholder', False)
        rowspan_match1 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', cell1['attrs'], re.IGNORECASE)
        rowspan_match2 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', cell2['attrs'], re.IGNORECASE)
        has_rowspan2 = rowspan_match2 is not None

        if is_placeholder1 and has_rowspan2:
            rowspan1 = cell1.get('original_rowspan', int(rowspan_match1.group(1)) if rowspan_match1 else 1)
            rowspan2 = int(rowspan_match2.group(1))
            merged_rowspan = rowspan1 + rowspan2 - 1
            # 如果cell2有内容，应该合并内容到cell1的起始行中
            # 但是，在合并后的行中，这一列应该被跳过（因为rowspan会被累加到起始行）
            # 内容会通过update_info传递，让调用者更新起始行
            skip_rowspan_columns.append(i)
            # 注意：如果cell2有内容，需要在update_info中记录，以便更新起始行的内容
            # 但是，由于rowspan占位列通常不应该有内容，这里先跳过
        elif i in skip_rowspan_columns:
            continue
        elif is_placeholder1:
            merged_cells.append(fmt_td(cell1['attrs'], cell1['content']))
        elif has_rowspan2:
            # 如果cell2有rowspan，需要合并rowspan
            # 如果cell1有内容，应该保留内容，但需要处理rowspan
            if cell1['content'].strip():
                # cell1有内容，cell2有rowspan，应该合并内容并保留rowspan属性
                # 但是，如果cell2是空的，说明这是rowspan占位，应该跳过
                if not cell2['content'].strip():
                    # cell2是空的rowspan占位，应该跳过（rowspan会被累加到前面的单元格）
                    skip_rowspan_columns.append(i)
                    continue
                else:
                    # cell2有内容且有rowspan，应该合并内容，但保留rowspan属性
                    content1 = cell1['content'].strip()
                    content2 = cell2['content'].strip()
                    if content1 and content2:
                        merged_content = content1 + '<br/>' + content2
                    elif content1:
                        merged_content = content1
                    else:
                        merged_content = content2
                    merged_cells.append(fmt_td(cell2['attrs'], merged_content))
            else:
                # cell1没有内容，cell2有rowspan，应该跳过（rowspan会被累加到前面的单元格）
                skip_rowspan_columns.append(i)
                continue
        else:
            content1 = cell1['content'].strip()
            content2 = cell2['content'].strip()
            
            # 合并时需要去除后页首行的该列td标签，不管colspan是多少，然后有值就合并到前面
            # 如果cell2有值，合并到cell1；如果cell2没有值，只保留cell1
            
            # 如果cell2的attrs有colspan但content为空，说明这是colspan占位，应该跳过（不添加td）
            colspan_match2 = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', cell2['attrs'], re.IGNORECASE)
            has_colspan2 = colspan_match2 is not None
            colspan_val2 = int(colspan_match2.group(1)) if colspan_match2 else 1
            
            # 如果cell2有colspan但content为空，这是colspan占位，跳过（不添加td）
            if has_colspan2 and not content2 and colspan_val2 > 1:
                continue
            
            # 如果cell2没有值，且cell1也没有值，跳过（不添加td）
            if not content1 and not content2:
                continue
            
            # 合并内容：如果cell2有值，合并到cell1
            if content1 and content2:
                merged_content = content1 + '<br/>' + content2
            elif content1:
                merged_content = content1
            elif content2:
                merged_content = content2
            else:
                merged_content = ''

            # 只使用cell1的attrs（去除后页首行的td标签，只保留前一页的td标签）
            final_attrs = cell1['attrs'].strip()
            
            merged_cells.append(fmt_td(final_attrs, merged_content))

    merged_row = '<tr>' + ''.join(merged_cells) + '</tr>'

    update_info_list = []
    for i in range(len(row1_full)):
        if i in skip_rowspan_columns:
            cell1 = row1_full[i]
            cell2 = row2_full[i] if i < len(row2_full) else {'attrs': '', 'content': '', 'is_rowspan_placeholder': False}
            rowspan_match2 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', cell2['attrs'], re.IGNORECASE)
            if rowspan_match2:
                rowspan1 = cell1.get('original_rowspan', 1)
                rowspan2 = int(rowspan_match2.group(1))
                merged_rowspan = rowspan1 + rowspan2 - 1
                start_row = cell1.get('start_row', -1)
                if start_row >= 0:
                    # 如果cell2有内容，需要合并到起始行
                    content2 = cell2.get('content', '').strip()
                    update_info_list.append({
                        'start_row': start_row,
                        'col_idx': i,
                        'merged_rowspan': merged_rowspan,
                        'original_rowspan': rowspan1,
                        'content_to_merge': content2 if content2 else None  # 记录需要合并的内容
                    })

    return True, merged_row, update_info_list if update_info_list else None
