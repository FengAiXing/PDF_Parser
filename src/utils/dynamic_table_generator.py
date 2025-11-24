"""
动态表格生成器 - 共享辅助函数
提供表格生成过程中使用的共享辅助函数
"""

from typing import List, Dict, Any
import re


def _extract_clauses_from_variables(extracted_variables: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    从变量列表中提取资格评审标准和商务评分标准的条款
    
    Args:
        extracted_variables: 变量列表
        
    Returns:
        Dict[str, List[str]]: 包含qualification和business两个键的字典
    """
    import logging
    logger = logging.getLogger(__name__)
    
    clauses = {
        "qualification": [],
        "business": []
    }
    
    # 构建变量映射
    variables_map = {}
    for var in extracted_variables:
        if isinstance(var, dict) and "variable_name" in var:
            variables_map[var["variable_name"]] = var
    
    # 提取资格评审标准
    qualification_var = variables_map.get("资格评审标准")
    if qualification_var:
        qualification_text = qualification_var.get("variable_value", "")
        if qualification_text:
            # 解析条款（可能是用顿号、逗号或分号分隔）
            qualification_clauses = _parse_clauses(qualification_text)
            clauses["qualification"] = qualification_clauses
            logger.info(f"提取到资格评审标准条款 {len(qualification_clauses)} 个: {qualification_clauses}")
        else:
            logger.warning("资格评审标准变量的值为空")
    else:
        logger.warning("未找到资格评审标准变量")
    
    # 提取商务评分标准
    business_var = variables_map.get("商务评分标准")
    if business_var:
        business_text = business_var.get("variable_value", "")
        if business_text:
            # 解析条款（可能是用顿号、逗号或分号分隔）
            business_clauses = _parse_clauses(business_text)
            clauses["business"] = business_clauses
            logger.info(f"提取到商务评分标准条款 {len(business_clauses)} 个: {business_clauses}")
        else:
            logger.warning("商务评分标准变量的值为空")
    else:
        logger.warning("未找到商务评分标准变量")
    
    return clauses


def _parse_clauses(clauses_text: str) -> List[str]:
    """
    解析条款文本，提取条款列表
    
    注意：条款统一使用'|'来分隔
    
    Args:
        clauses_text: 条款文本（使用'|'分隔）
        
    Returns:
        List[str]: 条款列表
    """
    import logging
    import re
    logger = logging.getLogger(__name__)
    
    if not clauses_text:
        return []
    
    # 清理文本：去除HTML标签和多余的空白
    cleaned_text = re.sub(r'<[^>]+>', '', clauses_text)  # 去除HTML标签
    cleaned_text = cleaned_text.strip()
    
    if not cleaned_text:
        return []
    
    # 条款统一使用'|'来分隔
    separator = '|'
    
    clauses = []
    current_text = cleaned_text
    
    # 使用'|'分隔符解析
    if separator in current_text:
        clauses = [clause.strip() for clause in current_text.split(separator) if clause.strip()]
        logger.debug(f"使用分隔符 '{separator}' 解析出 {len(clauses)} 个条款")
    else:
        # 如果没有找到'|'分隔符，返回整个文本作为单个条款
        clauses = [cleaned_text]
        logger.debug(f"未找到'|'分隔符，将整个文本作为一个条款: {cleaned_text[:50]}...")
    
    # 清理每个条款：去除分值范围【X~X】等
    cleaned_clauses = []
    for clause in clauses:
        # 去除分值范围，如【0~6】、【0~4】等
        cleaned = re.sub(r'【[^】]*】', '', clause)
        cleaned = cleaned.strip()
        if cleaned:
            cleaned_clauses.append(cleaned)
    
    logger.debug(f"清理后条款: {cleaned_clauses}")
    return cleaned_clauses


def _get_clause_from_variable_name(var_name: str, candidate_count: int) -> str:
    """
    从变量名中提取条款名称
    
    Args:
        var_name: 变量名（如"第一名业绩要求1"、"第一名投标人近年类似项目业绩2"、"三第一名投标人业绩1"、"分数第一名投标人近年类似项目业绩"）
        candidate_count: 候选人数量
        
    Returns:
        str: 条款名称（如"业绩要求"、"投标人近年类似项目业绩"、"投标人业绩"），如果无法提取则返回空字符串
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # 处理"第X名"开头的变量（商务评分标准，不再使用"三"前缀）
    # 先检查是否是"第X名"开头的变量
    chinese_ranks = ["第一", "第二", "第三", "第四", "第五", "第六"]
    for i, chinese_rank in enumerate(chinese_ranks, 1):
        if i <= candidate_count and var_name.startswith(f"{chinese_rank}名"):
            remaining = var_name[len(f"{chinese_rank}名"):]
            clause = re.sub(r'\d+$', '', remaining)
            logger.debug(f"从'第X名'变量 '{var_name}' 提取条款: '{clause}'")
            return clause
    # 尝试数字排名
    for rank in range(1, candidate_count + 1):
        if var_name.startswith(f"第{rank}名"):
            remaining = var_name[len(f"第{rank}名"):]
            clause = re.sub(r'\d+$', '', remaining)
            logger.debug(f"从'第X名'变量 '{var_name}' 提取条款: '{clause}'")
            return clause
    
    # 处理"分数第X名"开头的变量（商务评分标准的分数变量）
    if var_name.startswith("分数第"):
        # 匹配"分数第X名"模式
        match = re.match(r'分数(第[一二三四五六\d]+名)', var_name)
        if match:
            prefix_len = len(match.group(1)) + 2  # "分数" + "第X名"
            clause = var_name[prefix_len:]
            logger.debug(f"从'分数第X名'变量 '{var_name}' 提取条款: '{clause}'")
            return clause
    
    # 处理普通变量（资格评审标准）
    # 匹配模式：第X名 + 条款名称 + 可选的数字
    chinese_ranks = ["第一", "第二", "第三", "第四", "第五", "第六"]
    
    for i, chinese_rank in enumerate(chinese_ranks, 1):
        if i <= candidate_count and var_name.startswith(f"{chinese_rank}名"):
            # 去掉排名前缀
            remaining = var_name[len(f"{chinese_rank}名"):]
            # 去掉末尾的数字（如果有）
            clause = re.sub(r'\d+$', '', remaining)
            logger.debug(f"从普通变量 '{var_name}' 提取条款: '{clause}'")
            return clause
    
    # 尝试数字排名
    for rank in range(1, candidate_count + 1):
        if var_name.startswith(f"第{rank}名"):
            remaining = var_name[len(f"第{rank}名"):]
            clause = re.sub(r'\d+$', '', remaining)
            logger.debug(f"从数字排名变量 '{var_name}' 提取条款: '{clause}'")
            return clause
    
    logger.debug(f"无法从变量名 '{var_name}' 提取条款名称")
    return ""


def _is_variable_from_qualification(var_name: str, qualification_clauses: List[str], candidate_count: int) -> bool:
    """
    判断变量是否属于资格评审标准
    
    Args:
        var_name: 变量名
        qualification_clauses: 资格评审标准条款列表
        candidate_count: 候选人数量
        
    Returns:
        bool: 如果变量属于资格评审标准则返回True
    """
    import logging
    logger = logging.getLogger(__name__)
    
    clause = _get_clause_from_variable_name(var_name, candidate_count)
    if not clause:
        return False
    
    # 检查条款是否在资格评审标准中
    # 重要：需要精确匹配，避免"投标人业绩"被"投标人业绩要求"误匹配
    for qual_clause in qualification_clauses:
        # 1. 完全匹配（最精确）
        if clause == qual_clause:
            logger.debug(f"完全匹配: 变量 '{var_name}' 的条款 '{clause}' == 资格评审标准条款 '{qual_clause}'")
            return True
        # 2. 变量条款以资格评审标准条款开头（如"投标人业绩要求"匹配"投标人业绩要求1"）
        elif clause.startswith(qual_clause):
            logger.debug(f"前缀匹配: 变量 '{var_name}' 的条款 '{clause}' 以资格评审标准条款 '{qual_clause}' 开头")
            return True
        # 3. 资格评审标准条款以变量条款开头（如"投标人业绩要求"匹配"投标人业绩"）- 需要排除这种情况
        # 注意：这种情况会导致误匹配，例如"投标人业绩"会被"投标人业绩要求"匹配
        # 但我们需要保留这个逻辑，因为有些情况下确实需要（如"业绩要求"匹配"业绩要求1"）
        # 所以添加额外检查：如果变量条款不包含"要求"，而资格评审标准条款包含"要求"，则不匹配
        elif qual_clause.startswith(clause):
            # 如果变量条款不包含"要求"，而资格评审标准条款包含"要求"，则不匹配
            # 例如："投标人业绩" 不应该匹配 "投标人业绩要求"
            if "要求" not in clause and "要求" in qual_clause:
                logger.debug(f"跳过误匹配: 变量 '{var_name}' 的条款 '{clause}' 不包含'要求'，而资格评审标准条款 '{qual_clause}' 包含'要求'，不匹配")
                continue
            logger.debug(f"前缀匹配: 资格评审标准条款 '{qual_clause}' 以变量 '{var_name}' 的条款 '{clause}' 开头")
            return True
    
    return False


def _is_variable_from_business(var_name: str, business_clauses: List[str], candidate_count: int) -> bool:
    """
    判断变量是否属于商务评分标准
    
    Args:
        var_name: 变量名
        business_clauses: 商务评分标准条款列表
        candidate_count: 候选人数量
        
    Returns:
        bool: 如果变量属于商务评分标准则返回True
    """
    import logging
    logger = logging.getLogger(__name__)
    
    clause = _get_clause_from_variable_name(var_name, candidate_count)
    if not clause:
        return False
    
    # 检查条款是否在商务评分标准中
    for bus_clause in business_clauses:
        # 完全匹配或包含匹配（更宽松的匹配）
        if clause == bus_clause:
            logger.debug(f"完全匹配: 变量 '{var_name}' 的条款 '{clause}' == 商务评分标准条款 '{bus_clause}'")
            return True
        elif clause in bus_clause:
            logger.debug(f"✅ 包含匹配: 商务评分标准条款 '{bus_clause}' 包含变量 '{var_name}' 的条款 '{clause}'")
            return True
    
    return False


def _has_position_in_clause(clause_name: str) -> bool:
    """
    判断条款是否包含职位名称
    
    Args:
        clause_name: 条款名称（如"拟派项目经理近年类似业绩"、"项目技术负责人业绩"等）
        
    Returns:
        bool: 如果包含职位名称返回True，否则返回False
    """
    position_keywords = ['项目经理', '工程师', '负责人', '设计负责人', '施工负责人', '技术负责人', '安全负责人']
    return any(keyword in clause_name for keyword in position_keywords)
