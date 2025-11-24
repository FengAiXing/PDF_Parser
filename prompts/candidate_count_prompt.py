"""
推荐中标候选人数判断提示词生成器
用于生成判断推荐中标候选人数量的AI提示词
"""


def generate_candidate_count_prompt(review_results: str, candidates_rule: str) -> str:
    """
    生成判断推荐中标候选人数量的提示词
    
    Args:
        review_results: 评审结果内容
        candidates_rule: 推荐中标候选人数规则
        
    Returns:
        str: 生成的提示词
    """
    prompt = f"""
请根据以下评审结果和推荐规则，判断应该推荐的中标候选人数。

评审结果：
{review_results}

推荐中标候选人数规则：
{candidates_rule}

请仔细分析评审结果中的投标人总数，并结合推荐规则中的条件，判断应该推荐多少个中标候选人。

请只返回一个数字，不要包含任何其他文字。
"""
    return prompt

