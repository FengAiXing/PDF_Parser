"""
资质提取提示词生成器
用于生成资质相关信息的AI提取提示词
"""

from typing import Dict, List, Any
from .prompt_utils import get_rank_name


def generate_qualification_prompt(
    candidate_count: int,
    clauses: List[str],
    qualification_requirements: str,
    candidate_names: Dict[int, str] = None,
    target_ranking: str = None
) -> str:
    """生成资质专用提取提示词
    
    Args:
        candidate_count: 候选人总数
        clauses: 条款列表
        qualification_requirements: 资质要求
        candidate_names: 候选人名称字典
        target_ranking: 目标排名（如"第一名"、"第二名"），如果提供，只提取该排名的资质
    """
    
    # 生成候选人名称说明
    candidate_names_text = ""
    if candidate_names:
        candidate_names_text = "\n**各候选人名称：**\n"
        for rank, name in candidate_names.items():
            rank_name = get_rank_name(rank)
            candidate_names_text += f"- {rank_name}：{name}\n"
    
    # 格式化条款
    clauses_text = "\n".join([f"- {clause}" for clause in clauses])
    
    # 生成变量名示例（使用第一个条款作为示例）
    example_clause = clauses[0] if clauses else "资质"
    
    # 如果指定了目标排名，只生成该排名的变量名示例
    if target_ranking:
        example_var_names = f"- {target_ranking}{example_clause}"
        target_ranking_instruction = f"\n**重要提示：当前处理的文件是{target_ranking}的投标文件，请只提取{target_ranking}的资质信息，不要提取其他排名的资质。**"
    else:
        example_var_names = "\n".join([
            f"- 第{i}名{example_clause}" for i in range(1, min(candidate_count + 1, 4))
        ])
        target_ranking_instruction = ""
    
    prompt = f"""## 一、角色定义
你是一位经验丰富的评标专家，专门负责提取和分析候选人的资质信息。

## 二、任务说明
请仔细分析以下候选人投标文件内容，准确提取**资质相关信息**。
所有信息必须严格依据文件内容，不得自行编造或补充未提及内容。

## 三、文件类型特定指导
当前处理的文件类型：**candidate_bid_files（候选人投标文件）**

本次招标项目共有 {candidate_count} 名中标候选人。
{candidate_names_text}{target_ranking_instruction}

## 四、资质提取要求

**需要提取的资质条款：**
{clauses_text}

**资质条款要求（作为判断依据）：**
{qualification_requirements if qualification_requirements else "未提供"}

**资质提取的关键要求：**
1. **从资质条款要求中判断**：首先从"资质条款要求"这个变量中判断对投标人的资质要求是什么,注意安全许可证不属于资质相关信息，不要提取
   - **重要**："资质条款要求"是针对**职位**的要求（如"监理工程师"、"项目经理"等），不是针对特定人员姓名的要求
   - **不要将人员姓名当作资质要求**：如果"资质条款要求"中提到了人员姓名（如"赵政光"），这是示例或说明，不是要求查找该特定人员的资质
   - **应该提取该职位所有相关人员的资质**：根据职位要求，提取文件中该职位所有人员的资质证书，而不是只查找特定人员的资质
2. **根据要求提取**：根据资质条款要求中描述的内容，从文件中提取满足对应要求的资质
   - **重要**：如果文件中存在相关资质信息，即使不完全符合要求，也要提取出来（按照标准格式），并在evidence_text中说明情况
   - **只有完全找不到任何相关资质信息时，才将variable_value留空**
   - 不要因为资质不完全符合要求就返回空值，应该提取找到的资质信息
3. **严格按照格式**：必须按照以下格式提取

**资质信息提取格式（必须严格遵守）：**
```
资质名称：XXX
如果有等级，还需要提取等级，格式为：等级：XXX
资质编号：XXX
```

**特别说明：**
- 如果有多个资质，每个资质都按照上述格式提取，用换行分隔
- 提取资质名称和资质编号，不要遗漏、简化和修改，也不要编造
- 确保从投标文件第二部分 商务部分 第七章资格审查资料中查找
- 优先提取投标人基本情况表中的资质证书，然后根据资质条款要求中的要求提取其他资质证书

## 五、提取规则

1. **准确性原则**
   - 所有信息必须来自原文，不得编造
   - 资质名称、等级、编号必须完全准确
   - 如果某项信息不明确，请如实说明

2. **完整性原则**
   - 必须提取所有相关资质
   - 每个资质的信息应尽可能完整

3. **区分原则**
   - 请明确区分每个候选人的资质
   - 确保不要将A候选人的资质误提取为B候选人的资质

4. **判断原则**
   - 根据"资质条款要求"中的条件判断资质是否符合要求
   - **重要**：即使资质不完全符合要求，只要文件中存在相关资质信息，也要提取出来
   - 提取时需要包含完整的资质描述（资质名称、等级、编号）
   - **只有完全找不到任何相关资质信息时，才将variable_value留空**

## 六、输出格式

请严格按照JSON数组格式输出，每个变量是一个独立的对象：

```json
[
  {{
    "variable_name": "{target_ranking if target_ranking else '第一名'}{example_clause}",
    "variable_value": "资质名称：建筑工程施工总承包\n资质编号：A1234567890\n资质名称：市政公用工程施工总承包\n资质编号：B9876543210",
    "reference_source": {{
      "source_url": "文件URL",
      "evidence_text": "第二部分 商务部分 第七章资格审查资料 ...相关内容预览...",
      "pages": "1, 2, 3",
      "file_type": "candidate_bid_files"
    }}
  }}
]
```

**字段说明：**
- `variable_name`: 变量名称（必须使用完整条款名称，格式：第几名+条款名称，如"第一名资质要求"、"第二名安全生产许可证"）
- `variable_value`: 提取的变量值
- `reference_source`: 引用来源信息
  - `source_url`: 文件URL地址
  - `evidence_text`: 证据文本（包含章节和内容预览，50-100字）
  - `pages`: 信息所在页码（多个页码用英文逗号分隔，如 "1, 2, 3"）
  - `file_type`: 固定为 "candidate_bid_files"

**注意事项：**
- 必须严格按照"资质名称：XXX\n资质编号：XXX"的格式
- 如果有多个资质，每个资质都按此格式，用换行符（\n）分隔
- 不要添加序号、分号或其他格式
- **变量名必须使用完整条款名称**：
  - 条款名称：{example_clause}
  - 变量名格式：第几名+条款名称
  - 示例变量名：
{example_var_names}
  - 例如：如果条款是"资质要求"，则变量名为"{target_ranking if target_ranking else '第一名'}资质要求"{'（只提取当前文件对应的排名）' if target_ranking else '、"第二名资质要求"等'}
- 确保JSON格式正确，必须是数组格式

请开始分析以下投标文件的内容，提取相关信息：

## 文件内容：
$content
请严格按照上述文件内容进行信息提取，不得编造或使用其他文档的信息。
"""
    
    return prompt

