"""
评分信息填充提示词生成器
用于生成填充商务部分变量评分信息的AI提示词
"""

from typing import List, Dict, Any
from .prompt_utils import format_variables_for_prompt


def generate_score_enrichment_prompt(
    candidate_variables: List[Dict[str, Any]],
    review_card_score: str,
    business_standard: str,
    business_score_table: str,
    evaluation_result: str,
    rank_label: str = "",
    candidate_name: str = ""
) -> str:
    """
    生成填充评分信息的提示词
    
    Args:
        candidate_variables: 候选人变量列表（只包含商务部分变量，不包含业绩变量）
        review_card_score: 复核卡得分内容
        business_standard: 商务评分标准内容
        business_score_table: 商务部分评分表内容
        evaluation_result: 评审结果内容（包含排名与投标人名称对应关系）
        rank_label: 当前候选人的排名（如"第一名"）
        candidate_name: 当前候选人的具体名称（如"山西斯坦福机电设备有限公司"）
        
    Returns:
        str: 生成的提示词
    """
    candidate_info = ""
    if candidate_name:
        candidate_info = f"\n**⚠️ 重要：本次任务只处理【{candidate_name}】（{rank_label}）的评分，请忽略其他候选人的信息。**"
    else:
        candidate_info = f"\n**⚠️ 重要：本次任务只处理【{rank_label}】的评分，请忽略其他候选人的信息。**"
    
    # 构建候选人标识文本
    candidate_label = rank_label
    if candidate_name:
        candidate_label = f"{rank_label}（{candidate_name}）"
    
    prompt = f"""
你是一个专业的招投标评分系统助手。你需要根据提供的评分依据，为商务部分变量填充评分信息，并计算业绩得分。
{candidate_info}

## 任务说明
你需要：
1. 为【{candidate_label}】的商务部分变量填充评分信息
**⚠️ 关键要求：只处理当前指定的候选人，不要处理其他候选人的评分**
**注意：业绩得分已单独提取，本次任务只处理商务部分变量的评分填充**

## 评分填充规则

### 1. 当前处理的候选人信息
- **当前排名**：{rank_label}
{f"- **当前候选人名称**：{candidate_name}" if candidate_name else ""}
- **重要**：本次任务只处理上述指定的候选人，不要处理其他候选人的评分
- **关键**：变量名中只有"第X名"，但复核卡得分中使用的是具体的投标人公司名称
{f"- **匹配规则**：如果提供了候选人名称，请严格匹配该名称；如果未提供，请从【评审结果】中查找{rank_label}对应的投标人名称" if candidate_name else "- **匹配规则**：请从【评审结果】中查找当前排名对应的投标人名称，确保只处理当前候选人的评分"}

### 2. 优先级原则
- **最高优先级**：【复核卡得分】中的内容为准
- **次级优先级**：如果复核卡得分中没有对应项，则查看【商务评分标准】和【商务部分评分表】

### 3. 复核卡得分优先规则
- 复核卡得分中会明确给出各项的评价，使用具体的投标人公司名称，例如：
  - "业绩1（山西斯坦福机电设备有限公司）：有效，资格业绩不计分；"
  - "业绩2（潍坊博发动力设备有限公司）：有效，计2分；"
  - "质量管理体系（某公司）：有效，得1.0分"
- 你需要：
  1. {"确认当前处理的是【" + candidate_name + "】（" + rank_label + "）" if candidate_name else "通过【评审结果】确认当前处理的是" + rank_label + "对应的公司"}
  2. 在【复核卡得分】中查找该公司对应评分项的评价
  3. 将评价**换行**填入对应的候选人变量值后面
  4. **只处理当前候选人的变量，忽略其他候选人的评分**
- 严格按照复核卡得分中的原文描述填充，不要修改或简化

### 4. 无复核卡得分时的处理
- 当复核卡中不存在对应评分项时，按照以下优先顺序与规则处理：
  1) 使用【商务部分评分表】中**当前候选人**的对应条款分值进行判断；
  2) 结合【商务评分标准】确定具体给分方式。
- **⚠️ 重要：只查看【商务部分评分表】中当前候选人的列，不要查看其他候选人的列**
- 判断"有效/无效"的原则：
  - 如果【商务部分评分表】中**当前候选人**的该条款分值为非零（不为0且不是"/"等空缺），则视为"有效"；
  - 如果分值为0或空缺，视为"无效，得0分"。
- 分数填充：
  - 若有效，使用评分表中显示的数值作为分数，格式为"有效，得X分"；若无效，填"无效，得0分"。
  - **注意：业绩得分已单独提取，本次任务不需要计算业绩得分**

### 5. 填充格式要求
- 在原变量值的**尾部换行**后添加评价
- 格式：原变量值 + "\n" + 评价内容
- 例如：
  ```
  原值：某公司2023年完成XX项目
  填充后：某公司2023年完成XX项目
  有效，计2分；
  ```

### 8. 特殊情况处理
- 如果某个变量在所有来源中都找不到对应的评分信息，保持原值不变
- 如果评价内容有歧义，优先采用复核卡得分中的表述
- 保持JSON格式不变，只修改variable_value字段

---

## 以下是用于处理的数据

### 【评审结果】（包含排名与投标人名称对应关系）
```
{evaluation_result}
```

### 【复核卡得分】：
```
{review_card_score}
```

### 【商务评分标准】：
```
{business_standard}
```

### 【商务部分评分表】：
```
{business_score_table}
```

### 【需要填充的商务变量】（不包含业绩变量）
```json
{format_variables_for_prompt(candidate_variables)}
```

---

## 输出要求

请返回JSON格式的结果：

```json
{{
  "business_variables": [
    {{
      "variable_name": "原变量名称",
      "variable_value": "原值\n有效，得X分 或 无效，得0分",
      "reference_source": {{...}}
    }}
  ]
}}
```

**⚠️ 极其重要的输出要求**：
1. **只返回business_variables字段，不需要返回performance_scores字段**（业绩得分已单独提取）
2. 保持变量的所有字段不变，只修改variable_value
3. 评价内容必须换行添加，使用\n作为换行符
4. 只处理当前候选人的变量，不要处理其他候选人的评分
"""
    return prompt

