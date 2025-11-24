#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
第四步预变量处理模块

本模块用于根据商务评分标准和资格评审标准，判断是否包含'资质'和'业绩'关键词，
然后从投标人要求中提取对应的条款要求，并分类为业绩条款要求、资质条款要求、其他条款要求。
"""

import logging
import re
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from common.llm_client import LLMClient
from prompts.clause_requirement_extraction_prompt import build_clause_requirement_extraction_prompt
from prompts.resume_extraction_prompt import (
    build_resume_extraction_prompt,
    build_resume_performance_extraction_prompt,
    extract_position_from_clause
)
from prompts.qualification_personnel_extraction_prompt import build_qualification_personnel_extraction_prompt

logger = logging.getLogger(__name__)


class PreVariableForStep4:
    """第四步预变量处理器"""
    
    def __init__(self):
        """初始化处理器"""
        self.logger = logger
        self.llm_client = LLMClient()
    
    async def extract_clause_requirements(
        self,
        business_score_clauses: str,
        qualification_review_standard_table: str,
        bidder_requirements: str
    ) -> Dict[str, Any]:
        """
        根据商务评分标准和资格评审标准，从投标人要求中提取对应的条款要求
        
        Args:
            business_score_clauses: 商务评分标准内容（用逗号分隔）
            qualification_review_standard_table: 资格评审标准内容（用逗号分隔）
            bidder_requirements: 投标人要求内容
            
        Returns:
            Dict[str, Any]: 包含业绩条款要求、资质条款要求、其他条款要求的字典
        """
        try:
            self.logger.info("开始分析条款类型并提取对应要求...")
            
            # 1. 处理条款内容，按逗号分割并分析
            clause_analysis = self._process_clauses(
                business_score_clauses, 
                qualification_review_standard_table
            )
            
            self.logger.info(f"条款分析结果: {clause_analysis}")
            
            # 2. 根据条款分析结果提取对应的要求
            requirements = await self._extract_requirements_by_analysis(
                clause_analysis, 
                bidder_requirements
            )
            
            self.logger.info("条款要求提取完成")
            return requirements
            
        except Exception as e:
            self.logger.error(f"提取条款要求失败: {e}")
            return {
                'performance_requirements': '',
                'qualification_requirements': '',
                'other_requirements': '',
                'error': str(e)
            }
    
    def _process_clauses(
        self, 
        business_score_clauses: str, 
        qualification_review_standard_table: str
    ) -> Dict[str, Any]:
        """
        处理条款内容，按逗号分割并分析是否包含'资质'和'业绩'关键词
        
        Args:
            business_score_clauses: 商务评分标准内容（用逗号分隔）
            qualification_review_standard_table: 资格评审标准内容（用逗号分隔）
            
        Returns:
            Dict[str, Any]: 包含条款分析结果的字典
        """
        # 合并两个表格内容
        combined_clauses = f"{business_score_clauses},{qualification_review_standard_table}"
        
        # 按逗号分割条款
        clauses = [clause.strip() for clause in combined_clauses.split(',') if clause.strip()]
        
        # 分析条款类型
        performance_clauses = []
        qualification_clauses = []
        other_clauses = []
        
        for clause in clauses:
            if '业绩' in clause:
                performance_clauses.append(clause)
            elif '资质' in clause:
                qualification_clauses.append(clause)
            else:
                other_clauses.append(clause)
        
        has_performance = len(performance_clauses) > 0
        has_qualification = len(qualification_clauses) > 0
        has_other = len(other_clauses) > 0
        
        self.logger.info(f"条款分析结果 - 业绩条款: {len(performance_clauses)}个, 资质条款: {len(qualification_clauses)}个, 其他条款: {len(other_clauses)}个")
        
        return {
            'has_performance': has_performance,
            'has_qualification': has_qualification,
            'has_other': has_other,
            'performance_clauses': performance_clauses,
            'qualification_clauses': qualification_clauses,
            'other_clauses': other_clauses,
            'all_clauses': clauses
        }
    
    async def _extract_requirements_by_analysis(
        self, 
        clause_analysis: Dict[str, Any], 
        bidder_requirements: str
    ) -> Dict[str, Any]:
        """
        根据条款分析结果从投标人要求中提取对应的要求
        
        Args:
            clause_analysis: 条款分析结果
            bidder_requirements: 投标人要求内容
            
        Returns:
            Dict[str, Any]: 包含各类条款要求的字典
        """
        try:
            # 构建提示词
            prompt = build_clause_requirement_extraction_prompt(clause_analysis, bidder_requirements)
            
            # 替换$content占位符为投标人要求内容
            final_prompt = prompt.replace("$content", bidder_requirements)
            
            # 使用重试机制调用LLM进行提取
            parsed_result = await self._extract_with_retry(final_prompt)
            
            return parsed_result
            
        except Exception as e:
            self.logger.error(f"LLM提取失败: {e}")
            return {
                'performance_requirements': '',
                'qualification_requirements': '',
                'other_requirements': '',
                'error': str(e)
            }
    
    
    async def _extract_with_retry(self, prompt: str) -> Dict[str, Any]:
        """
        带重试机制的LLM提取方法
        
        Args:
            prompt: 提示词
            
        Returns:
            Dict[str, Any]: 解析后的结果
        """
        max_retries = 1
        
        for attempt in range(max_retries + 1):
            try:
                # 调用LLM进行提取
                result = await self.llm_client.call_llm(
                    prompt=prompt,
                    file_content="",
                    model_type="gemini"
                )
                
                # 检查结果是否为空
                if not result or result.strip() == "":
                    if attempt < max_retries:
                        self.logger.warning(f"第{attempt + 1}次调用返回空结果，准备重试")
                        continue
                    else:
                        self.logger.error("重试后仍然返回空结果")
                        return {
                            'performance_requirements': '',
                            'qualification_requirements': '',
                            'other_requirements': '',
                            'extraction_notes': '',
                            'success': False,
                            'error': 'AI模型返回空结果'
                        }
                
                # 解析LLM返回的结果
                parsed_result = self._parse_llm_result(result)
                
                # 检查解析结果
                if parsed_result['success']:
                    return parsed_result
                else:
                    if attempt < max_retries:
                        self.logger.warning(f"第{attempt + 1}次解析失败: {parsed_result.get('error', '未知错误')}，准备重试")
                        continue
                    else:
                        self.logger.error(f"重试后仍然解析失败: {parsed_result.get('error', '未知错误')}")
                        return parsed_result
                        
            except Exception as e:
                if attempt < max_retries:
                    self.logger.warning(f"第{attempt + 1}次调用发生异常: {e}，准备重试")
                    continue
                else:
                    self.logger.error(f"重试后仍然发生异常: {e}")
                    return {
                        'performance_requirements': '',
                        'qualification_requirements': '',
                        'other_requirements': '',
                        'extraction_notes': '',
                        'success': False,
                        'error': f'提取失败: {str(e)}'
                    }
        
        # 不应该到达这里，但为了安全起见
        return {
            'performance_requirements': '',
            'qualification_requirements': '',
            'other_requirements': '',
            'extraction_notes': '',
            'success': False,
            'error': '未知错误'
        }
    
    def _parse_llm_result(self, llm_result: str) -> Dict[str, Any]:
        """
        解析LLM返回的结果
        
        Args:
            llm_result: LLM返回的原始结果
            
        Returns:
            Dict[str, Any]: 解析后的结果
        """
        try:
            # 清理LLM返回的结果
            clean_result = llm_result.strip()
            
            # 移除可能的markdown代码块标记
            if clean_result.startswith("```json"):
                clean_result = clean_result[7:]
            if clean_result.startswith("```"):
                clean_result = clean_result[3:]
            if clean_result.endswith("```"):
                clean_result = clean_result[:-3]
            clean_result = clean_result.strip()
            
            # 尝试提取JSON部分
            json_match = re.search(r'\{[\s\S]*\}', clean_result)
            if json_match:
                clean_result = json_match.group(0)
            
            # 解析JSON
            result_data = json.loads(clean_result)
            
            # 验证和格式化结果
            formatted_result = {
                'performance_requirements': result_data.get('performance_requirements', ''),
                'qualification_requirements': result_data.get('qualification_requirements', ''),
                'other_requirements': result_data.get('other_requirements', ''),
                'extraction_notes': result_data.get('extraction_notes', ''),
                'success': True
            }
            
            self.logger.info("LLM结果解析成功")
            return formatted_result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"解析LLM结果JSON失败: {e}")
            self.logger.error(f"原始内容: {llm_result[:500]}")
            return {
                'performance_requirements': '',
                'qualification_requirements': '',
                'other_requirements': '',
                'extraction_notes': '',
                'success': False,
                'error': f'JSON解析失败: {str(e)}'
            }
        except Exception as e:
            self.logger.error(f"解析LLM结果失败: {e}")
            return {
                'performance_requirements': '',
                'qualification_requirements': '',
                'other_requirements': '',
                'extraction_notes': '',
                'success': False,
                'error': f'解析失败: {str(e)}'
            }
    
    async def extract_resume_personnel_names(
        self,
        business_score_clauses: str,
        resume_table_content: str,
        ranking: str = "第一名"
    ) -> Dict[str, Any]:
        """
        从简历表中提取指定职位的人物姓名
        
        Args:
            business_score_clauses: 商务评分标准内容（用逗号分隔）
            resume_table_content: 简历表部分内容（由resume_table_content_filter.py截取得到）
            
        Returns:
            Dict[str, Any]: 包含提取结果和人员姓名的字典，格式为统一的变量格式
        """
        try:
            self.logger.info("开始分析商务评分标准中的业绩条款...")
            
            # 1. 检查商务评分标准中"业绩"出现的次数
            performance_count = business_score_clauses.count('业绩')
            self.logger.info(f"商务评分标准中'业绩'出现次数: {performance_count}")
            
            # 如果业绩出现次数小于等于1，跳过提取
            if performance_count <= 1:
                self.logger.info("业绩条款数量不足，跳过简历表人员姓名提取")
                return {
                    'extraction_performed': False,
                    'reason': '业绩条款数量不足（≤1）',
                    'performance_count': performance_count,
                    'variables': [],
                    'success': True
                }
            
            # 2. 提取包含"业绩"的条款
            performance_clauses = self._extract_performance_clauses(business_score_clauses)
            self.logger.info(f"提取到包含'业绩'的条款: {performance_clauses}")
            
            # 3. 生成简历表提取提示词并调用模型
            variables = await self._extract_personnel_names_from_resume(
                performance_clauses, 
                resume_table_content,
                ranking
            )
            
            self.logger.info(f"简历表人员姓名提取完成，共生成 {len(variables)} 个变量")
            return {
                'extraction_performed': True,
                'performance_count': performance_count,
                'performance_clauses': performance_clauses,
                'variables': variables,
                'success': True
            }
            
        except Exception as e:
            self.logger.error(f"提取简历表人员姓名失败: {e}")
            return {
                'extraction_performed': False,
                'reason': f'提取失败: {str(e)}',
                'performance_count': 0,
                'variables': [],
                'success': False,
                'error': str(e)
            }
    
    def _extract_performance_clauses(self, business_score_clauses: str) -> List[str]:
        """
        从商务评分标准中提取包含"业绩"的条款
        
        Args:
            business_score_clauses: 商务评分标准内容（用逗号分隔）
            
        Returns:
            List[str]: 包含"业绩"的条款列表
        """
        # 按逗号分割条款
        clauses = [clause.strip() for clause in business_score_clauses.split(',') if clause.strip()]
        
        # 筛选包含"业绩"的条款
        performance_clauses = [clause for clause in clauses if '业绩' in clause]
        
        self.logger.info(f"从{len(clauses)}个条款中筛选出{len(performance_clauses)}个业绩条款")
        self.logger.info(f"业绩条款详情: {performance_clauses}")
        return performance_clauses
    
    async def _extract_personnel_names_from_resume(
        self, 
        performance_clauses: List[str], 
        resume_table_content: str,
        ranking: str = "第一名"
    ) -> List[Dict[str, Any]]:
        """
        从简历表中提取指定职位的人员姓名
        
        Args:
            performance_clauses: 包含"业绩"的条款列表
            resume_table_content: 简历表内容
            ranking: 排名信息（如"第一名"、"第二名"等）
            
        Returns:
            List[Dict[str, Any]]: 包含各职位人员姓名的变量列表
        """
        try:
            # 构建简历表提取提示词
            prompt = build_resume_extraction_prompt(performance_clauses, ranking)
            
            # 调用LLM进行提取
            result = await self.llm_client.call_llm(
                prompt=prompt,
                file_content=resume_table_content,
                model_type="gemini"
            )
            
            # 解析LLM返回的结果
            parsed_result = self._parse_resume_extraction_result(result)
            
            return parsed_result
            
        except Exception as e:
            self.logger.error(f"LLM提取简历表人员姓名失败: {e}")
            return []
    
    
    def _parse_resume_extraction_result(self, llm_result: str) -> List[Dict[str, Any]]:
        """
        解析LLM返回的简历表提取结果
        
        Args:
            llm_result: LLM返回的原始结果
            
        Returns:
            List[Dict[str, Any]]: 解析后的变量列表
        """
        try:
            # 清理LLM返回的结果
            clean_result = llm_result.strip()
            
            # 移除可能的markdown代码块标记
            if clean_result.startswith("```json"):
                clean_result = clean_result[7:]
            if clean_result.startswith("```"):
                clean_result = clean_result[3:]
            if clean_result.endswith("```"):
                clean_result = clean_result[:-3]
            clean_result = clean_result.strip()
            
            # 尝试提取JSON数组部分
            json_match = re.search(r'\[[\s\S]*\]', clean_result)
            if json_match:
                clean_result = json_match.group(0)
            
            # 解析JSON数组
            result_data = json.loads(clean_result)
            
            # 验证是否为数组格式
            if not isinstance(result_data, list):
                self.logger.error(f"期望JSON数组格式，但得到: {type(result_data)}")
                return []
            
            # 验证每个变量的格式
            valid_variables = []
            for item in result_data:
                if isinstance(item, dict) and 'variable_name' in item and 'variable_value' in item:
                    # 确保reference_source字段存在
                    if 'reference_source' not in item:
                        item['reference_source'] = '简历表人员配备信息'
                    valid_variables.append(item)
                else:
                    self.logger.warning(f"跳过无效的变量项: {item}")
            
            self.logger.info(f"成功解析简历表提取结果: {len(valid_variables)} 个变量")
            return valid_variables
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
            self.logger.error(f"原始内容: {llm_result[:500]}")
            return []
        except Exception as e:
            self.logger.error(f"解析简历表提取结果失败: {e}")
            return []

    def _extract_position_from_clause(self, clause_name: str) -> str:
        """
        提取条款名称中的职位信息
        """
        return extract_position_from_clause(clause_name)
    
    async def extract_performance_tables_from_resume(
        self,
        resume_table_content: str,
        ranking: str,
        clause_name: str
    ) -> Dict[str, Any]:
        """
        从简历表的主要工作经历中提取业绩表格
        
        Args:
            resume_table_content: 简历表内容
            ranking: 排名信息（如"第一名"、"第二名"等）
            clause_name: 条款名称（如"拟派项目经理近年类似业绩"等）
            
        Returns:
            Dict[str, Any]: 包含提取结果的字典，格式与extract_performance_tables_from_text相同
        """
        try:
            # 从条款名称中提取职位信息，用于日志
            position = self._extract_position_from_clause(clause_name)
            self.logger.info(f"开始从{ranking}的简历表中提取{clause_name}的业绩表格...")
            self.logger.info(f"提示词中给出的条款名称: {clause_name}")
            self.logger.info(f"从条款名称中提取到的职位: {position}")
            self.logger.info(f"简历表内容长度: {len(resume_table_content)} 字符")
            
            if not resume_table_content or len(resume_table_content.strip()) < 50:
                self.logger.warning(f"{ranking}的简历表内容为空或过短")
                return {
                    'success': False,
                    'error': '简历表内容为空或过短',
                    'performance_summary_table': '',
                    'individual_performances': []
                }
            
            # 构建简历表业绩提取提示词
            prompt = build_resume_performance_extraction_prompt(ranking, clause_name)
            
            # 调用LLM进行提取
            result = await self.llm_client.call_llm(
                prompt=prompt,
                file_content=resume_table_content,
                model_type="gemini"
            )
            
            # 解析LLM返回的结果
            parsed_result = self._parse_resume_performance_result(result, ranking, clause_name)
            
            if parsed_result['success']:
                self.logger.info(f"成功提取{ranking}的简历表业绩表格，汇总表1个，单个业绩{len(parsed_result['individual_performances'])}个")
            else:
                self.logger.error(f"提取{ranking}的简历表业绩表格失败: {parsed_result.get('error')}")
            
            return parsed_result
            
        except Exception as e:
            self.logger.error(f"提取{ranking}的简历表业绩表格失败: {e}")
            return {
                'success': False,
                'error': f'提取失败: {str(e)}',
                'performance_summary_table': '',
                'individual_performances': []
            }
    
    
    def _parse_resume_performance_result(
        self, 
        llm_result: str, 
        ranking: str, 
        clause_name: str
    ) -> Dict[str, Any]:
        """
        解析LLM返回的简历表业绩提取结果
        
        Args:
            llm_result: LLM返回的原始结果
            ranking: 排名信息
            clause_name: 条款名称
            
        Returns:
            Dict[str, Any]: 解析后的结果，格式与extract_performance_tables_from_text相同
        """
        try:
            # 清理LLM返回的结果
            clean_result = llm_result.strip()
            
            # 移除可能的markdown代码块标记
            if clean_result.startswith("```json"):
                clean_result = clean_result[7:]
            if clean_result.startswith("```"):
                clean_result = clean_result[3:]
            if clean_result.endswith("```"):
                clean_result = clean_result[:-3]
            clean_result = clean_result.strip()
            
            # 尝试提取JSON对象部分
            json_match = re.search(r'\{[\s\S]*\}', clean_result)
            if json_match:
                clean_result = json_match.group(0)
            
            # 解析JSON对象
            result_data = json.loads(clean_result)
            
            # 验证格式
            if not isinstance(result_data, dict):
                self.logger.error(f"期望JSON对象格式，但得到: {type(result_data)}")
                return {
                    'success': False,
                    'error': '返回格式错误',
                    'performance_summary_table': '',
                    'individual_performances': []
                }
            
            # 提取汇总表和单个业绩
            summary_table = result_data.get('performance_summary_table', {})
            individual_performances = result_data.get('individual_performances', [])
            
            # 验证汇总表格式
            if summary_table and isinstance(summary_table, dict):
                if 'variable_name' not in summary_table:
                    summary_table['variable_name'] = f"{ranking}{clause_name}汇总表"
                if 'table_content' not in summary_table:
                    summary_table['table_content'] = ''
            else:
                summary_table = {
                    'variable_name': f"{ranking}{clause_name}汇总表",
                    'table_content': ''
                }
            
            # 验证单个业绩格式
            valid_performances = []
            for perf in individual_performances:
                if isinstance(perf, dict) and 'variable_name' in perf and 'table_content' in perf:
                    valid_performances.append(perf)
                else:
                    self.logger.warning(f"跳过无效的业绩项: {perf}")
            
            self.logger.info(f"成功解析简历表业绩提取结果: 汇总表1个，单个业绩{len(valid_performances)}个")
            return {
                'success': True,
                'performance_summary_table': summary_table,
                'individual_performances': valid_performances
            }
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
            self.logger.error(f"原始内容: {llm_result[:500]}")
            return {
                'success': False,
                'error': f'JSON解析失败: {str(e)}',
                'performance_summary_table': '',
                'individual_performances': []
            }
        except Exception as e:
            self.logger.error(f"解析简历表业绩提取结果失败: {e}")
            return {
                'success': False,
                'error': f'解析失败: {str(e)}',
                'performance_summary_table': '',
                'individual_performances': []
            }
    


async def extract_clause_requirements_from_tables(
    business_score_clauses: str,
    qualification_review_standard_table: str,
    bidder_requirements: str
) -> Dict[str, Any]:
    """
    便捷函数：根据商务评分标准和资格评审标准，从投标人要求中提取对应的条款要求
    
    Args:
        business_score_clauses: 商务评分标准内容
        qualification_review_standard_table: 资格评审标准内容
        bidder_requirements: 投标人要求内容
        
    Returns:
        Dict[str, Any]: 包含业绩条款要求、资质条款要求、其他条款要求的字典
    """
    processor = PreVariableForStep4()
    return await processor.extract_clause_requirements(
        business_score_clauses,
        qualification_review_standard_table,
        bidder_requirements
    )


async def extract_resume_personnel_names_from_clauses(
    business_score_clauses: str,
    resume_table_content: str
) -> Dict[str, Any]:
    """
    便捷函数：从简历表中提取指定职位的人物姓名
    
    Args:
        business_score_clauses: 商务评分标准内容（用逗号分隔）
        resume_table_content: 简历表部分内容（由resume_table_content_filter.py截取得到）
        
    Returns:
        Dict[str, Any]: 包含提取结果和人员姓名的字典
    """
    processor = PreVariableForStep4()
    return await processor.extract_resume_personnel_names(
        business_score_clauses,
        resume_table_content
    )


async def extract_qualification_personnel_from_resume(
    clause_name: str,
    resume_table_content: str,
    ranking: str = "第一名"
) -> List[Dict[str, Any]]:
    """
    从简历表中提取资格评审标准条款中指定职位的人员信息
    
    Args:
        clause_name: 资格评审标准条款名称（如"设计负责人"、"项目经理兼设计负责人"等）
        resume_table_content: 简历表内容（人员配备组成表）
        ranking: 排名信息（如"第一名"、"第二名"等）
        
    Returns:
        List[Dict[str, Any]]: 提取的人员信息变量列表，格式：
        [
            {
                "variable_name": "第一名设计负责人",
                "variable_value": "张三\n注册化工工程师\nF0002911\n职称证\nI01239947",
                "reference_source": {...}
            }
        ]
        
        变量值格式说明：
        - 第一行：姓名
        - 第二行：第一个证书名称
        - 第三行：第一个证书编号
        - 第四行：第二个证书名称（如果有）
        - 第五行：第二个证书编号（如果有）
        - ...以此类推，所有信息用换行符\n分隔
    
    规则：
    - 确保职务名称完全匹配：如果条款是"设计负责人"，职务必须是"设计负责人"，不能是"XX设计负责人"
    - 如果是一个人兼任多个职位（如"项目经理兼设计负责人"），需要判断它属于两个职位
    """
    import logging
    from common.llm_client import LLMClient
    import json
    import re
    
    logger = logging.getLogger(__name__)
    
    try:
        # 1. 从条款中提取职位名称列表
        positions = _extract_positions_from_clause(clause_name)
        if not positions:
            logger.info(f"条款 '{clause_name}' 中未提取到职位名称，跳过简历表提取")
            return []
        
        logger.info(f"从条款 '{clause_name}' 中提取到职位: {positions}")
        
        # 2. 如果没有简历表内容，返回空列表
        if not resume_table_content or len(resume_table_content.strip()) < 50:
            logger.warning(f"简历表内容为空或过短，无法提取人员信息")
            return []
        
        # 3. 构建提示词，调用LLM提取人员信息
        prompt = build_qualification_personnel_extraction_prompt(
            clause_name=clause_name,
            positions=positions,
            ranking=ranking
        )
        
        llm_client = LLMClient()
        logger.info(f"开始从简历表中提取 {ranking} 的 {clause_name} 人员信息...")
        
        result = await llm_client.call_llm(
            prompt=prompt,
            file_content=resume_table_content,
            model_type="gemini"
        )
        
        if not result or not result.strip():
            logger.warning(f"LLM返回结果为空")
            return []
        
        # 4. 解析LLM返回结果
        variables = _parse_qualification_personnel_result(
            result=result,
            clause_name=clause_name,
            positions=positions,
            ranking=ranking
        )
        
        logger.info(f"成功提取 {len(variables)} 个人员信息变量")
        return variables
        
    except Exception as e:
        logger.error(f"从简历表提取人员信息失败: {e}", exc_info=True)
        return []


def _extract_positions_from_clause(clause_name: str) -> List[str]:
    """
    从条款名称中提取职位名称列表（支持兼任情况）
    
    Args:
        clause_name: 条款名称（如"拟派项目经理近年类似业绩"、"项目技术负责人业绩"、"项目经理兼设计负责人"等）
        
    Returns:
        List[str]: 职位名称列表，例如：["项目经理", "设计负责人"] 或 ["设计负责人"]
    
    规则：
    - 如果条款是"项目经理兼设计负责人"，返回["项目经理", "设计负责人"]
    - 如果条款是"设计负责人"，返回["设计负责人"]
    - 确保完全匹配：如果条款是"设计负责人"，不能匹配"XX设计负责人"
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # 定义所有可能的职位关键词（按长度从长到短排序，优先匹配长词）
    position_keywords = [
        '项目经理兼设计负责人', '项目经理兼施工负责人', '项目经理兼技术负责人',
        '设计负责人', '施工负责人', '技术负责人', '安全负责人', '质量负责人',
        '项目经理', '项目负责人', '总工程师', '总监理', '工程师'
    ]
    
    # 检查是否包含"兼"字，表示兼任多个职位
    if '兼' in clause_name:
        # 提取兼任的职位
        positions = []
        # 尝试匹配"XX兼YY"模式
        import re
        # 匹配模式：职位1兼职位2
        pattern = r'([^兼]+)兼([^兼]+)'
        match = re.search(pattern, clause_name)
        if match:
            pos1 = match.group(1).strip()
            pos2 = match.group(2).strip()
            # 清理职位名称，去除可能的修饰词
            for pos in [pos1, pos2]:
                # 查找匹配的职位关键词
                for keyword in position_keywords:
                    if keyword in pos:
                        if keyword not in positions:
                            positions.append(keyword)
                        break
        else:
            # 如果没有匹配到"XX兼YY"模式，尝试直接查找职位关键词
            for keyword in position_keywords:
                if keyword in clause_name:
                    if keyword not in positions:
                        positions.append(keyword)
        
        if positions:
            logger.debug(f"从条款 '{clause_name}' 中提取到兼任职位: {positions}")
            return positions
    else:
        # 不包含"兼"字，查找单个职位
        # 按长度从长到短排序，优先匹配长词（如"设计负责人"优先于"负责人"）
        for keyword in position_keywords:
            if keyword in clause_name:
                logger.debug(f"从条款 '{clause_name}' 中提取到职位: {keyword}")
                return [keyword]
    
    logger.debug(f"从条款 '{clause_name}' 中未提取到职位")
    return []




