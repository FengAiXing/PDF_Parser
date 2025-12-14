from typing import Any, Tuple


def should_merge_rows(self: Any, row1: str, row2: str, original_has_key_values: bool = None, has_next_new_row: bool = False) -> Tuple[bool, str]:
        """
        判断两行是否应该合并，并返回合并后的行
        
        Args:
            row1: 前一页的最后一行HTML（可能是跨页延续，关键列可能为空）
            row2: 后一页的第一行HTML
            original_has_key_values: 原始行的关键列是否有值（用于判断row1是否是跨页延续）
            has_next_new_row: row2后面是否有新行（完整行，关键列有值）
            
        Returns:
            (是否合并, 合并后的行HTML)
        """
        import re
        def fmt_td(attrs: str, content: str) -> str:
            attrs_clean = attrs.strip()
            prefix = f" {attrs_clean}" if attrs_clean else ""
            return f"<td{prefix}>{content}</td>"
        
        # 提取单元格
        cells1 = re.findall(r'<td([^>]*)>(.*?)</td>', row1, re.DOTALL | re.IGNORECASE)
        cells2 = re.findall(r'<td([^>]*)>(.*?)</td>', row2, re.DOTALL | re.IGNORECASE)
        
        if not cells1 or not cells2:
            return False, row1
        
        # 情况1：检查是否都是单列（1*1表格的特殊处理）
        if len(cells1) == 1 and len(cells2) == 1:
            attrs1, content1 = cells1[0]
            attrs2, content2 = cells2[0]
            
            # 检查是否有colspan属性
            has_colspan1 = 'colspan' in attrs1.lower()
            has_colspan2 = 'colspan' in attrs2.lower()
            
            # 检查内容
            content1_stripped = content1.strip()
            content2_stripped = content2.strip()
            
            # 【修改】1*1表格的特殊处理：只要后一页有内容，就应该合并（因为1*1表格通常是跨页内容的延续）
            # 或者两个单元格都有内容，也应该合并
            if content2_stripped or (content1_stripped and content2_stripped):
                # 可能是跨页的单列内容
                self.logger.debug(f"    检测到1*1表格跨页: 第一行有colspan={has_colspan1}, 第二行有colspan={has_colspan2}, 第一行内容='{content1_stripped[:30]}', 第二行内容='{content2_stripped[:30]}'")
                
                # 合并内容（用<br/>分隔，如果前一页有内容的话）
                if content1_stripped and content2_stripped:
                    merged_content = content1_stripped + '<br/>' + content2_stripped
                elif content1_stripped:
                    merged_content = content1_stripped
                else:
                    merged_content = content2_stripped
                
                # 保留colspan属性（优先保留前一页的colspan，如果前一页没有则使用后一页的）
                if has_colspan1:
                    merged_row = f'<tr>{fmt_td(attrs1, merged_content)}</tr>'
                elif has_colspan2:
                    merged_row = f'<tr>{fmt_td(attrs2, merged_content)}</tr>'
                else:
                    merged_row = f'<tr>{fmt_td("", merged_content)}</tr>'
                
                return True, merged_row
        
        # 情况2：列数不同，按colspan匹配合并
        if len(cells1) != len(cells2) and len(cells1) > 1 and len(cells2) > 1:
            self.logger.debug(f"    检测到列数不同: row1有{len(cells1)}列, row2有{len(cells2)}列，尝试按colspan匹配合并")
            
            # 计算每列的实际colspan和列位置
            def get_col_info(cells):
                """返回每列的信息：[(colspan, content, attrs, start_col_pos), ...]"""
                col_info = []
                col_pos = 0
                for attrs, content in cells:
                    colspan_match = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
                    colspan_val = int(colspan_match.group(1)) if colspan_match else 1
                    col_info.append({
                        'colspan': colspan_val,
                        'content': content,
                        'attrs': attrs,
                        'start_col_pos': col_pos,
                        'end_col_pos': col_pos + colspan_val
                    })
                    col_pos += colspan_val
                return col_info
            
            col_info1 = get_col_info(cells1)
            col_info2 = get_col_info(cells2)
            
            # 从前往后匹配，找到第一个colspan不匹配的列
            merged_cells = []
            next_row_cells = []
            merge_success = False
            first_mismatch_col = None
            
            # 按列位置匹配
            col_pos1 = 0
            col_pos2 = 0
            idx1 = 0
            idx2 = 0
            
            while idx1 < len(col_info1) and idx2 < len(col_info2):
                info1 = col_info1[idx1]
                info2 = col_info2[idx2]
                
                # 检查列位置是否对齐
                if col_pos1 == col_pos2:
                    # 列位置对齐，检查colspan是否相同
                    if info1['colspan'] == info2['colspan']:
                        # colspan相同，检查后一页的值是否为空
                        content1_stripped = info1['content'].strip()
                        content2_stripped = info2['content'].strip()
                        
                        if not content2_stripped:
                            # 后一页值为空，需要合并并添加rowspan
                            rowspan_match1 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', info1['attrs'], re.IGNORECASE)
                            rowspan_match2 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', info2['attrs'], re.IGNORECASE)
                            rowspan_val1 = int(rowspan_match1.group(1)) if rowspan_match1 else 1
                            rowspan_val2 = int(rowspan_match2.group(1)) if rowspan_match2 else 1
                            # 公式：new_rowspan = rowspan1 + (rowspan2 - 1)
                            new_rowspan = rowspan_val1 + (rowspan_val2 - 1)
                            
                            # 更新rowspan值
                            if rowspan_match1:
                                new_attrs1 = re.sub(r'rowspan\s*=\s*["\']?\d+["\']?', f'rowspan="{new_rowspan}"', info1['attrs'], flags=re.IGNORECASE)
                            else:
                                new_attrs1 = (info1['attrs'] + f' rowspan="{new_rowspan}"').strip()
                            
                            merged_cells.append(fmt_td(new_attrs1 if new_attrs1.strip() else '', content1_stripped))
                            self.logger.debug(f"      列位置{col_pos1}：colspan相同({info1['colspan']})且后一页值为空，合并，添加rowspan={new_rowspan}（原值{rowspan_val1}+({rowspan_val2}-1)）")
                            
                            merge_success = True
                            # 继续检查下一列
                            col_pos1 += info1['colspan']
                            col_pos2 += info2['colspan']
                            idx1 += 1
                            idx2 += 1
                        else:
                            # 后一页值不为空，停止合并，记录第一个不匹配的列
                            first_mismatch_col = col_pos1
                            self.logger.debug(f"      列位置{col_pos1}：colspan相同({info1['colspan']})但后一页值不为空，停止合并")
                            break
                    else:
                        # colspan不相同，停止合并
                        first_mismatch_col = col_pos1
                        self.logger.debug(f"      列位置{col_pos1}：colspan不匹配(row1={info1['colspan']}, row2={info2['colspan']})，停止合并")
                        break
                else:
                    # 列位置不对齐，可能是因为rowspan占位导致的
                    # 尝试跳过空列（rowspan占位），继续匹配
                    if col_pos1 < col_pos2:
                        # row1的列位置在前，说明row2前面有rowspan占位，跳过row2的空列
                        content2_stripped = info2['content'].strip()
                        if not content2_stripped:
                            # row2的列是空的（rowspan占位），跳过这一列
                            self.logger.debug(f"      列位置不对齐(col_pos1={col_pos1}, col_pos2={col_pos2})，row2的列是空的，跳过row2的这一列")
                            col_pos2 += info2['colspan']
                            idx2 += 1
                            continue
                        else:
                            # row2的列有内容，停止合并
                            first_mismatch_col = min(col_pos1, col_pos2)
                            self.logger.debug(f"      列位置不对齐(col_pos1={col_pos1}, col_pos2={col_pos2})，row2的列有内容，停止合并")
                            break
                    elif col_pos1 > col_pos2:
                        # row2的列位置在前，说明row1前面有rowspan占位，跳过row1的空列
                        content1_stripped = info1['content'].strip()
                        if not content1_stripped:
                            # row1的列是空的（rowspan占位），跳过这一列
                            self.logger.debug(f"      列位置不对齐(col_pos1={col_pos1}, col_pos2={col_pos2})，row1的列是空的，跳过row1的这一列")
                            col_pos1 += info1['colspan']
                            idx1 += 1
                            continue
                        else:
                            # row1的列有内容，停止合并
                            first_mismatch_col = min(col_pos1, col_pos2)
                            self.logger.debug(f"      列位置不对齐(col_pos1={col_pos1}, col_pos2={col_pos2})，row1的列有内容，停止合并")
                            break
                    else:
                        # 不应该到达这里，但为了安全，停止合并
                        first_mismatch_col = min(col_pos1, col_pos2)
                        self.logger.debug(f"      列位置不对齐(col_pos1={col_pos1}, col_pos2={col_pos2})，未知情况，停止合并")
                        break
            
            # 如果成功合并了至少一列，返回合并结果
            if merge_success:
                # 添加row1剩余的列
                while idx1 < len(col_info1):
                    info1 = col_info1[idx1]
                    merged_cells.append(fmt_td(info1['attrs'], info1['content'].strip()))
                    idx1 += 1
                
                merged_row = '<tr>' + ''.join(merged_cells) + '</tr>'
                
                # 如果row2还有剩余的列（从停止位置开始），构建下一行
                # 添加row2从停止位置开始的所有剩余列
                while idx2 < len(col_info2):
                    info2 = col_info2[idx2]
                    next_row_cells.append(fmt_td(info2['attrs'], info2['content'].strip()))
                    idx2 += 1
                
                if next_row_cells:
                    next_row = '<tr>' + ''.join(next_row_cells) + '</tr>'
                    merged_row_with_next = merged_row + '\n<!--PARTIAL_MERGE_NEXT_ROW-->\n' + next_row
                    self.logger.debug(f"    按colspan匹配合并成功：合并了列位置0到{first_mismatch_col if first_mismatch_col else '末尾'}，返回合并后的第一行和下一行")
                    return True, merged_row_with_next
                
                self.logger.debug(f"    按colspan匹配合并成功：合并了列位置0到{first_mismatch_col if first_mismatch_col else '末尾'}")
                return True, merged_row
            else:
                # 没有成功合并，列数不同且无法按colspan匹配，判定为新行，不合并
                self.logger.debug(f"    按colspan匹配合并失败：列数不同且无法匹配，判定为新行，不合并")
                return False, row1
        
        # 情况3：多列，列数相同，按照列的顺序从前往后合并
        if len(cells1) == len(cells2) and len(cells1) > 1:
            # 【新增】列数匹配的合并逻辑
            # 1. 从前往后遍历每一列
            # 2. 如果后一页的列为空值，并且colspan与前一页尾行colspan相同，那么合并到前一页尾行
            # 3. 直到后一页首行某一列的值不为空的时候，需要判断：
            #    - 如果从该列以及往后的列中的值与前一页尾行对应列的值都不相同，那么需要合并整行的每一列
            #    - 如果任一列出现值相同的，那么只有从有值的那一列以及往后的剩余列不合并，前面值为空的列都合并
            
            import re
            merged_cells = []
            merge_success = False
            first_non_empty_col_idx = None  # 后一页首行第一个非空列的索引
            merge_until_col = None  # 合并到哪一列（不包括这一列）
            
            # 第一步：从前往后遍历，找到第一个非空列
            for i in range(len(cells1)):
                attrs1, content1 = cells1[i]
                attrs2, content2 = cells2[i]
                
                content1_stripped = content1.strip()
                content2_stripped = content2.strip()
                
                # 检查colspan是否相同
                colspan_match1 = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs1, re.IGNORECASE)
                colspan_match2 = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs2, re.IGNORECASE)
                colspan1 = int(colspan_match1.group(1)) if colspan_match1 else 1
                colspan2 = int(colspan_match2.group(1)) if colspan_match2 else 1
                
                # 如果后一页的列为空值，并且colspan与前一页尾行colspan相同，那么合并到前一页尾行
                if not content2_stripped and colspan1 == colspan2:
                    # 合并这一列
                    rowspan_match1 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs1, re.IGNORECASE)
                    rowspan_match2 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs2, re.IGNORECASE)
                    rowspan1 = int(rowspan_match1.group(1)) if rowspan_match1 else 1
                    rowspan2 = int(rowspan_match2.group(1)) if rowspan_match2 else 1
                    
                    # 如果后一页有rowspan，需要累加
                    # 公式：new_rowspan = rowspan1 + (rowspan2 - 1)
                    # 如果rowspan2=1（没有rowspan或rowspan=1），那么new_rowspan = rowspan1 + 0 = rowspan1
                    # 如果rowspan2>1，那么new_rowspan = rowspan1 + (rowspan2 - 1)
                    new_rowspan = rowspan1 + (rowspan2 - 1)
                    
                    # 更新rowspan值
                    if rowspan_match1:
                        new_attrs1 = re.sub(r'rowspan\s*=\s*["\']?\d+["\']?', f'rowspan="{new_rowspan}"', attrs1, flags=re.IGNORECASE)
                    else:
                        new_attrs1 = (attrs1 + f' rowspan="{new_rowspan}"').strip()
                    
                    merged_cells.append(fmt_td(new_attrs1 if new_attrs1.strip() else '', content1_stripped))
                    merge_success = True
                    self.logger.debug(f"      列{i+1}：后一页为空且colspan相同({colspan1})，合并，rowspan={rowspan1}->{new_rowspan}")
                elif content2_stripped:
                    # 后一页这一列有值，记录第一个非空列的索引
                    if first_non_empty_col_idx is None:
                        first_non_empty_col_idx = i
                    # 不break，继续检查后续列是否有相同值
                else:
                    # 后一页为空但colspan不同，停止合并
                    break
            
            # 第二步：如果找到了第一个非空列，判断从该列往后的列
            if first_non_empty_col_idx is not None:
                # 检查从第一个非空列往后的列中，是否有与前一页尾行对应列的值相同的
                has_same_value_after_first_non_empty = False
                for i in range(first_non_empty_col_idx, len(cells1)):
                    content1_stripped = cells1[i][1].strip()
                    content2_stripped = cells2[i][1].strip()
                    if content1_stripped and content2_stripped and content1_stripped == content2_stripped:
                        has_same_value_after_first_non_empty = True
                        break
                
                if has_same_value_after_first_non_empty:
                    # 如果任一列出现值相同的，那么只有从有值的那一列以及往后的剩余列不合并，前面值为空的列都合并
                    merge_until_col = first_non_empty_col_idx
                    self.logger.debug(f"    检测到从第{first_non_empty_col_idx+1}列开始有值，且后续列中有与前一页尾行对应列的值相同的，只合并前{first_non_empty_col_idx}列（空值列）")
                else:
                    # 如果从该列以及往后的列中的值与前一页尾行对应列的值都不相同，那么需要合并整行的每一列
                    merge_until_col = len(cells1)
                    self.logger.debug(f"    检测到从第{first_non_empty_col_idx+1}列开始有值，且后续列中与前一页尾行对应列的值都不相同，合并整行")
            elif merge_success:
                # 如果所有列都是空的且colspan相同，合并整行
                merge_until_col = len(cells1)
                self.logger.debug(f"    所有列都是空的且colspan相同，合并整行")
            
            # 第三步：处理合并
            if merge_success:
                # 如果只合并部分列，需要处理剩余列
                if merge_until_col is not None and merge_until_col < len(cells1):
                    # 只合并前merge_until_col列，剩余列不合并
                    # 但是，如果前面合并的列有rowspan，需要更新rowspan
                    # 因为不合并后续列，所以前面合并的列的rowspan需要加上后一页对应列的rowspan（如果后一页有rowspan）
                    for i in range(len(merged_cells)):
                        if i < merge_until_col:
                            # 已经合并的列，检查是否需要更新rowspan
                            attrs2 = cells2[i][0] if i < len(cells2) else ''
                            rowspan_match2 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs2, re.IGNORECASE)
                            if rowspan_match2:
                                rowspan2 = int(rowspan_match2.group(1))
                                # 更新merged_cells中这一列的rowspan
                                cell_html = merged_cells[i]
                                rowspan_match_merged = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', cell_html, re.IGNORECASE)
                                if rowspan_match_merged:
                                    rowspan_merged = int(rowspan_match_merged.group(1))
                                    # 因为不合并后续列，所以rowspan在原有的值上加后一页的rowspan值
                                    new_rowspan = rowspan_merged + rowspan2
                                    merged_cells[i] = re.sub(r'rowspan\s*=\s*["\']?\d+["\']?', f'rowspan="{new_rowspan}"', cell_html, flags=re.IGNORECASE)
                                    self.logger.debug(f"      列{i+1}：更新rowspan={rowspan_merged}->{new_rowspan}（因为不合并后续列，累加后一页的rowspan={rowspan2}）")
                    
                    # 添加前一页尾行剩余列（不合并）
                    for i in range(merge_until_col, len(cells1)):
                        attrs1, content1 = cells1[i]
                        merged_cells.append(fmt_td(attrs1 if attrs1.strip() else '', content1.strip()))
                    
                    merged_row = '<tr>' + ''.join(merged_cells) + '</tr>'
                    
                    # 构建包含后一页首行从第一个非空列开始的下一行
                    next_row_cells = []
                    for i in range(len(cells2)):
                        if i < merge_until_col:
                            # 前面已合并的列，在下一行中应该被rowspan占位，不添加单元格
                            continue
                        attrs2, content2 = cells2[i]
                        content2_stripped = content2.strip()
                        next_row_cells.append(fmt_td(attrs2 if attrs2.strip() else '', content2_stripped))
                    
                    if next_row_cells:
                        next_row = '<tr>' + ''.join(next_row_cells) + '</tr>'
                        merged_row_with_next = merged_row + '\n<!--PARTIAL_MERGE_NEXT_ROW-->\n' + next_row
                        self.logger.debug(f"    部分合并：返回合并后的第一行（合并前{merge_until_col}列）和下一行（包含后一页首行从第{merge_until_col+1}列开始的值）")
                        return True, merged_row_with_next
                    
                    return True, merged_row
                elif merge_until_col == len(cells1):
                    # 合并整行的每一列
                    # 添加剩余列（从第一个非空列开始，或者所有列）
                    start_idx = len(merged_cells)
                    for i in range(start_idx, len(cells1)):
                        attrs1, content1 = cells1[i]
                        attrs2, content2 = cells2[i]
                        
                        content1_stripped = content1.strip()
                        content2_stripped = content2.strip()
                        
                        # 合并内容
                        if content1_stripped and content2_stripped:
                            merged_content = content1_stripped + '<br/>' + content2_stripped
                        elif content1_stripped:
                            merged_content = content1_stripped
                        elif content2_stripped:
                            merged_content = content2_stripped
                        else:
                            merged_content = ''
                        
                        # 检查rowspan
                        rowspan_match1 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs1, re.IGNORECASE)
                        rowspan_match2 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs2, re.IGNORECASE)
                        rowspan1 = int(rowspan_match1.group(1)) if rowspan_match1 else 1
                        rowspan2 = int(rowspan_match2.group(1)) if rowspan_match2 else 1
                        
                        # 公式：new_rowspan = rowspan1 + (rowspan2 - 1)
                        # 如果rowspan2=1（没有rowspan或rowspan=1），那么new_rowspan = rowspan1 + 0 = rowspan1
                        # 如果rowspan2>1，那么new_rowspan = rowspan1 + (rowspan2 - 1)
                        new_rowspan = rowspan1 + (rowspan2 - 1)
                        
                        # 更新rowspan值
                        if rowspan_match1:
                            new_attrs1 = re.sub(r'rowspan\s*=\s*["\']?\d+["\']?', f'rowspan="{new_rowspan}"', attrs1, flags=re.IGNORECASE)
                        else:
                            new_attrs1 = (attrs1 + f' rowspan="{new_rowspan}"').strip()
                        
                        merged_cells.append(fmt_td(new_attrs1 if new_attrs1.strip() else attrs2, merged_content))
                    
                    merged_row = '<tr>' + ''.join(merged_cells) + '</tr>'
                    self.logger.debug(f"    整行合并：合并了所有列，rowspan已更新")
                    return True, merged_row
            
            # 如果上面的逻辑没有匹配，继续使用原有的逻辑
            # 关键列是第一列（序号列）
            # 核心逻辑（用户提出的判断标准）：
            # 1. 如果row1的第一列为空，而row2的第一列突然有值了，说明这是新行
            # 2. 如果row1的第一列有值，row2的第一列也有值，且值不同，说明这是新行
            # 3. 如果row1的第一列有值，row2的第一列为空，这是正常的跨页延续（应该合并）
            # 4. 如果row1的第一列都为空，row2的第一列也都为空，且只有后面的列（如技术参数）有内容，这是跨页延续（应该合并）
            
            # 检查第一列（序号列）
            if len(cells1) > 0 and len(cells2) > 0:
                attrs1, content1 = cells1[0]
                attrs2, content2 = cells2[0]
                
                content1_stripped = content1.strip()
                content2_stripped = content2.strip()
                
                row1_has_key_values = bool(content1_stripped)
                row2_has_key_values = bool(content2_stripped)
                
                key_col_changed = False
                
                # 如果row1的第一列为空，但row2的第一列有值，说明这是新行
                if not content1_stripped and content2_stripped:
                    key_col_changed = True
                    self.logger.debug(f"    检测到第一列从空变为有值，这是新行")
                # 如果row1的第一列有值，row2的第一列也有值，且值不同，说明这是新行
                elif content1_stripped and content2_stripped and content1_stripped != content2_stripped:
                    key_col_changed = True
                    self.logger.debug(f"    检测到第一列值不同，这是新行")
            else:
                # 没有第一列，使用默认值
                row1_has_key_values = False
                row2_has_key_values = False
                key_col_changed = False
            
            # 如果关键列发生变化，说明这是新行，不应该合并
            if key_col_changed:
                return False, row1
            
            # 新增规则：如果首尾行在任意列上都有非空且内容完全相同，判定为新行（避免重复覆盖）
            # 但需要检查后一页首行是否存在"空rowspan"的列，如果存在，则对这些列进行部分合并
            same_value_cols = set()  # 记录同列相同值的列索引
            row2_empty_rowspan_cols = set()  # 记录后一页首行中"空rowspan"的列索引
            import re
            for i in range(min(len(cells1), len(cells2))):
                v1 = cells1[i][1].strip()
                v2 = cells2[i][1].strip()
                attrs2 = cells2[i][0] if i < len(cells2) else ''
                # 检查是否有rowspan且值为空
                rowspan_match2 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs2, re.IGNORECASE)
                has_rowspan2 = rowspan_match2 is not None
                if has_rowspan2 and not v2:
                    row2_empty_rowspan_cols.add(i)
                # 检查同列相同值
                if v1 and v2 and v1 == v2:
                    same_value_cols.add(i)
            
            # 如果存在同列相同值，且后一页首行存在空rowspan的列，进行部分合并
            # 条件：前一页尾行有值，后一页首行没有值（关键列），且存在同列相同值，且存在空rowspan列
            if same_value_cols and row2_empty_rowspan_cols and original_has_key_values and row1_has_key_values and not row2_has_key_values:
                self.logger.debug(f"    检测到同列相同值（列{same_value_cols}），但后一页首行存在空rowspan列（列{row2_empty_rowspan_cols}），进行部分合并")
                # 只合并空rowspan的列，其他列不合并（判定为新行）
                merged_cells = []
                for i in range(len(cells1)):
                    attrs1, content1 = cells1[i]
                    if i < len(cells2):
                        attrs2, content2 = cells2[i]
                    else:
                        attrs2, content2 = '', ''
                    
                    content1_stripped = content1.strip()
                    content2_stripped = content2.strip()
                    
                    # 检查是否有rowspan属性
                    rowspan_match2 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs2, re.IGNORECASE)
                    
                    # 如果这一列是空rowspan列，合并：保留前一页的值，添加rowspan
                    if i in row2_empty_rowspan_cols:
                        # 保留前一页的值，使用后一页的rowspan属性
                        rowspan_match1 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs1, re.IGNORECASE)
                        rowspan_val1 = int(rowspan_match1.group(1)) if rowspan_match1 else 1
                        rowspan_val2 = int(rowspan_match2.group(1)) if rowspan_match2 else 1
                        # 公式：new_rowspan = rowspan1 + (rowspan2 - 1)
                        new_rowspan = rowspan_val1 + (rowspan_val2 - 1)
                        # 更新rowspan值
                        if rowspan_match2:
                            new_attrs2 = re.sub(r'rowspan\s*=\s*["\']?\d+["\']?', f'rowspan="{new_rowspan}"', attrs2, flags=re.IGNORECASE)
                        else:
                            new_attrs2 = (attrs2 + f' rowspan="{new_rowspan}"').strip()
                        merged_cells.append(fmt_td(new_attrs2 if new_attrs2.strip() else attrs1, content1_stripped))
                        self.logger.debug(f"      列{i+1}：空rowspan列，合并，保留前一页值'{content1_stripped[:30]}'，添加rowspan={new_rowspan}（原值{rowspan_val1}+({rowspan_val2}-1)）")
                    elif i in same_value_cols:
                        # 如果同列相同值且不是空rowspan列，不合并（判定为新行），保留前一页的值
                        merged_cells.append(fmt_td(attrs1 if attrs1.strip() else attrs2, content1_stripped))
                        self.logger.debug(f"      列{i+1}：同列相同值且非空rowspan列，不合并，保留前一页值'{content1_stripped[:30]}'")
                    else:
                        # 其他列：在部分合并场景下，只合并空rowspan列，其他列都保留前一页的值
                        # 后一页的值会保留在下一行（因为这是部分合并，不是完全合并）
                        merged_cells.append(fmt_td(attrs1 if attrs1.strip() else attrs2, content1_stripped))
                        self.logger.debug(f"      列{i+1}：其他列，部分合并场景下保留前一页值'{content1_stripped[:30]}'，后一页值'{content2_stripped[:30]}'保留在下一行")
                
                merged_row = '<tr>' + ''.join(merged_cells) + '</tr>'
                
                # 在部分合并场景下，需要构建一个包含后一页首行其他列值的下一行
                # 这个下一行应该包含：空rowspan列的位置留空（因为已经被rowspan占位），其他列使用后一页的值
                next_row_cells = []
                empty_rowspan_count = 0  # 记录空rowspan列的数量
                for i in range(len(cells2)):
                    if i in row2_empty_rowspan_cols:
                        # 空rowspan列，在下一行中应该被占位，不添加单元格
                        empty_rowspan_count += 1
                        continue
                    attrs2, content2 = cells2[i]
                    content2_stripped = content2.strip()
                    # 其他列：使用后一页的值
                    next_row_cells.append(fmt_td(attrs2 if attrs2.strip() else '', content2_stripped))
                
                # 如果有其他列的值，构建下一行
                if next_row_cells:
                    next_row = '<tr>' + ''.join(next_row_cells) + '</tr>'
                    # 返回合并后的第一行和下一行（用特殊标记分隔，供调用者处理）
                    # 使用一个特殊的分隔符来标记这是部分合并的结果
                    merged_row_with_next = merged_row + '\n<!--PARTIAL_MERGE_NEXT_ROW-->\n' + next_row
                    self.logger.debug(f"    部分合并：返回合并后的第一行和下一行（包含后一页首行的其他列值）")
                    return True, merged_row_with_next
                
                return True, merged_row
            
            # 【新增】处理后一页首行前几列为空，从某列开始有值，且与前一页尾行对应列相同的情况
            # 如果存在同列相同值，且后一页首行前几列为空，需要判定为新行，但需要正确处理前面的空列
            if same_value_cols:
                # 检查后一页首行前几列是否为空
                first_non_empty_col_idx = None
                for i in range(len(cells2)):
                    if cells2[i][1].strip():
                        first_non_empty_col_idx = i
                        break
                
                # 如果后一页首行前几列为空，且从某列开始有值，且该列或后面的列与前一页尾行对应列的值相同
                if first_non_empty_col_idx is not None and first_non_empty_col_idx > 0:
                    # 检查同列相同值的列是否在第一个非空列之后（或等于）
                    same_value_after_first_non_empty = any(col_idx >= first_non_empty_col_idx for col_idx in same_value_cols)
                    
                    if same_value_after_first_non_empty:
                        self.logger.debug(f"    检测到同列相同值（列{same_value_cols}），且后一页首行前{first_non_empty_col_idx}列为空，从第{first_non_empty_col_idx+1}列开始有值，判定为新行，但需要合并前面的空列")
                        
                        # 判定为新行，但需要合并前面的空列并计算rowspan
                        merged_cells = []
                        for i in range(len(cells1)):
                            attrs1, content1 = cells1[i]
                            if i < len(cells2):
                                attrs2, content2 = cells2[i]
                            else:
                                attrs2, content2 = '', ''
                            
                            content1_stripped = content1.strip()
                            content2_stripped = content2.strip()
                            
                            # 如果这一列在前面的空列范围内（i < first_non_empty_col_idx）
                            if i < first_non_empty_col_idx:
                                # 前面的空列：如果前一页尾行有值，后一页首行为空，需要合并并添加rowspan
                                if content1_stripped and not content2_stripped:
                                    # 检查是否有rowspan属性
                                    rowspan_match1 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs1, re.IGNORECASE)
                                    rowspan_match2 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs2, re.IGNORECASE)
                                    rowspan_val1 = int(rowspan_match1.group(1)) if rowspan_match1 else 1
                                    rowspan_val2 = int(rowspan_match2.group(1)) if rowspan_match2 else 1
                                    # 公式：new_rowspan = rowspan1 + (rowspan2 - 1)
                                    new_rowspan = rowspan_val1 + (rowspan_val2 - 1)
                                    
                                    # 更新rowspan值
                                    if rowspan_match1:
                                        new_attrs1 = re.sub(r'rowspan\s*=\s*["\']?\d+["\']?', f'rowspan="{new_rowspan}"', attrs1, flags=re.IGNORECASE)
                                    else:
                                        new_attrs1 = (attrs1 + f' rowspan="{new_rowspan}"').strip()
                                    merged_cells.append(fmt_td(new_attrs1 if new_attrs1.strip() else '', content1_stripped))
                                    self.logger.debug(f"      列{i+1}：前面的空列，合并，保留前一页值'{content1_stripped[:30]}'，添加rowspan={new_rowspan}（原值{rowspan_val1}+({rowspan_val2}-1)）")
                                else:
                                    # 前一页尾行也为空，保留原值
                                    merged_cells.append(fmt_td(attrs1 if attrs1.strip() else attrs2, content1_stripped))
                            else:
                                # 从开始有值的列开始，不合并（判定为新行），保留前一页的值
                                merged_cells.append(fmt_td(attrs1 if attrs1.strip() else attrs2, content1_stripped))
                                self.logger.debug(f"      列{i+1}：从开始有值的列开始，不合并，保留前一页值'{content1_stripped[:30]}'")
                        
                        merged_row = '<tr>' + ''.join(merged_cells) + '</tr>'
                        
                        # 构建包含后一页首行从开始有值的列开始的下一行
                        next_row_cells = []
                        for i in range(len(cells2)):
                            if i < first_non_empty_col_idx:
                                # 前面的空列，在下一行中应该被rowspan占位，不添加单元格
                                continue
                            attrs2, content2 = cells2[i]
                            content2_stripped = content2.strip()
                            # 从开始有值的列开始：使用后一页的值
                            next_row_cells.append(fmt_td(attrs2 if attrs2.strip() else '', content2_stripped))
                        
                        # 构建下一行
                        if next_row_cells:
                            next_row = '<tr>' + ''.join(next_row_cells) + '</tr>'
                            # 返回合并后的第一行和下一行（用特殊标记分隔，供调用者处理）
                            merged_row_with_next = merged_row + '\n<!--PARTIAL_MERGE_NEXT_ROW-->\n' + next_row
                            self.logger.debug(f"    部分合并：返回合并后的第一行（包含前面空列的rowspan）和下一行（包含后一页首行从开始有值的列开始的值）")
                            return True, merged_row_with_next
                        else:
                            return True, merged_row
                
                # 如果不存在上述情况，按原逻辑处理
                self.logger.debug(f"    检测到同列相同值（列{same_value_cols}），且后一页首行无空rowspan列，判定为新行，不合并")
                return False, row1
            
            # 检查是否有重叠的非空列
            non_empty_cols1 = set()
            non_empty_cols2 = set()
            
            for i, (attrs, content) in enumerate(cells1):
                if content.strip():
                    non_empty_cols1.add(i)
            
            for i, (attrs, content) in enumerate(cells2):
                if content.strip():
                    non_empty_cols2.add(i)
            
            # 【新增】如果row2在row1原本为空的列上新增了非空内容，说明可能是新行，直接不合并
            if non_empty_cols2 - non_empty_cols1:
                self.logger.debug(f"    检测到row2在新的列{non_empty_cols2 - non_empty_cols1}上有内容，视为新行，不合并")
                return False, row1
            
            # 核心判断逻辑（用户提出的标准）：
            # 1. 如果原始行的关键列有值，row1的关键列有值，row2的关键列都为空
            #    这是明确的跨页延续，应该合并
            # 2. 如果原始行的关键列有值，row1的关键列都为空（跨页延续），row2的关键列都为空
            #    这也是跨页延续，应该合并
            # 3. 如果原始行的关键列有值，row2的关键列突然有值
            #    这是新行，不应该合并（已在key_col_changed中处理）
            # 4. 如果原始行的关键列都为空（row1本身就是跨页延续），row2的关键列都为空
            #    需要判断它们是否属于同一行，但为了安全，通常不应该合并
            
            # 如果original_has_key_values为None，使用row1的状态作为参考
            if original_has_key_values is None:
                original_has_key_values = row1_has_key_values
            
            # 情况1：原始行的关键列有值，row1的关键列有值，row2的关键列都为空
            # 这是明确的跨页延续，应该合并（不管row2后面是否有新行）
            if original_has_key_values and row1_has_key_values and not row2_has_key_values:
                # row1是完整行，row2是跨页延续
                # 【关键修复】对于跨页延续行（row2关键列为空），只要row2有非空列，就应该合并
                # 不需要检查重叠，因为跨页延续行的内容通常不会与上一行重叠
                if non_empty_cols2:  # row2至少有一列有内容
                    self.logger.debug(f"    检测到完整行的跨页延续: 原始行关键列有值，row1关键列有值，row2关键列为空，row2有{len(non_empty_cols2)}个非空列")
                    
                    # 合并单元格内容
                    merged_cells = []
                    import re
                    for i in range(len(cells1)):
                        attrs1, content1 = cells1[i]
                        # 确保row2有对应的列
                        if i < len(cells2):
                            attrs2, content2 = cells2[i]
                        else:
                            attrs2, content2 = '', ''
                        
                        # 检查是否有rowspan属性
                        rowspan_match1 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs1, re.IGNORECASE)
                        rowspan_match2 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs2, re.IGNORECASE)
                        has_rowspan1 = rowspan_match1 is not None
                        has_rowspan2 = rowspan_match2 is not None
                        
                        content1_stripped = content1.strip()
                        content2_stripped = content2.strip()
                        
                        # 如果第一个单元格有rowspan且内容为空，这是rowspan占位；优先使用row2的内容以防丢失
                        if has_rowspan1 and not content1_stripped:
                            merged_cells.append(fmt_td(attrs1, content2_stripped))
                            continue
                        
                        # 如果第二个单元格有rowspan且内容为空，这是rowspan占位；保留row1的内容，继承row2的rowspan属性（若有）
                        if has_rowspan2 and not content2_stripped:
                            merged_cells.append(fmt_td(attrs2 if attrs2.strip() else attrs1, content1_stripped))
                            continue
                        
                        if content1_stripped and content2_stripped:
                            # 两个都有内容
                            # 对于名称列（第2列，索引1），如果内容较短（可能是跨页分割的名称），直接拼接
                            # 对于技术参数列（第4列，索引3），用<br/>分隔
                            if i == 1 and (len(content1_stripped) < 50 or len(content2_stripped) < 50):
                                # 名称列，内容较短，直接拼接（处理"通风设备接入与监测模" + "块"的情况）
                                merged_content = content1_stripped + content2_stripped
                            else:
                                # 其他列或长内容，用<br/>合并
                                merged_content = content1_stripped + '<br/>' + content2_stripped
                        elif content1_stripped:
                            # 只有第一个有内容
                            merged_content = content1_stripped
                        elif content2_stripped:
                            # 只有第二个有内容（跨页延续）
                            merged_content = content2_stripped
                        else:
                            # 都为空，但都不是rowspan占位，保留空内容
                            merged_content = ''
                        
                        # 保留属性（优先使用第一行的，但移除rowspan如果内容为空）
                        final_attrs = attrs1.strip() if attrs1.strip() else attrs2.strip()
                        # 如果合并后内容为空且没有rowspan，移除rowspan属性
                        if not merged_content and final_attrs:
                            final_attrs = re.sub(r'rowspan\s*=\s*["\']?\d+["\']?', '', final_attrs, flags=re.IGNORECASE).strip()
                        
                        merged_cells.append(fmt_td(final_attrs, merged_content))
                    
                    merged_row = '<tr>' + ''.join(merged_cells) + '</tr>'
                    return True, merged_row
            
            # 情况2：原始行的关键列有值，row1的关键列都为空（跨页延续），row2的关键列都为空
            # 这也是跨页延续，应该合并
            # 但是，需要更严格的判断：如果row1的关键列都为空，说明row1本身是跨页延续
            # 在这种情况下，我们需要检查row2后面是否有新行（关键列有值）
            # 如果row2后面有新行，那么row2应该属于那个新行，而不是row1
            if original_has_key_values and not row1_has_key_values and not row2_has_key_values:
                # row1和row2都是跨页延续
                # 如果row2后面有新行（完整行），row2应该属于那个新行，而不是row1
                if has_next_new_row:
                    self.logger.debug(f"    检测到两个跨页延续行，但row2后面有新行，row2应该属于新行，不合并")
                    return False, row1
                
                # row1和row2都是跨页延续，且row2后面没有新行，应该合并
                # 【关键修复】对于跨页延续行的继续，只要row2有非空列，就应该合并
                # 不需要检查重叠，因为跨页延续行的内容通常不会与上一行重叠
                if non_empty_cols2:  # row2至少有一列有内容
                    self.logger.debug(f"    检测到跨页延续的继续: 原始行关键列有值，row1和row2关键列都为空，row2有{len(non_empty_cols2)}个非空列")
                    
                    # 合并单元格内容
                    merged_cells = []
                    import re
                    for i in range(len(cells1)):
                        attrs1, content1 = cells1[i]
                        # 确保row2有对应的列
                        if i < len(cells2):
                            attrs2, content2 = cells2[i]
                        else:
                            attrs2, content2 = '', ''
                        
                        # 检查是否有rowspan属性
                        rowspan_match1 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs1, re.IGNORECASE)
                        rowspan_match2 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs2, re.IGNORECASE)
                        has_rowspan1 = rowspan_match1 is not None
                        has_rowspan2 = rowspan_match2 is not None
                        
                        content1_stripped = content1.strip()
                        content2_stripped = content2.strip()
                        
                        # 如果第一个单元格有rowspan且内容为空，这是rowspan占位，不应该合并内容
                        if has_rowspan1 and not content1_stripped:
                            # 保留rowspan属性，不合并内容
                            merged_cells.append(fmt_td(attrs1, ""))
                            continue
                        
                        # 如果第二个单元格有rowspan且内容为空，这是rowspan占位，不应该合并
                        if has_rowspan2 and not content2_stripped:
                            # 保留rowspan属性，不合并内容
                            merged_cells.append(fmt_td(attrs2, ""))
                            continue
                        
                        if content1_stripped and content2_stripped:
                            # 两个都有内容
                            # 对于名称列（第2列，索引1），如果内容较短（可能是跨页分割的名称），直接拼接
                            # 对于技术参数列（第4列，索引3），用<br/>分隔
                            if i == 1 and (len(content1_stripped) < 50 or len(content2_stripped) < 50):
                                # 名称列，内容较短，直接拼接（处理"通风设备接入与监测模" + "块"的情况）
                                merged_content = content1_stripped + content2_stripped
                            else:
                                # 其他列或长内容，用<br/>合并
                                merged_content = content1_stripped + '<br/>' + content2_stripped
                        elif content1_stripped:
                            # 只有第一个有内容
                            merged_content = content1_stripped
                        elif content2_stripped:
                            # 只有第二个有内容（跨页延续）
                            merged_content = content2_stripped
                        else:
                            # 都为空，但都不是rowspan占位，保留空内容
                            merged_content = ''
                        
                        # 保留属性（优先使用第一行的，但移除rowspan如果内容为空）
                        final_attrs = attrs1.strip() if attrs1.strip() else attrs2.strip()
                        # 如果合并后内容为空且没有rowspan，移除rowspan属性
                        if not merged_content and final_attrs:
                            final_attrs = re.sub(r'rowspan\s*=\s*["\']?\d+["\']?', '', final_attrs, flags=re.IGNORECASE).strip()
                        
                        merged_cells.append(fmt_td(final_attrs, merged_content))
                    
                    merged_row = '<tr>' + ''.join(merged_cells) + '</tr>'
                    return True, merged_row
                else:
                    # 没有非空列，不应该合并
                    return False, row1
            
            # 情况3：如果原始行的关键列都为空（row1本身就是跨页延续），row2的关键列都为空
            # 这可能是不同行的跨页延续，为了安全，不应该合并
            if not original_has_key_values and not row1_has_key_values and not row2_has_key_values:
                self.logger.debug(f"    检测到两个跨页延续行，但原始行关键列都为空，为了安全不合并")
                return False, row1
            
            # 情况3：如果两行都有非空列，且没有重叠（或重叠很少），可能是跨页延续
            if non_empty_cols1 and non_empty_cols2:
                overlap = non_empty_cols1 & non_empty_cols2
                
                # 如果重叠列数少于非空列总数的一半，可能是跨页延续
                total_non_empty = len(non_empty_cols1) + len(non_empty_cols2)
                if len(overlap) < total_non_empty * 0.3:  # 重叠少于30%
                    self.logger.debug(f"    检测到多列部分为空跨页: 列数={len(cells1)}, 非空列1={non_empty_cols1}, 非空列2={non_empty_cols2}")
                    
                    # 合并单元格内容
                    merged_cells = []
                    for i in range(len(cells1)):
                        attrs1, content1 = cells1[i]
                        attrs2, content2 = cells2[i]
                        
                        # 检查是否有rowspan属性
                        import re
                        rowspan_match1 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs1, re.IGNORECASE)
                        rowspan_match2 = re.search(r'rowspan\s*=\s*["\']?(\d+)["\']?', attrs2, re.IGNORECASE)
                        has_rowspan1 = rowspan_match1 is not None
                        has_rowspan2 = rowspan_match2 is not None
                        
                        content1_stripped = content1.strip()
                        content2_stripped = content2.strip()
                        
                        # 如果第一个单元格有rowspan且内容为空，这是rowspan占位，不应该合并内容
                        if has_rowspan1 and not content1_stripped:
                            # 保留rowspan属性，不合并内容
                            merged_cells.append(fmt_td(attrs1, ""))
                            continue
                        
                        # 如果第二个单元格有rowspan且内容为空，这是rowspan占位，不应该合并
                        if has_rowspan2 and not content2_stripped:
                            # 保留rowspan属性，不合并内容
                            merged_cells.append(fmt_td(attrs2, ""))
                            continue
                        
                        if content1_stripped and content2_stripped:
                            # 两个都有内容，用<br/>合并
                            merged_content = content1_stripped + '<br/>' + content2_stripped
                        elif content1_stripped:
                            # 只有第一个有内容
                            merged_content = content1_stripped
                        elif content2_stripped:
                            # 只有第二个有内容
                            merged_content = content2_stripped
                        else:
                            # 都为空，但都不是rowspan占位，保留空内容
                            merged_content = ''
                        
                        # 保留属性（优先使用第一行的，但移除rowspan如果内容为空）
                        final_attrs = attrs1.strip() if attrs1.strip() else attrs2.strip()
                        # 如果合并后内容为空且没有rowspan，移除rowspan属性
                        if not merged_content and final_attrs:
                            final_attrs = re.sub(r'rowspan\s*=\s*["\']?\d+["\']?', '', final_attrs, flags=re.IGNORECASE).strip()
                        
                        merged_cells.append(fmt_td(final_attrs, merged_content))
                    
                    merged_row = '<tr>' + ''.join(merged_cells) + '</tr>'
                    return True, merged_row
        
        # 不满足合并条件
        return False, row1