#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预变量处理模块
用于在模板渲染前对变量进行预处理，如判断推荐中标候选人数等
"""

import logging
import re
import json
import asyncio
from typing import Dict, Any, Optional, List, Union

# 导入动态表格变量提取器
from prompts.pre_variable_prompt import DynamicTableVariableExtractor
# 导入商务部分评分表变量提取器
from prompts.pre_final_variable_prompt import BusinessScoreTableVariableExtractor
# 导入拆分的提示词生成函数
from prompts.candidate_count_prompt import generate_candidate_count_prompt
from prompts.candidate_filter_prompt import generate_candidate_filter_with_units_prompt, generate_candidate_filter_prompt
from prompts.candidate_names_prompt import generate_candidate_names_prompt
from prompts.score_enrichment_prompt import generate_score_enrichment_prompt
from prompts.performance_score_prompt import generate_performance_score_prompt
from prompts.prompt_utils import format_variables_for_prompt
# 导入第四步和第五步处理函数
from .pre_variables_step4_5 import (
    extract_failed_candidates_details,
    extract_failed_candidates_business_clauses,
    _count_extracted_performances,
    _clean_failed_candidates_performance_variables,
    _validate_performance_counts,
    _get_expected_performance_counts,
    _extract_business_clauses_from_ranked_files
)
# 导入简历表人员姓名提取函数
from .pre_variable_for_step4 import extract_resume_personnel_names_from_ranked_files
# 导入第五步业绩处理功能
from .bid_file_processor import process_step5_performance_variables
# 导入LLM工具函数
from .llm_utils import call_llm_with_retry, call_llm_with_retry_for_json_parse
# 导入变量提取工具函数
from .extraction_utils import (
    extract_performance_counts_from_variables,
    extract_performance_table_variables,
    parse_llm_json_result
)

logger = logging.getLogger(__name__)

# 业绩数量验证配置
PERFORMANCE_COUNT_VALIDATION_THRESHOLD = 3  # 允许的业绩数量差异阈值
MAX_PERFORMANCE_EXTRACTION_RETRIES = 3  # 最大重试次数

async def _convert_performance_tables_to_variables(
    variables_list: List[Dict[str, Any]], 
    candidate_files: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    将业绩表格数据转换为标准变量格式
    
    Args:
        variables_list: 变量列表
        candidate_files: 候选人文件字典，包含业绩表格数据
        
    Returns:
        List[Dict[str, Any]]: 更新后的变量列表
    """
    try:
        logger.info("开始将业绩表格数据转换为标准变量格式...")
        
        # 构建变量映射
        variables_map = {}
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                variables_map[var["variable_name"]] = var
        
        added_variables = 0
        
        for ranking, file_info in candidate_files.items():
            # 处理业绩汇总表
            performance_summary_table = file_info.get('performance_summary_table', {})
            if performance_summary_table.get('table_content'):
                variable_name = performance_summary_table.get('variable_name', f"{ranking}业绩汇总表")
                table_content = performance_summary_table.get('table_content', '')
                
                # 创建变量对象
                new_variable = {
                    "variable_name": variable_name,
                    "variable_value": table_content,
                    "reference_source": {
                        "file_type": "candidate_bid_files",
                        "page_number": "业绩部分",
                        "section": "业绩汇总表",
                        "content_preview": f"{ranking}业绩汇总表（HTML表格格式）",
                        "source_url": file_info.get('file_url', '')
                    }
                }
                
                # 添加到变量列表
                variables_list.append(new_variable)
                variables_map[variable_name] = new_variable
                added_variables += 1
                logger.info(f"添加业绩汇总表变量: {variable_name} (长度: {len(table_content)})")
            
            # 处理单个业绩表
            individual_performances = file_info.get('individual_performances', [])
            for perf in individual_performances:
                variable_name = perf.get('variable_name', '')
                table_content = perf.get('table_content', '')
                
                if variable_name and table_content:
                    # 创建变量对象
                    new_variable = {
                        "variable_name": variable_name,
                        "variable_value": table_content,
                        "reference_source": {
                            "file_type": "candidate_bid_files",
                            "page_number": "业绩部分",
                            "section": "单个业绩表",
                            "content_preview": f"{variable_name}（HTML表格格式）",
                            "source_url": file_info.get('file_url', '')
                        }
                    }
                    
                    # 添加到变量列表
                    variables_list.append(new_variable)
                    variables_map[variable_name] = new_variable
                    added_variables += 1
                    logger.info(f"添加单个业绩表变量: {variable_name} (长度: {len(table_content)})")
        
        logger.info(f"业绩表格变量转换完成，共添加 {added_variables} 个变量")
        return variables_list
        
    except Exception as e:
        logger.error(f"转换业绩表格数据失败: {e}")
        return variables_list


