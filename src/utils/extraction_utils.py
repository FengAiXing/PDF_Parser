"""
变量提取工具函数模块

本模块提供变量提取过程中的公共辅助函数。
"""

import logging
import json
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def extract_performance_counts_from_variables(
    variables_list: List[Dict[str, Any]], 
    candidate_count: int
) -> Dict[int, int]:
    """
    从变量列表中提取每个候选人的业绩数量
    
    Args:
        variables_list: 变量列表
        candidate_count: 候选人数量
        
    Returns:
        Dict[int, int]: 候选人排名到业绩数量的映射，例如 {1: 3, 2: 5}
    """
    performance_counts = {}
    
    for var in variables_list:
        if isinstance(var, dict) and "variable_name" in var:
            var_name = var["variable_name"]
            # 匹配"第X名业绩数量"
            if "业绩数量" in var_name:
                for i in range(1, candidate_count + 1):
                    rank_name = f"第{['一', '二', '三', '四', '五', '六', '七', '八', '九', '十'][i-1] if i <= 10 else i}名"
                    if var_name == f"{rank_name}业绩数量":
                        try:
                            count = int(var.get("variable_value", "0"))
                            performance_counts[i] = count
                            logger.info(f"提取到{rank_name}的业绩数量: {count}")
                        except (ValueError, TypeError):
                            logger.warning(f"无法解析{rank_name}的业绩数量: {var.get('variable_value')}")
                        break
    
    logger.info(f"共提取到 {len(performance_counts)} 个候选人的业绩数量: {performance_counts}")
    return performance_counts


def extract_performance_table_variables(
    variables_list: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    从变量列表中检测并提取业绩表格变量
    
    业绩表格变量是指包含"业绩表"但不包含"汇总表"的变量。
    
    Args:
        variables_list: 变量列表
        
    Returns:
        List[Dict[str, Any]]: 业绩表格变量列表
    """
    performance_table_variables = []
    
    for var in variables_list:
        if isinstance(var, dict) and "variable_name" in var:
            var_name = var["variable_name"]
            # 检测业绩表格变量（包含"业绩表"但不包含"汇总表"）
            if "业绩表" in var_name and "汇总表" not in var_name:
                performance_table_variables.append(var)
                logger.info(f"检测到业绩表格变量: {var_name}")
    
    logger.info(f"从variables_list中检测到 {len(performance_table_variables)} 个业绩表格变量")
    return performance_table_variables


def parse_llm_json_result(
    result: str, 
    task_type: str = "", 
    ranking: str = ""
) -> Optional[List[Dict[str, Any]]]:
    """
    解析LLM返回的JSON结果，清理markdown标记并返回变量列表
    
    Args:
        result: LLM返回的原始结果字符串
        task_type: 任务类型（用于日志）
        ranking: 排名（用于日志）
        
    Returns:
        Optional[List[Dict[str, Any]]]: 解析后的变量列表，失败时返回None
    """
    if not result or not result.strip():
        logger.warning(f"[{task_type}] {ranking} LLM返回结果为空")
        return None
    
    try:
        # 清理markdown标记
        clean_result = result.strip()
        if clean_result.startswith("```json"):
            clean_result = clean_result[7:]
        elif clean_result.startswith("```"):
            clean_result = clean_result[3:]
        if clean_result.endswith("```"):
            clean_result = clean_result[:-3]
        clean_result = clean_result.strip()
        
        # 尝试解析JSON
        parsed_result = json.loads(clean_result)
        
        # 确保返回列表格式
        if isinstance(parsed_result, list):
            return parsed_result
        elif isinstance(parsed_result, dict):
            # 如果是单个对象，包装成列表
            return [parsed_result]
        else:
            logger.warning(f"[{task_type}] {ranking} 返回结果格式不正确: {type(parsed_result)}")
            return None
            
    except json.JSONDecodeError as e:
        logger.error(f"[{task_type}] {ranking} JSON解析失败: {e}")
        logger.error(f"[{task_type}] {ranking} 清理后的内容前500字符: {clean_result[:500] if 'clean_result' in locals() else result[:500]}")
        return None
    except Exception as e:
        logger.error(f"[{task_type}] {ranking} 结果处理失败: {e}")
        return None

