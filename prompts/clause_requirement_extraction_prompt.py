"""
条款要求提取提示词生成器
用于从投标人要求中提取对应的条款要求
"""

from typing import Dict, List, Any


def build_clause_requirement_extraction_prompt(
    clause_analysis: Dict[str, Any], 
    bidder_requirements: str
) -> str:
    """
    构建条款要求提取的提示词
    
    Args:
        clause_analysis: 条款分析结果
        bidder_requirements: 投标人要求内容
        
    Returns:
        str: 构建的提示词
    """
    # 构建分析说明
    analysis_notes = []
    if clause_analysis['has_performance']:
        performance_clauses = ', '.join(clause_analysis['performance_clauses'])
        analysis_notes.append(f"- 检测到'业绩'相关条款：{performance_clauses}")
    if clause_analysis['has_qualification']:
        qualification_clauses = ', '.join(clause_analysis['qualification_clauses'])
        analysis_notes.append(f"- 检测到'资质'相关条款：{qualification_clauses}")
    if clause_analysis['has_other']:
        other_clauses = ', '.join(clause_analysis['other_clauses'])
        analysis_notes.append(f"- 其他条款：{other_clauses}")
    
    analysis_text = "\n".join(analysis_notes) if analysis_notes else "- 未检测到相关条款"
    
    prompt = f"""你是一个专业的招投标文件分析专家。请根据条款类型分析结果，从投标人要求中提取对应的条款要求。

## 条款类型分析结果

{analysis_text}

## 提取任务

请根据上述分析结果，从投标人要求中提取以下内容：

1. **业绩条款要求**：如果检测到'业绩'相关条款，请提取与业绩相关的要求内容
2. **资质条款要求**：如果检测到'资质'相关条款，请提取与资质相关的要求内容  
3. **其他条款要求**：提取除业绩和资质之外的其他条款要求

## 提取要求

1. **准确性**：严格按照投标人要求内容进行提取，不得编造、遗漏或混淆
2. **完整性**：确保提取的内容完整，不要遗漏重要信息
3. **分类清晰**：正确区分业绩、资质和其他条款要求
4. **保持原意**：保持原始内容的准确性和完整性

## 输出格式

请按照以下JSON格式输出提取结果：

```json
{{
  "performance_requirements": "业绩相关的要求内容（如果没有则返回空字符串）",
  "qualification_requirements": "资质相关的要求内容（如果没有则返回空字符串）",
  "other_requirements": "其他条款的要求内容",
  "extraction_notes": "提取过程中的说明或注意事项"
}}
```

## 注意事项

1. 仔细分析投标人要求内容，确保理解所有条款要求
2. 如果某些信息不明确，请根据上下文合理推断
3. 保持信息的原始准确性，不要添加原始内容中没有的信息
4. 如果某个类型的条款不存在，对应的字段应返回空字符串

请开始分析以下投标文件的内容，提取相关信息：

## 文件内容：
$content

请严格按照上述文件内容进行信息提取，不得编造或使用其他文档的信息。"""

    return prompt

