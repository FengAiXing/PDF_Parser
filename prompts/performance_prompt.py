"""
业绩提取提示词生成器
用于生成单个业绩表格的AI提取提示词
"""

from typing import Dict, List, Any


def generate_single_performance_prompt(
    table_var: Dict[str, Any],
    performance_var_name: str,
    clauses: List[str],
    candidate_names: Dict[int, str] = None
) -> str:
    """
    为单个业绩表格变量生成业绩提取提示词
    
    Args:
        table_var: 业绩表格变量
        performance_var_name: 业绩变量名
        clauses: 业绩相关条款
        candidate_names: 候选人名称字典
        
    Returns:
        str: 业绩提取提示词
    """
    table_var_name = table_var.get('variable_name', '')
    table_var_content = table_var.get('variable_value', '')
    
    # 从变量名中提取排名信息
    ranking = table_var_name.split('业绩表')[0] if '业绩表' in table_var_name else '投标人'
    
    # 构建候选人信息
    candidate_info = ""
    if candidate_names:
        candidate_info = f"\n## 候选人信息\n"
        for rank, name in candidate_names.items():
            candidate_info += f"- 第{rank}名: {name}\n"
    
    # 构建业绩条款
    clauses_text = ""
    if clauses:
        clauses_text = "\n## 业绩相关条款\n"
        for i, clause in enumerate(clauses, 1):
            clauses_text += f"{i}. {clause}\n"
    
    # 业绩提取不需要投标人要求
    requirements_text = ""
    
    prompt = f"""你是一个专业的招投标文件分析专家。请从投标文件的业绩部分内容中提取指定的业绩信息。

## 任务说明

你需要从投标文件的业绩部分内容中提取以下信息：

## 目标变量

**要提取的变量名**: {performance_var_name}
-下面的业绩表格变量中列出了单个的业绩大致信息，你需要根据表格中的信息去文本中提取对应的业绩信息
-表格变量中的信息与实际的合同信息可能会有所不同，你应该结合表格中多个列的数据来判断哪一个合同是符合表格中要求的业绩
**业绩表格变量**: {table_var_content}

{clauses_text}

## 提取要求

1. **完整性**: 提取所有可识别的业绩信息，不要遗漏任何重要细节
2. **准确性**: 确保提取的信息与原始内容完全一致
3. **结构化**: 按照标准格式组织提取的信息
4. **详细性**: 尽可能详细地描述每个业绩项目

## 输出格式

请按照以下JSON数组格式输出提取结果（即使只有一个业绩也要用数组格式）：

```json
[
  {{
    "variable_name": "{performance_var_name}",
    "variable_value": "业绩合同名称：XXX\\n甲方名称：XXX\\n合同签订日期：XXXX年XX月XX日\\n合同竣工日期：XXXX年XX月XX日",
    "reference_source": {{
      "source_url": "",
      "evidence_text": "",
      "pages": "1",
      "file_type": ""
    }}
  }}
]
```

## 变量值格式要求

variable_value 字段应该按照以下格式组织业绩信息（只包含这五个字段）：

1. **业绩合同名称**：
   - **优先提取规则**：首先在合同、中标通知书或协议书中查找明确写出的"项目名称"、"工程名称"、"建设项目名称"等字段，并按原文逐字提取
   - **备用规则**：如果上述文档没有明确标注项目名称，则直接使用传入的**业绩表格变量**中的项目名称作为项目名称
   - **验证要求**：提取的合同名称应该和传入的**业绩表格变量**中的项目名称几乎相同，如果差异较大，需要重新检查提取是否正确
   - **严禁事项**：严禁把"合同名称"、"协议名称"、"封面标题"等文件标题当作项目名称
   - **格式要求**：提取结果必须与原文保持一致，不得增删字符或留额外空格，确保提取完整的项目名称，不要遗漏、简化和修改
2. **甲方名称**：从合同中提取甲方名称或委托人名称，确保提取完整的名称，正确区分甲方和乙方，不要遗漏、简化和修改
3. **合同签订日期**：从合同或协议中提取
4. **合同竣工日期**：从验收单或验收证明中提取竣工日期，一般在验收单或者验收证明之类的位置查找，如果没有找到就留空

**提取格式示例：**
业绩合同名称：XX市XX路道路工程施工合同
甲方名称：XX市城市建设投资有限公司
合同签订日期：2023年3月15日
合同竣工日期：2024年6月20日

每项信息用换行符（\n）分隔，确保信息清晰易读，如果未提取到该项信息，则该项信息留空，但是抬头要给出来。

**⚠️ 重要格式要求：**
- 同一行中的文本不要添加换行的br标签
- 例如：襄樊泽东化工有限责任公司应该保持在一行，不要换行为"襄樊泽东化<br>工有限责任<br>公司"
- 所有文本内容应该保持原始格式，不要人为添加HTML换行标签

## 注意事项

1. 仔细分析投标文件业绩部分的内容，确保理解所有数据
2. 如果某些信息不明确，请根据上下文合理推断
3. 保持信息的原始准确性，不要添加原始内容中没有的信息
4. 文本内容中业绩开始的地方是合同相关的内容，结束的地方是下一个合同或者下一个章节，单个合同文本可能比较长，你需要根据这个特点去提取业绩信息

请开始分析以下投标文件的内容，提取相关信息：

## 文件内容：
$content

请严格按照上述文件内容进行信息提取，不得编造或使用其他文档的信息。"""

    return prompt

