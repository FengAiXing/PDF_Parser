"""
第四步和第五步处理逻辑模块

本模块包含预变量处理中第四步（候选人详细信息提取）和第五步（商务条款提取）的相关函数。
主要功能：
- 第四步：从投标文件中提取候选人的详细信息（资质、业绩等）
- 第五步：从投标文件中提取商务评分标准信息
- 业绩数量统计和验证
- 失败候选人的变量清理
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


async def extract_failed_candidates_details(
    variables_list: List[Dict[str, Any]], 
    candidate_bid_files_content,
    failed_candidates_step4: List[int],
    failed_candidates_step5: List[int]
) -> List[Dict[str, Any]]:
    """
    只提取验证失败的候选人的详细信息（第四步）
    
    Args:
        variables_list: 变量列表
        candidate_bid_files_content: 候选人投标文件内容
        failed_candidates_step4: 第四步失败的候选人排名列表
        failed_candidates_step5: 第五步失败的候选人排名列表（此函数不使用）
        
    Returns:
        List[Dict[str, Any]]: 更新后的变量列表
    """
    if not failed_candidates_step4:
        logger.info("没有第四步验证失败的候选人，跳过详细信息提取")
        return variables_list
    
    try:
        logger.info(f"只提取第四步验证失败的候选人详细信息: {failed_candidates_step4}")
        
        # 构建变量映射
        variables_map = {}
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                variables_map[var["variable_name"]] = var
        
        # 获取投标人要求和资格评审标准
        bidder_requirements_var = variables_map.get("投标人要求")
        qualification_review_standard_table_var = variables_map.get("资格评审标准")
        
        bidder_requirements = ""
        if bidder_requirements_var:
            bidder_requirements = bidder_requirements_var.get("variable_value", "")
            logger.info(f"获取到投标人要求内容，长度: {len(bidder_requirements)} 字符")
        else:
            logger.warning("未找到投标人要求变量")
        
        qualification_review_standard_table = ""
        if qualification_review_standard_table_var:
            qualification_review_standard_table = qualification_review_standard_table_var.get("variable_value", "")
            logger.info(f"获取到资格评审标准内容: {qualification_review_standard_table}")
        else:
            logger.warning("未找到资格评审标准变量")
        
        # 判断数据格式并处理
        if isinstance(candidate_bid_files_content, dict):
            # 新格式：只处理失败的候选人
            logger.info(f"检测到新格式（排名文件字典），只处理失败的候选人")
            
            # 过滤出只包含失败候选人的文件
            failed_candidate_files = {}
            chinese_ordinals = ["第一名", "第二名", "第三名", "第四名", "第五名", "第六名", "第七名", "第八名", "第九名", "第十名"]
            
            for rank in failed_candidates_step4:
                if rank <= len(chinese_ordinals):
                    rank_name = chinese_ordinals[rank-1]  # 直接使用，不需要再加"名"
                else:
                    rank_name = f"第{rank}名"
                
                if rank_name in candidate_bid_files_content:
                    failed_candidate_files[rank_name] = candidate_bid_files_content[rank_name]
                    logger.info(f"找到失败候选人 {rank_name} 的投标文件")
                else:
                    logger.warning(f"未找到失败候选人 {rank_name} 的投标文件")
            
            if failed_candidate_files:
                # 只处理失败的候选人，且只提取业绩相关任务
                return await _extract_performance_only_from_ranked_files(
                    variables_list,
                    failed_candidate_files,
                    len(failed_candidate_files),  # 使用失败候选人文件的数量
                    bidder_requirements,
                    qualification_review_standard_table
                )
            else:
                logger.warning("没有找到失败候选人的投标文件")
                return variables_list
        else:
            logger.warning("旧格式不支持选择性提取，跳过")
            return variables_list
        
    except Exception as e:
        logger.error(f"提取失败候选人详细信息失败: {e}")
        return variables_list


async def extract_failed_candidates_business_clauses(
    variables_list: List[Dict[str, Any]], 
    candidate_bid_files_content,
    failed_candidates_step4: List[int],
    failed_candidates_step5: List[int]
) -> List[Dict[str, Any]]:
    """
    只提取验证失败的候选人的商务评分标准（第五步）
    
    Args:
        variables_list: 变量列表
        candidate_bid_files_content: 候选人投标文件内容
        failed_candidates_step4: 第四步失败的候选人排名列表（此函数不使用）
        failed_candidates_step5: 第五步失败的候选人排名列表
        
    Returns:
        List[Dict[str, Any]]: 商务评分标准变量列表
    """
    if not failed_candidates_step5:
        logger.info("没有第五步验证失败的候选人，跳过商务条款提取")
        return []
    
    try:
        logger.info(f"只提取第五步验证失败的候选人商务条款: {failed_candidates_step5}")
        
        # 构建变量映射
        variables_map = {}
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                variables_map[var["variable_name"]] = var
        
        # 获取商务评分标准
        business_score_clauses_var = variables_map.get("商务评分标准")
        business_score_clauses = ""
        if business_score_clauses_var:
            business_score_clauses = business_score_clauses_var.get("variable_value", "")
            logger.info(f"获取到商务评分标准内容: {business_score_clauses}")
        else:
            logger.warning("未找到商务评分标准变量")
        
        # 判断数据格式并处理
        if isinstance(candidate_bid_files_content, dict):
            # 新格式：只处理失败的候选人
            logger.info(f"检测到新格式（排名文件字典），只处理失败的候选人")
            
            # 过滤出只包含失败候选人的文件
            failed_candidate_files = {}
            chinese_ordinals = ["第一名", "第二名", "第三名", "第四名", "第五名", "第六名", "第七名", "第八名", "第九名", "第十名"]
            
            for rank in failed_candidates_step5:
                if rank <= len(chinese_ordinals):
                    rank_name = chinese_ordinals[rank-1]  # 直接使用，不需要再加"名"
                else:
                    rank_name = f"第{rank}名"
                
                if rank_name in candidate_bid_files_content:
                    failed_candidate_files[rank_name] = candidate_bid_files_content[rank_name]
                    logger.info(f"找到失败候选人 {rank_name} 的投标文件")
                else:
                    logger.warning(f"未找到失败候选人 {rank_name} 的投标文件")
            
            if failed_candidate_files:
                # 构建失败候选人的名称字典
                failed_candidate_names = {}
                chinese_ordinals = ["第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]
                
                for rank in failed_candidates_step5:
                    if rank <= len(chinese_ordinals):
                        rank_name = chinese_ordinals[rank-1]
                    else:
                        rank_name = f"第{rank}"
                    
                    # 从variables_list中查找候选人名称
                    candidate_name_var = f"{rank_name}中标候选人名称"
                    for var in variables_list:
                        if isinstance(var, dict) and var.get("variable_name") == candidate_name_var:
                            failed_candidate_names[rank] = var.get("variable_value", "")
                            break
                
                # 只处理失败的候选人
                return await _extract_business_clauses_from_ranked_files(
                    failed_candidate_files,
                    len(failed_candidates_step5),
                    business_score_clauses,
                    failed_candidate_names,
                    variables_list
                )
            else:
                logger.warning("没有找到失败候选人的投标文件")
                return []
        else:
            logger.warning("旧格式不支持选择性提取，跳过")
            return []
        
    except Exception as e:
        logger.error(f"提取失败候选人商务条款失败: {e}")
        return []


async def _extract_performance_only_from_ranked_files(
    variables_list: List[Dict[str, Any]],
    ranked_files: Dict[str, Dict[str, Any]],
    candidate_count: int,
    bidder_requirements: str,
    qualification_review_standard_table: str
) -> List[Dict[str, Any]]:
    """
    从排名文件中只提取业绩相关信息（重试专用）
    
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
        from common.llm_client import LLMClient
        
        llm_client = LLMClient()
        extractor = DynamicTableVariableExtractor()
        
        # 从variables_list中提取业绩数量（使用工具函数）
        performance_counts = extract_performance_counts_from_variables(
            variables_list if variables_list else [], 
            candidate_count
        )
        
        # 解析条款，只保留业绩相关的条款
        clauses = extractor._parse_clauses(qualification_review_standard_table)
        performance_clauses = []
        
        for clause in clauses:
            clause_text = clause.strip()
            if not clause_text:
                continue
            # 只检测包含"业绩"的条款
            if re.search(r'业绩', clause_text):
                performance_clauses.append(clause_text)
        
        if not performance_clauses:
            logger.warning("没有找到业绩相关的条款，跳过业绩提取")
            return variables_list
        
        # 检查是否有业绩表格变量，如果没有则跳过业绩提取（使用工具函数）
        performance_table_variables = extract_performance_table_variables(
            variables_list if variables_list else []
        )
        if performance_table_variables:
            logger.info(f"重试时从variables_list中检测到 {len(performance_table_variables)} 个业绩表格变量")
        
        if performance_table_variables:
            logger.info(f"检测到 {len(performance_table_variables)} 个业绩表格变量，使用表格变量方法生成任务")
            # 使用业绩表格变量方法生成任务
            task_list = extractor.generate_qualification_review_variables(
                candidate_count=candidate_count,
                max_performance_count=10,
                bidder_requirements=bidder_requirements,
                qualification_review_standard_table=qualification_review_standard_table,
                performance_counts=performance_counts if performance_counts else None,
                performance_table_variables=performance_table_variables
            )
            logger.info(f"重试时使用业绩表格变量方法生成任务: {[task['task_type'] for task in task_list]}")
        else:
            logger.warning("重试时未检测到业绩表格变量，跳过业绩提取任务")
            # 只生成资质和通用任务，不生成业绩任务
            task_list = extractor.generate_qualification_review_variables(
                candidate_count=candidate_count,
                max_performance_count=0,  # 设置为0，不生成业绩任务
                bidder_requirements=bidder_requirements,
                qualification_review_standard_table=qualification_review_standard_table,
                performance_counts=None,  # 不传递业绩数量
                performance_table_variables=None
            )
            logger.info(f"重试时只生成非业绩任务: {[task['task_type'] for task in task_list]}")
        
        # 中文排名映射
        chinese_ordinals = ["第一名", "第二名", "第三名", "第四名", "第五名", "第六名", "第七名", "第八名", "第九名", "第十名"]

        # 为每个任务并发处理传入的排名文件
        async def process_single_task_rank(task: Dict[str, Any], ranking: str, file_info: Dict[str, Any]) -> List[Dict[str, Any]]:
            """处理单个任务的单个排名"""
            extracted: List[Dict[str, Any]] = []
            file_content = file_info.get('content', '')
            file_url = file_info.get('file_url', '')

            if not file_content:
                logger.warning(f"[{task['task_type']}] {ranking}的投标文件内容为空，跳过")
                return extracted

            logger.info(f"[{task['task_type']}] 开始从{ranking}的投标文件中提取信息... 长度: {len(file_content)} 字符")

            # 获取该任务的提示词
            prompt = task['prompt']
            
            # 仅提取当前排名候选人，并插入文件内容
            ranking_specific_prompt = (
                prompt.replace(
                    f"请从投标文件中提取前{candidate_count}名候选人",
                    f"请从投标文件中提取{ranking}候选人"
                )
                .replace("$content", file_content)  # 插入文件内容
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
            parsed_result = parse_llm_json_result(
                result, 
                task_type=task['task_type'], 
                ranking=ranking
            )
            
            if parsed_result is None:
                logger.error(f"[{task['task_type']}] {ranking} JSON解析失败")
                return extracted
            
            # 处理解析后的结果
            try:
                for item in parsed_result:
                    if isinstance(item, dict):
                        # 添加文件来源信息
                        item['reference_source'] = {
                            'source_type': 'bid_file',
                            'source_url': file_url
                        }
                        extracted.append(item)
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
            logger.info(f"成功从排名文件中并发提取了 {len(all_extracted_variables)} 个候选人业绩变量")
        
        return variables_list
        
    except Exception as e:
        logger.error(f"从排名文件提取业绩失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return variables_list


async def _extract_business_clauses_from_ranked_files(
    ranked_files: Dict[str, Dict[str, Any]],
    candidate_count: int,
    business_score_clauses: str,
    candidate_names: Dict[int, str],
    variables_list: List[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    从排名文件中提取商务评分标准信息（新方法）
    
    根据变量名称中的排名信息，从对应排名的投标文件中提取内容
    
    Args:
        ranked_files: 排名文件字典，格式为 {"第一名": {content, file_url, ...}, "第二名": {...}}
        candidate_count: 候选人数量
        business_score_clauses: 商务评分标准内容
        candidate_names: 候选人名称字典
        variables_list: 变量列表（用于提取业绩数量）
        
    Returns:
        List[Dict[str, Any]]: 提取的商务评分标准变量列表
    """
    try:
        from common.llm_client import LLMClient
        
        llm_client = LLMClient()
        extractor = BusinessScoreTableVariableExtractor()
        
        # 业绩提取已移至第五步处理，此处不再需要业绩数量
        # logger.info("商务条款提取-业绩提取已移至第五步处理，此处只处理通用条款")
        
        # 中文排名映射
        chinese_ordinals_full = ["第一名", "第二名", "第三名", "第四名", "第五名", "第六名", "第七名", "第八名", "第九名", "第十名"]

        async def process_single_rank(i: int, ranking: str) -> List[Dict[str, Any]]:
            extracted: List[Dict[str, Any]] = []
            if ranking not in ranked_files:
                logger.warning(f"未找到{ranking}的投标文件，跳过商务条款提取")
                return extracted

            file_info = ranked_files[ranking]
            file_content = file_info.get('content', '')
            file_url = file_info.get('file_url', '')

            if not file_content:
                logger.warning(f"{ranking}的投标文件内容为空，跳过商务条款提取")
                return extracted

            logger.info(f"开始从{ranking}的投标文件中提取商务评分标准信息... 长度: {len(file_content)} 字符")

            single_candidate_names = {i: candidate_names.get(i, "")}
            
            task_list = extractor.generate_business_score_extraction_variables(
                candidate_count=1,
                business_score_clauses=business_score_clauses,
                candidate_names=single_candidate_names
            )
            
            logger.info(f"{ranking} 生成了 {len(task_list)} 个商务条款提取任务: {[task['task_type'] for task in task_list]}")

            # 对每个任务分别调用LLM
            for task in task_list:
                prompt = task["prompt"].replace("$content", file_content)  # 插入文件内容
                task_type = task["task_type"]
                
                logger.info(f"{ranking} 开始处理商务条款任务类型: {task_type}, 条款数: {len(task.get('clauses', []))}")

                # 使用重试机制调用LLM
                llm_result = await call_llm_with_retry_for_json_parse(
                    llm_client=llm_client,
                    prompt=prompt,
                    file_content="",  # 文件内容已经在prompt中了
                    step_name=f"第5步-商务条款-{ranking}-{task_type}",
                    task_type=f"商务条款-{task_type}",
                    ranking=ranking
                )

                if not llm_result:
                    logger.error(f"{ranking} 商务条款提取[{task_type}] LLM调用失败或返回空结果")
                    continue

                logger.info(f"{ranking} 商务条款提取[{task_type}] LLM返回结果长度: {len(llm_result)}")

                try:
                    json_match = re.search(r'\[[\s\S]*\]', llm_result)
                    if not json_match:
                        logger.warning(f"{ranking} 商务条款提取[{task_type}] LLM返回结果中未找到有效的JSON数组")
                        continue

                    json_str = json_match.group(0)
                    extracted_clauses = json.loads(json_str)

                    for clause in extracted_clauses:
                        if 'reference_source' in clause and isinstance(clause['reference_source'], dict):
                            clause['reference_source']['source_url'] = file_url
                        extracted.append(clause)

                    logger.info(f"{ranking} 商务条款提取[{task_type}] 提取了 {len(extracted_clauses)} 个变量")
                except json.JSONDecodeError as e:
                    logger.error(f"{ranking} 商务条款提取[{task_type}] JSON解析失败: {e}")
                except Exception as e:
                    logger.error(f"{ranking} 商务条款结果处理[{task_type}] 失败: {e}")

            return extracted

        tasks = []
        # 只处理传入的排名文件，而不是所有候选人
        for ranking in ranked_files.keys():
            # 从排名名称中提取排名数字
            rank_num = None
            for i, ordinal in enumerate(chinese_ordinals_full, 1):
                if ranking == ordinal:
                    rank_num = i
                    break
            
            if rank_num:
                tasks.append(process_single_rank(rank_num, ranking))

        all_extracted_clauses: List[Dict[str, Any]] = []
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    logger.error(f"并发任务异常（商务条款）: {res}")
                    continue
                if res:
                    all_extracted_clauses.extend(res)

        # 特殊处理：标书质量变量不提取内容，但需要返回变量，值为空
        for clause in all_extracted_clauses:
            variable_name = clause.get("variable_name", "")
            if "标书质量" in variable_name:
                clause["variable_value"] = ""
                logger.info(f"标书质量变量 '{variable_name}' 已设置为空值（后续需要打分）")

        logger.info(f"成功从排名文件中并发提取了 {len(all_extracted_clauses)} 个商务评分标准变量")
        return all_extracted_clauses
        
    except Exception as e:
        logger.error(f"从排名文件提取商务条款失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def _count_extracted_performances(variables_list: List[Dict[str, Any]], candidate_count: int) -> Dict[int, Dict[str, int]]:
    """
    分别统计第四步和第五步提取到的业绩数量
    
    Args:
        variables_list: 变量列表
        candidate_count: 候选人数量
        
    Returns:
        Dict[int, Dict[str, int]]: 候选人排名到业绩数量的映射 
        {1: {"step4": 3, "step5": 2}, 2: {"step4": 5, "step5": 1}, ...}
    """
    performance_counts = {}
    
    # 中文排名映射
    chinese_ordinals = ["第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]
    
    for i in range(1, candidate_count + 1):
        if i <= len(chinese_ordinals):
            rank_name = f"{chinese_ordinals[i-1]}名"
        else:
            rank_name = f"第{i}名"
        
        # 第四步业绩：基于业绩表格变量提取的业绩，格式如"第一名业绩1", "第一名业绩2"
        step4_count = 0
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                var_name = var["variable_name"]
                # 匹配第四步业绩变量（基于业绩表格变量提取，排除业绩表格变量本身）
                if var_name.startswith(rank_name) and "业绩" in var_name and var_name != f"{rank_name}业绩数量" and "业绩表" not in var_name:
                    # 提取业绩编号
                    match = re.search(r'业绩(\d+)', var_name)
                    if match:
                        performance_num = int(match.group(1))
                        step4_count = max(step4_count, performance_num)
        
        # 第五步业绩：格式如"第一名投标人业绩1", "第一名投标人业绩2"（不再使用"三"前缀）
        # 注意：第五步现在是通过重新分类第四步的业绩变量，而不是重新提取
        step5_count = 0
        for var in variables_list:
            if isinstance(var, dict) and "variable_name" in var:
                var_name = var["variable_name"]
                # 匹配第五步业绩变量（以"第X名"开头，包含"业绩"，不再使用"三"前缀）
                if var_name.startswith(rank_name) and "业绩" in var_name:
                    # 提取业绩编号
                    match = re.search(r'业绩(\d+)', var_name)
                    if match:
                        performance_num = int(match.group(1))
                        step5_count = max(step5_count, performance_num)
        
        performance_counts[i] = {
            "step4": step4_count,
            "step5": step5_count
        }
        
        logger.info(f"{rank_name}业绩统计: 第四步{step4_count}个，第五步{step5_count}个")
    
    return performance_counts


def _get_expected_performance_counts(variables_list: List[Dict[str, Any]], candidate_count: int) -> Dict[int, int]:
    """
    获取预期的业绩数量（从业绩数量变量中获取）
    
    Args:
        variables_list: 变量列表
        candidate_count: 候选人数量
        
    Returns:
        Dict[int, int]: 候选人排名到预期业绩数量的映射 {1: 5, 2: 3, ...}
    """
    expected_counts = {}
    
    # 中文排名映射
    chinese_ordinals = ["第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]
    
    for i in range(1, candidate_count + 1):
        if i <= len(chinese_ordinals):
            rank_name = f"{chinese_ordinals[i-1]}名"
        else:
            rank_name = f"第{i}名"
        
        # 查找业绩数量变量
        performance_count_var_name = f"{rank_name}业绩数量"
        for var in variables_list:
            if isinstance(var, dict) and var.get("variable_name") == performance_count_var_name:
                try:
                    expected_count = int(var.get("variable_value", "0"))
                    expected_counts[i] = expected_count
                    logger.info(f"{rank_name}预期业绩数量: {expected_count}")
                    break
                except (ValueError, TypeError):
                    logger.warning(f"无法解析{rank_name}的预期业绩数量: {var.get('variable_value')}")
                    expected_counts[i] = 0
                    break
        else:
            # 如果没有找到业绩数量变量，默认为0
            expected_counts[i] = 0
            logger.warning(f"未找到{rank_name}的业绩数量变量")
    
    return expected_counts


def _clean_failed_candidates_performance_variables(variables_list: List[Dict[str, Any]], 
                                                   failed_candidates_step4: List[int], 
                                                   failed_candidates_step5: List[int]) -> List[Dict[str, Any]]:
    """
    精确清理失败候选人的业绩变量，区分第四步和第五步的失败
    
    Args:
        variables_list: 变量列表
        failed_candidates_step4: 第四步失败的候选人排名列表
        failed_candidates_step5: 第五步失败的候选人排名列表
        
    Returns:
        List[Dict[str, Any]]: 清理后的变量列表
    """
    if not failed_candidates_step4 and not failed_candidates_step5:
        return variables_list
    
    # 中文排名映射
    chinese_ordinals = ["第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]
    
    # 构建需要清理的变量名前缀
    step4_prefixes_to_remove = []  # 第四步变量前缀
    step5_prefixes_to_remove = []  # 第五步变量前缀
    
    # 处理第四步失败的候选人
    for rank in failed_candidates_step4:
        if rank <= len(chinese_ordinals):
            rank_name = f"{chinese_ordinals[rank-1]}名"
        else:
            rank_name = f"第{rank}名"
        step4_prefixes_to_remove.append(rank_name)
    
    # 处理第五步失败的候选人
    for rank in failed_candidates_step5:
        if rank <= len(chinese_ordinals):
            rank_name = f"{chinese_ordinals[rank-1]}名"
        else:
            rank_name = f"第{rank}名"
        step5_prefixes_to_remove.append(f"三{rank_name}")
    
    # 过滤掉失败候选人的业绩变量
    cleaned_variables = []
    for var in variables_list:
        if isinstance(var, dict) and "variable_name" in var:
            var_name = var["variable_name"]
            should_remove = False
            
            # 检查第四步变量（初步评审）
            for prefix in step4_prefixes_to_remove:
                if var_name.startswith(prefix) and ("业绩" in var_name or "投标人" in var_name):
                    should_remove = True
                    break
            
            # 检查第五步变量（商务评分）
            if not should_remove:
                for prefix in step5_prefixes_to_remove:
                    if var_name.startswith(prefix) and ("业绩" in var_name or "投标人" in var_name):
                        should_remove = True
                        break
            
            if not should_remove:
                cleaned_variables.append(var)
        else:
            cleaned_variables.append(var)
    
    logger.info(f"清理了第四步失败候选人 {failed_candidates_step4} 和第五步失败候选人 {failed_candidates_step5} 的业绩变量，保留 {len(cleaned_variables)} 个变量")
    return cleaned_variables


def _validate_performance_counts(extracted_counts: Dict[int, Dict[str, int]], expected_counts: Dict[int, int], threshold: int = 3) -> Dict[int, Dict[str, bool]]:
    """
    分别验证第四步和第五步的业绩数量是否在允许范围内
    
    现在只基于业绩表格变量进行验证，传统方法已废弃
    
    Args:
        extracted_counts: 提取到的业绩数量 {1: {"step4": 3, "step5": 2}, ...}
        expected_counts: 预期的业绩数量 {1: 5, 2: 3, ...}
        threshold: 允许的差异阈值
        
    Returns:
        Dict[int, Dict[str, bool]]: 候选人排名到验证结果的映射 
        {1: {"step4": True, "step5": False}, 2: {"step4": True, "step5": True}, ...}
    """
    validation_results = {}
    
    for rank in extracted_counts.keys():
        step4_extracted = extracted_counts.get(rank, {}).get("step4", 0)
        step5_extracted = extracted_counts.get(rank, {}).get("step5", 0)
        expected = expected_counts.get(rank, 0)
        
        # 验证第四步：检查提取的业绩数量是否符合预期
        # 如果预期数量为0（没有业绩表格变量），则跳过验证
        if expected == 0:
            step4_valid = True  # 没有业绩表格变量时，跳过验证
            logger.info(f"第{rank}名第四步业绩数量验证跳过: 没有业绩表格变量，预期{expected}个")
        else:
            step4_difference = abs(step4_extracted - expected)
            step4_valid = step4_difference <= threshold
            if step4_valid:
                logger.info(f"第{rank}名第四步业绩数量验证通过: 提取{step4_extracted}个，预期{expected}个，差异{step4_difference}个")
            else:
                logger.warning(f"第{rank}名第四步业绩数量验证失败: 提取{step4_extracted}个，预期{expected}个，差异{step4_difference}个（超过阈值{threshold}）")
        
        # 验证第五步：现在第五步是通过重新分类第四步的业绩变量
        # 所以第五步的业绩数量应该等于第四步的业绩数量
        step5_valid = step5_extracted == step4_extracted
        
        validation_results[rank] = {
            "step4": step4_valid,
            "step5": step5_valid
        }
        
        # 记录验证结果
        if step5_valid:
            logger.info(f"第{rank}名第五步业绩数量验证通过: 重新分类{step5_extracted}个（与第四步一致）")
        else:
            logger.warning(f"第{rank}名第五步业绩数量验证失败: 重新分类{step5_extracted}个，第四步{step4_extracted}个（数量不一致）")
    
    return validation_results
