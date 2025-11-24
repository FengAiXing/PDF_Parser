"""
提示词生成公共辅助函数
提供通用的辅助函数供各个提示词生成模块使用
"""

import json
from typing import Dict, List, Any


def get_rank_name(rank: int) -> str:
    """获取排名名称"""
    rank_names = {
        1: "第一名",
        2: "第二名",
        3: "第三名",
        4: "第四名",
        5: "第五名",
        6: "第六名",
        7: "第七名",
        8: "第八名",
        9: "第九名",
        10: "第十名"
    }
    return rank_names.get(rank, f"第{rank}名")


def parse_clauses(clause_text: str, separator: str = None) -> list:
    """
    解析条款文本，返回条款列表
    
    Args:
        clause_text: 条款文本
        separator: 分隔符，如果为None则自动检测
        
    Returns:
        List[str]: 条款列表
    """
    if not clause_text:
        return []
    
    clauses = []
    
    # 先尝试按换行符分割
    lines = clause_text.split('\n')
    
    # 如果只有一行，尝试按指定分隔符或自动检测分隔符分割
    if len(lines) == 1:
        if separator:
            lines = clause_text.split(separator)
        else:
            # 尝试多种分隔符：中文逗号、英文逗号、顿号、分号
            for sep in ['、', '，', ',', '；', ';']:
                if sep in clause_text:
                    lines = clause_text.split(sep)
                    break
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#'):
            clauses.append(line)
    
    return clauses


def has_multiple_positions(clause_text: str) -> bool:
    """
    检测条款是否包含多个职位（用'、'分隔）
    
    Args:
        clause_text: 条款文本
        
    Returns:
        bool: 如果包含多个职位返回True，否则返回False
    """
    # 定义所有可能的职位关键词
    position_keywords = [
        '项目经理', '设计负责人', '施工负责人', '技术负责人', 
        '安全负责人', '质量负责人', '项目负责人', '总工程师', 
        '总监理', '工程师', '负责人'
    ]
    
    # 检查是否包含'、'分隔符
    if '、' not in clause_text:
        return False
    
    # 检查是否包含职位关键词
    has_position = any(keyword in clause_text for keyword in position_keywords)
    
    # 如果包含职位关键词且包含'、'分隔符，则认为是多职位条款
    return has_position


def format_variables_for_prompt(variables: List[Dict[str, Any]]) -> str:
    """
    将变量列表格式化为提示词所需的JSON字符串
    
    Args:
        variables: 变量列表
        
    Returns:
        str: 格式化后的JSON字符串
    """
    # 简化变量格式，只保留关键字段
    simplified_vars = []
    for var in variables:
        simplified_vars.append({
            "variable_name": var.get("variable_name", ""),
            "variable_value": var.get("variable_value", ""),
            "reference_source": var.get("reference_source", {})
        })
    
    return json.dumps(simplified_vars, ensure_ascii=False, indent=2)

