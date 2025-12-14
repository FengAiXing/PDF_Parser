from typing import Any, Dict, List, Tuple
import re


def merge_cross_page_rows(merger: Any, all_html_parts: List[str]) -> List[str]:
    """
    跨页表格合并逻辑：
    - 将所有页面的行拼接，并对前一页尾行和后一页首行进行智能合并
    - 考虑rowspan占位和colspan匹配
    """
    self = merger

    # 提取每页的行
    all_page_rows: List[List[str]] = []
    for i, html in enumerate(all_html_parts):
        if html:
            rows = re.findall(r'<tr>.*?</tr>', html, re.DOTALL)
            if rows:
                all_page_rows.append(rows)
        else:
            all_page_rows.append([])

    if not all_page_rows or all(len(rows) == 0 for rows in all_page_rows):
        return []

    # 合并结果
    merged_rows: List[str] = []

    for page_idx, page_rows in enumerate(all_page_rows):
        if not page_rows:
            continue

        if page_idx == 0:
            # 第一页，直接添加所有行
            merged_rows.extend(page_rows)
        else:
            # 非第一页，需要判断是否合并前一页尾行和当前页首行
            if merged_rows and page_rows:
                last_row = merged_rows[-1]
                first_row = page_rows[0]
                
                # 尝试合并
                should_merge, merged_row, remaining_first_row = try_merge_tail_and_head(
                    self, merged_rows, first_row
                )
                
                if should_merge:
                    # 替换尾行为合并后的行
                    merged_rows[-1] = merged_row
                    
                    # 如果首行有剩余部分未合并，添加为新行
                    if remaining_first_row:
                        merged_rows.append(remaining_first_row)
                    
                    # 添加当前页剩余的行（跳过首行）
                    merged_rows.extend(page_rows[1:])
                else:
                    # 不合并，直接添加所有行
                    merged_rows.extend(page_rows)
            else:
                merged_rows.extend(page_rows)

    return merged_rows


