"""
业绩得分提取提示词生成器
用于生成提取指定排名业绩得分的AI提示词
"""


def generate_performance_score_prompt(
    rank_label: str,
    evaluation_result: str,
    review_card_score: str,
    business_standard: str,
    business_score_table: str
) -> str:
    """
    生成提取业绩得分的提示词
    
    Args:
        rank_label: 排名标签（如"第一名"、"第二名"）
        evaluation_result: 评审结果内容
        review_card_score: 复核卡得分内容
        business_standard: 商务评分标准内容
        business_score_table: 商务部分评分表内容
        
    Returns:
        str: 生成的提示词
    """
    prompt = f"""
你是一个专业的招投标评分系统助手。请根据提供的评分依据，计算指定排名的业绩得分。

## 任务说明
根据【评审结果】【复核卡得分】【商务评分标准】【商务部分评分表】计算{rank_label}的业绩得分。

## 评分规则
1. 优先级：【复核卡得分】 > 【商务评分标准】 + 【商务部分评分表】
2. 业绩得分计算：
   - 如果评分表分值为0，则得0分
   - 如果评分表分值为非零，则一律返回2分（忽略X值等复杂规则）
   - 只返回整数，不返回任何文字说明（只能是 0 或 2）

## 输入数据

### 【评审结果】
```
{evaluation_result}
```

### 【复核卡得分】
```
{review_card_score}
```

### 【商务评分标准】
```
{business_standard}
```

### 【商务部分评分表】
```
{business_score_table}
```

## 输出要求
请直接返回业绩得分的整数：0 或 2（二选一）
只返回整数，不要任何文字说明
"""
    return prompt