async def process_recommended_candidates_count(variables_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    处理推荐中标候选人数，根据评审结果和规则判断最终的推荐人数
    
    Args:
        variables_list: 变量列表
        
    Returns:
        List[Dict[str, Any]]: 处理后的变量列表（包含新增的推荐中标候选人数变量）
    """
    try:
        # 构建变量映射
        variables_map = {}
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                variables_map[var["variable_name"]] = var
        
        # 获取评审结果和推荐中标候选人数规则
        review_results_var = variables_map.get("评审结果")
        candidates_rule_var = variables_map.get("推荐中标候选人数规则")
        
        # 检查是否都有数据
        if not review_results_var or not candidates_rule_var:
            logger.warning("评审结果或推荐中标候选人数规则为空，跳过处理")
            return variables_list
        
        review_results = review_results_var.get("variable_value", "")
        candidates_rule = candidates_rule_var.get("variable_value", "")
        
        if not review_results or not candidates_rule:
            logger.warning("评审结果或推荐中标候选人数规则的值为空，跳过处理")
            return variables_list
        
        logger.info("开始处理推荐中标候选人数...")
        
        # 调用LLM判断推荐人数
        recommended_count = await get_recommended_count_by_llm(review_results, candidates_rule)
        
        if recommended_count is not None:
            # 合并两个源变量的reference_source
            merged_reference_source = _merge_reference_sources([
                review_results_var.get("reference_source", {}),
                candidates_rule_var.get("reference_source", {})
            ])
            
            # 创建新变量
            new_variable = {
                "variable_name": "推荐中标候选人数",
                "variable_value": str(recommended_count),
                "reference_source": merged_reference_source
            }
            
            # 添加到列表中
            variables_list.append(new_variable)
            logger.info(f"推荐中标候选人数处理完成: {recommended_count}")
        else:
            logger.warning("LLM未能返回有效的推荐人数")
        
        return variables_list
        
    except Exception as e:
        logger.error(f"处理推荐中标候选人数失败: {e}")
        return variables_list

async def get_recommended_count_by_llm(review_results: str, candidates_rule: str) -> Optional[int]:
    """
    使用LLM根据评审结果和规则判断推荐中标候选人数
    
    Args:
        review_results: 评审结果内容
        candidates_rule: 推荐中标候选人数规则
        
    Returns:
        Optional[int]: 推荐的中标候选人数，如果判断失败返回None
    """
    try:
        # 导入LLM客户端
        from common.llm_client import LLMClient
        llm_client = LLMClient()
        
        # 构建提示词
        prompt = generate_candidate_count_prompt(review_results, candidates_rule)
        
        # 调用LLM（带重试机制）
        result = await call_llm_with_retry(
            llm_client=llm_client,
            prompt=prompt,
            file_content="",
            step_name="第1步-推荐中标候选人数"
        )
        
        # 提取数字
        numbers = re.findall(r'\d+', result.strip())
        if numbers:
            recommended_count = int(numbers[0])
            logger.info(f"LLM返回的推荐人数: {recommended_count}")
            return recommended_count
        else:
            logger.warning(f"LLM返回结果中未找到有效数字: {result}")
            return None
            
    except Exception as e:
        logger.error(f"LLM判断推荐人数失败: {e}")
        return None

async def process_candidates_score_summary(variables_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    处理中标候选人得分汇总情况，根据推荐中标候选人数过滤表格内容，并添加投标报价单位
    
    Args:
        variables_list: 变量列表
        
    Returns:
        List[Dict[str, Any]]: 处理后的变量列表
    """
    try:
        # 构建变量映射
        variables_map = {}
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                variables_map[var["variable_name"]] = var
        
        # 获取中标候选人得分汇总情况、推荐中标候选人数和开标记录表格
        score_summary_var = variables_map.get("中标候选人得分汇总情况")
        recommended_count_var = variables_map.get("推荐中标候选人数")
        opening_record_var = variables_map.get("开标记录表格")
        
        # 检查是否都有数据
        if not score_summary_var or not recommended_count_var:
            logger.warning("中标候选人得分汇总情况或推荐中标候选人数为空，跳过处理")
            return variables_list
        
        score_summary = score_summary_var.get("variable_value", "")
        recommended_count = recommended_count_var.get("variable_value", "")
        opening_record = opening_record_var.get("variable_value", "") if opening_record_var else ""
        
        if not score_summary or not recommended_count:
            logger.warning("中标候选人得分汇总情况或推荐中标候选人数的值为空，跳过处理")
            return variables_list
        
        # 尝试将推荐人数转换为整数
        try:
            count = int(recommended_count)
        except (ValueError, TypeError):
            logger.warning(f"推荐中标候选人数无法转换为整数: {recommended_count}")
            return variables_list
        
        # 先检查原始表格中的候选人数量
        import re
        tr_pattern = r'<tr[^>]*>.*?</tr>'
        tr_matches = re.findall(tr_pattern, score_summary, re.DOTALL | re.IGNORECASE)
        original_candidate_count = max(0, len(tr_matches) - 1)  # 减去表头行
        
        logger.info(f"开始处理中标候选人得分汇总情况，原始表格中有{original_candidate_count}名候选人，需要保留{count}名并添加投标报价单位...")
        
        # 如果原始表格中的候选人数量少于推荐人数，记录警告并尝试从评审结果中补充信息
        if original_candidate_count < count:
            logger.warning(f"发现原始表格中只有{original_candidate_count}名候选人，但推荐人数为{count}名。可能存在以下情况：1) 文档中其他位置还有候选人信息；2) 初始提取时遗漏了部分候选人")
            # 获取评审结果，看是否能补充候选人信息
            review_results_var = variables_map.get("评审结果")
            if review_results_var:
                review_results = review_results_var.get("variable_value", "")
                if review_results and len(review_results) > 100:  # 评审结果有内容
                    logger.info("尝试从评审结果中查找是否有遗漏的候选人信息...")
        
        # 调用LLM过滤表格内容并添加单位
        filtered_summary = await filter_candidates_by_count_with_units(score_summary, count, opening_record)
        
        if filtered_summary:
            # 再次检查返回结果中的候选人数量
            result_tr_matches = re.findall(tr_pattern, filtered_summary, re.DOTALL | re.IGNORECASE)
            result_candidate_count = max(0, len(result_tr_matches) - 1)
            
            # 更新变量值（保留原有的reference_source）
            score_summary_var["variable_value"] = filtered_summary
            
            if result_candidate_count < count:
                logger.warning(f"中标候选人得分汇总情况处理完成，但只保留了{result_candidate_count}名候选人（要求{count}名）。这可能说明原始数据中确实只有这么多候选人，或者文档中其他位置的候选人信息未被提取到得分汇总表格中")
            else:
                logger.info(f"中标候选人得分汇总情况处理完成，保留了{result_candidate_count}名候选人并添加了投标报价单位")
        else:
            logger.warning("LLM未能返回有效的过滤结果")
        
        return variables_list
        
    except Exception as e:
        logger.error(f"处理中标候选人得分汇总情况失败: {e}")
        return variables_list

async def filter_candidates_by_count_with_units(score_summary: str, count: int, opening_record: str = "") -> Optional[str]:
    """
    使用LLM根据推荐人数过滤中标候选人得分汇总表格，并添加投标报价单位
    
    Args:
        score_summary: 中标候选人得分汇总情况内容（HTML表格）
        count: 需要保留的候选人数量
        opening_record: 开标记录表格内容（用于获取投标报价单位）
        
    Returns:
        Optional[str]: 过滤后的HTML表格，如果处理失败返回None
    """
    try:
        # 导入LLM客户端
        from common.llm_client import LLMClient
        llm_client = LLMClient()
        
        # 先统计原始表格中的候选人数量（通过计算<tr>标签数量，排除表头）
        import re
        tr_pattern = r'<tr[^>]*>.*?</tr>'
        tr_matches = re.findall(tr_pattern, score_summary, re.DOTALL | re.IGNORECASE)
        original_count = max(0, len(tr_matches) - 1)  # 减去表头行
        
        logger.info(f"原始表格中有{original_count}名候选人，需要保留{count}名")
        
        if original_count < count:
            logger.warning(f"原始表格中只有{original_count}名候选人，少于推荐的{count}名，将在提示词中强调需要提取所有候选人信息")
        
        # 构建提示词
        prompt = generate_candidate_filter_with_units_prompt(
            score_summary, count, opening_record, original_count
        )
        
        # 调用LLM（带重试机制）
        result = await call_llm_with_retry(
            llm_client=llm_client,
            prompt=prompt,
            file_content="",
            step_name="第2步-候选人名称提取"
        )
        
        # 检查返回结果是否包含HTML表格标签
        if '<table' in result and '</table>' in result:
            # 再次统计返回结果中的候选人数量
            result_tr_matches = re.findall(tr_pattern, result, re.DOTALL | re.IGNORECASE)
            result_count = max(0, len(result_tr_matches) - 1)
            logger.info(f"LLM成功过滤表格并添加单位，保留了{result_count}名候选人（要求保留{count}名）")
            
            if result_count < count:
                logger.warning(f"警告：返回的表格中只有{result_count}名候选人，少于要求的{count}名。可能原因：1) 原始表格数据不完整；2) 文档中其他位置的候选人信息未被提取")
            
            return result.strip()
        else:
            logger.warning(f"LLM返回结果不是有效的HTML表格格式: {result}")
            return None
            
    except Exception as e:
        logger.error(f"LLM过滤候选人表格并添加单位失败: {e}")
        return None

async def filter_candidates_by_count(score_summary: str, count: int) -> Optional[str]:
    """
    使用LLM根据推荐人数过滤中标候选人得分汇总表格
    
    Args:
        score_summary: 中标候选人得分汇总情况内容（HTML表格）
        count: 需要保留的候选人数量
        
    Returns:
        Optional[str]: 过滤后的HTML表格，如果处理失败返回None
    """
    try:
        # 导入LLM客户端
        from common.llm_client import LLMClient
        llm_client = LLMClient()
        
        # 构建提示词
        prompt = generate_candidate_filter_prompt(score_summary, count)
        
        # 调用LLM（带重试机制）
        result = await call_llm_with_retry(
            llm_client=llm_client,
            prompt=prompt,
            file_content="",
            step_name="第3步-候选人名称和三体系认证得分"
        )
        
        # 检查返回结果是否包含HTML表格标签
        if '<table' in result and '</table>' in result:
            logger.info(f"LLM成功过滤表格，保留了{count}名候选人")
            return result.strip()
        else:
            logger.warning(f"LLM返回结果不是有效的HTML表格格式: {result}")
            return None
            
    except Exception as e:
        logger.error(f"LLM过滤候选人表格失败: {e}")
        return None

async def extract_candidate_names_by_count(variables_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    根据推荐中标候选人数动态提取候选人名称和商务部分评分表中的所有评标条款得分
    
    注意：此函数提取所有评标条款的得分，对包含"三体系认证"的条款名称进行特殊处理
    
    Args:
        variables_list: 变量列表
        
    Returns:
        List[Dict[str, Any]]: 处理后的变量列表（包含新增的候选人名称变量和评标条款得分变量）
    """
    try:
        # 构建变量映射
        variables_map = {}
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                variables_map[var["variable_name"]] = var
        
        # 获取推荐中标候选人数、评审结果和商务部分评分表
        recommended_count_var = variables_map.get("推荐中标候选人数")
        review_results_var = variables_map.get("评审结果")
        business_score_table_var = variables_map.get("商务部分评分表")
        
        # 检查是否有必要的数据
        if not recommended_count_var or not review_results_var:
            logger.warning("推荐中标候选人数或评审结果为空，跳过候选人名称提取")
            return variables_list
        
        recommended_count = recommended_count_var.get("variable_value", "")
        review_results = review_results_var.get("variable_value", "")
        business_score_table = business_score_table_var.get("variable_value", "") if business_score_table_var else ""
        
        if not recommended_count or not review_results:
            logger.warning("推荐中标候选人数或评审结果的值为空，跳过候选人名称提取")
            return variables_list
        
        # 尝试将推荐人数转换为整数
        try:
            count = int(recommended_count)
        except (ValueError, TypeError):
            logger.warning(f"推荐中标候选人数无法转换为整数: {recommended_count}")
            return variables_list
        
        if count <= 0:
            logger.warning(f"推荐中标候选人数无效: {count}")
            return variables_list
        
        logger.info(f"开始提取前{count}名中标候选人名称和商务部分评分表中的三体系认证得分...")
        
        # 调用LLM提取候选人名称和得分
        result = await get_candidate_names_by_llm(review_results, count, business_score_table)
        
        if result and result.get("candidate_names"):
            candidate_names = result["candidate_names"]
            score_variables = result.get("score_variables", [])
            
            # 合并评审结果的reference_source
            reference_source = review_results_var.get("reference_source", {})
            
            # 将提取的候选人名称添加到变量列表
            for i, name in enumerate(candidate_names, 1):
                if i > count:
                    break
                
                # 生成中文序号
                chinese_numbers = ["第一", "第二", "第三", "第四", "第五", "第六"]
                if i <= len(chinese_numbers):
                    variable_name = f"{chinese_numbers[i-1]}中标候选人名称"
                else:
                    variable_name = f"第{i}中标候选人名称"
                
                # 检查是否已存在该变量，存在则更新，不存在则添加
                if variable_name in variables_map:
                    # 更新现有变量
                    variables_map[variable_name]["variable_value"] = name
                    variables_map[variable_name]["reference_source"] = reference_source
                    logger.debug(f"更新候选人变量: {variable_name} = {name}")
                else:
                    # 添加新变量
                    new_variable = {
                        "variable_name": variable_name,
                        "variable_value": name,
                        "reference_source": reference_source
                    }
                    variables_list.append(new_variable)
                    variables_map[variable_name] = new_variable
                    logger.debug(f"添加候选人变量: {variable_name} = {name}")
            
            # 添加商务部分评分表得分变量
            for score_var in score_variables:
                variable_name = score_var.get("variable_name", "")
                variable_value = score_var.get("variable_value", "")
                var_reference_source = score_var.get("reference_source", {})
                
                if variable_name and variable_value:
                    # 检查是否已存在该变量，存在则更新，不存在则添加
                    if variable_name in variables_map:
                        # 更新现有变量
                        variables_map[variable_name]["variable_value"] = variable_value
                        variables_map[variable_name]["reference_source"] = var_reference_source
                        logger.debug(f"更新得分变量: {variable_name} = {variable_value}")
                    else:
                        # 添加新变量
                        new_variable = {
                            "variable_name": variable_name,
                            "variable_value": variable_value,
                            "reference_source": var_reference_source
                        }
                        variables_list.append(new_variable)
                        variables_map[variable_name] = new_variable
                        logger.debug(f"添加得分变量: {variable_name} = {variable_value}")
            
            logger.info(f"成功提取{len(candidate_names)}个候选人名称和{len(score_variables)}个评标条款得分变量")
        else:
            logger.warning("LLM未能返回有效的候选人名称")
        
        return variables_list
        
    except Exception as e:
        logger.error(f"提取候选人名称和得分失败: {e}")
        return variables_list

async def get_candidate_names_by_llm(review_results: str, count: int, business_score_table: str = "") -> Optional[Dict[str, Any]]:
    """
    使用LLM从评审结果中动态提取指定数量的候选人名称，并从商务部分评分表中提取所有评标条款得分
    
    注意：此函数提取所有评标条款的得分，对包含"三体系认证"的条款名称进行特殊处理
    
    Args:
        review_results: 评审结果内容（HTML表格）
        count: 需要提取的候选人数量
        business_score_table: 商务部分评分表内容（HTML表格）
        
    Returns:
        Optional[Dict[str, Any]]: 包含候选人名称和得分的字典，如果提取失败返回None
        格式: {
            "candidate_names": List[str],  # 候选人名称列表
            "score_variables": List[Dict]  # 得分变量列表，每个变量包含variable_name, variable_value, reference_source
        }
    """
    try:
        # 导入LLM客户端和JSON处理工具
        from common.llm_client import LLMClient
        import json
        import re
        
        llm_client = LLMClient()
        
        # 构建动态提示词
        prompt = generate_candidate_names_prompt(review_results, count, business_score_table)
        
        # 调用LLM（带重试机制）
        result = await call_llm_with_retry(
            llm_client=llm_client,
            prompt=prompt,
            file_content="",
            step_name="商务评分标准提取"
        )
        
        # 提取JSON内容
        # 尝试多种方式提取JSON
        json_str = result.strip()
        
        # 如果结果包含```json```标记，提取其中的内容
        if "```json" in json_str:
            json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', json_str)
            if json_match:
                json_str = json_match.group(1)
        elif "```" in json_str:
            json_match = re.search(r'```\s*(\{[\s\S]*?\})\s*```', json_str)
            if json_match:
                json_str = json_match.group(1)
        
        # 解析JSON
        try:
            result_data = json.loads(json_str)
            
            if not isinstance(result_data, dict):
                logger.warning(f"LLM返回的JSON不是对象格式: {json_str}")
                return None
            
            candidate_names = result_data.get("candidate_names", [])
            score_variables = result_data.get("score_variables", [])
            
            if candidate_names:
                logger.info(f"成功提取{len(candidate_names)}个候选人名称: {candidate_names}")
                logger.info(f"成功提取{len(score_variables)}个得分变量")
                
                return {
                    "candidate_names": candidate_names[:count],  # 确保不超过指定数量
                    "score_variables": score_variables
                }
            else:
                logger.warning(f"从JSON中未提取到有效的候选人名称: {result_data}")
                return None
                
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败（提取评标条款得分）: {e}, 原始内容: {json_str}")
            
            # 尝试备用方案：从文本中直接提取候选人名称
            # 查找所有可能的企业名称（包含"公司"、"集团"等关键词）
            company_pattern = r'[\u4e00-\u9fa5a-zA-Z0-9（）()]+(?:有限公司|股份有限公司|集团|公司)'
            companies = re.findall(company_pattern, result)
            
            if companies:
                # 去重并保持顺序
                unique_companies = []
                for company in companies:
                    if company not in unique_companies:
                        unique_companies.append(company)
                
                logger.info(f"使用备用方案提取到{len(unique_companies)}个候选人名称")
                return {
                    "candidate_names": unique_companies[:count],
                    "score_variables": []  # 备用方案无法提取三体系认证得分
                }
            else:
                logger.warning("备用方案也未能提取到候选人名称")
                return None
            
    except Exception as e:
        logger.error(f"LLM提取候选人名称和三体系认证得分失败: {e}")
        return None

def _convert_reference_source_format(ref_source: Dict[str, Any], original_url: str = None, file_type: str = "") -> Dict[str, Any]:
    """
    将旧格式的reference_source转换为新格式
    
    旧格式: page_number, section, content_preview
    新格式: pages, evidence_text
    
    Args:
        ref_source: 原始reference_source字典
        original_url: 原始URL（如果ref_source中没有source_url）
        file_type: 文件类型
        
    Returns:
        Dict[str, Any]: 转换后的标准格式reference_source
    """
    if not isinstance(ref_source, dict):
        return {
            "source_url": original_url or "",
            "evidence_text": "",
            "pages": "",
            "file_type": file_type
        }
    
    # 检查是否是旧格式（包含page_number, section, content_preview）
    has_old_format = any(key in ref_source for key in ["page_number", "section", "content_preview"])
    
    if has_old_format:
        # 转换旧格式到新格式
        # 将page_number转换为pages
        pages = ref_source.get("page_number", "")
        # 如果pages包含"第"和"页"，提取数字部分
        if pages and "第" in pages and "页" in pages:
            # 提取所有页码数字，支持"第142-159页"或"710, 711, 712"等格式
            # 提取所有数字
            page_numbers = re.findall(r'\d+', pages)
            if page_numbers:
                pages = ", ".join(page_numbers)
        
        # 合并section和content_preview为evidence_text
        section = ref_source.get("section", "")
        content_preview = ref_source.get("content_preview", "")
        evidence_text_parts = []
        if section:
            evidence_text_parts.append(section)
        if content_preview:
            evidence_text_parts.append(content_preview)
        evidence_text = " ".join(evidence_text_parts)
        
        # 获取source_url，优先使用ref_source中的，否则使用original_url
        source_url = ref_source.get("source_url", original_url or "")
        
        # 获取file_type，优先使用ref_source中的
        ref_file_type = ref_source.get("file_type", file_type)
        
        return {
            "source_url": source_url,
            "evidence_text": evidence_text,
            "pages": pages,
            "file_type": ref_file_type
        }
    else:
        # 已经是新格式，直接使用，但确保所有字段都存在
        result = {
            "source_url": ref_source.get("source_url", original_url or ""),
            "evidence_text": ref_source.get("evidence_text", ""),
            "pages": ref_source.get("pages", ""),
            "file_type": ref_source.get("file_type", file_type)
        }
        return result


async def _extract_from_ranked_files(
    variables_list: List[Dict[str, Any]],
    ranked_files: Dict[str, Dict[str, Any]],
    candidate_count: int,
    bidder_requirements: str,
    qualification_review_standard_table: str
) -> List[Dict[str, Any]]:
    """
    从排名文件中提取候选人详细信息（新方法）
    
    根据变量名称中的排名信息，从对应排名的投标文件中提取内容
    例如：提取"第一中标候选人名称"时，使用"第一名"对应的投标文件
    
    Args:
        variables_list: 变量列表
        ranked_files: 排名文件字典，格式为 {"第一名": {content, file_url, ...}, "第二名": {...}}
        candidate_count: 候选人数量
        bidder_requirements: 投标人要求
        qualification_review_standard_table: 资格评审标准
        
    Returns:
        List[Dict[str, Any]]: 更新后的变量列表
    """
    try:
        from prompts.pre_variable_prompt import DynamicTableVariableExtractor
        from common.llm_client import LLMClient
        
        llm_client = LLMClient()
        extractor = DynamicTableVariableExtractor()
        
        # 从variables_list中提取业绩数量（使用工具函数）
        performance_counts = extract_performance_counts_from_variables(
            variables_list, 
            candidate_count
        )
        
        # 检查是否有业绩表格变量（使用工具函数）
        performance_table_variables = extract_performance_table_variables(variables_list)
        
        # 只使用业绩表格变量方法生成任务
        if performance_table_variables:
            logger.info(f"检测到 {len(performance_table_variables)} 个业绩表格变量，使用表格变量方法生成任务")
            task_list = extractor.generate_qualification_review_variables(
                candidate_count=candidate_count,
                max_performance_count=10,
                bidder_requirements=bidder_requirements,
                qualification_review_standard_table=qualification_review_standard_table,
                performance_counts=performance_counts if performance_counts else None,
                performance_table_variables=performance_table_variables
            )
        else:
            logger.warning("未检测到业绩表格变量，跳过业绩提取任务")
            # 只生成资质和通用任务，不生成业绩任务
            task_list = extractor.generate_qualification_review_variables(
                candidate_count=candidate_count,
                max_performance_count=0,  # 设置为0，不生成业绩任务
                bidder_requirements=bidder_requirements,
                qualification_review_standard_table=qualification_review_standard_table,
                performance_counts=None,  # 不传递业绩数量
                performance_table_variables=None
            )
        
        logger.info(f"生成了 {len(task_list)} 个提取任务: {[task['task_type'] for task in task_list]}")
        
        # 中文排名映射
        chinese_ordinals = ["第一名", "第二名", "第三名", "第四名", "第五名", "第六名", "第七名", "第八名", "第九名", "第十名"]

        # 为每个任务、每个候选人从对应排名的文件中提取信息（并发）
        import asyncio, json

        async def process_single_task_rank(task: Dict[str, Any], ranking: str, file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
            """处理单个任务的单个排名"""
            extracted: List[Dict[str, Any]] = []
            file_content = file_info.get('content', '')
            file_url = file_info.get('file_url', '')

            if not file_content:
                logger.warning(f"[{task['task_type']}] {ranking}的投标文件内容为空，跳过")
                return extracted

            # 根据任务类型选择合适的内容进行提取
            task_type = task.get('task_type', '')
            extraction_content = file_content  # 默认使用原始内容
            
            # 检查是否使用业绩表格变量方法
            if performance_table_variables and ('业绩' in task_type or 'performance' in task_type.lower()):
                # 对于业绩表格变量任务，优先使用业绩部分的内容，而不是表格内容
                # logger.info(f"[{task['task_type']}] 检查file_info中的字段: {list(file_info.keys())}")
                if 'performance_content' in file_info:
                    extraction_content = file_info.get('performance_content', file_content)
                    logger.info(f"[{task['task_type']}] 使用截取的业绩内容进行提取（业绩表格变量任务），长度: {len(extraction_content)} 字符")
                else:
                    logger.warning(f"[{task['task_type']}] 未找到业绩部分内容，使用原始内容")
                    extraction_content = file_content
            # 检查是否有内容截取的结果
            elif 'performance_extraction_content' in file_info:
                if '业绩' in task_type or 'performance' in task_type.lower():
                    # 业绩相关任务使用截取的业绩内容
                    extraction_content = file_info.get('performance_extraction_content', file_content)
                    logger.info(f"[{task['task_type']}] 使用截取的业绩内容进行提取，长度: {len(extraction_content)} 字符")
                elif '资质' in task_type or 'qualification' in task_type.lower():
                    # 资质相关任务使用截取的资质内容
                    extraction_content = file_info.get('qualification_extraction_content', file_content)
                    logger.info(f"[{task['task_type']}] 使用截取的资质内容进行提取，长度: {len(extraction_content)} 字符")
                elif '简历' in task_type or 'resume' in task_type.lower():
                    # 简历表相关任务使用截取的简历表内容
                    extraction_content = file_info.get('resume_table_extraction_content', file_content)
                    logger.info(f"[{task['task_type']}] 使用截取的简历表内容进行提取，长度: {len(extraction_content)} 字符")
                else:
                    # 其他任务使用清理后的内容（去除业绩、资质、简历表部分）
                    extraction_content = file_info.get('general_terms_extraction_content', file_content)
                    logger.info(f"[{task['task_type']}] 使用清理后的通用内容进行提取，长度: {len(extraction_content)} 字符")
            else:
                logger.info(f"[{task['task_type']}] 使用原始文件内容进行提取，长度: {len(file_content)} 字符")

            logger.info(f"[{task['task_type']}] 开始从{ranking}的投标文件中提取信息... 长度: {len(extraction_content)} 字符")

            # 获取该任务的提示词
            prompt = task['prompt']
            
            # 仅提取当前排名候选人，并插入文件内容
            ranking_specific_prompt = (
                prompt.replace(
                    f"请从投标文件中提取前{candidate_count}名候选人",
                    f"请从投标文件中提取{ranking}候选人"
                )
                .replace("$content", extraction_content)  # 插入选择的内容
                + f"\n\n仅针对{ranking}候选人的信息进行提取，忽略其他候选人的内容。"
            )

            # 使用重试机制调用LLM
            result = await call_llm_with_retry_for_json_parse(
                llm_client=llm_client,
                prompt=ranking_specific_prompt,
                file_content="",  # 文件内容已经在prompt中了
                step_name=f"第4步-{task['task_type']}-{ranking}",
                task_type=task['task_type'],
                ranking=ranking
            )

            if not result:
                logger.error(f"[{task['task_type']}] {ranking} LLM调用失败或返回空结果")
                return extracted

            logger.info(f"[{task['task_type']}] {ranking} LLM返回结果长度: {len(result)}")

            # 使用工具函数解析JSON结果
            extracted_vars = parse_llm_json_result(
                result, 
                task_type=task['task_type'], 
                ranking=ranking
            )
            
            if extracted_vars is None:
                logger.error(f"[{task['task_type']}] {ranking} JSON解析失败")
                return extracted
            
            # 调试：打印前3个变量的名称
            for i, var in enumerate(extracted_vars[:3]):
                var_name = var.get('variable_name', '')
                logger.info(f"[{task['task_type']}] {ranking} 原始变量 {i+1}: {var_name}")

            try:
                for var in extracted_vars:
                    var_name = var.get('variable_name', '')
                    ranking_key = ranking.replace('名', '')
                    # 检查变量名是否包含排名信息（支持"二第几名"格式）
                    if ranking_key in var_name or f"二{ranking_key}" in var_name:
                        if 'reference_source' in var and isinstance(var['reference_source'], dict):
                            # 转换格式（支持旧格式和新格式）
                            var['reference_source'] = _convert_reference_source_format(
                                var['reference_source'], file_url, "candidate_bid_files"
                            )
                        extracted.append(var)
                        logger.info(f"[{task['task_type']}] {ranking} 匹配变量: {var_name}")
                    else:
                        logger.debug(f"[{task['task_type']}] {ranking} 跳过变量: {var_name} (不包含'{ranking_key}'或'二{ranking_key}')")

                # logger.info(f"[{task['task_type']}] 从{ranking}中提取了 {len(extracted)} 个变量")
                
                # 打印第四步业绩提取的详细结果
                if task['task_type'] == 'performance':
                    # logger.info(f"[第四步业绩提取] {ranking} 提取结果详情:")
                    for i, var in enumerate(extracted, 1):
                        var_name = var.get('variable_name', '')
                        var_value = var.get('variable_value', '')
                        logger.info(f"[第四步业绩提取] {i}. 变量名: {var_name}")
                        logger.info(f"[第四步业绩提取] {i}. 变量值长度: {len(var_value)} 字符")
                        # logger.info(f"[第四步业绩提取] {i}. 变量值前800字符: {var_value[:800]}")
                        if 'reference_source' in var:
                            ref_source = var['reference_source']
                            # logger.info(f"[第四步业绩提取] {i}. 参考来源: {ref_source}")
                        # logger.info(f"[第四步业绩提取] {i}. " + "="*50)
            except Exception as e:
                logger.error(f"[{task['task_type']}] {ranking} 结果处理失败: {e}")

            return extracted

        # 为每个任务并发处理传入的排名文件
        all_tasks = []
        for task in task_list:
            logger.info(f"处理任务类型: {task['task_type']}, 条款数: {len(task.get('clauses', []))}")
            # 只处理传入的排名文件，而不是所有候选人
            for ranking in ranked_files.keys():
                all_tasks.append(process_single_task_rank(task, ranking, ranked_files[ranking]))

        all_extracted_variables: List[Dict[str, Any]] = []
        if all_tasks:
            logger.info(f"开始并发执行 {len(all_tasks)} 个提取任务（{len(task_list)}个任务类型 × {len(ranked_files)}个候选人）")
            results = await asyncio.gather(*all_tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    logger.error(f"并发任务异常: {res}")
                    continue
                if res:
                    all_extracted_variables.extend(res)

        if all_extracted_variables:
            variables_list.extend(all_extracted_variables)
            logger.info(f"成功从排名文件中并发提取了 {len(all_extracted_variables)} 个候选人初步评审变量")
        
        return variables_list
        
    except Exception as e:
        logger.error(f"从排名文件提取失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return variables_list


# _extract_performance_only_from_ranked_files 函数已转移到 pre_variables_step4_5.py


async def extract_candidate_details_from_bid_files(
    variables_list: List[Dict[str, Any]], 
    candidate_bid_files_content
) -> List[Dict[str, Any]]:
    """
    第四次模型调用：从candidate_bid_files中提取每个候选人的详细信息（资质、业绩等）
    基于"投标人要求"变量的值来动态提取相关内容
    
    支持两种数据格式：
    1. 新格式：字典类型，键为排名（如"第一名"、"第二名"），值为文件信息字典
    2. 旧格式：字符串类型，包含所有文件的合并内容
    
    Args:
        variables_list: 变量列表（包含推荐中标候选人数和候选人名称）
        candidate_bid_files_content: candidate_bid_files的文件内容（字典或字符串）
        
    Returns:
        List[Dict[str, Any]]: 处理后的变量列表（包含新增的候选人详细变量）
    """
    try:
        # 构建变量映射
        variables_map = {}
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                variables_map[var["variable_name"]] = var
        
        # 获取推荐中标候选人数
        recommended_count_var = variables_map.get("推荐中标候选人数")
        if not recommended_count_var:
            logger.warning("推荐中标候选人数为空，跳过候选人详细信息提取")
            return variables_list
        
        recommended_count = recommended_count_var.get("variable_value", "")
        if not recommended_count:
            logger.warning("推荐中标候选人数的值为空，跳过候选人详细信息提取")
            return variables_list
        
        # 尝试将推荐人数转换为整数
        try:
            count = int(recommended_count)
        except (ValueError, TypeError):
            logger.warning(f"推荐中标候选人数无法转换为整数: {recommended_count}")
            return variables_list
        
        if count <= 0:
            logger.warning(f"推荐中标候选人数无效: {count}")
            return variables_list
        
        # 获取投标人要求变量
        bidder_requirements_var = variables_map.get("投标人要求")
        bidder_requirements = ""
        if bidder_requirements_var:
            bidder_requirements = bidder_requirements_var.get("variable_value", "")
            logger.info(f"获取到投标人要求内容，长度: {len(bidder_requirements)} 字符")
        else:
            logger.warning("未找到投标人要求变量")
        
        # 获取资格评审标准变量
        qualification_review_standard_table_var = variables_map.get("资格评审标准")
        qualification_review_standard_table = ""
        if qualification_review_standard_table_var:
            qualification_review_standard_table = qualification_review_standard_table_var.get("variable_value", "")
            logger.info(f"获取到资格评审标准内容: {qualification_review_standard_table}")
        else:
            logger.warning("未找到资格评审标准变量")
        
        if not bidder_requirements and not qualification_review_standard_table:
            logger.warning("投标人要求和资格评审标准都为空，将按照默认规则提取所有信息")
        
        logger.info(f"开始从candidate_bid_files中提取{count}名候选人的详细信息...")
        
        # 判断数据格式并处理
        if isinstance(candidate_bid_files_content, dict):
            # 新格式：使用排名识别后的文件字典
            logger.info(f"检测到新格式（排名文件字典），共 {len(candidate_bid_files_content)} 个文件")
            logger.info(f"文件键: {list(candidate_bid_files_content.keys())}")
            
            # 根据排名逐个处理每个候选人的文件
            return await _extract_from_ranked_files(
                variables_list,
                candidate_bid_files_content,
                count,
                bidder_requirements,
                qualification_review_standard_table
            )
        else:
            # 旧格式：使用合并的内容字符串
            logger.warning("检测到旧格式（合并内容字符串），使用旧的提取方式")
            logger.info(f"候选人投标文件内容长度: {len(candidate_bid_files_content)} 字符")
            
            # 【调试】输出候选人投标文件内容的前1000字符
            logger.info(f"候选人投标文件内容预览（前1000字符）:\n{candidate_bid_files_content[:1000]}")
        
        # 使用DynamicTableVariableExtractor生成提取提示词
        extractor = DynamicTableVariableExtractor()
        
        # 生成资质、资格业绩等评审情况的变量定义和提示词（新版本返回任务列表）
        # 旧格式不支持业绩表格变量，只生成资质和通用任务
        task_list = extractor.generate_qualification_review_variables(
            candidate_count=count,
            max_performance_count=0,  # 设置为0，不生成业绩任务
            bidder_requirements=bidder_requirements,  # 传递投标人要求
            qualification_review_standard_table=qualification_review_standard_table,  # 传递资格评审标准
            performance_counts=None,  # 不传递业绩数量
            performance_table_variables=None  # 不传递业绩表格变量
        )
        
        logger.info(f"生成了 {len(task_list)} 个提取任务（旧格式）: {[task['task_type'] for task in task_list]}")
        
        # 调用LLM提取候选人详细信息
        # 【重要】只使用 candidate_bid_files 的内容，不使用其他文件类型
        from common.llm_client import LLMClient
        llm_client = LLMClient()
        
        # 对每个任务分别调用LLM
        import json
        for task in task_list:
            logger.info("=" * 80)
            logger.info(f"⚠️ 处理任务类型: {task['task_type']}")
            logger.info(f"⚠️ 条款数: {len(task.get('clauses', []))}")
            logger.info("=" * 80)
            
            prompt = task["prompt"].replace("$content", candidate_bid_files_content)  # 插入文件内容
            logger.info(f"生成的提取提示词长度: {len(prompt)}")
            logger.info(f"提示词预览（前1000字符）:\n{prompt[:1000]}")
            
            # 使用重试机制调用LLM
            result = await call_llm_with_retry_for_json_parse(
                llm_client=llm_client,
                prompt=prompt,
                file_content="",  # 文件内容已经在prompt中了
                step_name="旧格式-候选人详细信息提取",
                task_type=task['task_type'],
                ranking=""
            )
            
            if not result:
                logger.error(f"[{task['task_type']}] LLM调用失败或返回空结果")
                continue
            
            logger.info(f"[{task['task_type']}] LLM返回结果长度: {len(result)}")
            logger.info(f"[{task['task_type']}] LLM返回结果预览（前1000字符）:\n{result[:1000]}")
            
            # 解析LLM返回的JSON结果
            try:
                # 首先尝试提取JSON数组
                json_match = re.search(r'\[[\s\S]*\]', result)
                if json_match:
                    json_str = json_match.group(0)
                    extracted_details = json.loads(json_str)
                    logger.info(f"[{task['task_type']}] 成功解析JSON数组，提取到 {len(extracted_details)} 个变量")
                else:
                    # 如果没有找到JSON数组，尝试提取单个JSON对象
                    json_match = re.search(r'\{[\s\S]*\}', result)
                    if json_match:
                        json_str = json_match.group(0)
                        single_detail = json.loads(json_str)
                        # 将单个对象包装成数组
                        extracted_details = [single_detail]
                        logger.info(f"[{task['task_type']}] 成功解析单个JSON对象，提取到 1 个变量")
                    else:
                        logger.warning(f"[{task['task_type']}] LLM返回结果中未找到有效的JSON")
                        continue
                
                # 【调试】输出前3个提取的变量
                logger.info(f"[{task['task_type']}] 提取到的变量示例（前3个）：")
                for idx, detail in enumerate(extracted_details[:3]):
                    logger.info(f"  变量 {idx+1}:")
                    logger.info(f"    variable_name: {detail.get('variable_name', 'N/A')}")
                    logger.info(f"    variable_value: {detail.get('variable_value', 'N/A')[:100]}...")
                    ref_source = detail.get('reference_source', {})
                    logger.info(f"    file_type: {ref_source.get('file_type', 'N/A')}")
                
                # 将提取的变量添加到变量列表中
                variables_list.extend(extracted_details)
                
                logger.info(f"[{task['task_type']}] 成功添加变量到列表中")
            except json.JSONDecodeError as e:
                logger.error(f"[{task['task_type']}] JSON解析失败: {e}")
                logger.error(f"[{task['task_type']}] 原始返回内容: {result[:500]}")
        
        return variables_list
        
    except Exception as e:
        logger.error(f"提取候选人详细信息失败: {e}")
        return variables_list


# _extract_business_clauses_from_ranked_files 函数已转移到 pre_variables_step4_5.py


async def extract_business_score_table_clauses(
    variables_list: List[Dict[str, Any]], 
    candidate_bid_files_content
) -> List[Dict[str, Any]]:
    """
    从candidate_bid_files中基于商务部分评分表提取条款内容（业绩、业主反馈、综合实力等）
    此函数与第四次模型调用并发执行
    
    支持两种数据格式：
    1. 新格式：字典类型，键为排名（如"第一名"、"第二名"），值为文件信息字典
    2. 旧格式：字符串类型，包含所有文件的合并内容
    
    Args:
        variables_list: 变量列表（包含推荐中标候选人数、候选人名称和商务评分标准）
        candidate_bid_files_content: candidate_bid_files的文件内容（字典或字符串）
        
    Returns:
        List[Dict[str, Any]]: 提取的商务评分标准变量列表
    """
    try:
        # 构建变量映射
        variables_map = {}
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                variables_map[var["variable_name"]] = var
        
        # 获取推荐中标候选人数
        recommended_count_var = variables_map.get("推荐中标候选人数")
        if not recommended_count_var:
            logger.warning("推荐中标候选人数为空，跳过商务评分标准提取")
            return []
        
        recommended_count = recommended_count_var.get("variable_value", "")
        if not recommended_count:
            logger.warning("推荐中标候选人数的值为空，跳过商务评分标准提取")
            return []
        
        # 尝试将推荐人数转换为整数
        try:
            count = int(recommended_count)
        except (ValueError, TypeError):
            logger.warning(f"推荐中标候选人数无法转换为整数: {recommended_count}")
            return []
        
        if count <= 0:
            logger.warning(f"推荐中标候选人数无效: {count}")
            return []
        
        # 获取商务评分标准变量
        business_score_clauses_var = variables_map.get("商务评分标准")
        business_score_clauses = ""
        if business_score_clauses_var:
            business_score_clauses = business_score_clauses_var.get("variable_value", "")
            logger.info(f"获取到商务评分标准内容: {business_score_clauses}")
        else:
            logger.warning("未找到商务评分标准变量，跳过商务评分标准提取")
            return []
        
        if not business_score_clauses:
            logger.warning("商务评分标准内容为空，跳过商务评分标准提取")
            return []
        
        # 获取候选人名称字典
        candidate_names = {}
        chinese_ordinals = ["第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]
        for i in range(1, count + 1):
            if i <= len(chinese_ordinals):
                var_name = f"{chinese_ordinals[i-1]}中标候选人名称"
            else:
                var_name = f"第{i}中标候选人名称"
            
            candidate_var = variables_map.get(var_name)
            if candidate_var:
                name = candidate_var.get("variable_value", "")
                if name:
                    candidate_names[i] = name
        
        logger.info(f"开始从candidate_bid_files中提取{count}名候选人的商务评分标准信息...")
        
        # 判断数据格式并处理
        if isinstance(candidate_bid_files_content, dict):
            # 新格式：使用排名识别后的文件字典
            logger.info(f"检测到新格式（排名文件字典），共 {len(candidate_bid_files_content)} 个文件")
            logger.info(f"文件键: {list(candidate_bid_files_content.keys())}")
            
            # 根据排名逐个处理每个候选人的文件
            return await _extract_business_clauses_from_ranked_files(
                candidate_bid_files_content,
                count,
                business_score_clauses,
                candidate_names,
                variables_list
            )
        else:
            # 旧格式：使用合并的内容字符串
            logger.warning("检测到旧格式（合并内容字符串），使用旧的提取方式")
            logger.info(f"候选人投标文件内容长度: {len(candidate_bid_files_content)} 字符")
        
        # 使用BusinessScoreTableVariableExtractor生成提取提示词
        extractor = BusinessScoreTableVariableExtractor()
        
        # 生成商务评分标准的变量定义和提示词（新版本返回任务列表）
        task_list = extractor.generate_business_score_extraction_variables(
            candidate_count=count,
            business_score_clauses=business_score_clauses,
            candidate_names=candidate_names
        )
        
        logger.info(f"生成了 {len(task_list)} 个商务条款提取任务（旧格式）: {[task['task_type'] for task in task_list]}")
        
        # 调用LLM提取商务评分标准信息
        from common.llm_client import LLMClient
        llm_client = LLMClient()
        
        # 对每个任务分别调用LLM
        import json
        all_extracted_clauses = []
        
        for task in task_list:
            logger.info("=" * 80)
            logger.info(f"⚠️ 处理商务条款任务类型: {task['task_type']}")
            logger.info(f"⚠️ 条款数: {len(task.get('clauses', []))}")
            logger.info("=" * 80)
            
            prompt = task["prompt"].replace("$content", candidate_bid_files_content)  # 插入文件内容
            logger.info(f"生成的商务评分标准提取提示词长度: {len(prompt)}")
            logger.info(f"提示词预览（前1000字符）:\n{prompt[:1000]}")
            
            # 使用重试机制调用LLM
            llm_result = await call_llm_with_retry_for_json_parse(
                llm_client=llm_client,
                prompt=prompt,
                file_content="",  # 文件内容已经在prompt中了
                step_name="旧格式-商务评分标准提取",
                task_type=task['task_type'],
                ranking=""
            )
            
            if not llm_result:
                logger.error(f"[{task['task_type']}] LLM调用失败或返回空结果")
                continue
            
            logger.info(f"[{task['task_type']}] LLM返回结果长度: {len(llm_result)}")
            logger.info(f"[{task['task_type']}] LLM返回结果预览（前1000字符）:\n{llm_result[:1000]}")
            
            # 解析LLM返回的JSON结果
            try:
                # 提取JSON部分
                json_match = re.search(r'\[[\s\S]*\]', llm_result)
                if json_match:
                    json_str = json_match.group(0)
                    extracted_clauses = json.loads(json_str)
                    logger.info(f"[{task['task_type']}] 成功解析JSON，提取到 {len(extracted_clauses)} 个变量")
                    
                    # 【调试】输出前3个提取的变量
                    logger.info(f"[{task['task_type']}] 提取到的变量示例（前3个）：")
                    for idx, clause in enumerate(extracted_clauses[:3]):
                        logger.info(f"  变量 {idx+1}:")
                        logger.info(f"    variable_name: {clause.get('variable_name', 'N/A')}")
                        logger.info(f"    variable_value: {clause.get('variable_value', 'N/A')[:100]}...")
                        ref_source = clause.get('reference_source', {})
                        logger.info(f"    file_type: {ref_source.get('file_type', 'N/A')}")
                    
                    all_extracted_clauses.extend(extracted_clauses)
                    logger.info(f"[{task['task_type']}] 成功添加变量到列表中")
                else:
                    logger.warning(f"[{task['task_type']}] LLM返回结果中未找到有效的JSON数组")
            except json.JSONDecodeError as e:
                logger.error(f"[{task['task_type']}] JSON解析失败: {e}")
        
        # 特殊处理：标书质量变量不提取内容，但需要返回变量，值为空
        for clause in all_extracted_clauses:
            variable_name = clause.get("variable_name", "")
            if "标书质量" in variable_name:
                clause["variable_value"] = ""
                logger.info(f"标书质量变量 '{variable_name}' 已设置为空值（后续需要打分）")
        
        logger.info(f"成功提取商务评分标准变量，共 {len(all_extracted_clauses)} 个")
        return all_extracted_clauses
        
    except Exception as e:
        logger.error(f"提取商务评分标准失败: {e}")
        return []


async def generate_candidates_summary_text(variables_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    动态生成推荐中标候选人名称的描述文本
    
    格式：根据招标文件规定，推荐了X名中标候选人。A公司为第一中标候选人；B公司为第二中标候选人。具体情况如下：
    
    Args:
        variables_list: 变量列表
        
    Returns:
        List[Dict[str, Any]]: 处理后的变量列表（包含新增的推荐中标候选人名称变量）
    """
    try:
        # 构建变量映射
        variables_map = {}
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                variables_map[var["variable_name"]] = var
        
        # 获取推荐中标候选人数
        recommended_count_var = variables_map.get("推荐中标候选人数")
        
        if not recommended_count_var:
            logger.warning("推荐中标候选人数为空，跳过生成候选人描述文本")
            return variables_list
        
        recommended_count = recommended_count_var.get("variable_value", "")
        
        if not recommended_count:
            logger.warning("推荐中标候选人数的值为空，跳过生成候选人描述文本")
            return variables_list
        
        # 尝试将推荐人数转换为整数
        try:
            count = int(recommended_count)
        except (ValueError, TypeError):
            logger.warning(f"推荐中标候选人数无法转换为整数: {recommended_count}")
            return variables_list
        
        if count <= 0:
            logger.warning(f"推荐中标候选人数无效: {count}")
            return variables_list
        
        logger.info(f"开始生成推荐中标候选人描述文本，共{count}名候选人...")
        
        # 中文数字映射
        chinese_numbers = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
        chinese_ordinals = ["第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]
        
        # 收集所有候选人名称
        candidate_names = []
        reference_sources = []
        
        for i in range(1, count + 1):
            if i <= len(chinese_ordinals):
                var_name = f"{chinese_ordinals[i-1]}中标候选人名称"
            else:
                var_name = f"第{i}中标候选人名称"
            
            candidate_var = variables_map.get(var_name)
            if candidate_var:
                name = candidate_var.get("variable_value", "")
                if name:
                    candidate_names.append({
                        "index": i,
                        "name": name,
                        "ordinal": chinese_ordinals[i-1] if i <= len(chinese_ordinals) else f"第{i}"
                    })
                    # 收集引用来源
                    ref_source = candidate_var.get("reference_source", {})
                    if ref_source:
                        reference_sources.append(ref_source)
        
        if not candidate_names:
            logger.warning("未找到任何有效的候选人名称，跳过生成描述文本")
            return variables_list
        
        # 构建描述文本（使用实际值和HTML标签）
        # 第一部分：使用推荐中标候选人数的原始值（带id和灰色高亮）
        recommended_count_value = recommended_count_var.get("variable_value", str(count))
        summary_text = f'根据招标文件规定，推荐了<span id="推荐中标候选人数" style="background-color: rgb(192,192,192);">{recommended_count_value}</span>名中标候选人。'
        
        # 第二部分：各候选人名称（使用实际名称，带id和灰色高亮）
        candidate_descriptions = []
        for candidate in candidate_names:
            var_name = f"{candidate['ordinal']}中标候选人名称"
            # 直接使用候选人的实际名称
            candidate_descriptions.append(f'<span id="{var_name}" style="background-color: rgb(192,192,192);">{candidate["name"]}</span>为{candidate["ordinal"]}中标候选人')
        
        # 用分号连接所有候选人
        summary_text += "；".join(candidate_descriptions) + "。具体情况如下："
        
        # logger.info(f"生成的候选人描述文本（使用实际值）: {summary_text}")
        
        # 推荐中标候选人名称的reference_source留空
        empty_reference_source = {
            "source_url": "",
            "evidence_text": "",
            "pages": "",
            "file_type": ""
        }
        
        # 创建新变量（只包含变量名和变量值，引用来源留空）
        new_variable = {
            "variable_name": "推荐中标候选人名称",
            "variable_value": summary_text,
            "reference_source": empty_reference_source
        }
        
        # 检查是否已存在该变量
        if "推荐中标候选人名称" in variables_map:
            # 更新现有变量
            variables_map["推荐中标候选人名称"]["variable_value"] = summary_text
            variables_map["推荐中标候选人名称"]["reference_source"] = empty_reference_source
            logger.info("更新推荐中标候选人名称变量")
        else:
            # 添加新变量
            variables_list.append(new_variable)
            logger.info("添加推荐中标候选人名称变量")
        
        return variables_list
        
    except Exception as e:
        logger.error(f"生成候选人描述文本失败: {e}")
        return variables_list

# _count_extracted_performances 函数已转移到 pre_variables_step4_5.py


# _get_expected_performance_counts 函数已转移到 pre_variables_step4_5.py


# _clean_failed_candidates_performance_variables 函数已转移到 pre_variables_step4_5.py


# _validate_performance_counts 函数已转移到 pre_variables_step4_5.py


async def preprocess_variables(
    variables_list: List[Dict[str, Any]], 
    merged_contents: Dict[str, Any] = None,
    skip_early_steps: bool = False
) -> List[Dict[str, Any]]:
    """
    预变量处理主函数，调用所有预处理函数
    
    模型调用流程：
    1. 第一次：提取 variable_templates.py 中的固定变量（在调用此函数前已完成）
    2. 第二次：判断推荐中标候选人数量（如果skip_early_steps=True则跳过）
    3. 第三次：提取每个候选人的公司名称（如果skip_early_steps=True则跳过）
    4. 第四次 & 第五次（并发执行）：
       - 第四次：从 candidate_bid_files 中提取每个候选人的资质、业绩等详细信息
       - 第五次：从 candidate_bid_files 中基于商务部分评分表提取条款内容
    
    Args:
        variables_list: 原始变量列表（来自第一次模型调用）
        merged_contents: 合并的文件内容字典，包含各文件类型的内容（可选）
        skip_early_steps: 如果为True，跳过推荐人数处理、候选人名称提取和投标人要求拆分（这些步骤已在外部完成）
        
    Returns:
        List[Dict[str, Any]]: 处理后的变量列表
    """
    try:
        logger.info("开始预变量处理...")
        logger.info("=" * 80)
        
        if skip_early_steps:
            logger.info("跳过早期步骤（推荐人数、候选人名称、投标人要求拆分），这些步骤已在外部完成")
            # 即使跳过早期步骤，仍然需要处理中标候选人得分汇总情况（基于推荐人数过滤）
            variables_list = await process_candidates_score_summary(variables_list)
        else:
            # 第二次模型调用：处理推荐中标候选人数 + 第四步预变量处理（并发执行）
            logger.info("[第二次模型调用] 判断推荐中标候选人数量...")
            logger.info("[第四步预变量处理] 开始条款类型分析和要求提取...")
            
            # 并发执行推荐中标候选人数处理和第四步预变量处理
            import asyncio
            from src.utils.pre_variable_for_step4 import extract_clause_requirements_from_tables
            
            # 获取必要的数据
            variables_map = {}
            for var in variables_list:
                if isinstance(var, dict) and "variable_name" in var:
                    variables_map[var["variable_name"]] = var
            
            # 获取投标人要求
            bidder_requirements_var = variables_map.get("投标人要求")
            bidder_requirements = ""
            if bidder_requirements_var:
                bidder_requirements = bidder_requirements_var.get("variable_value", "")
                logger.info(f"获取到投标人要求内容，长度: {len(bidder_requirements)} 字符")
            else:
                logger.warning("未找到投标人要求变量")
            
            # 获取资格评审标准
            qualification_review_standard_table_var = variables_map.get("资格评审标准")
            qualification_review_standard_table = ""
            if qualification_review_standard_table_var:
                qualification_review_standard_table = qualification_review_standard_table_var.get("variable_value", "")
                logger.info(f"获取到资格评审标准内容: {qualification_review_standard_table}")
            else:
                logger.warning("未找到资格评审标准变量")
            
            # 获取商务评分标准
            business_score_clauses_var = variables_map.get("商务评分标准")
            business_score_clauses = ""
            if business_score_clauses_var:
                business_score_clauses = business_score_clauses_var.get("variable_value", "")
                logger.info(f"获取到商务评分标准内容: {business_score_clauses}")
            else:
                logger.warning("未找到商务评分标准变量")
            
            # 并发执行两个任务
            async def process_recommended_candidates():
                return await process_recommended_candidates_count(variables_list)
            
            async def process_step4_requirements():
                if bidder_requirements and qualification_review_standard_table and business_score_clauses:
                    return await extract_clause_requirements_from_tables(
                        business_score_clauses,
                        qualification_review_standard_table,
                        bidder_requirements
                    )
                else:
                    logger.warning("缺少必要数据，跳过第四步预变量处理")
                    return {
                        'performance_requirements': '',
                        'qualification_requirements': '',
                        'other_requirements': '',
                        'success': False,
                        'error': '缺少必要数据'
                    }
            
            # 并发执行
            logger.info("开始并发执行推荐中标候选人数处理和第四步预变量处理...")
            variables_list, step4_result = await asyncio.gather(
                process_recommended_candidates(),
                process_step4_requirements()
            )
            
            # 处理第四步预变量处理结果
            if step4_result.get('success', False):
                logger.info("第四步预变量处理成功，添加条款要求变量...")
                
                # 添加业绩条款要求变量
                if step4_result.get('performance_requirements'):
                    performance_req_var = {
                        "variable_name": "业绩条款要求",
                        "variable_value": step4_result['performance_requirements'],
                        "reference_source": {
                            "file_type": "evaluation_summary_file",
                            "page_number": "投标人要求",
                            "section": "业绩条款",
                            "content_preview": "业绩相关条款要求",
                            "source_url": ""
                        }
                    }
                    variables_list.append(performance_req_var)
                    logger.info(f"添加业绩条款要求变量，长度: {len(step4_result['performance_requirements'])} 字符")
                
                # 添加资质条款要求变量
                if step4_result.get('qualification_requirements'):
                    qualification_req_var = {
                        "variable_name": "资质条款要求",
                        "variable_value": step4_result['qualification_requirements'],
                        "reference_source": {
                            "file_type": "evaluation_summary_file",
                            "page_number": "投标人要求",
                            "section": "资质条款",
                            "content_preview": "资质相关条款要求",
                            "source_url": ""
                        }
                    }
                    variables_list.append(qualification_req_var)
                    logger.info(f"添加资质条款要求变量，长度: {len(step4_result['qualification_requirements'])} 字符")
                
                # 添加其他条款要求变量
                if step4_result.get('other_requirements'):
                    other_req_var = {
                        "variable_name": "其他条款要求",
                        "variable_value": step4_result['other_requirements'],
                        "reference_source": {
                            "file_type": "evaluation_summary_file",
                            "page_number": "投标人要求",
                            "section": "其他条款",
                            "content_preview": "其他条款要求",
                            "source_url": ""
                        }
                    }
                    variables_list.append(other_req_var)
                    logger.info(f"添加其他条款要求变量，长度: {len(step4_result['other_requirements'])} 字符")
            else:
                logger.warning(f"第四步预变量处理失败: {step4_result.get('error', '未知错误')}")
            
            logger.info("[第二次模型调用] 完成")
            logger.info("[第四步预变量处理] 完成")
            
            # 处理中标候选人得分汇总情况（基于推荐人数过滤）
            variables_list = await process_candidates_score_summary(variables_list)
            
            # 第三次模型调用：动态提取候选人名称
            logger.info("[第三次模型调用] 提取每个候选人的公司名称...")
            variables_list = await extract_candidate_names_by_count(variables_list)
            logger.info("[第三次模型调用] 完成")
            
            # 动态生成候选人描述文本
            variables_list = await generate_candidates_summary_text(variables_list)
        
        # 第四次和第五次模型调用（并发执行）：从candidate_bid_files中提取候选人详细信息
        if merged_contents and "candidate_bid_files" in merged_contents:
            logger.info("[准备第四次 & 第五次模型调用] 首先识别投标文件排名...")
            
            # 获取candidate_bid_files的内容
            candidate_bid_files_data = merged_contents["candidate_bid_files"]
            
            # 处理新的数据结构（每个文件独立保存）
            if isinstance(candidate_bid_files_data, dict) and 'files' in candidate_bid_files_data:
                # 新的数据结构：包含独立的文件字典
                candidate_files = candidate_bid_files_data['files']
                
                # 获取评审结果用于排名识别
                variables_map = {var.get("variable_name"): var for var in variables_list if isinstance(var, dict)}
                evaluation_result_var = variables_map.get("评审结果")
                
                if evaluation_result_var and evaluation_result_var.get("variable_value"):
                    evaluation_result = evaluation_result_var.get("variable_value", "")
                    
                    # 识别每个文件的排名
                    from prompts.bid_file_ranking_prompt import BidFileRankingIdentifier, rename_files_by_ranking
                    ranking_identifier = BidFileRankingIdentifier()
                    
                    # 准备文件预览字典（前2000字符）
                    file_previews = {
                        file_key: file_info['preview'] 
                        for file_key, file_info in candidate_files.items()
                    }
                    
                    logger.info(f"开始识别 {len(file_previews)} 个投标文件的排名...")
                    
                    # 调用LLM识别排名
                    ranking_map = await ranking_identifier.identify_bid_file_rankings(
                        file_previews, 
                        evaluation_result
                    )
                    
                    if ranking_map:
                        # 根据排名重命名文件
                        candidate_files = rename_files_by_ranking(candidate_files, ranking_map)
                        logger.info(f"投标文件已根据排名重命名: {list(candidate_files.keys())}")
                        
                        # 过滤出成功识别排名的文件（只处理"第X名"格式的文件）
                        recognized_files = {}
                        chinese_ordinals = ["第一名", "第二名", "第三名", "第四名", "第五名", "第六名", "第七名", "第八名", "第九名", "第十名"]
                        
                        for file_key, file_info in candidate_files.items():
                            if file_key in chinese_ordinals or file_key.startswith("第") and file_key.endswith("名"):
                                recognized_files[file_key] = file_info
                                logger.info(f"识别到排名文件: {file_key}")
                            else:
                                logger.info(f"跳过未识别的文件: {file_key}")
                        
                        if recognized_files:
                            logger.info(f"共识别到 {len(recognized_files)} 个排名文件，开始处理...")
                            
                            # ========== 新增：对重命名后的文件进行内容截取处理 ==========
                            logger.info("开始对重命名后的文件进行内容截取处理...")
                            try:
                                from src.business.service.content_filter_service import ContentFilterService
                                content_filter_service = ContentFilterService()
                                
                                # 对重命名后的文件进行内容截取
                                recognized_files = await content_filter_service.filter_ranked_files_content(recognized_files)
                                
                                # 验证内容截取结果
                                validation_results = content_filter_service.validate_content_filter_results(recognized_files)
                                # logger.info(f"内容截取处理完成: {validation_results}")
                                
                                # 获取内容截取摘要
                                content_summary = content_filter_service.get_content_summary(recognized_files)
                                # logger.info(f"内容截取摘要: {content_summary}")
                                
                            except Exception as e:
                                logger.error(f"内容截取处理失败: {e}")
                                logger.warning("继续使用原始文件内容，跳过内容截取")
                            
                            # 将业绩表格数据转换为标准变量格式
                            variables_list = await _convert_performance_tables_to_variables(variables_list, recognized_files)
                            
                            # 更新merged_contents中的数据（只更新识别到的文件）
                            merged_contents["candidate_bid_files"]['files'] = recognized_files
                            
                            # 更新candidate_files变量，使其包含内容截取后的结果
                            candidate_files = recognized_files
                        else:
                            logger.warning("没有识别到任何排名文件，跳过后续处理")
                            candidate_files = None
                    else:
                        logger.warning("排名识别失败，使用原始文件名称")
                else:
                    logger.warning("未找到评审结果变量，跳过排名识别")
                
            elif isinstance(candidate_bid_files_data, dict) and 'content' in candidate_bid_files_data:
                # 兼容旧的数据结构（合并的内容）
                logger.warning("检测到旧的数据结构（合并内容），无法进行排名识别")
                candidate_files = None
            else:
                # 兼容最旧的数据结构（直接是字符串）
                logger.warning("检测到最旧的数据结构（字符串），无法进行排名识别")
                candidate_files = None
            
            # 准备文件内容（兼容新旧数据结构）
            if candidate_files is not None:
                # 新的数据结构：使用排名识别后的文件字典
                logger.info(f"使用新的数据结构（排名文件），共 {len(candidate_files)} 个文件")
                candidate_content_dict = candidate_files
            else:
                # 旧的数据结构：使用合并的内容或字符串
                if isinstance(candidate_bid_files_data, dict) and 'content' in candidate_bid_files_data:
                    candidate_content_dict = candidate_bid_files_data['content']
                else:
                    candidate_content_dict = candidate_bid_files_data
                logger.info("使用旧的数据结构（合并内容）")
            
            # 检查是否有可处理的文件
            if candidate_files is None or not candidate_files:
                # 即使没有可处理的文件，仍然需要执行打分功能
                logger.warning("没有可处理的投标文件，跳过第四步和第五步提取，但将继续执行打分功能")
                # 不直接返回，继续执行打分功能
                candidate_content_dict = None
            else:
                candidate_content_dict = candidate_files if candidate_files is not None else candidate_content_dict
            
            # 获取候选人数量
            recommended_count_var = None
            for var in variables_list:
                if isinstance(var, dict) and var.get("variable_name") == "推荐中标候选人数":
                    recommended_count_var = var
                    break
            
            if not recommended_count_var:
                logger.warning("未找到推荐中标候选人数，跳过第四步和第五步处理，但将继续执行打分功能")
                candidate_count = 0
                current_variables = variables_list.copy()
            else:
                try:
                    candidate_count = int(recommended_count_var.get("variable_value", "0"))
                except (ValueError, TypeError):
                    logger.warning("推荐中标候选人数无法转换为整数，跳过第四步和第五步处理，但将继续执行打分功能")
                    candidate_count = 0
                    current_variables = variables_list.copy()
            
            # ========== 第四次 & 第五次模型调用：使用业绩数量提取业绩等信息 ==========
            # 只有在有可处理的文件内容时才执行第四步和第五步
            if candidate_content_dict is not None and candidate_content_dict:
                logger.info("[第四次 & 第五次模型调用] 并发执行：提取候选人详细信息 + 商务评分标准...")
                
                # 执行提取任务（不再需要重试机制）
                current_variables = variables_list.copy()  # 保存基础变量列表
                
                # 并发执行三个提取任务
                import asyncio
                
                # 获取商务评分标准用于简历表人员姓名提取
                business_score_clauses = ""
                variables_map = {var.get("variable_name"): var for var in current_variables if isinstance(var, dict)}
                business_score_clauses_var = variables_map.get("商务评分标准")
                if business_score_clauses_var:
                    business_score_clauses = business_score_clauses_var.get("variable_value", "")
                    logger.info(f"获取到商务评分标准，长度: {len(business_score_clauses)} 字符")
                else:
                    logger.warning("未找到商务评分标准变量")
                
                # 提取所有候选人的详细信息
                logger.info("开始提取所有候选人的详细信息")
                task1 = extract_candidate_details_from_bid_files(
                    current_variables.copy(),  # 传递副本避免并发修改问题
                    candidate_content_dict
                )
                task2 = extract_business_score_table_clauses(
                    current_variables,  # 传递原始列表
                    candidate_content_dict
                )
                # 添加简历表人员姓名提取任务
                task3 = extract_resume_personnel_names_from_ranked_files(
                    candidate_content_dict,
                    business_score_clauses
                )
                
                # 并发执行
                logger.info("⚠️ 开始并发执行三个提取任务...")
                result1, result2, result3 = await asyncio.gather(task1, task2, task3)
                logger.info("✅ 并发执行完成")
                
                # 合并结果
                # result1 是更新后的完整变量列表（包含原有变量 + 第四次提取的变量）
                # result2 是第五次提取的商务评分标准变量列表
                # result3 是简历表人员姓名提取的变量列表
                current_variables = result1  # 先使用第四次的结果作为基础
                if result2:
                    current_variables.extend(result2)  # 添加第五次提取的变量
                    logger.info(f"成功添加 {len(result2)} 个商务评分标准变量")
                if result3:
                    current_variables.extend(result3)  # 添加简历表人员姓名变量
                    logger.info(f"成功添加 {len(result3)} 个简历表人员姓名变量")
                
                # 第五步业绩处理：根据商务评分标准重新分类第四步的业绩变量
                logger.info("开始第五步业绩变量处理...")
                try:
                    current_variables = await process_step5_performance_variables(
                        variables_list=current_variables,
                        business_score_clauses=business_score_clauses,
                        candidate_count=candidate_count
                    )
                    logger.info("第五步业绩变量处理完成")
                except Exception as e:
                    logger.error(f"第五步业绩变量处理失败: {e}")
                    # 继续处理，不中断流程
                
                # 使用最终结果
                variables_list = current_variables
                logger.info("[第四次 & 第五次模型调用] 完成")
            else:
                logger.info("跳过第四步和第五步提取（没有可处理的文件内容），直接进入打分功能")
                current_variables = variables_list.copy()
                variables_list = current_variables
            
            # ========== 第六次模型调用：评分填充 ==========
            # 无论是否有文件内容，都需要执行打分功能
            logger.info("[第六次模型调用] 开始执行打分功能...")
            variables_list = await enrich_variables_with_scores(variables_list)
        else:
            logger.warning("未提供candidate_bid_files内容，跳过第四次和第五次模型调用")
        
        logger.info("=" * 80)
        logger.info("预变量处理完成")
        return variables_list
        
    except Exception as e:
        logger.error(f"预变量处理失败: {e}")
        return variables_list


# 第四步函数已转移到 pre_variables_step4_5.py


# 第五步函数已转移到 pre_variables_step4_5.py




async def enrich_variables_with_scores(variables_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    使用【评审结果】【复核卡得分】【商务评分标准】【商务部分评分表】四个变量来对每个候选人变量进行评分填充
    
    处理逻辑：
    1. 从【评审结果】中提取排名与投标人名称的对应关系（如：第一名 → 山西斯坦福机电设备有限公司）
    2. 优先以【复核卡得分】中的内容为准（使用投标人公司名称）
    3. 如果复核卡得分中没有对应的分数，则根据【商务评分标准】和【商务部分评分表】来确定
    4. 在变量值尾部换行填入评价（如"有效，资格业绩不计分；"、"有效，计2分；"等）
    
    关键点：
    - 变量名中只有"第X名"（如"第一名业绩1"）
    - 复核卡得分中使用具体的投标人公司名称
    - 需要通过评审结果建立两者的对应关系
    
    Args:
        variables_list: 变量列表（包含第五次提取的变量）
        
    Returns:
        List[Dict[str, Any]]: 处理后的变量列表
    """
    try:
        logger.info("=" * 80)
        logger.info("[第六次模型调用] 开始根据复核卡得分、商务评分标准、商务部分评分表填充候选人变量评分...")
        
        # 构建变量映射
        variables_map = {}
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                variables_map[var["variable_name"]] = var
        
        # 获取关键变量
        review_card_score_var = variables_map.get("复核卡得分")
        business_standard_var = variables_map.get("商务评分标准")
        business_score_table_var = variables_map.get("商务部分评分表")
        evaluation_result_var = variables_map.get("评审结果")
        
        # 检查关键变量是否存在
        if not evaluation_result_var:
            logger.warning("未找到【评审结果】变量，跳过评分填充")
            return variables_list
        
        # 允许【复核卡得分】缺失或为空，走降级逻辑
        review_card_score = ""
        if review_card_score_var:
            review_card_score = review_card_score_var.get("variable_value", "") or ""
            if not review_card_score:
                logger.info("【复核卡得分】为空，将按无复核卡得分规则处理")
        else:
            logger.info("未找到【复核卡得分】变量，将按无复核卡得分规则处理")
        
        business_standard = business_standard_var.get("variable_value", "") if business_standard_var else ""
        business_score_table = business_score_table_var.get("variable_value", "") if business_score_table_var else ""
        evaluation_result = evaluation_result_var.get("variable_value", "")
        
        if not evaluation_result:
            logger.warning("【评审结果】变量值为空，跳过评分填充")
            return variables_list
        
        logger.info(f"复核卡得分内容长度: {len(review_card_score)}")
        logger.info(f"商务评分标准内容长度: {len(business_standard)}")
        logger.info(f"商务部分评分表内容长度: {len(business_score_table)}")
        logger.info(f"评审结果内容长度: {len(evaluation_result)}")
        
        # 解析商务评分标准，获取商务条款列表
        business_clauses = []
        if business_standard:
            try:
                from src.utils.dynamic_table_generator import _parse_clauses
                business_clauses = _parse_clauses(business_standard)
                logger.info(f"从商务评分标准中解析出 {len(business_clauses)} 个商务条款: {business_clauses}")
            except Exception as e:
                logger.warning(f"解析商务评分标准失败: {e}")
                # 如果解析失败，仍然继续处理，但会使用更宽松的匹配规则
        
        # 解析资格评审标准，获取资格评审条款列表（用于排除资格评审标准的业绩变量）
        qualification_clauses = []
        qualification_standard_var = variables_map.get("资格评审标准")
        if qualification_standard_var:
            qualification_standard = qualification_standard_var.get("variable_value", "") or ""
            if qualification_standard:
                try:
                    from src.utils.dynamic_table_generator import _parse_clauses
                    qualification_clauses = _parse_clauses(qualification_standard)
                    logger.info(f"从资格评审标准中解析出 {len(qualification_clauses)} 个资格评审条款: {qualification_clauses}")
                except Exception as e:
                    logger.warning(f"解析资格评审标准失败: {e}")
        
        # 获取候选人数量（用于判断变量是否属于商务条款）
        recommended_count_var = variables_map.get("推荐中标候选人数")
        candidate_count = 3  # 默认值
        if recommended_count_var:
            try:
                candidate_count = int(recommended_count_var.get("variable_value", "3"))
            except (ValueError, TypeError):
                logger.warning(f"无法获取候选人数量，使用默认值: {candidate_count}")
        
        # 筛选并按排名分组以"第X名"开头的变量（候选人相关变量，不再使用"三"前缀）
        candidate_groups: Dict[str, List[Dict[str, Any]]] = {}
        candidate_variable_total = 0
        chinese_ordinals_full = ["第一名", "第二名", "第三名", "第四名", "第五名", "第六名", "第七名", "第八名", "第九名", "第十名"]
        
        def detect_rank(var_name: str) -> Optional[str]:
            # 直接匹配"第X名"开头，不再需要"三"前缀
            for rank_label in chinese_ordinals_full:
                if var_name.startswith(rank_label):
                    return rank_label
            return None
        
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                var_name = var["variable_name"]
                rank_label = detect_rank(var_name)
                if rank_label:
                    candidate_groups.setdefault(rank_label, []).append(var)
                    candidate_variable_total += 1
        
        if not candidate_groups:
            logger.warning("未找到以'第X名'开头的候选人变量，跳过评分填充")
            return variables_list
        
        logger.info(f"按排名分组候选人变量，共 {candidate_variable_total} 个，组数 {len(candidate_groups)}：{list(candidate_groups.keys())}")
        
        # 筛选出属于商务评分标准的变量（使用商务评分标准来判断）
        business_groups = {}
        rank_order = {label: idx for idx, label in enumerate(chinese_ordinals_full, start=1)}
        
        # 导入判断函数
        from src.utils.dynamic_table_generator import _is_variable_from_business
        
        for rank_label, group_vars in candidate_groups.items():
            business_vars = []
            
            for var in group_vars:
                var_name = var.get("variable_name", "")
                # 排除业绩变量（业绩变量单独处理）
                if "业绩" in var_name:
                    continue
                
                # 使用商务评分标准判断变量是否属于商务条款
                if business_clauses:
                    if _is_variable_from_business(var_name, business_clauses, candidate_count):
                        business_vars.append(var)
                        logger.debug(f"✅ 商务条款变量: {var_name}")
                    else:
                        logger.debug(f"⏭️ 跳过非商务条款变量: {var_name}")
                else:
                    # 如果没有商务评分标准，记录警告但不进行打分
                    logger.warning(f"缺少商务评分标准，无法判断变量 {var_name} 是否属于商务条款，跳过该变量")
            
            if business_vars:
                business_groups[rank_label] = business_vars
                logger.info(f"{rank_label} 筛选出 {len(business_vars)} 个商务条款变量")
        
        # 并发为每个候选人调用模型进行商务变量评分填充
        import asyncio
        tasks = []
        
        # 构建排名到候选人名称的映射
        rank_to_candidate_name = {}
        chinese_ordinals = ["第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]
        for var in variables_list:
            var_name = var.get("variable_name", "")
            for i, ordinal in enumerate(chinese_ordinals, 1):
                if var_name == f"{ordinal}中标候选人名称":
                    rank_label = f"第{'一二三四五六七八九十'[i-1]}名"
                    candidate_name = var.get("variable_value", "")
                    if candidate_name:
                        rank_to_candidate_name[rank_label] = candidate_name
                        logger.info(f"找到{rank_label}对应的候选人名称: {candidate_name}")
        
        for rank_label in sorted(business_groups.keys(), key=lambda k: rank_order.get(k, 999)):
            group_vars = business_groups[rank_label]
            # 获取对应的候选人名称
            candidate_name = rank_to_candidate_name.get(rank_label, "")
            if not candidate_name:
                logger.warning(f"未找到{rank_label}对应的候选人名称，将使用排名标识")
            
            logger.info(f"为{rank_label}创建商务变量评分填充任务，变量数: {len(group_vars)}, 候选人名称: {candidate_name}")
            tasks.append(_call_llm_to_enrich_scores(
                candidate_variables=group_vars,
                review_card_score=review_card_score,
                business_standard=business_standard,
                business_score_table=business_score_table,
                evaluation_result=evaluation_result,
                rank_label=rank_label,
                candidate_name=candidate_name
            ))
        
        enriched_business: List[Dict[str, Any]] = []
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for rank_label, res in zip(sorted(business_groups.keys(), key=lambda k: rank_order.get(k, 999)), results):
                if isinstance(res, Exception) or res is None:
                    logger.error(f"{rank_label} 商务变量评分填充任务失败或返回空")
                    continue
                if isinstance(res, dict):
                    business_vars = res.get("business_variables", [])
                    enriched_business.extend(business_vars)
                    logger.info(f"{rank_label} 成功填充 {len(business_vars)} 个商务变量")
        
        # 创建业绩得分变量 - 单独调用模型提取
        performance_score_variables: List[Dict[str, Any]] = []
        
        # 确定需要提取业绩得分的排名列表
        ranks_to_process = set()
        
        # 如果有商务变量，使用商务变量对应的排名
        if business_groups:
            ranks_to_process = set(business_groups.keys())
        else:
            # 如果没有商务变量，从业绩变量中提取排名
            for var in variables_list:
                var_name = var.get("variable_name", "")
                # 匹配"第X名"开头的业绩变量，不再使用"三"前缀，排除包含"表"的变量
                for rank in chinese_ordinals_full:
                    if var_name.startswith(rank) and "业绩" in var_name and "表" not in var_name and "得分" not in var_name:
                        ranks_to_process.add(rank)
                        break
            
            # 如果没有找到业绩变量，尝试从评审结果中提取排名
            if not ranks_to_process:
                import re
                rank_pattern = r'第[一二三四五六七八九十]+名'
                matches = re.findall(rank_pattern, evaluation_result)
                ranks_to_process = set(matches)
                logger.info(f"从评审结果中提取到排名: {ranks_to_process}")
        
        # 并发为每个排名单独调用模型提取业绩得分
        if ranks_to_process:
            logger.info(f"开始单独调用模型提取业绩得分，共 {len(ranks_to_process)} 个排名")
            import asyncio
            
            async def extract_single_performance_score(rank_label: str) -> Dict[str, Any]:
                """为单个排名提取业绩得分"""
                try:
                    performance_score = await _extract_performance_score_by_llm(
                        rank_label=rank_label,
                        evaluation_result=evaluation_result,
                        review_card_score=review_card_score,
                        business_standard=business_standard,
                        business_score_table=business_score_table
                    )
                    
                    return {
                        "variable_name": f"{rank_label}业绩得分",
                        "variable_value": performance_score,
                        "reference_source": {
                            "source_url": "",
                            "evidence_text": "",
                            "pages": "",
                            "file_type": ""
                        }
                    }
                except Exception as e:
                    logger.error(f"提取{rank_label}业绩得分失败: {e}")
                    return {
                        "variable_name": f"{rank_label}业绩得分",
                        "variable_value": 0,
                        "reference_source": {
                            "source_url": "",
                            "evidence_text": "",
                            "pages": "",
                            "file_type": ""
                        }
                    }
            
            # 并发执行所有排名的业绩得分提取
            tasks = [extract_single_performance_score(rank_label) for rank_label in ranks_to_process]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 收集结果
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"业绩得分提取任务异常: {result}")
                    continue
                if result and isinstance(result, dict):
                    performance_score_variables.append(result)
                    logger.info(f"创建业绩得分变量: {result['variable_name']} = {result['variable_value']}")
            
            logger.info(f"成功提取 {len(performance_score_variables)} 个业绩得分变量")
        
        # 合并所有填充后的变量
        enriched_all = enriched_business + performance_score_variables
        
        if enriched_all:
            # 更新变量列表中的候选人变量
            enriched_map = {var["variable_name"]: var for var in enriched_all if isinstance(var, dict) and var.get("variable_name")}
            updated_count = 0
            for i, var in enumerate(variables_list):
                if isinstance(var, dict) and "variable_name" in var:
                    var_name = var["variable_name"]
                    if var_name in enriched_map:
                        variables_list[i] = enriched_map[var_name]
                        updated_count += 1
            logger.info(f"成功并发填充 {updated_count} 个候选人变量的评分（总返回 {len(enriched_all)}）")
        else:
            logger.warning("并发评分填充未返回任何有效结果")
        
        # 在代码中为所有业绩变量添加得分信息
        performance_updated_count = 0
        
        # 首先从已创建的业绩得分变量中构建得分映射
        performance_score_map = {}
        for var in performance_score_variables:
            var_name = var.get("variable_name", "")
            if var_name.endswith("业绩得分"):
                # 提取排名信息
                for rank in chinese_ordinals_full:
                    if var_name.startswith(rank):
                        score_value = var.get("variable_value", 0)
                        # 确保是整数类型
                        if isinstance(score_value, str):
                            import re
                            score_match = re.search(r'(\d+)', score_value)
                            if score_match:
                                score_value = int(score_match.group(1))
                            else:
                                score_value = 0
                        # 限制业绩得分不大于3分，超过3分改为2分
                        if score_value > 3:
                            score_value = 2
                            logger.warning(f"业绩得分变量{var_name}超过3，已限制为2")
                        performance_score_map[rank] = score_value
                        break
        
        logger.info(f"从业绩得分变量中构建得分映射: {performance_score_map}")
        
        # 为所有业绩变量添加得分信息（只处理属于商务条款的业绩变量）
        logger.info(f"开始为业绩变量添加得分信息，当前得分映射: {performance_score_map}")
        logger.info(f"变量列表中的业绩变量:")
        
        # 检查商务条款中是否包含业绩相关条款
        has_performance_clause = False
        if business_clauses:
            for clause in business_clauses:
                if "业绩" in clause:
                    has_performance_clause = True
                    logger.info(f"发现商务条款中的业绩条款: {clause}")
                    break
        
        if not has_performance_clause:
            logger.warning("商务评分标准中未包含业绩相关条款，跳过业绩变量打分")
        else:
            logger.info("商务评分标准中包含业绩相关条款，将处理业绩变量")
        
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                var_name = var["variable_name"]
                # 匹配"第X名"开头的业绩变量，不再需要"三"前缀，排除包含"表"的变量
                if any(var_name.startswith(rank) and "业绩" in var_name and "得分" not in var_name and "表" not in var_name for rank in chinese_ordinals_full):
                    logger.info(f"  发现业绩变量: {var_name}")
        
        for i, var in enumerate(variables_list):
            if isinstance(var, dict) and "variable_name" in var:
                var_name = var["variable_name"]
                # 查找所有"第几名XXX业绩"格式的变量（不再使用"三"前缀）
                # 排除包含"表"的变量（如"第一名业绩要求表1"），只处理不包含"表"的变量（如"第一名业绩要求1"）
                rank_label = None
                for rank in chinese_ordinals_full:
                    if var_name.startswith(rank) and "业绩" in var_name and "得分" not in var_name and "表" not in var_name:
                        rank_label = rank
                        break
                
                if rank_label:
                    logger.info(f"处理业绩变量: {var_name}, 提取到排名: {rank_label}")
                    
                    # 优先使用变量提取时标记的来源信息（is_business_clause）
                    # 如果变量在提取时已经标记为商务部分，直接使用；否则再判断
                    is_business_performance = var.get("is_business_clause", False)
                    
                    if is_business_performance:
                        logger.info(f"✅ 业绩变量 {var_name} 在提取时已标记为商务部分，将添加得分")
                    else:
                        # 如果变量没有标记，则通过判断来确定（向后兼容）
                        # 首先检查该业绩变量是否属于资格评审标准（如果是，明确排除，不添加得分）
                        is_qualification_performance = False
                        if qualification_clauses:
                            from src.utils.dynamic_table_generator import _is_variable_from_qualification
                            is_qualification_performance = _is_variable_from_qualification(var_name, qualification_clauses, candidate_count)
                            if is_qualification_performance:
                                logger.info(f"❌ 业绩变量 {var_name} 属于资格评审标准，明确排除，不添加得分")
                        
                        # 检查该业绩变量是否属于商务条款（只有商务条款的业绩才添加得分）
                        if not is_qualification_performance and business_clauses and has_performance_clause:
                            # 使用商务评分标准判断该业绩变量是否属于商务条款
                            is_business_performance = _is_variable_from_business(var_name, business_clauses, candidate_count)
                            if is_business_performance:
                                logger.debug(f"✅ 商务条款业绩变量: {var_name}")
                            else:
                                logger.debug(f"⏭️ 跳过非商务条款业绩变量: {var_name}")
                        elif not business_clauses and not is_qualification_performance:
                            logger.warning(f"缺少商务评分标准，无法判断业绩变量 {var_name} 是否属于商务条款，跳过该变量")
                            is_business_performance = False
                    
                    # 只有属于商务条款的业绩变量才添加得分
                    if is_business_performance and rank_label in performance_score_map:
                        performance_score = performance_score_map[rank_label]
                        original_value = var.get("variable_value", "")
                        score_text = f"该业绩得{performance_score}分"
                        variables_list[i]["variable_value"] = f"{original_value}\n{score_text}"
                        performance_updated_count += 1
                        logger.info(f"为业绩变量添加得分: {var_name} -> {score_text}")
                    elif is_business_performance and rank_label not in performance_score_map:
                        logger.warning(f"未找到排名 {rank_label} 对应的业绩得分")
                    elif not is_business_performance:
                        logger.debug(f"业绩变量 {var_name} 不属于商务条款，跳过打分")
        
        logger.info(f"成功为 {performance_updated_count} 个业绩变量添加得分信息")
        
        logger.info("[第六次模型调用] 完成")
        logger.info("=" * 80)
        
        return variables_list
        
    except Exception as e:
        logger.error(f"评分填充处理失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return variables_list


async def _call_llm_to_enrich_scores(
    candidate_variables: List[Dict[str, Any]],
    review_card_score: str,
    business_standard: str,
    business_score_table: str,
    evaluation_result: str,
    rank_label: str = "",
    candidate_name: str = ""
) -> Optional[Dict[str, Any]]:
    """
    调用LLM来填充候选人变量的评分
    
    Args:
        candidate_variables: 候选人变量列表（只包含商务部分变量，不包含业绩变量）
        review_card_score: 复核卡得分内容
        business_standard: 商务评分标准内容
        business_score_table: 商务部分评分表内容
        evaluation_result: 评审结果内容（包含排名与投标人名称对应关系）
        rank_label: 当前候选人的排名（如"第一名"）
        candidate_name: 当前候选人的具体名称（如"山西斯坦福机电设备有限公司"）
        
    Returns:
        Optional[Dict[str, Any]]: 包含填充后的商务变量和业绩得分信息
        {
            "business_variables": List[Dict[str, Any]],  # 填充后的商务变量
            "performance_scores": Dict[str, int]  # 业绩得分，只包含当前候选人的得分 {rank_label: 0或2}
        }
    """
    try:
        from common.llm_client import LLMClient
        llm_client = LLMClient()
        
        # 构建提示词
        candidate_info = ""
        if candidate_name:
            candidate_info = f"\n**⚠️ 重要：本次任务只处理【{candidate_name}】（{rank_label}）的评分，请忽略其他候选人的信息。**"
        else:
            candidate_info = f"\n**⚠️ 重要：本次任务只处理【{rank_label}】的评分，请忽略其他候选人的信息。**"
        
        # 构建候选人标识文本
        candidate_label = rank_label
        if candidate_name:
            candidate_label = f"{rank_label}（{candidate_name}）"
        
        prompt = generate_score_enrichment_prompt(
            candidate_variables,
            review_card_score,
            business_standard,
            business_score_table,
            evaluation_result,
            rank_label,
            candidate_name
        )
        
        logger.info("开始调用LLM进行评分填充...")
        logger.info(f"提示词长度: {len(prompt)}")
        
        # 使用重试机制调用LLM
        response = await call_llm_with_retry_for_json_parse(
            llm_client=llm_client,
            prompt=prompt,
            file_content="",  # 不需要额外的文件内容，所有信息已在prompt中
            step_name="第6步-评分填充",
            task_type="评分填充",
            ranking=rank_label if rank_label else ""
        )
        
        if not response:
            logger.error("LLM调用失败或返回空结果")
            return None
        
        logger.info(f"LLM返回内容长度: {len(response)}")
        logger.debug(f"LLM原始返回:\n{response[:500]}...")
        
        # 解析JSON结果
        import json
        import re
        
        # 首先清理响应内容，移除markdown代码块标记
        clean_response = response.strip()
        
        # 移除markdown代码块标记
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:]
        elif clean_response.startswith("```"):
            clean_response = clean_response[3:]
        
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3]
        
        clean_response = clean_response.strip()
        
        try:
            # 尝试直接解析清理后的内容
            result = json.loads(clean_response)
            logger.info("直接解析清理后的JSON成功")
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            logger.error(f"清理后的内容前500字符: {clean_response[:500]}")
            return None
        
        # 验证返回结果
        if not isinstance(result, dict):
            logger.error("LLM返回的不是字典格式")
            return None
        
        if "business_variables" not in result:
            logger.error("LLM返回结果中缺少business_variables字段")
            return None
        
        business_vars = result.get("business_variables", [])
        
        if not isinstance(business_vars, list):
            logger.error("business_variables不是列表格式")
            return None
        
        if len(business_vars) != len(candidate_variables):
            logger.warning(f"LLM返回的商务变量数量({len(business_vars)})与输入不一致({len(candidate_variables)})")
        
        logger.info(f"成功解析 {len(business_vars)} 个填充后的商务变量")
        
        return {
            "business_variables": business_vars
        }
        
    except Exception as e:
        logger.error(f"调用LLM填充评分失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


async def _extract_performance_score_by_llm(
    rank_label: str,
    evaluation_result: str,
    review_card_score: str,
    business_standard: str,
    business_score_table: str
) -> int:
    """
    单独调用模型提取指定排名的业绩得分
    
    只传入必要的变量（评审结果、复核卡得分、商务评分标准、商务部分评分表），
    不传入其他不相关的变量。
    
    Args:
        rank_label: 排名标签（如"第一名"、"第二名"）
        evaluation_result: 评审结果内容
        review_card_score: 复核卡得分内容
        business_standard: 商务评分标准内容
        business_score_table: 商务部分评分表内容
        
    Returns:
        int: 业绩得分（0或2）
    """
    try:
        from common.llm_client import LLMClient
        llm_client = LLMClient()
        
        # 构建业绩得分查询提示词（只包含必要的变量，不包含其他不相关的变量）
        performance_prompt = generate_performance_score_prompt(
            rank_label,
            evaluation_result,
            review_card_score,
            business_standard,
            business_score_table
        )
        
        logger.info(f"开始单独调用模型提取{rank_label}的业绩得分...")
        
        # 调用LLM获取业绩得分
        response = await llm_client.call_llm(performance_prompt, "", "default")
        
        if response:
            # 提取数值，去除所有非数字字符
            import re
            score_match = re.search(r'(\d+)', response.strip())
            if score_match:
                parsed = int(score_match.group(1))
                performance_score = 0 if parsed == 0 else 2
            else:
                performance_score = 0
            logger.info(f"LLM返回{rank_label}业绩得分: {performance_score}")
            return performance_score
        else:
            performance_score = 0
            logger.warning(f"LLM未返回{rank_label}业绩得分，使用默认值")
            return performance_score
            
    except Exception as e:
        logger.error(f"获取{rank_label}业绩得分失败: {e}")
        return 0




def _merge_reference_sources(reference_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    合并多个reference_source，用于新生成的变量
    
    Args:
        reference_sources: reference_source列表
        
    Returns:
        Dict[str, Any]: 合并后的reference_source
    """
    merged = {
        "source_url": "",
        "evidence_text": "",
        "pages": "",
        "file_type": ""
    }
    
    # 收集所有非空值
    source_urls = []
    evidence_texts = []
    pages = []
    file_types = []
    
    for ref_source in reference_sources:
        if not isinstance(ref_source, dict):
            continue
        
        # 收集source_url
        source_url = ref_source.get("source_url", "")
        if source_url and source_url not in source_urls:
            source_urls.append(source_url)
        
        # 收集evidence_text
        evidence_text = ref_source.get("evidence_text", "")
        if evidence_text and evidence_text not in evidence_texts:
            evidence_texts.append(evidence_text)
        
        # 收集pages
        page = ref_source.get("pages", "")
        if page and page not in pages:
            pages.append(page)
        
        # 收集file_type
        file_type = ref_source.get("file_type", "")
        if file_type and file_type not in file_types:
            file_types.append(file_type)
    
    # 合并为逗号分隔的字符串
    merged["source_url"] = ", ".join(source_urls) if source_urls else ""
    merged["evidence_text"] = ", ".join(evidence_texts) if evidence_texts else ""
    merged["pages"] = ", ".join(pages) if pages else ""
    merged["file_type"] = ", ".join(file_types) if file_types else ""
    
    return merged

