"""
动态表格变量提取提示词生成器
用于生成候选人资质、业绩等信息的AI提取提示词
重构版：支持业绩、资质、通用三种不同的提示词
"""

from typing import Dict, List, Any
import re

# 导入拆分的提示词生成函数
from .performance_prompt import generate_single_performance_prompt
from .qualification_prompt import generate_qualification_prompt
from .position_prompt import generate_position_prompt
from .general_prompt import generate_general_prompt
from .prompt_utils import get_rank_name, parse_clauses, has_multiple_positions


class DynamicTableVariableExtractor:
    """动态表格变量提取器 - 生成AI提取提示词（重构版）"""
    
    def __init__(self):
        """初始化"""
        pass
    
    def generate_qualification_review_variables(
        self,
        candidate_count: int,
        max_performance_count: int = 10,
        bidder_requirements: str = "",
        qualification_review_standard_table: str = "",
        candidate_names: Dict[int, str] = None,
        performance_counts: Dict[int, int] = None,
        performance_table_variables: List[Dict[str, Any]] = None,
        performance_requirements: str = "",
        qualification_requirements: str = "",
        other_requirements: str = ""
    ) -> List[Dict[str, Any]]:
        """
        生成资质、资格业绩等评审情况的变量定义和提取提示词（重构版）
        
        将条款分类为：业绩、资质、其他，分别生成不同的提示词
        
        Args:
            candidate_count: 推荐中标候选人数量
            max_performance_count: 每个候选人最多业绩数量（当performance_counts未提供时使用）
            bidder_requirements: 投标人要求的完整内容（兼容旧版本）
            qualification_review_standard_table: 资格评审标准中提取的条款
            candidate_names: 候选人名称字典，格式: {1: "第一名候选人", 2: "第二名候选人", ...}
            performance_counts: 每个候选人的业绩数量字典，格式: {1: 5, 2: 3, ...}，优先使用此参数
            performance_table_variables: 业绩表格变量列表
            performance_requirements: 业绩条款要求（优先使用）
            qualification_requirements: 资质条款要求（优先使用）
            other_requirements: 其他条款要求（优先使用）
            
        Returns:
            List[Dict]: 包含多个提取任务的列表，每个任务包含：
                - task_type: 任务类型（'performance', 'qualification', 'general'）
                - variables: 变量定义字典
                - variable_list: 变量名称列表
                - prompt: AI提取提示词
                - clauses: 相关条款列表
        """
        # 解析条款
        clauses = self._parse_clauses(qualification_review_standard_table)
        
        # 分类条款
        performance_clauses = []
        qualification_clauses = []
        position_clauses = []  # 包含多个职位（用'、'分隔）的条款
        general_clauses = []
        
        for clause in clauses:
            clause_text = clause.strip()
            if not clause_text:
                continue
            
            # 检测是否包含"业绩"
            if re.search(r'业绩', clause_text):
                performance_clauses.append(clause_text)
            # 检测是否包含"资质"
            elif re.search(r'资质', clause_text):
                qualification_clauses.append(clause_text)
            # 检测是否包含多个职位（用'、'分隔）
            elif self._has_multiple_positions(clause_text):
                position_clauses.append(clause_text)
            # 其他条款
            else:
                general_clauses.append(clause_text)
        
        # 生成任务列表
        tasks = []
        
        # 1. 业绩提取任务
        if performance_clauses and max_performance_count > 0:
            # 业绩提取不需要投标人要求，去除bidder_requirements参数
            if performance_table_variables:
                # 使用业绩表格变量方法（返回任务列表）
                performance_tasks = self._generate_performance_task_from_tables(
                    performance_table_variables,
                    performance_clauses,
                    "",  # 业绩提取不需要投标人要求
                    candidate_names
                )
                tasks.extend(performance_tasks)  # 添加所有业绩任务
            else:
                # 传统方法已废弃，不再使用
                pass
        
        # 2. 资质提取任务
        if qualification_clauses:
            # 优先使用分类后的资质条款要求，如果没有则使用完整投标人要求
            requirements_for_qualification = qualification_requirements if qualification_requirements else bidder_requirements
            
            qualification_task = self._generate_qualification_task(
                candidate_count,
                qualification_clauses,
                requirements_for_qualification,
                candidate_names
            )
            tasks.append(qualification_task)
        
        # 2.5. 多职位条款提取任务（单独处理）
        if position_clauses:
            # 优先使用分类后的其他条款要求，如果没有则使用完整投标人要求
            requirements_for_position = other_requirements if other_requirements else bidder_requirements
            
            position_task = self._generate_position_task(
                candidate_count,
                position_clauses,
                requirements_for_position,
                candidate_names
            )
            tasks.append(position_task)
        
        # 3. 通用条款提取任务
        if general_clauses:
            # 优先使用分类后的其他条款要求，如果没有则使用完整投标人要求
            requirements_for_general = other_requirements if other_requirements else bidder_requirements
            
            general_task = self._generate_general_task(
                candidate_count,
                general_clauses,
                requirements_for_general,
                candidate_names
            )
            tasks.append(general_task)
        
        return tasks
    
    def _parse_clauses(self, qualification_review_standard_table: str) -> List[str]:
        """
        解析资格评审标准中的条款
        
        Args:
            qualification_review_standard_table: 资格评审标准内容
            
        Returns:
            List[str]: 条款列表
        """
        return parse_clauses(qualification_review_standard_table)
    
    def _has_multiple_positions(self, clause_text: str) -> bool:
        """
        检测条款是否包含多个职位（用'、'分隔）
        
        Args:
            clause_text: 条款文本
            
        Returns:
            bool: 如果包含多个职位返回True，否则返回False
        """
        return has_multiple_positions(clause_text)
    
    # 传统业绩提取方法已废弃，不再使用
    
    def _generate_performance_task_from_tables(
        self,
        performance_table_variables: List[Dict[str, Any]],
        clauses: List[str],
        bidder_requirements: str,
        candidate_names: Dict[int, str] = None
    ) -> List[Dict[str, Any]]:
        """
        基于业绩表格变量生成业绩提取任务列表（每个业绩表格变量一个任务）
        
        Args:
            performance_table_variables: 业绩表格变量列表
            clauses: 业绩相关条款
            bidder_requirements: 投标人要求
            candidate_names: 候选人名称字典
            
        Returns:
            List[Dict]: 业绩提取任务列表
        """
        tasks = []
        
        # 为每个业绩表格变量生成单独的任务
        for table_var in performance_table_variables:
            table_var_name = table_var.get('variable_name', '')
            if not table_var_name or '业绩表' not in table_var_name:
                continue
            
            # 从表格变量名中提取排名和序号
            # 例如：第一名业绩表1 -> 第一名业绩1
            performance_var_name = table_var_name.replace('业绩表', '业绩')
            
            # 生成单个业绩表格的提示词
            prompt = self._generate_single_performance_prompt(
                table_var=table_var,
                performance_var_name=performance_var_name,
                clauses=clauses,
                candidate_names=candidate_names
            )
            
            # 输出业绩提取提示词前800字符到日志
            import logging
            prompt_preview = prompt[:800] + "..." if len(prompt) > 800 else prompt
            # logging.info(f"[业绩提取提示词] {performance_var_name} (基于{table_var_name}): {prompt_preview}")
            
            # 创建单个业绩提取任务
            task = {
                "task_type": "performance",
                "variables": {
                    performance_var_name: {
                        "description": f"基于{table_var_name}提取的业绩信息",
                        "type": "text",
                        "performance_type": "业绩",
                        "source_table": table_var_name  # 记录源表格变量名
                    }
                },
                "variable_list": [performance_var_name],
                "prompt": prompt,
                "clauses": clauses,
                "source_table": table_var_name,  # 记录源表格变量名
                "performance_table_variables": [table_var]  # 只包含当前表格变量
            }
            
            tasks.append(task)
        
        return tasks
    
    def _generate_single_performance_prompt(
        self,
        table_var: Dict[str, Any],
        performance_var_name: str,
        clauses: List[str],
        candidate_names: Dict[int, str] = None
    ) -> str:
        """
        为单个业绩表格变量生成业绩提取提示词
        
        Args:
            table_var: 业绩表格变量
            performance_var_name: 业绩变量名
            clauses: 业绩相关条款
            candidate_names: 候选人名称字典
            
        Returns:
            str: 业绩提取提示词
        """
        return generate_single_performance_prompt(
            table_var=table_var,
            performance_var_name=performance_var_name,
            clauses=clauses,
            candidate_names=candidate_names
        )
    
    def _generate_qualification_task(
        self,
        candidate_count: int,
        clauses: List[str],
        qualification_requirements: str,
        candidate_names: Dict[int, str] = None
    ) -> Dict[str, Any]:
        """
        生成资质提取任务
        
        Args:
            candidate_count: 候选人数量
            clauses: 资质相关条款
            qualification_requirements: 资质条款要求
            candidate_names: 候选人名称字典
            
        Returns:
            Dict: 资质提取任务
        """
        variables = {}
        variable_list = []
        
        # 为每个候选人的每个资质条款生成变量（使用完整条款名称）
        for i in range(1, candidate_count + 1):
            rank_name = self._get_rank_name(i)
            
            for clause in clauses:
                # 使用完整的条款名称作为变量名
                var_name = f"{rank_name}{clause}"
                variables[var_name] = {
                    "description": f"{rank_name}候选人的{clause}信息",
                    "type": "text",
                    "qualification_type": "资质",
                    "clause": clause
                }
                variable_list.append(var_name)
        
        # 生成资质专用提示词
        prompt = generate_qualification_prompt(
            candidate_count, 
            clauses,
            qualification_requirements,
            candidate_names
        )
        
        return {
            "task_type": "qualification",
            "variables": variables,
            "variable_list": variable_list,
            "prompt": prompt,
            "clauses": clauses
        }
    
    def _generate_position_task(
        self,
        candidate_count: int,
        clauses: List[str],
        other_requirements: str,
        candidate_names: Dict[int, str] = None
    ) -> Dict[str, Any]:
        """
        生成多职位条款提取任务
        
        Args:
            candidate_count: 候选人数量
            clauses: 多职位条款列表（包含'、'分隔的多个职位）
            other_requirements: 其他条款要求
            candidate_names: 候选人名称字典
            
        Returns:
            Dict: 多职位提取任务
        """
        variables = {}
        variable_list = []
        
        # 为每个候选人的每个多职位条款生成变量
        for i in range(1, candidate_count + 1):
            rank_name = self._get_rank_name(i)
            
            for clause in clauses:
                # 使用完整的条款名称作为变量名
                var_name = f"{rank_name}{clause}"
                variables[var_name] = {
                    "description": f"{rank_name}候选人的{clause}信息",
                    "type": "text",
                    "position_type": "多职位",
                    "clause": clause
                }
                variable_list.append(var_name)
        
        # 生成多职位专用提示词
        prompt = generate_position_prompt(
            candidate_count,
            clauses,
            other_requirements,
            candidate_names
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
        other_requirements: str,
        candidate_names: Dict[int, str] = None
    ) -> Dict[str, Any]:
        """
        生成通用条款提取任务
        
        Args:
            candidate_count: 候选人数量
            clauses: 通用条款列表（已排除业绩和资质条款）
            other_requirements: 其他条款要求
            candidate_names: 候选人名称字典
            
        Returns:
            Dict: 通用条款提取任务
        """
        variables = {}
        variable_list = []
        
        # 为每个候选人的每个条款生成变量（使用完整条款名称）
        for i in range(1, candidate_count + 1):
            rank_name = self._get_rank_name(i)
            
            for clause in clauses:
                # 使用完整的条款名称作为变量名
                var_name = f"{rank_name}{clause}"
                variables[var_name] = {
                    "description": f"{rank_name}候选人的{clause}信息",
                    "type": "text",
                    "clause": clause
                }
                variable_list.append(var_name)
        
        # 生成通用提示词
        prompt = generate_general_prompt(
            candidate_count,
            clauses,
            other_requirements,
            candidate_names
        )
        
        return {
            "task_type": "general",
            "variables": variables,
            "variable_list": variable_list,
            "prompt": prompt,
            "clauses": clauses
        }
    
    def _extract_clause_key(self, clause: str) -> str:
        """
        从条款中提取关键词作为变量名
        
        Args:
            clause: 条款文本
            
        Returns:
            str: 关键词
        """
        # 移除标点符号和数字
        cleaned = re.sub(r'[^\u4e00-\u9fa5a-zA-Z]', '', clause)
        
        # 提取前10个字符作为关键词
        key = cleaned[:10] if len(cleaned) > 10 else cleaned
        
        # 如果为空，使用默认值
        if not key:
            key = "条款"
        
        return key
    
    # 传统业绩提取提示词生成方法已废弃，不再使用
    
    def _generate_qualification_prompt(
        self,
        candidate_count: int,
        clauses: List[str],
        qualification_requirements: str,
        candidate_names: Dict[int, str] = None,
        target_ranking: str = None
    ) -> str:
        """生成资质专用提取提示词（包装器方法，用于兼容现有调用）"""
        return generate_qualification_prompt(
            candidate_count,
            clauses,
            qualification_requirements,
            candidate_names,
            target_ranking
        )
    
    def _generate_position_prompt(
        self,
        candidate_count: int,
        clauses: List[str],
        other_requirements: str,
        candidate_names: Dict[int, str] = None,
        target_ranking: str = None
    ) -> str:
        """生成多职位条款提取提示词（包装器方法，用于兼容现有调用）"""
        return generate_position_prompt(
            candidate_count,
            clauses,
            other_requirements,
            candidate_names,
            target_ranking
        )
    
    def _generate_general_prompt(
        self,
        candidate_count: int,
        clauses: List[str],
        other_requirements: str,
        candidate_names: Dict[int, str] = None,
        target_ranking: str = None
    ) -> str:
        """生成通用条款提取提示词（包装器方法，用于兼容现有调用）"""
        return generate_general_prompt(
            candidate_count,
            clauses,
            other_requirements,
            candidate_names,
            target_ranking
        )
    
    
    
    
    
    def _get_rank_name(self, rank: int) -> str:
        """获取排名名称"""
        return get_rank_name(rank)
