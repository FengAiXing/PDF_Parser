from typing import Any, Tuple


def merge_two_rows(merger: Any, row1: str, row2: str) -> Tuple[bool, str]:
    """
    尝试合并两行（仅用于上一页最后一行与下一页第一行）。
    返回 (是否合并, 合并后的行)。
    """
    self = merger

    def fmt_td(attrs: str, content: str) -> str:
        attrs_clean = attrs.strip()
        prefix = f" {attrs_clean}" if attrs_clean else ""
        return f"<td{prefix}>{content}</td>"

    original_has_key = self.has_key_column_values(row1)
    should_merge, merged = self.should_merge_rows(row1, row2, original_has_key, has_next_new_row=False)
    return should_merge, (merged if should_merge else row1)

