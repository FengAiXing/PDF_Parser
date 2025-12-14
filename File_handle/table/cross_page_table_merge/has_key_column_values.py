from typing import Any
import re


def has_key_column_values(merger: Any, row_html: str) -> bool:
    """
    检查行的关键列（第一列，序号列）是否有值。
    """
    cells = re.findall(r'<td([^>]*)>(.*?)</td>', row_html, re.DOTALL | re.IGNORECASE)

    if not cells:
        return False

    attrs, content = cells[0]
    return bool(content.strip())

