"""
业绩提取提示词生成器
用于从业绩文本中提取业绩汇总表和单个业绩信息
"""


def build_performance_extraction_prompt(performance_text: str, ranking: str, clause_name: str = "业绩") -> str:
    """
    构建业绩提取的AI提示词
    
    Args:
        performance_text: 业绩文本内容
        ranking: 排名信息
        clause_name: 条款名称（如"业绩要求"、"投标人近年类似项目业绩"等）
        
    Returns:
        str: 构建的提示词
    """
    return f"""
你是一个专业的招投标文件分析专家。请从以下业绩文本中提取业绩汇总表和单个业绩信息。

## 任务要求

### 1. 提取业绩汇总表
- 从文本中找到最完整的业绩汇总表
- 表格应包含所有业绩项目的汇总信息
- 使用HTML表格格式输出（table、tr、td标签）
- 变量名：{ranking}{clause_name}汇总表

### 2. 提取单个业绩
- 将汇总表中的每个业绩项目单独提取
- 每个业绩包含完整的表格结构（表头+数据）
- 使用HTML表格格式输出
- 变量名：{ranking}{clause_name}表1、{ranking}{clause_name}表2、{ranking}{clause_name}表3...（按顺序编号）

### 3. 表格格式要求
- 必须使用标准的HTML表格标签：<table>、<tr>、<td>
- 表格要有清晰的表头行
- 数据行要完整，包含所有相关信息
- 保持原始数据的完整性和准确性

### 4. 提取规则
- 优先选择包含"汇总表"、"情况表"等关键词的表格
- 如果表格不完整，选择最接近完整格式的表格
- 确保每个业绩项目都有完整的项目信息
- 保持原始文本中的数据和格式

## 输出格式

请严格按照以下JSON格式输出：

```json
{{
  "performance_summary_table": {{
    "variable_name": "{ranking}{clause_name}汇总表",
    "table_content": "<table><tr><td>表头1</td><td>表头2</td></tr><tr><td>数据1</td><td>数据2</td></tr></table>"
  }},
  "individual_performances": [
    {{
      "variable_name": "{ranking}{clause_name}表1",
      "table_content": "<table><tr><td>表头1</td><td>表头2</td></tr><tr><td>数据1</td><td>数据2</td></tr></table>"
    }},
    {{
      "variable_name": "{ranking}{clause_name}表2", 
      "table_content": "<table><tr><td>表头1</td><td>表头2</td></tr><tr><td>数据1</td><td>数据2</td></tr></table>"
    }}
  ]
}}
```

## 重要提醒

1. **表格完整性**：确保每个表格都包含完整的表头和数据行
2. **数据准确性**：严格按照原始文本提取，不要修改或遗漏数据
3. **格式标准**：使用标准的HTML表格标签，确保格式正确
4. **变量命名**：严格按照要求的格式命名变量
5. **JSON格式**：确保返回的是有效的JSON格式
6. **文本格式要求**：表格中单个格子中的信息不要加br标签，例如：襄樊泽东化工有限责任公司应该保持在一行，不要换行为"襄樊泽东化<br>工有限责任<br>公司"

请开始分析以下投标文件的内容，提取相关信息：

## 文件内容：
{performance_text}
请严格按照上述文件内容进行信息提取，不得编造或使用其他文档的信息。
"""

