"""
候选人表格过滤提示词生成器
用于生成过滤候选人表格并添加单位的AI提示词
"""


def generate_candidate_filter_with_units_prompt(
    score_summary: str, 
    count: int, 
    opening_record: str = "",
    original_count: int = None
) -> str:
    """
    生成过滤候选人表格并添加单位的提示词
    
    Args:
        score_summary: 中标候选人得分汇总情况内容（HTML表格）
        count: 需要保留的候选人数量
        opening_record: 开标记录表格内容（用于获取投标报价单位）
        original_count: 原始表格中的候选人数量（可选）
        
    Returns:
        str: 生成的提示词
    """
    warning_text = ""
    if original_count is not None and original_count < count:
        warning_text = f"\n**⚠️ 重要提示：原始表格中只有{original_count}名候选人，少于推荐的{count}名，请仔细检查原始表格内容，确保已经提取了所有可用的候选人信息。**\n"
    
    prompt = f"""
请根据以下中标候选人得分汇总表格，保留前{count}名候选人，去除多余的候选人，并根据开标记录表格中的单位信息添加投标报价单位。

原始表格内容：
{score_summary}

开标记录表格（用于获取投标报价单位信息）：
{opening_record}
{warning_text}
要求：
1. **重要：必须保留前{count}名候选人（按排名顺序）**
2. 如果原始表格中候选人数量少于{count}名，请仔细检查原始表格内容，确保已经提取了所有可用的候选人信息
3. 如果原始表格确实只有较少候选人但文档中提到应该有{count}名候选人，请保持原始表格不变（这种情况可能说明文档其他位置还有候选人信息未提取）
4. 保持原有的HTML表格结构（<table>、<tr>、<td>标签）
5. 保持表头行不变
6. 只保留前{count}行数据（不包括表头），但如果原始表格数据行少于{count}行，则保留所有数据行
7. 检查表头中的"投标报价"和"修正后报价"列的单位处理：
   - 首先检查这些列的数据单元格中是否已经包含单位
   - 判断标准：如果数值中包含中文单位字符（如：元、万元、千元、亿、万、千、吨、千克、米、平方米等），则认为已有单位
   - 如果数据单元格中已经有单位，则表头不需要添加单位，保持原样
   - 如果数据单元格中没有单位（纯数字格式），则从开标记录表格中提取单位并添加到表头
   - 从开标记录表格中提取的单位应该是简洁的，如：元、万元、元/千克等，不要包含"含税"等额外解释
   - 如果开标记录表格中没有明确的单位信息，则保持原样
   - 单位添加格式：将"投标报价"改为"投标报价（万元）"这样的格式
   - 重要：避免重复添加单位，确保不会出现"投标报价（万元）"而数据是"123万元"的情况
8. 返回完整的HTML表格格式

请直接返回处理后的HTML表格，不要添加任何其他文字说明。
"""
    return prompt


def generate_candidate_filter_prompt(score_summary: str, count: int) -> str:
    """
    生成过滤候选人表格的提示词（不添加单位）
    
    Args:
        score_summary: 中标候选人得分汇总情况内容（HTML表格）
        count: 需要保留的候选人数量
        
    Returns:
        str: 生成的提示词
    """
    prompt = f"""
请根据以下中标候选人得分汇总表格，保留前{count}名候选人，去除多余的候选人，但保持原有的HTML表格格式。

原始表格内容：
{score_summary}

要求：
1. 只保留前{count}名候选人（按排名顺序）
2. 保持原有的HTML表格结构（<table>、<tr>、<td>标签）
3. 保持表头行不变
4. 只保留前{count}行数据（不包括表头）
5. 如果候选人数量少于{count}，则保持原表格不变
6. 返回完整的HTML表格格式

请直接返回处理后的HTML表格，不要添加任何其他文字说明。
"""
    return prompt

