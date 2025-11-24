"""
商务部分评分表变量提取提示词生成器（重构版）
用于从商务部分评分表中提取业绩、业主反馈、综合实力等条款信息的AI提取提示词
重构版：支持业绩和通用两种不同的提示词
"""

from typing import Dict, List, Any
import re

# 导入拆分的提示词生成函数
from .business_position_prompt import generate_business_position_prompt
from .business_general_prompt import generate_business_general_prompt
from .prompt_utils import get_rank_name, parse_clauses, has_multiple_positions


class BusinessScoreTableVariableExtractor:
    """商务部分评分表变量提取器 - 生成AI提取提示词"""
    
    def __init__(self):
        """初始化"""
        pass
    
    def generate_business_score_extraction_variables(
        self, 
        candidate_count: int,
        business_score_clauses: str = "",
        candidate_names: Dict[int, str] = None,
        performance_counts: Dict[int, int] = None,
        performance_requirements: str = "",
        other_requirements: str = ""
    ) -> List[Dict[str, Any]]:
        """
        生成商务评分标准的变量定义和提取提示词（重构版）
        
        注意：业绩提取已移至第五步处理，此函数只处理通用条款
        
        Args:
            candidate_count: 推荐中标候选人数量
            business_score_clauses: 商务评分标准（顿号分隔的条款名称列表）
            candidate_names: 候选人名称字典，格式: {1: "第一名候选人", 2: "第二名候选人", ...}
            performance_counts: 每个候选人的业绩数量字典（已废弃，业绩在第五步处理）
            performance_requirements: 业绩条款要求（已废弃，业绩在第五步处理）
            other_requirements: 其他条款要求（优先使用）
            
        Returns:
            List[Dict]: 包含通用条款提取任务的列表，每个任务包含：
                - task_type: 任务类型（'general'）
                - variables: 变量定义字典
                - variable_list: 变量名称列表
                - prompt: AI提取提示词
                - clauses: 相关条款列表
        """
        # 解析条款（用顿号分隔）
        clauses = self._parse_clauses(business_score_clauses)
        
        # 分类条款 - 排除业绩条款
        position_clauses = []  # 包含多个职位（用'、'分隔）的条款
        general_clauses = []
        
        for clause in clauses:
            clause_text = clause.strip()
            if not clause_text:
                continue
            
            # 排除包含"业绩"的条款，业绩在第五步处理
            if not re.search(r'业绩', clause_text):
                # 检测是否包含多个职位（用'、'分隔）
                if self._has_multiple_positions(clause_text):
                    position_clauses.append(clause_text)
                else:
                    general_clauses.append(clause_text)
        
        # 生成任务列表
        tasks = []
        
        # 多职位条款提取任务（单独处理）
        if position_clauses:
            # 优先使用分类后的其他条款要求，如果没有则使用空字符串
            requirements_for_position = other_requirements if other_requirements else ""
            
            position_task = self._generate_position_task(
                candidate_count,
                position_clauses,
                candidate_names,
                requirements_for_position
            )
            tasks.append(position_task)
        
        # 通用条款提取任务
        if general_clauses:
            # 优先使用分类后的其他条款要求，如果没有则使用空字符串
            requirements_for_general = other_requirements if other_requirements else ""
            
            general_task = self._generate_general_task(
                candidate_count,
                general_clauses,
                candidate_names,
                requirements_for_general
            )
            tasks.append(general_task)
        else:
            # 如果没有通用条款，记录日志
            import logging
            logger = logging.getLogger(__name__)
            logger.info("商务评分标准中只有业绩条款，已移至第五步处理，跳过通用条款提取")
        
        return tasks
    
    def _parse_clauses(self, business_score_clauses: str) -> List[str]:
        """
        解析商务评分标准
        
        Args:
            business_score_clauses: 条款字符串（用顿号分隔）
            
        Returns:
            List[str]: 条款列表
        """
        return parse_clauses(business_score_clauses, separator='、')
    
    def _has_multiple_positions(self, clause_text: str) -> bool:
        """
        检测条款是否包含多个职位（用'、'分隔）
        
        Args:
            clause_text: 条款文本
            
        Returns:
            bool: 如果包含多个职位返回True，否则返回False
        """
        return has_multiple_positions(clause_text)
    
    # 业绩提取任务已移至第五步处理，此方法已废弃
    
    def _generate_position_task(
        self,
        candidate_count: int,
        clauses: List[str],
        candidate_names: Dict[int, str] = None,
        other_requirements: str = ""
    ) -> Dict[str, Any]:
        """
        生成多职位条款提取任务
        
        Args:
            candidate_count: 候选人数量
            clauses: 多职位条款列表（包含'、'分隔的多个职位）
            candidate_names: 候选人名称字典
            other_requirements: 其他条款要求
            
        Returns:
            Dict: 多职位提取任务
        """
        variables = {}
        variable_list = []
        
        # 为每个候选人的每个多职位条款生成变量
        for i in range(1, candidate_count + 1):
            rank_name = self._get_rank_name(i)
            
            for clause in clauses:
                # 使用完整的条款名称作为变量名（格式：排名+条款名称，不再使用"三"前缀）
                var_name = f"{rank_name}{clause}"
                variables[var_name] = {
                    "description": f"{rank_name}候选人的{clause}信息",
                    "type": "text",
                    "position_type": "多职位",
                    "clause": clause
                }
                variable_list.append(var_name)
        
        # 生成多职位专用提示词
        prompt = generate_business_position_prompt(
            candidate_count,
            clauses,
            candidate_names,
            other_requirements
        )
        
        return {
            "task_type": "position",
            "variables": variables,
            "variable_list": variable_list,
            "prompt": prompt,
            "clauses": clauses
        }
    
    def _generate_general_task(
        self,
        candidate_count: int,
        clauses: List[str],
        candidate_names: Dict[int, str] = None,
        other_requirements: str = ""
    ) -> Dict[str, Any]:
        """
        生成通用条款提取任务
        
        Args:
            candidate_count: 候选人数量
            clauses: 通用条款列表（已排除业绩条款）
            candidate_names: 候选人名称字典
            other_requirements: 其他条款要求
            
        Returns:
            Dict: 通用条款提取任务
        """
        variables = {}
        variable_list = []
        
        # 生成通用提示词
        prompt = generate_business_general_prompt(
            candidate_count,
            clauses,
            candidate_names,
            other_requirements
        )
        
        return {
            "task_type": "general",
            "variables": variables,
            "variable_list": variable_list,
            "prompt": prompt,
            "clauses": clauses
        }
    
    # 业绩提示词生成已移至第五步处理，此方法已废弃
    
    
    def _get_rank_name(self, rank: int) -> str:
        """获取排名名称"""
        return get_rank_name(rank)
