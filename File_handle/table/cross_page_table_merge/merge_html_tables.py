from typing import Any, Dict, List


def merge_html_tables(merger: Any, tables: List[Dict]) -> List[Dict]:
    """
    合并跨页表格的HTML内容（从原始图片的识别结果中提取）

    Args:
        merger: CrossPageTableMerger 实例
        tables: 表格列表（包含original_results）

    Returns:
        合并后的表格列表
    """
    try:
        import os
        import re

        for table in tables:
            # 只处理跨页表格
            if not table.get("is_cross_page", False):
                continue

            # 从original_results中获取所有原始图片的HTML
            original_results = table.get("original_results", {})
            original_image_paths = table.get("original_image_paths", [])

            if not original_results or not original_image_paths:
                merger.logger.warning(f"跨页表格{table['id']}没有原始识别结果")
                table["recognized_content"] = None
                continue

            # 按照原始图片顺序收集HTML
            html_parts = []
            for img_path in original_image_paths:
                if img_path in original_results:
                    html_parts.append(original_results[img_path])
                else:
                    merger.logger.warning(f"  缺少图片的识别结果: {os.path.basename(img_path)}")

            if not html_parts:
                merger.logger.warning(f"跨页表格{table['id']}没有找到任何HTML内容")
                table["recognized_content"] = None
                continue

            # 【新增】智能合并跨页表格的行
            merged_rows = merger.merge_cross_page_rows(html_parts)

            if merged_rows:
                # 【关键】使用compute_display_cols计算每行列数（考虑rowspan占位和colspan）
                col_counts = merger.compute_display_cols(merged_rows)

                if col_counts:
                    from collections import Counter

                    counter = Counter(col_counts)
                    detected_max = max(col_counts)
                    head_cols = None
                    # 尝试从首段首行推导头部列数
                    first_part_rows = merged_rows[:5]  # 取前几行估计
                    if first_part_rows:
                        head_cols_list = merger.compute_display_cols(first_part_rows)
                        if head_cols_list:
                            head_cols = max(head_cols_list)

                    # 优先顺序：首段推导列数 > table.col_count > detected_max > 众数
                    expected_cols = (
                        head_cols
                        or table.get("col_count")
                        or detected_max
                        or counter.most_common(1)[0][0]
                    )


                    # 校验每行列数（含rowspan占位和colspan），若少于/超过expected_cols则告警
                    # 同时，对于1*1表格（只有1个td的行），如果列数少于expected_cols，应该添加colspan使其与整个表格保持一致
                    normalized_rows = []
                    for idx, row_html in enumerate(merged_rows):
                        dc = col_counts[idx] if idx < len(col_counts) else expected_cols
                        if dc > expected_cols:
                            normalized_rows.append(row_html)
                        elif dc < expected_cols:
                            # 检查是否是1*1表格（只有1个td的行）
                            cells = re.findall(r'<td([^>]*)>(.*?)</td>', row_html, re.DOTALL | re.IGNORECASE)
                            if len(cells) == 1:
                                # 1*1表格，需要添加colspan使其与整个表格列数一致
                                attrs, content = cells[0]
                                # 检查是否已有colspan
                                colspan_match = re.search(r'colspan\s*=\s*["\']?(\d+)["\']?', attrs, re.IGNORECASE)
                                if colspan_match:
                                    # 已有colspan，更新为expected_cols
                                    new_attrs = re.sub(r'colspan\s*=\s*["\']?\d+["\']?', f'colspan="{expected_cols}"', attrs, flags=re.IGNORECASE)
                                else:
                                    # 没有colspan，添加colspan
                                    new_attrs = (attrs + f' colspan="{expected_cols}"').strip()
                                
                                # 确保attrs前面有空格（如果attrs不为空）
                                attrs_str = f' {new_attrs}' if new_attrs else ''
                                normalized_row = f'<tr><td{attrs_str}>{content}</td></tr>'
                                normalized_rows.append(normalized_row)
                            else:
                                normalized_rows.append(row_html)
                        else:
                            normalized_rows.append(row_html)

                    # 使用标准化后的行
                    merged_html = "<table>\n" + "\n".join(normalized_rows) + "\n</table>"
                    table["recognized_content"] = merged_html
                    merger.logger.info(f"跨页表格{table['id']}合并完成")
                else:
                    table["recognized_content"] = None
                    merger.logger.warning(f"跨页表格{table['id']}无法确定列数")
            else:
                table["recognized_content"] = None
                merger.logger.warning(f"跨页表格{table['id']}HTML合并失败：未提取到任何行")

        return tables

    except Exception as e:
        merger.logger.error(f"HTML表格合并失败: {e}")
        import traceback

        traceback.print_exc()
        return tables
