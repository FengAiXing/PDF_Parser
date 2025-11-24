"""
多职位提取提示词生成器（资格评审标准）
用于生成包含多个职位（用'、'分隔）的条款信息的AI提取提示词
"""

from typing import Dict, List, Any
from .prompt_utils import get_rank_name


def generate_position_prompt(
    candidate_count: int,
    clauses: List[str],
    other_requirements: str,
    candidate_names: Dict[int, str] = None,
    target_ranking: str = None
) -> str:
    """
    生成多职位条款提取提示词
    
    Args:
        candidate_count: 候选人总数
        clauses: 多职位条款列表（包含'、'分隔的多个职位）
        other_requirements: 其他条款要求
        candidate_names: 候选人名称字典
        target_ranking: 目标排名（如"第一名"、"第二名"），如果提供，只提取该排名的信息
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
    
    # 如果指定了目标排名，只生成该排名的变量名示例
    if target_ranking:
        example_clause = clauses[0] if clauses else "项目经理、设计负责人、施工负责人"
        example_var_names = f"- {target_ranking}{example_clause}"
        target_ranking_instruction = f"\n**重要提示：当前处理的文件是{target_ranking}的投标文件，请只提取{target_ranking}的信息，不要提取其他排名的信息。**"
    else:
        example_clause = clauses[0] if clauses else "项目经理、设计负责人、施工负责人"
        example_var_names = "\n".join([
            f"- 第{i}名{example_clause}" for i in range(1, min(candidate_count + 1, 4))
        ])
        target_ranking_instruction = ""
    
    prompt = f"""## 一、角色定义
你是一位经验丰富的评标专家，负责提取和分析候选人投标文件中的职位人员信息。

## 二、任务说明
请仔细分析以下候选人投标文件内容，准确提取**包含多个职位（用'、'分隔）的条款信息**。
所有信息必须严格依据文件内容，不得自行编造或补充未提及内容。

## 三、文件类型特定指导
当前处理的文件类型：**candidate_bid_files（候选人投标文件）**

本次招标项目共有 {candidate_count} 名中标候选人。
{candidate_names_text}{target_ranking_instruction}

## 四、需要提取的条款信息

**⚠️ 重要说明：以下是包含多个职位（用'、'分隔）的条款列表**

**多职位条款：**
{clauses_text}

**其他条款要求（作为判断依据）：**
{other_requirements if other_requirements else "未提供"}

## 五、核心提取要求（⚠️ 极其重要）

### 5.1 职位提取原则
1. **条款中有哪些职位就要提取哪些，不能只提一个**
   - 如果条款是"项目经理、设计负责人、施工负责人"，必须提取这三个职位的信息
   - 不能只提取其中一个或两个职位

2. **每个职位占一个位置**
   - 除非是一个人兼职多个职位，否则每个职位都要单独提取
   - 如果条款中有3个职位，必须提取3个职位的信息

3. **兼任职位处理**
   - 如果一个人同时兼任多个职位，这一个人也算占了每一个兼任的职位
   - 例如：如果条款是"项目经理、设计负责人、施工负责人"，而某个人同时担任"项目经理"和"设计负责人"，那么：
     - 这个人占用了"项目经理"的位置
     - 这个人也占用了"设计负责人"的位置
     - 还需要另外一个人担任"施工负责人"

4. **优先提取规则**
   - 靠前的职位优先提取
   - 如果一个人兼任多个职位，优先提取靠前的职位组合

## 六、提取格式要求（⚠️ 必须严格遵守）

### 6.1 单个职位格式
如果某个职位只有一个人担任，格式为：
```
职位名称：设计负责人
姓名：XXX
证书名称：XXX
证书编号：XXX
```

### 6.2 多个职位格式
如果条款中有多个职位，每个职位单独一段，用换行符（\n）分隔：
```
职位名称：项目经理
姓名：XXX
证书名称：XXX
证书编号：XXX
职位名称：设计负责人
姓名：XXX
证书名称：XXX
证书编号：XXX
职位名称：施工负责人
姓名：XXX
证书名称：XXX
证书编号：XXX
```

### 6.3 一个人兼任多个职位格式
如果一个人同时兼任多个职位（且这些职位在条款中靠前），格式为：
```
职位名称：项目经理、设计负责人
姓名：XXX
证书名称：XXX
证书编号：XXX
职位名称：施工负责人
姓名：XXX
证书名称：XXX
证书编号：XXX
```

**重要说明：**
- 职位名称中多个职位用顿号（、）连接
- 每个职位信息单独一段，用换行符（\n）分隔
- 确保条款中列出的所有职位都被提取，不要遗漏

## 七、提取规则

1. **准确性原则**
   - 所有信息必须来自原文，不得编造
   - 如实提取，保持原文表述
   - 如果信息不完整，请如实提取已有部分

2. **完整性原则**
   - 条款中列出的每个职位都要提取
   - 不要遗漏任何一个职位

3. **区分原则**
   - 请明确区分每个候选人的信息
   - 确保不要混淆不同候选人的信息

4. **判断原则**
   - 根据"其他条款要求"中的条件进行判断
   - 从投标文件第二部分 商务部分 第七章资格审查资料中查找

## 八、输出格式

请严格按照JSON数组格式输出，每个变量是一个独立的对象：

```json
[
  {{
    "variable_name": "{target_ranking if target_ranking else '第一名'}{example_clause}",
    "variable_value": "职位名称：项目经理\\n姓名：XXX\\n证书名称：XXX\\n证书编号：XXX\\n职位名称：设计负责人\\n姓名：XXX\\n证书名称：XXX\\n证书编号：XXX",
    "reference_source": {{
      "file_type": "candidate_bid_files",
      "page_number": "第X页",
      "section": "第二部分 商务部分 第七章资格审查资料",
      "content_preview": "...相关内容预览..."
    }}
  }}
]
```

**字段说明：**
- `variable_name`: 变量名称（由"候选人名次"+"条款名称"组成），变量名中的条款名称要与条款列表中的条款名称完全一致，不要简化和修改
- `variable_value`: 提取的变量值，必须按照上述格式要求组织
- `reference_source`: 引用来源信息
  - `file_type`: 固定为 "candidate_bid_files"
  - `page_number`: 信息所在页码
  - `section`: 信息所在章节
  - `content_preview`: 相关内容预览（50-100字）

**注意事项：**
- **⚠️ 最重要**：条款中列出的所有职位都必须提取，不能遗漏
- **⚠️ 格式要求**：必须严格按照上述格式，职位名称在前，然后是姓名、证书名称、证书编号
- 如果一个人兼任多个职位，职位名称用顿号（、）连接
- 每个职位信息单独一段，用换行符（\n）分隔
- 确保从投标文件第二部分 商务部分 第七章资格审查资料中查找
- 确保JSON格式正确，必须是数组格式
- **变量名必须与候选人排名对应**：{f'当前文件的变量以"{target_ranking}"开头（只提取当前文件对应的排名）' if target_ranking else '第一名的变量以"第一名"开头，第二名的变量以"第二名"开头'}

请开始分析以下投标文件的内容，提取相关信息：

## 文件内容：
$content
请严格按照上述文件内容进行信息提取，不得编造或使用其他文档的信息。
"""
    
    return prompt

