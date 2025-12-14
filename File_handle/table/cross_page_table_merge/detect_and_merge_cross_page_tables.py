from typing import List, Dict, Callable, Optional, Any


def detect_and_merge_cross_page_tables(
    merger: Any,
    tables: List[Dict],
    pdf_path: str,
    output_dir: str,
    is_valid_table_func: Optional[Callable] = None,
    save_images: bool = True,
) -> List[Dict]:
    """
    检测并合并跨页表格（支持连续多页跨页）

    Args:
        merger: CrossPageTableMerger 实例
        tables: 表格列表
        pdf_path: PDF文件路径
        output_dir: 输出目录
        is_valid_table_func: 验证表格有效性的函数（可选）
        save_images: 是否保存合并后的表格图片

    Returns:
        合并后的表格列表
    """
    if len(tables) <= 1:
        return tables

    merged_tables = []
    skip_indices = set()

    i = 0
    while i < len(tables):
        if i in skip_indices:
            i += 1
            continue

        # 查找从当前表格开始的连续跨页表格链
        cross_page_chain = [tables[i]]
        j = i + 1

        while j < len(tables):
            # 检查当前链的最后一个表格和下一个表格是否跨页
            if merger.detector.is_cross_page_table(cross_page_chain[-1], tables[j], pdf_path):
                cross_page_chain.append(tables[j])
                skip_indices.add(j)
                j += 1
            else:
                break

        # 如果找到跨页表格链（长度>1），合并它们
        if len(cross_page_chain) > 1:
            merger.logger.info(
                f"检测到跨页表格: 页{cross_page_chain[0]['page']}-{cross_page_chain[-1]['page']}"
            )

            # 收集所有表格的图片路径和ID
            image_paths = [t["image_path"] for t in cross_page_chain]
            table_ids = [t["id"] for t in cross_page_chain]

            # 只有需要保存图片时才合并图片
            merged_image_path = None
            if save_images and output_dir and all(image_paths):
                merged_image_path = merger.merge_multiple_table_images(
                    image_paths, output_dir, f"merged_table_{'_'.join(map(str, table_ids))}"
                )

            # 计算总行数
            total_rows = sum(t.get("row_count", 0) for t in cross_page_chain)

            merged_table = {
                "id": cross_page_chain[0]["id"],
                "page": f"{cross_page_chain[0]['page']}-{cross_page_chain[-1]['page']}",
                "bbox": cross_page_chain[0]["bbox"],
                "image_path": merged_image_path,
                "is_cross_page": True,
                "merged_from": table_ids,
                "col_count": cross_page_chain[0].get("col_count", 0),
                "row_count": total_rows,
                "page_count": len(cross_page_chain),
                "original_image_paths": image_paths,  # 保存原始图片路径用于识别
                "original_tables": cross_page_chain,  # 保存原始表格信息
            }

            merged_tables.append(merged_table)
        else:
            # 单页表格，需要再次验证（严格模式）
            table = cross_page_chain[0]

            # 对单页表格使用严格验证：必须有2列以上
            if is_valid_table_func:
                if is_valid_table_func(
                    table.get("table_data"),
                    table.get("col_count", 0),
                    table.get("row_count", 0),
                    table.get("bbox"),
                    strict_mode=True,  # 严格模式
                ):
                    merged_tables.append(table)
                else:
                    merger.logger.info(
                        f"  ⚠️ 过滤单页小表格: 第{table['page']}页表格{table['id']} "
                        f"({table.get('col_count', 0)}列×{table.get('row_count', 0)}行)"
                    )
            else:
                # 如果没有提供验证函数，直接添加
                merged_tables.append(table)

        i += 1

    return merged_tables
