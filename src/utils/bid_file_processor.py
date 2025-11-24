#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投标文件处理器模块

本模块用于从截取的业绩文本中提取业绩汇总表和单个业绩信息。
主要功能包括：
- 从业绩文本中提取完整的业绩汇总表
- 提取每个单独的业绩项目
- 使用HTML表格标签格式化输出
- 调用AI模型进行智能提取
"""

import logging
import re
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from common.llm_client import LLMClient
from prompts.performance_extraction_prompt import build_performance_extraction_prompt

logger = logging.getLogger(__name__)


class BidFileProcessor:
    """投标文件处理器"""
    
    def __init__(self):
        """初始化处理器"""
        self.logger = logger
        self.llm_client = LLMClient()
    
    async def extract_performance_tables_from_text(
        self, 
        performance_text: str, 
        ranking: str = "第一名",
        clause_name: str = "业绩"
    ) -> Dict[str, Any]:
        """
        从业绩文本中提取业绩汇总表和单个业绩
        
        Args:
            performance_text: 截取的业绩文本内容
            ranking: 排名信息（如"第一名"、"第二名"等）
            clause_name: 条款名称（如"业绩要求"、"投标人近年类似项目业绩"等）
            
        Returns:
            Dict[str, Any]: 包含业绩汇总表和单个业绩的字典
        """
        try:
            self.logger.info(f"开始从{ranking}的{clause_name}文本中提取业绩表格...")
            self.logger.info(f"业绩文本长度: {len(performance_text)} 字符")
            
            if not performance_text or len(performance_text.strip()) < 50:
                self.logger.warning(f"{ranking}的{clause_name}文本内容为空或过短")
                return {
                    'success': False,
                    'error': '业绩文本内容为空或过短',
                    'performance_summary_table': '',
                    'individual_performances': []
                }
            
            # 构建AI提取提示词
            prompt = build_performance_extraction_prompt(performance_text, ranking, clause_name)
            
            # 调用AI模型进行提取（带重试机制）
            parsed_result = await self._extract_with_retry(prompt, performance_text, ranking, clause_name)
            
            if parsed_result['success']:
                self.logger.info(f"成功提取{ranking}的业绩表格，汇总表1个，单个业绩{len(parsed_result['individual_performances'])}个")
            else:
                self.logger.error(f"提取{ranking}的业绩表格失败: {parsed_result['error']}")
            
            return parsed_result
            
        except Exception as e:
            self.logger.error(f"提取{ranking}的业绩表格失败: {e}")
            return {
                'success': False,
                'error': f'提取失败: {str(e)}',
                'performance_summary_table': '',
                'individual_performances': []
            }
    
    
    def _parse_ai_result(self, ai_result: str, ranking: str, clause_name: str = "业绩") -> Dict[str, Any]:
        """
        解析AI返回的结果
        
        Args:
            ai_result: AI返回的原始结果
            ranking: 排名信息
            clause_name: 条款名称
            
        Returns:
            Dict[str, Any]: 解析后的结果
        """
        try:
            # 清理AI返回的结果
            clean_result = ai_result.strip()
            
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
            
            # 尝试直接解析JSON
            result_data = json.loads(clean_result)
            
            # 验证和格式化结果
            formatted_result = self._format_extraction_result(result_data, ranking, clause_name)
            
            return formatted_result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"解析AI结果JSON失败: {e}")
            self.logger.error(f"原始内容: {ai_result[:500]}")
            return {
                'success': False,
                'error': f'JSON解析失败: {str(e)}',
                'performance_summary_table': '',
                'individual_performances': []
            }
        except Exception as e:
            self.logger.error(f"解析AI结果失败: {e}")
            return {
                'success': False,
                'error': f'解析失败: {str(e)}',
                'performance_summary_table': '',
                'individual_performances': []
            }
    
    async def _extract_with_retry(self, prompt: str, performance_text: str, ranking: str, clause_name: str = "业绩") -> Dict[str, Any]:
        """
        带重试机制的AI提取方法
        
        Args:
            prompt: 提示词
            performance_text: 业绩文本
            ranking: 排名信息
            clause_name: 条款名称
            
        Returns:
            Dict[str, Any]: 解析后的结果
        """
        max_retries = 1
        
        for attempt in range(max_retries + 1):
            try:
                # 调用AI模型进行提取
                result = await self.llm_client.call_llm(
                    prompt=prompt,
                    file_content=performance_text,
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
                            'success': False,
                            'error': 'AI模型返回空结果',
                            'performance_summary_table': '',
                            'individual_performances': []
                        }
                
                # 解析AI返回的结果
                parsed_result = self._parse_ai_result(result, ranking, clause_name)
                
                # 检查解析结果
                if parsed_result['success']:
                    return parsed_result
                else:
                    if attempt < max_retries:
                        self.logger.warning(f"第{attempt + 1}次解析失败: {parsed_result['error']}，准备重试")
                        continue
                    else:
                        self.logger.error(f"重试后仍然解析失败: {parsed_result['error']}")
                        return parsed_result
                        
            except Exception as e:
                if attempt < max_retries:
                    self.logger.warning(f"第{attempt + 1}次调用发生异常: {e}，准备重试")
                    continue
                else:
                    self.logger.error(f"重试后仍然发生异常: {e}")
                    return {
                        'success': False,
                        'error': f'提取失败: {str(e)}',
                        'performance_summary_table': '',
                        'individual_performances': []
                    }
        
        # 不应该到达这里，但为了安全起见
        return {
            'success': False,
            'error': '未知错误',
            'performance_summary_table': '',
            'individual_performances': []
        }
    
    def _fix_truncated_json(self, json_str: str) -> str:
        """
        修复被截断的JSON
        
        Args:
            json_str: 被截断的JSON字符串
            
        Returns:
            str: 修复后的JSON字符串
        """
        # 如果JSON被截断，尝试补全
        if not json_str.strip().endswith('}'):
            # 找到最后一个完整的键值对
            last_complete_pos = json_str.rfind('",')
            if last_complete_pos != -1:
                # 截断到最后一个完整的键值对
                json_str = json_str[:last_complete_pos + 1]
                # 补全JSON结构
                json_str += '}'
            else:
                # 如果找不到完整的键值对，尝试补全基本结构
                if '"table_content":' in json_str:
                    # 找到table_content的开始位置
                    table_start = json_str.find('"table_content":')
                    if table_start != -1:
                        # 截断到table_content开始
                        json_str = json_str[:table_start + len('"table_content":')]
                        json_str += '""}'
                    else:
                        json_str += '}'
                else:
                    json_str += '}'
        
        return json_str
    
    def _aggressive_json_fix(self, json_str: str) -> str:
        """
        激进的JSON修复策略
        
        Args:
            json_str: JSON字符串
            
        Returns:
            str: 修复后的JSON字符串
        """
        # 确保JSON以{开始，}结束
        if not json_str.strip().startswith('{'):
            json_str = '{' + json_str
        if not json_str.strip().endswith('}'):
            json_str = json_str + '}'
        
        # 修复未闭合的字符串
        json_str = re.sub(r'("table_content":\s*"[^"]*?)\n([^"]*?")', r'\1\\n\2', json_str)
        
        # 修复未转义的换行符
        json_str = re.sub(r'(?<!\\)\n', '\\n', json_str)
        
        # 修复未转义的引号
        json_str = re.sub(r'(?<!\\)"', '\\"', json_str)
        
        # 修复未转义的反斜杠
        json_str = re.sub(r'(?<!\\)\\', '\\\\', json_str)
        
        return json_str
    
    def _format_extraction_result(self, result_data: Dict[str, Any], ranking: str, clause_name: str = "业绩") -> Dict[str, Any]:
        """
        格式化提取结果
        
        Args:
            result_data: 解析后的数据
            ranking: 排名信息
            clause_name: 条款名称
            
        Returns:
            Dict[str, Any]: 格式化后的结果
        """
        try:
            # 验证必要字段
            if 'performance_summary_table' not in result_data:
                return {
                    'success': False,
                    'error': '缺少业绩汇总表字段',
                    'performance_summary_table': '',
                    'individual_performances': []
                }
            
            if 'individual_performances' not in result_data:
                result_data['individual_performances'] = []
            
            # 格式化业绩汇总表
            summary_table = result_data['performance_summary_table']
            if isinstance(summary_table, dict) and 'table_content' in summary_table:
                formatted_summary = {
                    'variable_name': f"{ranking}{clause_name}汇总表",
                    'table_content': summary_table['table_content']
                }
            else:
                formatted_summary = {
                    'variable_name': f"{ranking}{clause_name}汇总表",
                    'table_content': str(summary_table) if summary_table else ''
                }
            
            # 格式化单个业绩
            individual_performances = []
            if isinstance(result_data['individual_performances'], list):
                for i, perf in enumerate(result_data['individual_performances'], 1):
                    if isinstance(perf, dict) and 'table_content' in perf:
                        formatted_perf = {
                            'variable_name': f"{ranking}{clause_name}表{i}",
                            'table_content': perf['table_content']
                        }
                    else:
                        formatted_perf = {
                            'variable_name': f"{ranking}{clause_name}表{i}",
                            'table_content': str(perf) if perf else ''
                        }
                    individual_performances.append(formatted_perf)
            
            # 验证表格内容
            if not self._validate_table_content(formatted_summary['table_content']):
                self.logger.warning(f"{ranking}业绩汇总表内容格式可能不正确")
            
            for i, perf in enumerate(individual_performances):
                if not self._validate_table_content(perf['table_content']):
                    self.logger.warning(f"{ranking}业绩表{i+1}内容格式可能不正确")
            
            return {
                'success': True,
                'error': '',
                'performance_summary_table': formatted_summary,
                'individual_performances': individual_performances
            }
            
        except Exception as e:
            self.logger.error(f"格式化提取结果失败: {e}")
            return {
                'success': False,
                'error': f'格式化失败: {str(e)}',
                'performance_summary_table': '',
                'individual_performances': []
            }
    
    def _validate_table_content(self, table_content: str) -> bool:
        """
        验证表格内容格式
        
        Args:
            table_content: 表格内容
            
        Returns:
            bool: 格式是否正确
        """
        if not table_content or not isinstance(table_content, str):
            return False
        
        # 检查是否包含基本的HTML表格标签
        has_table = '<table' in table_content.lower()
        has_tr = '<tr' in table_content.lower()
        has_td = '<td' in table_content.lower()
        
        return has_table and has_tr and has_td
    
    async def process_multiple_rankings(
        self, 
        performance_texts: Dict[str, str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        批量处理多个排名的业绩文本（异步并发处理）
        
        Args:
            performance_texts: 业绩文本字典，格式为 {"第一名": "业绩文本", "第二名": "业绩文本", ...}
            
        Returns:
            Dict[str, Dict[str, Any]]: 处理结果字典
        """
        try:
            self.logger.info(f"开始批量处理 {len(performance_texts)} 个排名的业绩文本（异步并发）")
            
            # 创建所有任务的字典，键为ranking，值为task
            async def process_single_ranking(ranking: str, performance_text: str) -> Tuple[str, Dict[str, Any]]:
                """处理单个排名的包装函数，用于捕获异常"""
                try:
                    result = await self.extract_performance_tables_from_text(performance_text, ranking)
                    self.logger.info(f"{ranking}处理完成，成功: {result['success']}")
                    return (ranking, result)
                except Exception as e:
                    self.logger.error(f"{ranking}处理失败: {e}")
                    return (ranking, {
                        'success': False,
                        'error': f'处理失败: {str(e)}',
                        'performance_summary_table': '',
                        'individual_performances': []
                    })
            
            # 创建所有任务
            tasks = [
                process_single_ranking(ranking, performance_text)
                for ranking, performance_text in performance_texts.items()
            ]
            
            # 并发执行所有任务
            results_list = await asyncio.gather(*tasks)
            
            # 将结果列表转换为字典
            results = {ranking: result for ranking, result in results_list}
            
            success_count = sum(1 for r in results.values() if r['success'])
            self.logger.info(f"批量处理完成，成功处理 {success_count}/{len(performance_texts)} 个排名")
            
            return results
            
        except Exception as e:
            self.logger.error(f"批量处理失败: {e}")
            return {}
    
    def get_extraction_summary(self, results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取提取结果摘要
        
        Args:
            results: 处理结果字典
            
        Returns:
            Dict[str, Any]: 摘要信息
        """
        try:
            total_rankings = len(results)
            successful_rankings = sum(1 for r in results.values() if r['success'])
            total_individual_performances = sum(
                len(r.get('individual_performances', [])) 
                for r in results.values() 
                if r['success']
            )
            
            summary = {
                'total_rankings': total_rankings,
                'successful_rankings': successful_rankings,
                'failed_rankings': total_rankings - successful_rankings,
                'total_individual_performances': total_individual_performances,
                'success_rate': f"{(successful_rankings / total_rankings * 100):.1f}%" if total_rankings > 0 else "0%"
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"生成摘要失败: {e}")
            return {}
    
    async def process_step5_performance_variables(
        self,
        variables_list: List[Dict[str, Any]],
        business_score_clauses: str,
        candidate_count: int = 3
    ) -> List[Dict[str, Any]]:
        """
        第五步业绩变量处理功能 -
        
        新的分类逻辑（不再使用"三"前缀）：
        1. 新建'第几名业绩1'变量，复制'第几名业绩1'的内容（如果不存在）
        2. 保持其他'第几名业绩+序号'变量不变（不再重命名为'三第几名业绩+序号'）
        3. 通过'第几名业绩表+序号'和'二第几名+业绩条款+姓名'匹配
        4. 匹配后新建'第几名+业绩条款+序号'变量（不再使用"三"前缀）
        5. 剩余变量重命名为'第几名+剩下条款+序号'（不再使用"三"前缀）
        
        Args:
            variables_list: 第四步提取的变量列表
            business_score_clauses: 商务评分标准内容
            candidate_count: 候选人数量
            
        Returns:
            List[Dict[str, Any]]: 处理后的变量列表
        """
        try:
            self.logger.info("开始第五步业绩变量处理（重构版本）...")
            
            # 1. 获取商务评分标准，提取包含业绩的条款
            performance_clauses = self._extract_performance_clauses(business_score_clauses)
            self.logger.info(f"提取到业绩条款: {performance_clauses}")
            
            if not performance_clauses:
                self.logger.warning("没有找到业绩相关条款，跳过第五步处理")
                return variables_list
            
            # 2. 执行新的分类逻辑
            new_variables = await self._process_new_performance_classification(
                variables_list, performance_clauses, candidate_count
            )
            
            # 3. 合并原变量和新变量
            result_variables = variables_list + new_variables
            self.logger.info(f"第五步处理完成，新增变量: {len(new_variables)} 个")
            
            return result_variables
            
        except Exception as e:
            self.logger.error(f"第五步业绩变量处理失败: {e}")
            return variables_list
    
    def _extract_performance_clauses(self, business_score_clauses: str) -> List[str]:
        """
        从商务评分标准中提取包含业绩的条款
        
        Args:
            business_score_clauses: 商务评分标准内容
            
        Returns:
            List[str]: 包含业绩的条款列表
        """
        try:
            if not business_score_clauses:
                return []
            
            # 按顿号分割条款
            clauses = [clause.strip() for clause in business_score_clauses.split('、') if clause.strip()]
            
            # 筛选包含业绩的条款
            performance_clauses = []
            for clause in clauses:
                if '业绩' in clause:
                    performance_clauses.append(clause)
            
            return performance_clauses
            
        except Exception as e:
            self.logger.error(f"提取业绩条款失败: {e}")
            return []
    
    def _filter_step4_performance_variables(
        self, 
        variables_list: List[Dict[str, Any]], 
        candidate_count: int
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        筛选第四步的业绩变量，分别获取业绩表变量和业绩变量
        
        Args:
            variables_list: 变量列表
            candidate_count: 候选人数量
            
        Returns:
            Dict[str, Dict[str, List[Dict[str, Any]]]]: 按排名分组的业绩变量
            格式: {"第一名": {"performance_tables": [...], "performances": [...]}}
        """
        try:
            # 中文排名映射
            chinese_ordinals = ["第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]
            
            step4_performance_vars = {}
            
            for i in range(1, candidate_count + 1):
                if i <= len(chinese_ordinals):
                    rank_name = f"{chinese_ordinals[i-1]}名"
                else:
                    rank_name = f"第{i}名"
                
                step4_performance_vars[rank_name] = {
                    "performance_tables": [],  # 业绩表变量（用于匹配姓名）
                    "performances": []         # 业绩变量（用于复制内容）
                }
                
                # 筛选该排名的业绩表变量（格式：第几名{条款名称}表1、第几名{条款名称}表2等）
                # 例如："第一名业绩要求表1"、"第一名投标人近年类似项目业绩表2"
                for var in variables_list:
                    if isinstance(var, dict) and "variable_name" in var:
                        var_name = var["variable_name"]
                        if (var_name.startswith(rank_name) and 
                            "表" in var_name and 
                            "汇总表" not in var_name and
                            var_name != f"{rank_name}业绩数量"):
                            # 匹配模式：排名 + 条款名称 + "表" + 数字
                            # 例如："第一名业绩要求表1" -> 提取"1"
                            match = re.search(rf'{re.escape(rank_name)}(.+?)表(\d+)', var_name)
                            if match:
                                step4_performance_vars[rank_name]["performance_tables"].append(var)
                
                # 筛选该排名的业绩变量（格式：第几名{条款名称}1、第几名{条款名称}2等）
                # 例如："第一名业绩要求1"、"第一名投标人近年类似项目业绩2"
                for var in variables_list:
                    if isinstance(var, dict) and "variable_name" in var:
                        var_name = var["variable_name"]
                        if (var_name.startswith(rank_name) and 
                            "业绩" in var_name and 
                            "表" not in var_name and
                            "汇总表" not in var_name and
                            var_name != f"{rank_name}业绩数量"):
                            # 匹配模式：排名 + 条款名称 + 数字
                            # 例如："第一名业绩要求1" -> 提取"1"
                            match = re.search(rf'{re.escape(rank_name)}(.+?)(\d+)$', var_name)
                            if match:
                                step4_performance_vars[rank_name]["performances"].append(var)
            
            return step4_performance_vars
            
        except Exception as e:
            self.logger.error(f"筛选第四步业绩变量失败: {e}")
            return {}
    
    def _process_single_performance_clause(
        self,
        step4_performance_vars: Dict[str, Dict[str, List[Dict[str, Any]]]],
        performance_clause: str,
        candidate_count: int
    ) -> List[Dict[str, Any]]:
        """
        处理单个业绩条款的情况
        
        Args:
            step4_performance_vars: 第四步业绩变量
            performance_clause: 业绩条款名称
            candidate_count: 候选人数量
            
        Returns:
            List[Dict[str, Any]]: 新增的变量列表
        """
        try:
            new_variables = []
            
            # 中文排名映射
            chinese_ordinals = ["第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]
            
            for i in range(1, candidate_count + 1):
                if i <= len(chinese_ordinals):
                    rank_name = f"{chinese_ordinals[i-1]}名"
                else:
                    rank_name = f"第{i}名"
                
                # 获取该排名的业绩变量
                rank_vars = step4_performance_vars.get(rank_name, {})
                performance_vars = rank_vars.get("performances", [])
                
                # 为每个业绩变量创建新变量（不再使用"三"前缀）
                for j, var in enumerate(performance_vars, 1):
                    new_var = {
                        "variable_name": f"{rank_name}{performance_clause}{j}",
                        "variable_value": var.get("variable_value", ""),
                        "reference_source": var.get("reference_source", {})
                    }
                    new_variables.append(new_var)
                    self.logger.info(f"创建新变量: {new_var['variable_name']}")
            
            return new_variables
            
        except Exception as e:
            self.logger.error(f"处理单个业绩条款失败: {e}")
            return []
    
    async def _process_multiple_performance_clauses(
        self,
        step4_performance_vars: Dict[str, Dict[str, List[Dict[str, Any]]]],
        performance_clauses: List[str],
        variables_list: List[Dict[str, Any]],
        candidate_count: int
    ) -> List[Dict[str, Any]]:
        """
        处理多个业绩条款的情况
        
        Args:
            step4_performance_vars: 第四步业绩变量
            performance_clauses: 业绩条款列表
            variables_list: 完整变量列表（用于查找简历表姓名变量）
            candidate_count: 候选人数量
            
        Returns:
            List[Dict[str, Any]]: 新增的变量列表
        """
        try:
            new_variables = []
            
            # 中文排名映射
            chinese_ordinals = ["第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]
            
            for i in range(1, candidate_count + 1):
                if i <= len(chinese_ordinals):
                    rank_name = f"{chinese_ordinals[i-1]}名"
                else:
                    rank_name = f"第{i}名"
                
                # 获取该排名的业绩变量
                rank_vars = step4_performance_vars.get(rank_name, {})
                performance_tables = rank_vars.get("performance_tables", [])  # 业绩表变量（用于匹配姓名）
                performance_vars = rank_vars.get("performances", [])          # 业绩变量（用于复制内容）
                
                # 1. 筛选得到尾部含"姓名"且以"二"开头的变量名
                name_variable_names = []
                for var in variables_list:
                    if isinstance(var, dict) and "variable_name" in var:
                        var_name = var["variable_name"]
                        # 筛选二第几名+XXX姓名的变量
                        if (var_name.endswith("姓名") and 
                            var_name.startswith("二") and 
                            var_name.startswith(f"二{rank_name}")):
                            name_variable_names.append(var)
                
                self.logger.info(f"{rank_name} 找到姓名变量: {[var['variable_name'] for var in name_variable_names]}")
                
                # 2. 从姓名变量名中提取条款名称（去掉"二第几名"和"姓名"后缀）
                matched_clauses_from_names = []
                for name_var in name_variable_names:
                    var_name = name_var.get("variable_name", "")
                    # 去掉"姓名"后缀
                    base_name = var_name.replace("姓名", "")
                    # 去掉"二第几名"前缀
                    if base_name.startswith(f"二{rank_name}"):
                        clause_name = base_name[len(f"二{rank_name}"):]
                        if clause_name and clause_name not in matched_clauses_from_names:
                            matched_clauses_from_names.append(clause_name)
                            self.logger.info(f"{rank_name} 从姓名变量 {var_name} 提取条款: {clause_name}")
                
                # 3. 从商务评分标准中排除已匹配的条款，获取默认业绩条款
                default_clause = None
                for clause in performance_clauses:
                    if clause not in matched_clauses_from_names:
                        default_clause = clause
                        break
                
                self.logger.info(f"{rank_name} 匹配到的条款: {matched_clauses_from_names}")
                self.logger.info(f"{rank_name} 默认条款: {default_clause}")
                
                # 4. 记录已使用的业绩变量
                used_performance_vars = set()
                
                # 5. 对每个匹配到的条款进行姓名匹配和业绩分类
                for clause in matched_clauses_from_names:
                    # 查找对应的姓名变量
                    name_var = None
                    for var in name_variable_names:
                        var_name = var.get("variable_name", "")
                        if var_name == f"二{rank_name}{clause}姓名":
                            name_var = var
                            break
                    
                    if name_var:
                        # 在业绩表中查找匹配的姓名
                        matched_vars = self._match_performance_by_name_in_table(
                            performance_tables, performance_vars, name_var, clause, rank_name
                        )
                        new_variables.extend(matched_vars)
                        
                        # 记录已使用的业绩变量
                        for var in matched_vars:
                            var_name = var.get('variable_name', '')
                            if '业绩' in var_name:
                                # 从新变量名中提取原始业绩变量名
                                # 例如："第一名项目经理业绩1" -> "第一名业绩1"
                                # 需要提取序号
                                import re
                                match = re.search(r'业绩(\d+)', var_name)
                                if match:
                                    performance_num = match.group(1)
                                    original_name = f"{rank_name}业绩{performance_num}"
                                    used_performance_vars.add(original_name)
                                    self.logger.info(f"记录已使用业绩变量: {original_name}")
                        
                        self.logger.info(f"{rank_name} {clause} 匹配到姓名变量，新建 {len(matched_vars)} 个变量")
                
                # 6. 处理剩余未匹配的业绩变量，统一归入默认条款
                if default_clause:
                    # 找出未被使用的业绩变量
                    remaining_performance_vars = []
                    for var in performance_vars:
                        var_name = var.get('variable_name', '')
                        if var_name not in used_performance_vars:
                            remaining_performance_vars.append(var)
                    
                    if remaining_performance_vars:
                        # 为剩余变量创建新变量，变量名 = 第几名+默认条款名称+序号（不再使用"三"前缀）
                        default_vars = self._create_default_performance_variables_with_reset_counter(
                            remaining_performance_vars, default_clause, rank_name
                        )
                        new_variables.extend(default_vars)
                        self.logger.info(f"{rank_name} 默认条款 {default_clause} 新建 {len(default_vars)} 个变量")
                    else:
                        self.logger.info(f"{rank_name} 默认条款 {default_clause} 没有剩余业绩变量")
                else:
                    self.logger.info(f"{rank_name} 所有条款都匹配到了姓名变量，无需创建默认条款变量")
            
            return new_variables
            
        except Exception as e:
            self.logger.error(f"处理多个业绩条款失败: {e}")
            return []
    
    def _find_resume_name_variables(
        self, 
        variables_list: List[Dict[str, Any]], 
        performance_clauses: List[str],
        rank_name: str = None
    ) -> List[Dict[str, Any]]:
        """
        查找简历表中的姓名变量
        
        Args:
            variables_list: 变量列表
            performance_clauses: 业绩条款列表
            rank_name: 排名名称（如"第一名"、"第二名"等），如果提供则只查找对应排名的姓名变量
            
        Returns:
            List[Dict[str, Any]]: 姓名变量列表
        """
        try:
            name_vars = []
            
            for var in variables_list:
                if isinstance(var, dict) and "variable_name" in var:
                    var_name = var["variable_name"]
                    # 查找以"姓名"结尾且以"二"开头的变量
                    if var_name.endswith("姓名") and var_name.startswith("二"):
                        # 如果指定了排名，只查找对应排名的姓名变量
                        if rank_name:
                            if var_name.startswith(f"二{rank_name}"):
                                name_vars.append(var)
                                self.logger.info(f"找到{rank_name}的姓名变量: {var_name}")
                        else:
                            name_vars.append(var)
            
            if rank_name:
                self.logger.info(f"为{rank_name}找到 {len(name_vars)} 个姓名变量")
            else:
                self.logger.info(f"找到 {len(name_vars)} 个姓名变量")
            
            return name_vars
            
        except Exception as e:
            self.logger.error(f"查找简历表姓名变量失败: {e}")
            return []
    
    def _find_matching_name_variable(
        self, 
        name_vars: List[Dict[str, Any]], 
        clause: str
    ) -> Optional[Dict[str, Any]]:
        """
        查找与业绩条款匹配的姓名变量
        
        Args:
            name_vars: 姓名变量列表
            clause: 业绩条款名称
            
        Returns:
            Optional[Dict[str, Any]]: 匹配的姓名变量，如果没有则返回None
        """
        try:
            for name_var in name_vars:
                var_name = name_var.get("variable_name", "")
                self.logger.info(f"检查姓名变量: {var_name} 是否匹配条款: {clause}")
                
                # 新的变量名格式：二第几名+条款原文+姓名
                # 去掉"姓名"后缀和"二"前缀，检查是否与条款匹配
                base_name = var_name.replace("姓名", "")
                if base_name.startswith("二"):
                    base_name = base_name[1:]
                
                # 更精确的匹配逻辑
                if (base_name in clause or 
                    clause in base_name or
                    any(keyword in base_name and keyword in clause 
                        for keyword in ["项目经理", "技术负责人", "施工负责人", "设计负责人", "安全负责人"])):
                    self.logger.info(f"找到匹配的姓名变量: {var_name}")
                    return name_var
            
            self.logger.warning(f"未找到匹配条款 '{clause}' 的姓名变量")
            return None
            
        except Exception as e:
            self.logger.error(f"查找匹配姓名变量失败: {e}")
            return None
    
    def _match_performance_by_name(
        self,
        performance_vars: List[Dict[str, Any]],
        name_var: Dict[str, Any],
        clause: str,
        rank_name: str
    ) -> List[Dict[str, Any]]:
        """
        根据姓名匹配业绩变量
        
        Args:
            performance_vars: 业绩变量列表
            name_var: 姓名变量
            clause: 业绩条款名称
            rank_name: 排名名称
            
        Returns:
            List[Dict[str, Any]]: 匹配后的新变量列表
        """
        try:
            new_variables = []
            person_name = name_var.get("variable_value", "")
            
            # 从姓名变量名中提取职位名称（去掉"姓名"后缀）
            position_name = name_var.get("variable_name", "").replace("姓名", "")
            
            # 为每个业绩变量创建新变量
            for j, var in enumerate(performance_vars, 1):
                # 检查业绩内容中是否包含该姓名
                performance_content = var.get("variable_value", "")
                if person_name in performance_content:
                    new_var = {
                        "variable_name": f"{rank_name}{position_name}{j}",
                        "variable_value": var.get("variable_value", ""),
                        "reference_source": var.get("reference_source", {})
                    }
                    new_variables.append(new_var)
                    self.logger.info(f"根据姓名匹配创建变量: {new_var['variable_name']}")
            
            return new_variables
            
        except Exception as e:
            self.logger.error(f"根据姓名匹配业绩失败: {e}")
            return []
    
    def _match_performance_by_name_in_table(
        self,
        performance_tables: List[Dict[str, Any]],
        performance_vars: List[Dict[str, Any]],
        name_var: Dict[str, Any],
        clause: str,
        rank_name: str
    ) -> List[Dict[str, Any]]:
        """
        在业绩表中查找匹配的姓名，然后复制对应序号的业绩变量
        
        Args:
            performance_tables: 业绩表变量列表（用于匹配姓名）
            performance_vars: 业绩变量列表（用于复制内容）
            name_var: 姓名变量
            clause: 业绩条款名称
            rank_name: 排名名称
            
        Returns:
            List[Dict[str, Any]]: 匹配后的新变量列表
        """
        try:
            new_variables = []
            person_name = name_var.get("variable_value", "").strip()
            
            if not person_name:
                self.logger.warning(f"姓名变量值为空，跳过{clause}条款的业绩匹配")
                return []
            
            self.logger.info(f"在业绩表中查找姓名: '{person_name}'")
            
            # 计数器，从1开始
            counter = 1
            
            # 遍历每个业绩表变量，查找匹配的姓名
            for table_var in performance_tables:
                table_content = table_var.get("variable_value", "")
                table_name = table_var.get("variable_name", "")
                
                self.logger.info(f"检查业绩表 {table_name} 是否包含姓名 '{person_name}'")
                self.logger.info(f"业绩表内容前200字符: {table_content[:200]}")
                
                if person_name in table_content:
                    # 找到匹配的业绩表，复制对应的业绩变量
                    # 从业绩表名中提取条款名称和序号，如"第一名业绩要求表1" -> 条款："业绩要求"，序号："1"
                    # 匹配模式：排名 + 条款名称 + "表" + 数字
                    match = re.search(rf'{re.escape(rank_name)}(.+?)表(\d+)', table_name)
                    if match:
                        clause_in_table = match.group(1)  # 条款名称，如"业绩要求"
                        table_index = int(match.group(2))  # 序号，如"1"
                        # 查找对应的业绩变量（如"第一名业绩要求1"）
                        for perf_var in performance_vars:
                            perf_name = perf_var.get("variable_name", "")
                            # 匹配模式：排名 + 条款名称 + 数字
                            perf_match = re.search(rf'{re.escape(rank_name)}(.+?)(\d+)$', perf_name)
                            if perf_match:
                                clause_in_perf = perf_match.group(1)  # 条款名称
                                perf_index = int(perf_match.group(2))  # 序号
                                # 匹配条款名称和序号
                                if clause_in_perf == clause_in_table and perf_index == table_index:
                                    new_var = {
                                        "variable_name": f"{rank_name}{clause}{counter}",
                                        "variable_value": perf_var.get("variable_value", ""),
                                        "reference_source": perf_var.get("reference_source", {})
                                    }
                                    new_variables.append(new_var)
                                    self.logger.info(f"根据业绩表姓名'{person_name}'匹配创建变量: {new_var['variable_name']} (从{perf_name}匹配)")
                                    counter += 1
                                    break
            
            self.logger.info(f"为{clause}条款匹配到 {len(new_variables)} 个业绩变量")
            return new_variables
            
        except Exception as e:
            self.logger.error(f"根据业绩表姓名匹配业绩失败: {e}")
            return []
    
    def _match_performance_by_table_name_with_reset_counter(
        self,
        performance_tables: List[Dict[str, Any]],
        performance_vars: List[Dict[str, Any]],
        name_var: Dict[str, Any],
        clause: str,
        rank_name: str
    ) -> List[Dict[str, Any]]:
        """
        根据业绩表变量中的姓名匹配业绩变量（序号从1开始重新计数）
        
        Args:
            performance_tables: 业绩表变量列表（用于匹配姓名）
            performance_vars: 业绩变量列表（用于复制内容）
            name_var: 姓名变量
            clause: 业绩条款名称
            rank_name: 排名名称
            
        Returns:
            List[Dict[str, Any]]: 匹配后的新变量列表
        """
        try:
            new_variables = []
            person_name = name_var.get("variable_value", "").strip()
            
            if not person_name:
                self.logger.warning(f"姓名变量值为空，将所有业绩归入{clause}条款")
                # 如果姓名为空，将所有业绩都归入这个条款类型
                return self._create_default_performance_variables_with_reset_counter(
                    performance_vars, clause, rank_name
                )
            
            # 从姓名变量名中提取职位名称（去掉排名和"姓名"后缀）
            var_name = name_var.get("variable_name", "")
            # 去掉"姓名"后缀
            base_name = var_name.replace("姓名", "")
            # 去掉排名前缀（如"第一名"、"第二名"等）
            position_name = base_name
            for prefix in ["第一名", "第二名", "第三名", "第四名", "第五名", "第六名", "第七名", "第八名", "第九名", "第十名"]:
                if position_name.startswith(prefix):
                    position_name = position_name[len(prefix):]
                    break
            
            # 计数器，每类条款都从1开始
            counter = 1
            
                # 为每个业绩表变量匹配对应的业绩变量
            for table_var in performance_tables:
                # 检查业绩表内容中是否包含该姓名
                table_content = table_var.get("variable_value", "")
                table_name = table_var.get("variable_name", "")
                self.logger.info(f"检查业绩表 {table_name} 是否包含姓名 '{person_name}'")
                self.logger.info(f"业绩表内容前200字符: {table_content[:200]}")
                if person_name in table_content:
                    # 找到匹配的业绩表，复制对应的业绩变量
                    table_name = table_var.get("variable_name", "")
                    # 从业绩表名中提取条款名称和序号，如"第一名业绩要求表1" -> 条款："业绩要求"，序号："1"
                    # 匹配模式：排名 + 条款名称 + "表" + 数字
                    match = re.search(rf'{re.escape(rank_name)}(.+?)表(\d+)', table_name)
                    if match:
                        clause_in_table = match.group(1)  # 条款名称，如"业绩要求"
                        table_index = int(match.group(2))  # 序号，如"1"
                        # 查找对应的业绩变量（如"第一名业绩要求1"）
                        for perf_var in performance_vars:
                            perf_name = perf_var.get("variable_name", "")
                            # 匹配模式：排名 + 条款名称 + 数字
                            perf_match = re.search(rf'{re.escape(rank_name)}(.+?)(\d+)$', perf_name)
                            if perf_match:
                                clause_in_perf = perf_match.group(1)  # 条款名称
                                perf_index = int(perf_match.group(2))  # 序号
                                # 匹配条款名称和序号
                                if clause_in_perf == clause_in_table and perf_index == table_index:
                                    new_var = {
                                        "variable_name": f"{rank_name}{position_name}{counter}",
                                        "variable_value": perf_var.get("variable_value", ""),
                                        "reference_source": perf_var.get("reference_source", {})
                                    }
                                    new_variables.append(new_var)
                                    self.logger.info(f"根据业绩表姓名'{person_name}'匹配创建变量: {new_var['variable_name']} (从{perf_name}匹配)")
                                    counter += 1
                                    break
                else:
                    # 没有匹配到姓名，也要创建变量，归入默认条款
                    table_name = table_var.get("variable_name", "")
                    # 从业绩表名中提取条款名称和序号
                    match = re.search(rf'{re.escape(rank_name)}(.+?)表(\d+)', table_name)
                    if match:
                        clause_in_table = match.group(1)  # 条款名称
                        table_index = int(match.group(2))  # 序号
                        # 查找对应的业绩变量
                        for perf_var in performance_vars:
                            perf_name = perf_var.get("variable_name", "")
                            # 匹配模式：排名 + 条款名称 + 数字
                            perf_match = re.search(rf'{re.escape(rank_name)}(.+?)(\d+)$', perf_name)
                            if perf_match:
                                clause_in_perf = perf_match.group(1)  # 条款名称
                                perf_index = int(perf_match.group(2))  # 序号
                                # 匹配条款名称和序号
                                if clause_in_perf == clause_in_table and perf_index == table_index:
                                    new_var = {
                                        "variable_name": f"{rank_name}{clause}{counter}",
                                        "variable_value": perf_var.get("variable_value", ""),
                                        "reference_source": perf_var.get("reference_source", {})
                                    }
                                    new_variables.append(new_var)
                                    self.logger.info(f"未匹配到姓名'{person_name}'，归入默认条款: {new_var['variable_name']} (从{perf_name}匹配)")
                                    counter += 1
                                    break
            
            return new_variables
            
        except Exception as e:
            self.logger.error(f"根据业绩表姓名匹配业绩失败: {e}")
            return []
    
    def _create_default_performance_variables(
        self,
        performance_vars: List[Dict[str, Any]],
        clause: str,
        rank_name: str
    ) -> List[Dict[str, Any]]:
        """
        创建默认条款的业绩变量
        
        Args:
            performance_vars: 业绩变量列表
            clause: 业绩条款名称
            rank_name: 排名名称
            
        Returns:
            List[Dict[str, Any]]: 默认变量列表
        """
        try:
            new_variables = []
            
            # 为每个业绩变量创建新变量
            for j, var in enumerate(performance_vars, 1):
                new_var = {
                    "variable_name": f"{rank_name}{clause}{j}",
                    "variable_value": var.get("variable_value", ""),
                    "reference_source": var.get("reference_source", {})
                }
                new_variables.append(new_var)
                self.logger.info(f"创建默认条款变量: {new_var['variable_name']}")
            
            return new_variables
            
        except Exception as e:
            self.logger.error(f"创建默认业绩变量失败: {e}")
            return []
    
    def _create_default_performance_variables_with_reset_counter(
        self,
        performance_vars: List[Dict[str, Any]],
        clause: str,
        rank_name: str
    ) -> List[Dict[str, Any]]:
        """
        创建默认条款的业绩变量（序号从1开始重新计数）
        
        Args:
            performance_vars: 业绩变量列表
            clause: 业绩条款名称
            rank_name: 排名名称
            
        Returns:
            List[Dict[str, Any]]: 默认变量列表
        """
        try:
            new_variables = []
            
            # 计数器，每类条款都从1开始
            counter = 1
            
            # 为每个业绩变量创建新变量（不再使用"三"前缀）
            for var in performance_vars:
                new_var = {
                    "variable_name": f"{rank_name}{clause}{counter}",
                    "variable_value": var.get("variable_value", ""),
                    "reference_source": var.get("reference_source", {})
                }
                new_variables.append(new_var)
                self.logger.info(f"创建默认条款变量: {new_var['variable_name']}")
                counter += 1
            
            return new_variables
            
        except Exception as e:
            self.logger.error(f"创建默认业绩变量失败: {e}")
            return []

    async def _process_new_performance_classification(
        self,
        variables_list: List[Dict[str, Any]],
        performance_clauses: List[str],
        candidate_count: int
    ) -> List[Dict[str, Any]]:
        """
        新的业绩分类处理逻辑
        
        Args:
            variables_list: 变量列表
            performance_clauses: 业绩条款列表
            candidate_count: 候选人数量
            
        Returns:
            List[Dict[str, Any]]: 新增的变量列表
        """
        try:
            new_variables = []
            
            # 中文排名映射
            chinese_ordinals = ["第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]
            
            for i in range(1, candidate_count + 1):
                if i <= len(chinese_ordinals):
                    rank_name = f"{chinese_ordinals[i-1]}名"
                else:
                    rank_name = f"第{i}名"
                
                self.logger.info(f"开始处理 {rank_name} 的业绩分类...")
                
                # 1. 找到所有业绩变量（基于条款名称的，如"第一名业绩要求1"、"第一名投标人近年类似项目业绩2"）
                # 为每个条款的第一个业绩创建"三第几名{条款名称}1"变量
                performance_vars = self._find_performance_variables_by_rank(variables_list, rank_name)
                clause_first_performance = {}  # 记录每个条款的第一个业绩
                
                for var in performance_vars:
                    var_name = var.get('variable_name', '')
                    # 匹配模式：排名 + 条款名称 + 数字
                    match = re.search(rf'{re.escape(rank_name)}(.+?)(\d+)$', var_name)
                    if match:
                        clause_name = match.group(1)  # 条款名称
                        perf_num = int(match.group(2))  # 序号
                        
                        # 记录每个条款的第一个业绩
                        if clause_name not in clause_first_performance or perf_num == 1:
                            if perf_num == 1:
                                clause_first_performance[clause_name] = var
                
                # 为每个条款的第一个业绩创建"三第几名{条款名称}1"变量
                for clause_name, first_var in clause_first_performance.items():
                    new_performance_1 = dict(first_var)
                    new_performance_1['variable_name'] = f"{rank_name}{clause_name}1"
                    new_performance_1['extraction_method'] = 'step5_new_classification'
                    new_variables.append(new_performance_1)
                    self.logger.info(f"新建变量: {rank_name}{clause_name}1")
                
                # 2. 不再重命名其他变量（保持原样，不再使用"三"前缀）
                # 注意：变量名已经是以"第几名"开头，不需要添加"三"前缀
                
                # 3. 通过'第几名业绩表+序号'和'二第几名+业绩条款+姓名'匹配
                matched_clauses = self._match_performance_tables_with_names(
                    variables_list, performance_clauses, rank_name
                )
                self.logger.info(f"{rank_name} 匹配到的条款: {matched_clauses}")
                
                # 4. 为匹配的条款创建新变量
                clause_counter = {}  # 为每个条款维护独立的计数器
                used_performance_vars = set()  # 记录已使用的业绩变量
                
                for clause, table_sequences in matched_clauses.items():
                    for table_sequence in table_sequences:
                        # 查找对应的业绩表变量，提取条款名称
                        # 例如："第一名业绩要求表1" -> 条款："业绩要求"
                        table_var_name = f"{rank_name}{clause}表{table_sequence}"
                        table_var = self._find_variable_by_name(variables_list, table_var_name)
                        
                        if table_var:
                            # 从业绩表变量名中提取条款名称（如果匹配成功，clause就是条款名称）
                            # 查找对应的业绩变量（如"第一名业绩要求1"）
                            source_var_name = f"{rank_name}{clause}{table_sequence}"
                            source_var = self._find_variable_by_name(variables_list + new_variables, source_var_name)
                            
                            # 如果找不到，尝试查找原始变量（如"第一名业绩要求1"）
                            if not source_var:
                                original_var_name = f"{rank_name}{clause}{table_sequence}"
                                original_var = self._find_variable_by_name(variables_list, original_var_name)
                                if original_var:
                                    source_var = dict(original_var)
                                    source_var['variable_name'] = source_var_name
                            
                            if source_var:
                                # 为当前条款分配新的序号（从1开始）
                                if clause not in clause_counter:
                                    clause_counter[clause] = 1
                                else:
                                    clause_counter[clause] += 1
                                new_var = dict(source_var)
                                new_var['variable_name'] = f"{rank_name}{clause}{clause_counter[clause]}"
                                new_var['extraction_method'] = 'step5_matched_clause'
                                new_variables.append(new_var)
                                used_performance_vars.add(source_var_name)
                                self.logger.info(f"创建匹配变量: {rank_name}{clause}{clause_counter[clause]}")
                
                # 4.5 步骤不再需要，因上一步已处理每个条款的全部匹配表
                
                # 5. 处理剩余变量，重命名为'第几名+剩下条款+序号'（不再使用"三"前缀）
                remaining_clause = self._get_remaining_clause(performance_clauses, matched_clauses)
                if remaining_clause:
                    # 找出所有'第几名{条款名称}+序号'变量（除了已匹配的）
                    remaining_vars = []
                    for var in variables_list + new_variables:
                        var_name = var.get('variable_name', '')
                        # 匹配模式：排名 + 条款名称 + 数字（不再使用"三"前缀）
                        if var_name.startswith(rank_name) and "业绩" in var_name:
                            # 检查是否已被使用
                            if var_name not in used_performance_vars:
                                # 提取条款名称和序号
                                match = re.search(rf'^{re.escape(rank_name)}(.+?)(\d+)$', var_name)
                                if match:
                                    clause_in_var = match.group(1)
                                    perf_num = int(match.group(2))
                                    # 如果这个条款不在已匹配的条款中，且不是第一个业绩，则加入剩余变量
                                    if clause_in_var not in matched_clauses or perf_num != 1:
                                        remaining_vars.append(var)
                    
                    # 重命名为'第几名+剩下条款+序号'（序号从1开始重新编号，不再使用"三"前缀）
                    remaining_counter = 1
                    for var in remaining_vars:
                        var_name = var.get('variable_name', '')
                        var['variable_name'] = f"{rank_name}{remaining_clause}{remaining_counter}"
                        self.logger.info(f"重命名为剩余条款变量: {var_name} -> {rank_name}{remaining_clause}{remaining_counter}")
                        remaining_counter += 1
            
            return new_variables
            
        except Exception as e:
            self.logger.error(f"新业绩分类处理失败: {e}")
            return []
    
    def _find_variable_by_name(self, variables_list: List[Dict[str, Any]], variable_name: str) -> Optional[Dict[str, Any]]:
        """
        根据变量名查找变量
        
        Args:
            variables_list: 变量列表
            variable_name: 变量名
            
        Returns:
            Optional[Dict[str, Any]]: 找到的变量，如果没找到返回None
        """
        for var in variables_list:
            if isinstance(var, dict) and var.get('variable_name') == variable_name:
                return var
        return None
    
    def _find_performance_variables_by_rank(self, variables_list: List[Dict[str, Any]], rank_name: str) -> List[Dict[str, Any]]:
        """
        根据排名查找业绩变量（支持基于条款名称的变量）
        
        Args:
            variables_list: 变量列表
            rank_name: 排名名称
            
        Returns:
            List[Dict[str, Any]]: 业绩变量列表
        """
        import re
        performance_vars = []
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                var_name = var["variable_name"]
                # 匹配模式：排名 + 条款名称（包含"业绩"）+ 数字
                # 例如："第一名业绩要求1"、"第一名投标人近年类似项目业绩2"
                if var_name.startswith(rank_name) and "业绩" in var_name:
                    # 检查是否以数字结尾（表示是业绩变量，不是汇总表或表）
                    match = re.search(rf'{re.escape(rank_name)}(.+?)(\d+)$', var_name)
                    if match and "表" not in var_name and "汇总表" not in var_name:
                        performance_vars.append(var)
        return performance_vars
    
    def _match_performance_tables_with_names(
        self, 
        variables_list: List[Dict[str, Any]], 
        performance_clauses: List[str], 
        rank_name: str
    ) -> Dict[str, List[int]]:
        """
        通过'第几名业绩表+序号'和'二第几名+业绩条款+姓名'匹配
        
        Args:
            variables_list: 变量列表
            performance_clauses: 业绩条款列表
            rank_name: 排名名称
            
        Returns:
            Dict[str, List[int]]: 匹配结果，键为条款名称，值为匹配到的业绩表序号列表
        """
        matched_clauses: Dict[str, List[int]] = {}
        
        # 查找所有'二第几名+业绩条款+姓名'变量
        name_vars = []
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                var_name = var["variable_name"]
                if (var_name.endswith("姓名") and 
                    var_name.startswith("二") and 
                    var_name.startswith(f"二{rank_name}")):
                    name_vars.append(var)
        
        # 从姓名变量中提取条款名称
        for name_var in name_vars:
            var_name = name_var.get("variable_name", "")
            # 去掉"姓名"后缀和"二第几名"前缀
            base_name = var_name.replace("姓名", "")
            if base_name.startswith(f"二{rank_name}"):
                clause_name = base_name[len(f"二{rank_name}"):]
                if clause_name:
                    # 查找对应的业绩表变量（支持多项）
                    table_sequences = self._find_all_matching_performance_tables(
                        variables_list, rank_name, clause_name
                    )
                    if table_sequences:
                        matched_clauses[clause_name] = table_sequences
                        self.logger.info(f"匹配成功: {clause_name} -> 业绩表{table_sequences}")
        
        return matched_clauses

    def _find_all_matching_performance_tables(
        self,
        variables_list: List[Dict[str, Any]],
        rank_name: str,
        clause_name: str
    ) -> List[int]:
        """
        返回与条款对应姓名在业绩表中出现的所有业绩表序号列表。
        """
        # 1) 拿到姓名变量：二第几名+业绩条款+姓名
        expected_name_var = f"二{rank_name}{clause_name}姓名"
        person_name: Optional[str] = None
        for var in variables_list:
            if isinstance(var, dict) and var.get("variable_name") == expected_name_var:
                person_name = (var.get("variable_value") or "").strip()
                break
        if not person_name:
            self.logger.info(f"未找到姓名或为空: {expected_name_var}")
            return []

        # 2) 扫描所有业绩表，找到包含该姓名的表，收集序号
        matches: List[int] = []
        import re
        for var in variables_list:
            if not (isinstance(var, dict) and "variable_name" in var):
                continue
            var_name = var["variable_name"]
            # 匹配模式：排名 + 条款名称 + "表" + 数字
            # 例如："第一名业绩要求表1"、"第一名投标人近年类似项目业绩表2"
            if not (var_name.startswith(rank_name) and "表" in var_name and "汇总表" not in var_name):
                continue
            # 匹配：排名 + 条款名称 + "表" + 数字
            m = re.search(rf'{re.escape(rank_name)}(.+?)表(\d+)$', var_name)
            if not m:
                continue
            clause_in_table = m.group(1)  # 条款名称
            table_index = int(m.group(2))  # 序号
            # 只处理与指定条款名称匹配的业绩表
            if clause_name != clause_in_table:
                continue
            table_content = (var.get("variable_value") or "")
            if person_name in table_content:
                matches.append(table_index)
        return sorted(set(matches))
    
    def _find_matching_performance_table(
        self, 
        variables_list: List[Dict[str, Any]], 
        rank_name: str, 
        clause_name: str
    ) -> Optional[int]:
        """
        查找匹配的业绩表序号
        
        Args:
            variables_list: 变量列表
            rank_name: 排名名称
            clause_name: 条款名称
            
        Returns:
            Optional[int]: 业绩表序号，如果没找到返回None
        """
        # 兼容旧接口：返回第一个匹配表（若存在）
        all_matches = self._find_all_matching_performance_tables(
            variables_list, rank_name, clause_name
        )
        return all_matches[0] if all_matches else None
    
    def _get_remaining_clause(
        self, 
        performance_clauses: List[str], 
        matched_clauses: Dict[str, List[int]]
    ) -> Optional[str]:
        """
        获取剩余条款
        
        Args:
            performance_clauses: 所有业绩条款
            matched_clauses: 已匹配的条款
            
        Returns:
            Optional[str]: 剩余条款，如果没有剩余返回None
        """
        matched_clause_names = set(matched_clauses.keys())
        for clause in performance_clauses:
            if clause not in matched_clause_names:
                return clause
        return None


# 便捷函数
async def extract_performance_tables(
    performance_text: str, 
    ranking: str = "第一名"
) -> Dict[str, Any]:
    """
    便捷函数：从业绩文本中提取业绩表格
    
    Args:
        performance_text: 业绩文本内容
        ranking: 排名信息
        
    Returns:
        Dict[str, Any]: 提取结果
    """
    processor = BidFileProcessor()
    return await processor.extract_performance_tables_from_text(performance_text, ranking)


async def batch_extract_performance_tables(
    performance_texts: Dict[str, str]
) -> Dict[str, Dict[str, Any]]:
    """
    便捷函数：批量提取业绩表格
    
    Args:
        performance_texts: 业绩文本字典
        
    Returns:
        Dict[str, Dict[str, Any]]: 批量处理结果
    """
    processor = BidFileProcessor()
    return await processor.process_multiple_rankings(performance_texts)


async def process_step5_performance_variables(
    variables_list: List[Dict[str, Any]],
    business_score_clauses: str,
    candidate_count: int = 3
) -> List[Dict[str, Any]]:
    """
    便捷函数：第五步业绩变量处理
    
    Args:
        variables_list: 第四步提取的变量列表
        business_score_clauses: 商务评分标准内容
        candidate_count: 候选人数量
        
    Returns:
        List[Dict[str, Any]]: 处理后的变量列表
    """
    processor = BidFileProcessor()
    return await processor.process_step5_performance_variables(
        variables_list, business_score_clauses, candidate_count
    )