def try_merge_tail_and_head(
    merger: Any, 
    all_rows_before: List[str], 
    first_row: str
) -> Tuple[bool, str, str]:
    """
    尝试合并前一页尾行和后一页首行
    
    Args:
        merger: CrossPageTableMerger实例
        all_rows_before: 到目前为止所有的行（包括尾行）
        first_row: 后一页的首行
    
    Returns:
        (是否合并, 合并后的尾行, 首行剩余部分)
    """
    self = merger
    
    if not all_rows_before:
        return False, "", first_row
    
    last_row = all_rows_before[-1]
    last_row_idx = len(all_rows_before) - 1
    
    # ============================================
    # 步骤1: 计算尾行的完整列结构（考虑rowspan占位）
    # ============================================
    tail_full_structure = get_tail_row_full_structure(self, all_rows_before)
    tail_col_count = len(tail_full_structure)
    
    # ============================================
    # 步骤2: 计算首行的列结构
    # ============================================
    head_cells = re.findall(r'<td([^>]*)>(.*?)</td>', first_row, re.DOTALL | re.IGNORECASE)
    head_structure = []
    for attrs, content in head_cells:
        colspan_match = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
        rowspan_match = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
        colspan_val = int(colspan_match.group(1)) if colspan_match else 1
        rowspan_val = int(rowspan_match.group(1)) if rowspan_match else 1
        
        head_structure.append({
            'attrs': attrs,
            'content': content,
            'colspan': colspan_val,
            'rowspan': rowspan_val,
            'content_stripped': content.strip()
        })
    
    head_col_count = sum(cell['colspan'] for cell in head_structure)
    
    # ============================================
    # 步骤3: 列匹配 - 按顺序对比尾行和首行的colspan
    # ============================================
    # matched_cols记录匹配的单元格对: [(tail_struct_idx, head_cell_idx), ...]
    # tail_struct_idx是tail_full_structure的索引
    # head_cell_idx是head_structure的索引
    matched_cols = []
    tail_struct_idx = 0
    head_cell_idx = 0
    
    while tail_struct_idx < len(tail_full_structure) and head_cell_idx < len(head_structure):
        tail_cell = tail_full_structure[tail_struct_idx]
        head_cell = head_structure[head_cell_idx]
        
        # 获取colspan
        tail_colspan = tail_cell.get('colspan', 1)
        head_colspan = head_cell['colspan']
        
        if tail_colspan == head_colspan:
            # colspan匹配
            matched_cols.append((tail_struct_idx, head_cell_idx))
            tail_struct_idx += 1  # 移动到下一个尾行单元格
            head_cell_idx += 1    # 移动到下一个首行单元格
        else:
            # colspan不匹配，终止匹配
            break
    
    if not matched_cols:
        # 【特殊处理】尾行和首行都只有1个td时，即使colspan不同也应该合并
        # 检查：尾行只有1个实际td（非rowspan占位），首行只有1个td
        tail_actual_cells = [c for c in tail_full_structure if not c.get('is_rowspan_placeholder', False)]
        if len(tail_actual_cells) == 1 and len(head_structure) == 1:
            tail_cell = tail_actual_cells[0]
            head_cell = head_structure[0]
            
            tail_content = tail_cell.get('content', '').strip()
            head_content = head_cell['content_stripped']
            
            # 如果首行有内容，合并到尾行
            if head_content:
                # 合并内容
                if tail_content and head_content:
                    merged_content = tail_content + '<br/>' + head_content
                elif tail_content:
                    merged_content = tail_content
                else:
                    merged_content = head_content
                
                # 保留尾行的attrs（包括colspan）
                attrs = tail_cell.get('attrs', '')
                merged_tail_row = f'<tr>{format_td(attrs, merged_content)}</tr>'
                
                return True, merged_tail_row, ''
        
        return False, last_row, first_row
    
    # ============================================
    # 步骤4: 判断哪些列需要合并
    # ============================================
    
    # 检查首行是否每一列都有值，如果是则不合并（视为新的完整行）
    all_head_cells_have_value = all(cell['content_stripped'] for cell in head_structure)
    if all_head_cells_have_value:
        return False, last_row, first_row
    
    # 从前往后检查首行的值
    first_non_empty_match_idx = None  # 首行第一个非空值的匹配索引
    merge_all_matched = True  # 是否合并所有匹配的列
    
    for match_idx, (tail_struct_idx, head_cell_idx) in enumerate(matched_cols):
        head_cell = head_structure[head_cell_idx]
        
        if head_cell['content_stripped']:
            # 首行这一列有值
            first_non_empty_match_idx = match_idx
            
            # 检查从这一列开始，是否有任何列的值与尾行对应列的值相同
            has_same_value = False
            for check_idx in range(match_idx, len(matched_cols)):
                check_tail_struct_idx, check_head_cell_idx = matched_cols[check_idx]
                check_head_cell = head_structure[check_head_cell_idx]
                check_tail_cell = tail_full_structure[check_tail_struct_idx]
                
                head_val = check_head_cell['content_stripped']
                tail_val = check_tail_cell.get('content', '').strip()
                
                if head_val and tail_val and head_val == tail_val:
                    has_same_value = True
                    break
            
            if has_same_value:
                # 有相同值，从第一次出现值的这一列开始不合并
                merge_all_matched = False
            else:
                # 没有相同值，需要合并从第一次出现值的这一列及剩余列
                merge_all_matched = True
            break
    
    # 确定需要合并的列范围
    if first_non_empty_match_idx is None:
        # 首行所有匹配列都是空值，全部合并
        merge_until_match_idx = len(matched_cols)
    elif merge_all_matched:
        # 合并所有匹配列（包括有值的列）
        merge_until_match_idx = len(matched_cols)
    else:
        # 只合并空值列，不合并有值的列
        merge_until_match_idx = first_non_empty_match_idx
    
    if merge_until_match_idx == 0:
        return False, last_row, first_row
    
    # ============================================
    # 步骤5: 执行合并
    # ============================================
    # 判断是否整行合并：所有首行单元格都被合并了
    merged_head_cell_indices = set(head_idx for _, head_idx in matched_cols[:merge_until_match_idx])
    entire_row_merged = len(merged_head_cell_indices) == len(head_structure)
    
    # 需要更新rowspan的原始单元格
    rowspan_updates: List[Dict] = []  # [{row_idx, cell_idx, new_rowspan}, ...]
    
    # 构建合并后的尾行
    merged_tail_cells = []
    
    # 遍历尾行的所有单元格
    processed_tail_structs = set()
    
    for struct_idx, tail_cell in enumerate(tail_full_structure):
        if struct_idx in processed_tail_structs:
            continue
        
        # 查找这个单元格是否在匹配列表中
        match_info = None
        for match_idx, (matched_tail_struct_idx, matched_head_cell_idx) in enumerate(matched_cols):
            if matched_tail_struct_idx == struct_idx:
                match_info = (match_idx, matched_head_cell_idx)
                break
        
        if match_info and match_info[0] < merge_until_match_idx:
            # 这个单元格需要合并
            match_idx, matched_head_idx = match_info
            head_cell = head_structure[matched_head_idx]
            
            tail_content = tail_cell.get('content', '').strip()
            head_content = head_cell['content_stripped']
            
            # 合并值
            if tail_content and head_content:
                merged_content = tail_content + '<br/>' + head_content
            elif tail_content:
                merged_content = tail_content
            elif head_content:
                merged_content = head_content
            else:
                merged_content = ''
            
            # 计算合并后的rowspan
            tail_rowspan = tail_cell.get('rowspan', 1)
            head_rowspan = head_cell['rowspan']
            
            if entire_row_merged:
                # 整行合并：new_rowspan = rowspan1 + rowspan2 - 1
                new_rowspan = tail_rowspan + head_rowspan - 1
            else:
                # 部分合并：new_rowspan = rowspan1 + rowspan2
                new_rowspan = tail_rowspan + head_rowspan
            
            # 如果是rowspan占位，需要更新原始单元格的rowspan
            if tail_cell.get('is_rowspan_placeholder'):
                # 记录需要更新的原始单元格
                original_row_idx = tail_cell.get('original_row_idx', -1)
                original_col_idx = tail_cell.get('original_col_idx', -1)
                if original_row_idx >= 0 and original_col_idx >= 0:
                    rowspan_updates.append({
                        'row_idx': original_row_idx,
                        'col_idx': original_col_idx,
                        'new_rowspan': tail_cell.get('original_rowspan', 1) + head_rowspan - (1 if entire_row_merged else 0),
                        'content_to_add': head_content
                    })
                # rowspan占位单元格不生成新的td，跳过
                processed_tail_structs.add(struct_idx)
                continue
            
            # 构建合并后的单元格
            attrs = tail_cell.get('attrs', '')
            
            # 更新rowspan属性
            if new_rowspan > 1:
                rowspan_pattern = r'rowspan\s*=\s*["\']?\d+["\']?'
                if re.search(rowspan_pattern, attrs, re.IGNORECASE):
                    attrs = re.sub(rowspan_pattern, f'rowspan="{new_rowspan}"', attrs, flags=re.IGNORECASE)
                else:
                    attrs = (attrs + f' rowspan="{new_rowspan}"').strip()
            
            merged_tail_cells.append(format_td(attrs, merged_content))
            
            # 标记已处理
            processed_tail_structs.add(struct_idx)
        else:
            # 这个单元格不需要合并，直接保留
            # 【新增】但如果是rowspan占位，且首行对应列有rowspan，需要更新原始rowspan
            if tail_cell.get('is_rowspan_placeholder') and match_info:
                match_idx, matched_head_idx = match_info
                head_cell = head_structure[matched_head_idx]
                head_rowspan = head_cell['rowspan']
                head_content = head_cell['content_stripped']
                
                # 如果首行对应列是空的rowspan（rowspan > 1且内容为空），需要更新原始rowspan
                if head_rowspan > 1 and not head_content:
                    original_row_idx = tail_cell.get('original_row_idx', -1)
                    original_col_idx = tail_cell.get('original_col_idx', -1)
                    if original_row_idx >= 0 and original_col_idx >= 0:
                        # 部分合并场景：rowspan = original + head_rowspan
                        rowspan_updates.append({
                            'row_idx': original_row_idx,
                            'col_idx': original_col_idx,
                            'new_rowspan': tail_cell.get('original_rowspan', 1) + head_rowspan,
                            'content_to_add': ''
                        })
            elif not tail_cell.get('is_rowspan_placeholder'):
                attrs = tail_cell.get('attrs', '')
                content = tail_cell.get('content', '')
                merged_tail_cells.append(format_td(attrs, content.strip()))
            
            processed_tail_structs.add(struct_idx)
    
    merged_tail_row = '<tr>' + ''.join(merged_tail_cells) + '</tr>'
    
    # 更新之前行中的rowspan
    if rowspan_updates:
        for update in rowspan_updates:
            row_idx = update['row_idx']
            if row_idx < len(all_rows_before) - 1:  # 不是尾行
                all_rows_before[row_idx] = update_row_rowspan(
                    self, all_rows_before[row_idx], 
                    update['col_idx'], 
                    update['new_rowspan'],
                    update.get('content_to_add', '')
                )
    
    # 构建首行剩余部分
    remaining_head_cells = []
    for i in range(len(head_structure)):
        # 检查这个单元格是否已被合并
        merged = False
        for match_idx, (matched_tail_idx, matched_head_cell_idx) in enumerate(matched_cols):
            if matched_head_cell_idx == i and match_idx < merge_until_match_idx:
                merged = True
                break
        
        if not merged:
            head_cell = head_structure[i]
            
            # 【新增】检查对应的尾行列是否是rowspan占位
            # 如果首行该列是空的（或空rowspan），且对应尾行列是rowspan占位，则不添加这个td
            # 因为这些列应该被前一页的rowspan覆盖
            tail_idx_for_head = None
            for match_idx, (matched_tail_idx, matched_head_cell_idx) in enumerate(matched_cols):
                if matched_head_cell_idx == i:
                    tail_idx_for_head = matched_tail_idx
                    break
            
            if tail_idx_for_head is not None and tail_idx_for_head < len(tail_full_structure):
                tail_cell = tail_full_structure[tail_idx_for_head]
                # 如果尾行该列是rowspan占位，且首行该列是空的，跳过
                if tail_cell.get('is_rowspan_placeholder', False) and not head_cell['content_stripped']:
                    continue
            
            remaining_head_cells.append(format_td(head_cell['attrs'], head_cell['content_stripped']))
    
    remaining_first_row = ''
    if remaining_head_cells:
        remaining_first_row = '<tr>' + ''.join(remaining_head_cells) + '</tr>'
    
    return True, merged_tail_row, remaining_first_row


def get_tail_row_full_structure(merger: Any, all_rows: List[str]) -> List[Dict]:
    """
    获取尾行的完整列结构，包括rowspan占位
    
    Returns:
        列表，每个元素包含：
        - attrs: 单元格属性
        - content: 单元格内容
        - colspan: colspan值
        - rowspan: rowspan值
        - is_rowspan_placeholder: 是否是rowspan占位
        - original_row_idx: 如果是占位，原始单元格所在行索引
        - original_col_idx: 如果是占位，原始单元格所在列索引
        - original_rowspan: 如果是占位，原始的rowspan值
    """
    self = merger
    
    if not all_rows:
        return []
    
    target_row_idx = len(all_rows) - 1
    
    # 追踪活跃的rowspan
    active_rowspans: List[Dict] = []
    
    for row_idx, row_html in enumerate(all_rows):
        cells = re.findall(r'<td([^>]*)>(.*?)</td>', row_html, re.DOTALL | re.IGNORECASE)
        
        col_idx = 0
        cell_idx = 0
        
        for attrs, content in cells:
            # 跳过被rowspan占位的列（remaining >= 0 表示当前行被该rowspan覆盖）
            while col_idx < len(active_rowspans) and active_rowspans[col_idx] is not None and active_rowspans[col_idx]['remaining'] >= 0:
                col_idx += 1
            
            colspan_match = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            rowspan_match = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            colspan_val = int(colspan_match.group(1)) if colspan_match else 1
            rowspan_val = int(rowspan_match.group(1)) if rowspan_match else 1
            
            # 扩展active_rowspans数组
            while len(active_rowspans) < col_idx + colspan_val:
                active_rowspans.append(None)
            
            # 如果有rowspan，记录到active_rowspans
            # remaining表示当前行之后还需要占位的行数
            if rowspan_val > 1:
                for c in range(colspan_val):
                    active_rowspans[col_idx + c] = {
                        'remaining': rowspan_val - 1,  # 当前行已经使用了一行
                        'attrs': attrs,
                        'content': content,
                        'colspan': colspan_val,
                        'rowspan': rowspan_val,
                        'original_row_idx': row_idx,
                        'original_col_idx': cell_idx
                    }
            
            col_idx += colspan_val
            cell_idx += 1
        
        # 递减所有active_rowspans的remaining（当前行处理完毕，准备处理下一行）
        # 不在最后一行时递减，因为我们需要尾行时的状态
        if row_idx < target_row_idx:
            for i in range(len(active_rowspans)):
                if active_rowspans[i] is not None:
                    active_rowspans[i]['remaining'] -= 1
                    if active_rowspans[i]['remaining'] < 0:
                        active_rowspans[i] = None
    
    # 构建尾行的完整结构（每个元素代表一个单元格，不展开colspan）
    target_row = all_rows[target_row_idx]
    target_cells = re.findall(r'<td([^>]*)>(.*?)</td>', target_row, re.DOTALL | re.IGNORECASE)
    
    # 计算尾行自身的总显示列数（考虑colspan）
    target_total_display_cols = 0
    for attrs, _ in target_cells:
        colspan_match = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
        colspan_val = int(colspan_match.group(1)) if colspan_match else 1
        target_total_display_cols += colspan_val
    
    # 计算rowspan占位的显示列数（remaining >= 0 表示尾行被该rowspan覆盖）
    rowspan_placeholder_count = sum(1 for i in range(len(active_rowspans)) 
                                     if active_rowspans[i] is not None and active_rowspans[i]['remaining'] >= 0)
    
    # 总显示列数 = rowspan占位 + 实际单元格的显示列数
    max_display_cols = rowspan_placeholder_count + target_total_display_cols
    
    full_structure = []
    display_col_idx = 0  # 显示列位置
    cell_idx = 0  # 尾行单元格索引
    
    while display_col_idx < max_display_cols or cell_idx < len(target_cells):
        # 检查是否有rowspan占位（remaining >= 0 表示尾行被该rowspan覆盖，包括最后一行）
        if display_col_idx < len(active_rowspans) and active_rowspans[display_col_idx] is not None and active_rowspans[display_col_idx]['remaining'] >= 0:
            # rowspan占位：这一列被前面某行的rowspan占用
            info = active_rowspans[display_col_idx]
            full_structure.append({
                'attrs': info['attrs'],
                'content': info['content'],
                'colspan': info['colspan'],
                'rowspan': info['rowspan'],
                'is_rowspan_placeholder': True,
                'original_row_idx': info['original_row_idx'],
                'original_col_idx': info['original_col_idx'],
                'original_rowspan': info['rowspan'],
                'display_col_start': display_col_idx
            })
            # 跳过colspan占用的所有显示列
            display_col_idx += info['colspan']
        elif cell_idx < len(target_cells):
            # 实际单元格
            attrs, content = target_cells[cell_idx]
            colspan_match = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            rowspan_match = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            colspan_val = int(colspan_match.group(1)) if colspan_match else 1
            rowspan_val = int(rowspan_match.group(1)) if rowspan_match else 1
            
            full_structure.append({
                'attrs': attrs,
                'content': content,
                'colspan': colspan_val,
                'rowspan': rowspan_val,
                'is_rowspan_placeholder': False,
                'cell_idx': cell_idx,
                'display_col_start': display_col_idx
            })
            display_col_idx += colspan_val
            cell_idx += 1
        else:
            break
    
    return full_structure


def update_row_rowspan(merger: Any, row_html: str, target_cell_idx: int, new_rowspan: int, content_to_add: str = '') -> str:
    """
    更新行中指定单元格的rowspan，并可选地添加内容
    """
    cells = re.findall(r'<td([^>]*)>(.*?)</td>', row_html, re.DOTALL | re.IGNORECASE)
    
    if target_cell_idx >= len(cells):
        return row_html
    
    new_cells = []
    for i, (attrs, content) in enumerate(cells):
        if i == target_cell_idx:
            # 更新rowspan
            rowspan_pattern = r'rowspan\s*=\s*["\']?\d+["\']?'
            if re.search(rowspan_pattern, attrs, re.IGNORECASE):
                new_attrs = re.sub(rowspan_pattern, f'rowspan="{new_rowspan}"', attrs, flags=re.IGNORECASE)
            else:
                new_attrs = (attrs + f' rowspan="{new_rowspan}"').strip()
            
            # 添加内容
            if content_to_add:
                new_content = content.strip() + '<br/>' + content_to_add if content.strip() else content_to_add
            else:
                new_content = content
            
            new_cells.append(format_td(new_attrs, new_content))
        else:
            new_cells.append(format_td(attrs, content))
    
    return '<tr>' + ''.join(new_cells) + '</tr>'


def format_td(attrs: str, content: str) -> str:
    """格式化td标签"""
    attrs_clean = attrs.strip()
    prefix = f" {attrs_clean}" if attrs_clean else ""
    return f"<td{prefix}>{content}</td>"