def _parse_qualification_personnel_result(
    result: str,
    clause_name: str,
    positions: List[str],
    ranking: str
) -> List[Dict[str, Any]]:
    """
    解析LLM返回的资格评审标准人员信息提取结果
    
    Args:
        result: LLM返回的JSON字符串
        clause_name: 条款名称
        positions: 职位名称列表
        ranking: 排名信息
        
    Returns:
        List[Dict[str, Any]]: 解析后的变量列表
    """
    import logging
    import json
    import re
    
    logger = logging.getLogger(__name__)
    
    try:
        # 尝试提取JSON数组
        json_match = re.search(r'\[.*\]', result, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            variables = json.loads(json_str)
        else:
            # 如果没有找到JSON数组，尝试直接解析整个结果
            variables = json.loads(result)
        
        if not isinstance(variables, list):
            variables = [variables]
        
        # 验证和清理变量
        valid_variables = []
        for var in variables:
            if isinstance(var, dict) and "variable_name" in var and "variable_value" in var:
                # 确保reference_source格式正确
                if "reference_source" not in var:
                    var["reference_source"] = {
                        "source_url": "",
                        "evidence_text": "人员配备组成表",
                        "pages": "",
                        "file_type": "candidate_bid_file"
                    }
                valid_variables.append(var)
        
        logger.info(f"成功解析资格评审标准人员信息提取结果: {len(valid_variables)} 个变量")
        return valid_variables
        
    except json.JSONDecodeError as e:
        logger.error(f"解析JSON失败: {e}, 原始结果: {result[:500]}")
        return []
    except Exception as e:
        logger.error(f"解析资格评审标准人员信息提取结果失败: {e}")
        return []


async def extract_resume_personnel_names_from_ranked_files(
    ranked_files: Dict[str, Dict[str, Any]],
    business_score_clauses: str
) -> List[Dict[str, Any]]:
    """
    从排名文件中并发提取简历表人员姓名（集成到第四步）
    
    Args:
        ranked_files: 排名文件字典，格式为 {"第一名": {content, file_url, ...}, "第二名": {...}}
        business_score_clauses: 商务评分标准内容（用逗号分隔）
        
    Returns:
        List[Dict[str, Any]]: 提取的简历表人员姓名变量列表
    """
    import asyncio
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("开始从排名文件中并发提取简历表人员姓名...")
        
        # 检查业绩条款数量
        performance_count = business_score_clauses.count('业绩')
        if performance_count <= 1:
            logger.info(f"业绩条款数量不足（{performance_count}），跳过简历表人员姓名提取")
            return []
        
        # 创建处理器
        processor = PreVariableForStep4()
        
        async def process_single_ranking(ranking: str, file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
            """处理单个排名的简历表人员姓名提取"""
            extracted_variables = []
            
            try:
                # 获取简历表内容
                resume_table_content = file_info.get('resume_table_content', '')
                original_content = file_info.get('content', '')
                
                # 如果简历表截取失败，使用源文件
                if not resume_table_content:
                    logger.warning(f"{ranking} 简历表截取失败，使用源文件进行提取")
                    resume_table_content = original_content
                else:
                    logger.info(f"{ranking} 使用截取的简历表内容进行提取，长度: {len(resume_table_content)} 字符")
                
                # 调用简历表人员姓名提取
                result = await processor.extract_resume_personnel_names(
                    business_score_clauses,
                    resume_table_content,
                    ranking
                )
                
                if result.get('extraction_performed', False):
                    variables = result.get('variables', [])
                    
                    # 为每个变量添加排名信息和引用来源
                    for var in variables:
                        var['reference_source'] = {
                            'source_type': 'resume_table_extraction',
                            'source_url': file_info.get('file_url', ''),
                            'ranking': ranking,
                            'extraction_method': 'resume_table_cut' if file_info.get('resume_table_content') else 'source_file'
                        }
                        extracted_variables.append(var)
                    
                    logger.info(f"{ranking} 成功提取 {len(variables)} 个简历表人员姓名变量")
                else:
                    logger.info(f"{ranking} 跳过简历表人员姓名提取: {result.get('reason', '未知原因')}")
                    
            except Exception as e:
                logger.error(f"{ranking} 简历表人员姓名提取失败: {e}")
            
            return extracted_variables
        
        # 并发处理所有排名
        tasks = []
        for ranking, file_info in ranked_files.items():
            tasks.append(process_single_ranking(ranking, file_info))
        
        if tasks:
            logger.info(f"开始并发执行 {len(tasks)} 个简历表人员姓名提取任务")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            all_extracted_variables = []
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    ranking = list(ranked_files.keys())[i]
                    logger.error(f"{ranking} 简历表人员姓名提取任务异常: {res}")
                    continue
                if res:
                    all_extracted_variables.extend(res)
            
            logger.info(f"成功从排名文件中并发提取了 {len(all_extracted_variables)} 个简历表人员姓名变量")
            return all_extracted_variables
        else:
            logger.warning("没有找到需要处理的排名文件")
            return []
            
    except Exception as e:
        logger.error(f"从排名文件提取简历表人员姓名失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []
