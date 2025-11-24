## 2025.11.07
## 新增需求:用户指定评审点的页码范围，重新生成评标报告

## 接受参数：project_id, bid_url 
## 数据库检索出对应的评审项及其页码范围以及历史评标报告内容
## 使用新的页码范围，重新生成评标报告
## 新的评标报告内容与历史评估报告内容进行对比合并(新的替换掉旧项,无新的就保留旧项)
## 将新的评标报告内容保存到数据库
## 只更新新的部分内容 

import asyncio
import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from database.file_info_service import get_file_info_and_range_by_project_id
from database.data_process import (
    get_variables_values_by_id, 
    save_task_results_to_database, 
    save_final_report_to_database,
    get_template_type_by_id,
    update_parse_task_progress,
    update_parse_task_status,
    set_parse_task_progress_direct
)
from src.business.service.parse_task_service import ParseTaskService
from src.business.service.report_generation_service import ReportGenerationService
from src.utils.pre_variables import enrich_variables_with_scores
from database.database import db_manager
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==================== 步骤1：获取新的页码范围 ====================
def get_new_page_range(project_id: int, bid_url: str) -> List[tuple]:
    """
    根据项目ID和投标文件URL，获取该投标文件的评审点参考页码范围,并对页码范围进行动态合并
    
    Args:
        project_id: 项目ID
        bid_url: 投标文件URL
        
        
    Returns:
        List[tuple]: 合并后的页码范围列表，如 [(20, 50), (60, 90)]
    """
    # 拿到的是该项目下所有投标文件的评审点的页码范围列表
    file_info_and_range = get_file_info_and_range_by_project_id(project_id)
    # 根据bid_url，筛选出同一投标文件的评审点的页码范围列表
    file_info_and_range = [item for item in file_info_and_range if item["bid_url"] == bid_url]
    
    # 提取有效的页码范围
    page_ranges = []
    eval_items = []  # 记录对应的评审项，用于后续识别变量
    for item in file_info_and_range:
        if item.get("start") is not None and item.get("end") is not None:
            page_ranges.append((item["start"], item["end"]))
            eval_items.append({
                "eval_item": item["eval_item"],
                "start": item["start"],
                "end": item["end"],
                "file_info_id": item["file_info_id"]
            })
    
    if not page_ranges:
        logger.warning(f"未找到bid_url={bid_url}的有效页码范围")
        return [], []
    
    # 创建ParseTaskService实例并合并页码范围
    parse_service = ParseTaskService()
    merged_ranges = parse_service.merge_page_ranges(page_ranges)
    logger.info(f"合并后的页码范围: {merged_ranges}")
    logger.info(f"对应的评审项: {eval_items}")
    
    return merged_ranges, eval_items


# ==================== 步骤2：获取历史变量和报告内容 ====================
def get_historical_variables_and_report(project_id: int) -> tuple:
    """
    从数据库获取历史评标报告的变量和内容
    
    Args:
        project_id: 项目ID
        
    Returns:
        tuple: (历史变量字典, 历史报告内容, template_id)
    """
    try:
        project_id_int = int(project_id) if isinstance(project_id, str) else project_id
        
        with db_manager.get_db_session() as session:
            # 获取历史变量（从reference_sources字段）
            historical_variables_dict = get_variables_values_by_id(str(project_id))
            
            # 获取历史报告内容和template_id
            query = text("""
                SELECT content, template_id, reference_sources 
                FROM eval_report 
                WHERE id = :project_id
            """)
            result = session.execute(query, {"project_id": project_id_int}).fetchone()
            
            if not result:
                logger.warning(f"未找到项目 {project_id} 的历史报告")
                return {}, "", None
            
            historical_report_content = result[0] or ""
            template_id = str(result[1]) if result[1] else None
            reference_sources = result[2]  # 原始变量列表（用于识别变量来源）
            
            # 解析reference_sources为列表格式（用于后续识别变量来源）
            historical_variables_list = []
            if reference_sources:
                import json
                try:
                    historical_variables_list = json.loads(reference_sources)
                    if not isinstance(historical_variables_list, list):
                        historical_variables_list = []
                except json.JSONDecodeError:
                    historical_variables_list = []
            
            logger.info(f"获取到历史变量数量: {len(historical_variables_dict)}")
            logger.info(f"历史报告内容长度: {len(historical_report_content)} 字符")
            logger.info(f"模板ID: {template_id}")
            
            return historical_variables_dict, historical_report_content, template_id, historical_variables_list
            
    except Exception as e:
        logger.error(f"获取历史变量和报告失败: {e}")
        return {}, "", None, []


# ==================== 步骤3：获取排名并删除以第几名开头的变量 ====================
def get_ranking_and_delete_rank_variables(
    project_id: int,
    bid_url: str,
    historical_variables_list: List[Dict[str, Any]]
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    从数据库中获取【第几中标候选人】变量，根据投标人名称匹配排名，
    然后删除所有以该排名开头的变量并更新数据库
    
    Args:
        project_id: 项目ID
        bid_url: 投标文件URL
        historical_variables_list: 历史变量列表
        
    Returns:
        tuple: (排名名称, 删除后的变量列表)
    """
    from src.business.service.parse_task_service import ParseTaskService
    from database.data_process import save_task_results_to_database
    from database.file_info_service import get_file_info_and_range_by_project_id
    
    parse_service = ParseTaskService()
    
    # 1. 获取投标人名称
    bidder_name = ""
    file_info_list = get_file_info_and_range_by_project_id(project_id)
    for item in file_info_list:
        if item["bid_url"] == bid_url:
            bidder_name = item.get("bidder_name", "")
            break
    
    if not bidder_name:
        logger.warning(f"未找到投标文件 {bid_url} 的投标人名称，跳过删除排名变量步骤")
        return "第一名", historical_variables_list
    
    # 2. 从历史变量中获取候选人名称
    candidate_names = parse_service._get_candidate_names_from_variables(historical_variables_list)
    
    if not candidate_names:
        logger.warning("未找到候选人名称变量，跳过删除排名变量步骤")
        return "第一名", historical_variables_list
    
    # 3. 根据投标人名称匹配排名
    ranking = parse_service._get_ranking_by_bidder_name(bidder_name, candidate_names)
    logger.info(f"投标人 {bidder_name} 匹配到的排名: {ranking}")
    
    # 4. 筛选出以该排名开头的变量名
    rank_prefix = ranking  # 例如："第二名"
    variables_to_delete = []
    filtered_variables = []
    
    for var in historical_variables_list:
        if not isinstance(var, dict):
            filtered_variables.append(var)
            continue
        
        var_name = var.get("variable_name", "")
        
        # 检查变量名是否以该排名开头
        if var_name.startswith(rank_prefix):
            variables_to_delete.append(var_name)
            logger.debug(f"标记删除变量: {var_name} (排名: {ranking})")
        else:
            # 保留不以该排名开头的变量
            filtered_variables.append(var)
    
    logger.info(f"找到 {len(variables_to_delete)} 个以'{rank_prefix}'开头的变量，将被删除")
    if variables_to_delete:
        logger.info(f"删除的变量示例（前10个）: {variables_to_delete[:10]}")
    
    # 5. 更新数据库（保存删除后的变量列表）
    # 需要获取template_id
    template_id = None
    with db_manager.get_db_session() as session:
        query = text("SELECT template_id FROM eval_report WHERE id = :project_id")
        result = session.execute(query, {"project_id": project_id}).fetchone()
        if result and result[0]:
            template_id = str(result[0])
    
    if template_id:
        save_success = save_task_results_to_database(str(project_id), filtered_variables, template_id)
        if save_success:
            logger.info(f"已更新数据库，删除了 {len(variables_to_delete)} 个以'{rank_prefix}'开头的变量")
        else:
            logger.error("更新数据库失败，但继续处理流程")
    else:
        logger.warning("未找到template_id，跳过数据库更新")
    
    return ranking, filtered_variables


# ==================== 步骤4：识别属于该投标文件的变量 ====================
def identify_bid_file_variables(
    historical_variables_list: List[Dict[str, Any]], 
    bid_url: str,
    eval_items: List[Dict[str, Any]]
) -> List[str]:
    """
    识别历史变量中属于该投标文件的变量名称列表
    
    识别规则：
    1. 通过 reference_source 中的 source_url 匹配 bid_url
    2. 通过 reference_source 中的 evidence_text 或变量名匹配 eval_item
    
    注意：排除关键变量（这些变量应该来自招标文件，不应该被识别为属于投标文件）：
    - 推荐中标候选人数
    - 资格评审标准
    - 商务评分标准
    - 投标人要求
    - 以及其他全局变量
    
    Args:
        historical_variables_list: 历史变量列表
        bid_url: 投标文件URL
        eval_items: 评审项列表
        
    Returns:
        List[str]: 属于该投标文件的变量名称列表
    """
    # 定义需要排除的关键变量（这些变量应该来自招标文件，不应该被识别为属于投标文件）
    EXCLUDED_VARIABLES = {
        "推荐中标候选人数",
        "资格评审标准",
        "商务评分标准",
        "投标人要求",
        "评审结果",
        "分值部分",
        "推荐中标候选人数规则",
        "资格评审标准表格",
        "商务部分评分表",
        "商务评分标准表格"
    }
    
    bid_file_variable_names = set()
    eval_item_names = {item["eval_item"] for item in eval_items}
    
    for var in historical_variables_list:
        if not isinstance(var, dict):
            continue
            
        var_name = var.get("variable_name", "")
        
        # 排除关键变量（这些变量应该来自招标文件）
        if var_name in EXCLUDED_VARIABLES:
            logger.debug(f"排除关键变量（应来自招标文件）: {var_name}")
            continue
        
        reference_source = var.get("reference_source", {})
        
        if not isinstance(reference_source, dict):
            continue
        
        # 规则1：通过source_url匹配
        source_url = reference_source.get("source_url", "")
        if source_url == bid_url:
            bid_file_variable_names.add(var_name)
            logger.debug(f"通过source_url匹配到变量: {var_name}")
            continue
        
        # 规则2：通过eval_item匹配（变量名或evidence_text中包含评审项名称）
        # 注意：使用精确匹配或包含匹配，避免误匹配
        for eval_item in eval_item_names:
            # 检查变量名或evidence_text中是否包含评审项名称
            evidence_text = str(reference_source.get("evidence_text", ""))
            if eval_item in var_name or eval_item in evidence_text:
                bid_file_variable_names.add(var_name)
                logger.debug(f"通过eval_item匹配到变量: {var_name} (评审项: {eval_item})")
                break
    
    logger.info(f"识别到属于该投标文件的变量数量: {len(bid_file_variable_names)}")
    logger.info(f"变量名称列表（前10个）: {list(bid_file_variable_names)[:10]}")
    
    return list(bid_file_variable_names)


# ==================== 步骤5：使用新页码范围重新生成变量 ====================
async def regenerate_variables_for_bid_file(
    project_id: int,
    bid_url: str,
    merged_ranges: List[tuple],
    eval_items: List[Dict[str, Any]],
    template_id: str,
    previous_variables: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    使用新的页码范围重新生成该投标文件的变量
    
    复用 ParseTaskService 的逻辑，但只处理单个投标文件
    
    Args:
        project_id: 项目ID
        bid_url: 投标文件URL
        merged_ranges: 合并后的页码范围
        eval_items: 评审项列表
        template_id: 模板ID
        previous_variables: 前一个接口提取的变量（用于预处理）
        
    Returns:
        List[Dict[str, Any]]: 新生成的变量列表
    """
    parse_service = ParseTaskService()
    
    # 构造文件数据结构（模拟 process_parse_task 中的 file_groups）
    file_data = {
        "bidder_name": "",  # 需要从数据库获取
        "items": eval_items,
        "merged_ranges": merged_ranges
    }
    
    # 获取投标人名称
    file_info_list = get_file_info_and_range_by_project_id(project_id)
    for item in file_info_list:
        if item["bid_url"] == bid_url:
            file_data["bidder_name"] = item.get("bidder_name", "")
            break
    
    # 提取PDF内容（复用 ParseTaskService 的方法）
    full_content = await parse_service.extract_pdf_content_by_ranges(bid_url, merged_ranges)
    
    if not full_content:
        logger.warning(f"文件 {bid_url} 内容提取失败")
        return []
    
    # 单个文件重试时不需要预处理变量，因为首次处理时已经预处理好了
    # 直接使用历史变量（已包含预处理后的变量，如推荐中标候选人数、候选人名称、拆分后的投标人要求等）
    logger.info("单个文件重试：跳过预处理变量步骤，直接使用历史变量（首次处理时已预处理完成）")
    preprocessed_variables = previous_variables
    
    # 为每个评审项提取变量（并发执行）
    all_extracted_variables = []
    candidate_count = parse_service._get_candidate_count_from_variables(preprocessed_variables)
    candidate_names = parse_service._get_candidate_names_from_variables(preprocessed_variables)

    async def process_single_eval_item(item: Dict[str, Any]) -> List[Dict[str, Any]]:
        eval_item = item["eval_item"]
        start = item["start"]
        end = item["end"]

        try:
            logger.info(f"处理评审项: {eval_item}, 页码范围: {start}-{end}")

            item_content = parse_service.extract_content_by_range(full_content, start, end)
            if not item_content.strip():
                logger.warning(f"评审项 {eval_item} 的内容为空，跳过")
                return []

            clause_type = parse_service._determine_clause_type(eval_item)

            extracted_vars = await parse_service._extract_variables_by_clause_type(
                item_content=item_content,
                eval_item=eval_item,
                clause_type=clause_type,
                bid_url=bid_url,
                candidate_count=candidate_count,
                candidate_names=candidate_names,
                previous_variables=preprocessed_variables,
                file_data=file_data,
                page_range=(start, end)
            )

            if extracted_vars:
                for var in extracted_vars:
                    if isinstance(var, dict):
                        var["eval_item"] = eval_item
                        var["bid_url"] = bid_url
                        var["bidder_name"] = file_data["bidder_name"]
                logger.info(f"评审项 {eval_item} 提取完成: 共 {len(extracted_vars)} 个变量")
                return extracted_vars

            logger.warning(f"评审项 {eval_item} 未提取到变量")
            return []
        except Exception as e:
            logger.error(f"评审项 {eval_item} 提取失败: {e}", exc_info=True)
            return []

    item_tasks = [process_single_eval_item(item) for item in eval_items]
    if item_tasks:
        logger.info(f"开始并发处理 {len(item_tasks)} 个评审项")
        item_results = await asyncio.gather(*item_tasks, return_exceptions=True)

        for result in item_results:
            if isinstance(result, Exception):
                logger.error(f"评审项提取协程异常: {result}", exc_info=True)
                continue
            if result:
                all_extracted_variables.extend(result)
    else:
        logger.warning("没有可处理的评审项")

    return all_extracted_variables


# ==================== 步骤6：合并变量（新的替换旧的，无新的保留旧的）====================
def merge_variables(
    historical_variables_list: List[Dict[str, Any]],
    new_variables: List[Dict[str, Any]],
    bid_file_variable_names: List[str]
) -> List[Dict[str, Any]]:
    """
    合并变量：新的替换旧的，无新的保留旧的
    
    规则：
    1. 如果变量名在 bid_file_variable_names 中，且新变量中有，则用新的替换
    2. 如果变量名在 bid_file_variable_names 中，但新变量中没有，则删除（可选，或保留旧值）
    3. 如果变量名不在 bid_file_variable_names 中，则保留旧值
    4. **重要**：关键变量（资格评审标准、商务评分标准等）必须保留，即使被识别为属于投标文件
    
    Args:
        historical_variables_list: 历史变量列表
        new_variables: 新生成的变量列表
        bid_file_variable_names: 属于该投标文件的变量名称列表
        
    Returns:
        List[Dict[str, Any]]: 合并后的变量列表
    """
    # 定义关键变量（这些变量必须保留，即使被识别为属于投标文件）
    # 这些变量应该来自招标文件，不应该在重新生成单个投标文件时被替换
    CRITICAL_VARIABLES = {
        "推荐中标候选人数",
        "资格评审标准",
        "商务评分标准",
        "投标人要求",
        "评审结果",
        "分值部分",
        "推荐中标候选人数规则",
        "资格评审标准表格",
        "商务部分评分表",
        "商务评分标准表格"
    }
    
    # 将新变量转换为字典（变量名 -> 变量）
    # 注意：如果新变量中有重复的变量名，只保留最后一个
    new_variables_dict = {}
    duplicate_names = []
    for var in new_variables:
        if isinstance(var, dict) and "variable_name" in var:
            var_name = var["variable_name"]
            if var_name in new_variables_dict:
                duplicate_names.append(var_name)
            new_variables_dict[var_name] = var
    
    if duplicate_names:
        logger.warning(f"新变量中发现重复的变量名: {set(duplicate_names)}，将只保留最后一个")
    
    # 构建历史变量的变量名集合（用于快速查找）
    historical_var_names = set()
    for var in historical_variables_list:
        if isinstance(var, dict) and "variable_name" in var:
            historical_var_names.add(var.get("variable_name", ""))
    
    # 定义第四步和第五步生成的变量模式（这些变量应该保留，即使不属于当前投标文件）
    # 第四步变量：如"第一名资质"、"第一名业绩1"等（以"第X名"开头，包含资质、业绩等）
    # 第五步变量：如"分数第一名投标人业绩"、"分数第一名三体系认证"等（以"分数第X名"开头）
    STEP4_5_VARIABLE_PATTERNS = [
        "资质",  # 第四步：资质相关变量
        "业绩",  # 第四步和第五步：业绩相关变量
        "分数第",  # 第五步：分数相关变量
    ]
    
    def is_step4_5_variable(var_name: str) -> bool:
        """判断变量是否是第四步或第五步生成的变量"""
        # 检查是否以"第X名"开头（第四步和第五步的变量）
        chinese_ranks = ["第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十"]
        for rank in chinese_ranks:
            if var_name.startswith(f"{rank}名"):
                # 检查是否包含第四步或第五步的特征
                for pattern in STEP4_5_VARIABLE_PATTERNS:
                    if pattern in var_name:
                        return True
        # 检查是否以"分数第"开头（第五步的分数变量）
        if var_name.startswith("分数第"):
            return True
        return False
    
    # 构建合并后的变量列表
    merged_variables = []
    replaced_count = 0
    kept_count = 0
    removed_count = 0  # 被删除的变量数量（属于该投标文件但新变量中没有的）
    added_count = 0    # 新增的变量数量
    critical_kept_count = 0  # 保留的关键变量数量
    step4_5_kept_count = 0  # 保留的第四步和第五步变量数量
    
    # 遍历历史变量
    for var in historical_variables_list:
        if not isinstance(var, dict):
            merged_variables.append(var)
            continue
        
        var_name = var.get("variable_name", "")
        
        # **重要**：关键变量必须保留，即使被识别为属于投标文件
        # 这些变量应该来自招标文件，不应该在重新生成单个投标文件时被替换
        if var_name in CRITICAL_VARIABLES:
            # 关键变量始终保留历史值，不替换
            merged_variables.append(var)
            critical_kept_count += 1
            logger.debug(f"保留关键变量（不替换）: {var_name}")
            continue
        
        # **重要**：第四步和第五步生成的变量必须保留
        # 这些变量（如"第一名资质"、"分数第一名投标人业绩"等）对动态表格生成非常重要
        # 即使被识别为属于当前投标文件，也应该保留，因为重新生成时只处理单个文件
        if is_step4_5_variable(var_name):
            # 第四步和第五步变量始终保留历史值，不替换
            # 因为重新生成时只处理单个文件，无法重新生成所有候选人的变量
            merged_variables.append(var)
            step4_5_kept_count += 1
            logger.debug(f"保留第四步/第五步变量（不替换）: {var_name}")
            continue
        
        # 如果变量属于该投标文件
        if var_name in bid_file_variable_names:
            # 如果新变量中有，则替换
            if var_name in new_variables_dict:
                merged_variables.append(new_variables_dict[var_name])
                replaced_count += 1
                logger.debug(f"替换变量: {var_name}")
            else:
                # 新变量中没有，可以选择删除或保留旧值
                # 这里选择保留旧值（如果需要删除，可以注释掉下面这行，并取消注释删除逻辑）
                merged_variables.append(var)
                removed_count += 1
                logger.debug(f"保留旧变量（新变量中未找到）: {var_name}")
                # 如果需要删除，使用下面的代码：
                # logger.debug(f"删除变量（新变量中未找到）: {var_name}")
        else:
            # 不属于该投标文件的变量，保留旧值
            merged_variables.append(var)
            kept_count += 1
    
    # 添加新变量中独有的变量（不在历史变量中的）
    # 构建已合并变量的变量名集合（用于快速查找）
    merged_var_names = {var.get("variable_name", "") for var in merged_variables if isinstance(var, dict) and "variable_name" in var}
    
    for var_name, var in new_variables_dict.items():
        # 如果这个变量还没有在合并后的列表中，则添加
        # 说明这是一个全新的变量（不在历史变量中）
        if var_name not in merged_var_names:
            merged_variables.append(var)
            added_count += 1
            logger.debug(f"添加新变量: {var_name}")
        else:
            # 如果变量已经在merged_var_names中，说明已经被处理过了，跳过
            # 可能的情况：
            # 1. 已经被替换（在bid_file_variable_names中，且新变量中有）→ 正常
            # 2. 是历史变量中不属于该投标文件的变量（不在bid_file_variable_names中）→ 正常
            # 3. 是历史变量中属于该投标文件但新变量中没有的变量（在bid_file_variable_names中，但新变量中没有）→ 正常
            # 4. 是关键变量（在CRITICAL_VARIABLES中）→ 正常，已保留历史值
            # 这些都是正常情况，不需要警告
            pass
    
    logger.info(f"变量合并完成: 替换 {replaced_count} 个, 保留 {kept_count} 个, 新增 {added_count} 个, 保留旧值（新变量中未找到）{removed_count} 个, 保留关键变量 {critical_kept_count} 个, 保留第四步/第五步变量 {step4_5_kept_count} 个")
    
    # 验证关键变量是否存在
    merged_var_names_set = {var.get("variable_name", "") for var in merged_variables if isinstance(var, dict) and "variable_name" in var}
    missing_critical = [v for v in CRITICAL_VARIABLES if v not in merged_var_names_set]
    if missing_critical:
        logger.warning(f"合并后的变量中缺少关键变量: {missing_critical}")
    else:
        logger.info(f"所有关键变量都已保留: {CRITICAL_VARIABLES}")
    
    return merged_variables


# ==================== 步骤7：重新生成报告 ====================
async def regenerate_report(
    project_id: int,
    template_id: str,
    merged_variables: List[Dict[str, Any]]
) -> str:
    """
    使用合并后的变量重新生成报告
    
    Args:
        project_id: 项目ID
        template_id: 模板ID
        merged_variables: 合并后的变量列表
        
    Returns:
        str: 新生成的报告内容
    """
    save_success = save_task_results_to_database(project_id, merged_variables, template_id)
    if not save_success:
        raise Exception("保存合并后的变量到数据库失败")
    logger.info(f"合并后的变量已保存到数据库，共 {len(merged_variables)} 个变量")
    
    
    # 使用 ReportGenerationService 生成报告
    report_service = ReportGenerationService()
    
    # 将变量列表转换为字典格式（用于模板渲染）
    variables_dict = {}
    for var in merged_variables:
        if isinstance(var, dict) and "variable_name" in var:
            var_name = var.get("variable_name", "")
            var_value = var.get("variable_value", "")
            # 处理null值
            if var_value is None or var_value == "null":
                var_value = ""
            variables_dict[var_name] = var_value
    
    logger.info(f"变量字典数量: {len(variables_dict)}")
    
    # 检查关键变量是否存在
    key_variables = ["推荐中标候选人数", "资格评审标准", "商务评分标准"]
    missing_key_vars = []
    for key_var in key_variables:
        if key_var not in variables_dict or not variables_dict[key_var]:
            logger.warning(f"关键变量 '{key_var}' 缺失或为空，可能导致动态表格生成失败")
            missing_key_vars.append(key_var)
        else:
            logger.info(f"关键变量 '{key_var}' 存在，值长度: {len(str(variables_dict[key_var]))}")
            # 打印关键变量的值预览（前100字符）
            value_preview = str(variables_dict[key_var])[:100]
            logger.info(f"   值预览: {value_preview}...")
    
    if missing_key_vars:
        logger.error(f"缺少关键变量: {missing_key_vars}，动态表格生成可能会失败")
        # 尝试从历史变量中查找这些变量
        for key_var in missing_key_vars:
            for var in merged_variables:
                if isinstance(var, dict) and var.get("variable_name") == key_var:
                    var_value = var.get("variable_value", "")
                    if var_value:
                        logger.warning(f"在merged_variables中找到 '{key_var}'，但未添加到variables_dict，值长度: {len(str(var_value))}")
                        # 手动添加到variables_dict
                        variables_dict[key_var] = var_value
                        logger.info(f"已手动添加关键变量 '{key_var}' 到variables_dict")
                    break
    
    # 检查候选人相关变量（用于诊断）
    candidate_vars = []
    for var_name in variables_dict.keys():
        if any(rank in var_name for rank in ["第一名", "第二名", "第三名", "第四名", "第五名", "第六名"]):
            candidate_vars.append(var_name)
    
    logger.info(f"候选人相关变量数量: {len(candidate_vars)}")
    if candidate_vars:
        logger.info(f"   变量示例（前10个）: {candidate_vars[:10]}")
    else:
        logger.warning("未找到候选人相关变量，动态表格可能为空")
    
    # 获取模板
    from common.rich_text_templates import RichTextTemplateManager
    template_manager = RichTextTemplateManager()
    template = template_manager.get_template(template_id)
    
    if not template:
        raise Exception(f"未找到模板ID为 {template_id} 的模板")
    
    # 生成动态表格（如果需要）
    # 使用完整的变量对象（包含 reference_source），而不是简化的字典
    # 这样动态表格生成函数可以正确识别变量来源
    results_list = []
    for var in merged_variables:
        if isinstance(var, dict) and "variable_name" in var:
            # 保留完整的变量对象，包括 reference_source
            results_list.append(var)
    
    logger.info(f"准备生成动态表格，变量列表数量: {len(results_list)}")
    
    # 检查results_list中是否包含关键变量
    results_var_names = {var.get("variable_name", "") for var in results_list if isinstance(var, dict)}
    for key_var in key_variables:
        if key_var in results_var_names:
            logger.info(f"results_list中包含关键变量: {key_var}")
        else:
            logger.warning(f"results_list中缺少关键变量: {key_var}")
    
    # 生成动态表格
    logger.info("开始生成动态表格...")
    report_service._generate_dynamic_tables(results_list, variables_dict)
    
    # 检查动态表格是否生成成功
    qualification_table = variables_dict.get("中标候选人资质资格业绩等评审情况表格", "")
    detailed_score_table = variables_dict.get("中标候选人详细评审客观分得分情况表格", "")
    
    if qualification_table:
        logger.info(f"资质评审表格生成成功，长度: {len(qualification_table)} 字符")
    else:
        logger.warning("资质评审表格为空，可能原因：")
        logger.warning("   1. 资格评审标准变量缺失或为空")
        logger.warning("   2. 没有找到符合条件的候选人变量")
        logger.warning("   3. 动态表格生成函数出错")
    
    if detailed_score_table:
        logger.info(f"详细评审表格生成成功，长度: {len(detailed_score_table)} 字符")
    else:
        logger.warning("详细评审表格为空，可能原因：")
        logger.warning("   1. 商务评分标准变量缺失或为空")
        logger.warning("   2. 没有找到符合条件的候选人变量（如'分数第一名'开头的变量）")
        logger.warning("   3. 动态表格生成函数出错")
    
    # 渲染模板
    final_report = await template_manager.render_template(template, variables_dict)
    
    # 清理多余的换行符
    final_report = report_service._clean_newlines(final_report)
    
    return final_report


# ==================== 主函数：单个投标文件报告重新生成 ====================
async def single_file_report_re_generate(project_id: int, bid_url: str) -> Dict[str, Any]:
    """
    单个投标文件的评标报告重新生成主函数
    
    完整流程：
    1. 合并页码范围
    2. 解析对应页码范围的内容（在regenerate_variables_for_bid_file中完成）
    3. 从数据库中获取【第几中标候选人】变量，根据投标人名称匹配排名，删除以该排名开头的变量并更新数据库
    4. 文件解析完成之后根据评审项的页码范围截取对应的页码范围的解析内容（在regenerate_variables_for_bid_file中完成）
    5. 提取对应的评审项的变量，按照不同类型的评审项来重新提取变量（在regenerate_variables_for_bid_file中完成）
    6. 对商务部分的变量进行打分（在regenerate_variables_for_bid_file中完成）
    7. 保存变量到数据库（在regenerate_report中完成）
    8. 从数据库中获取变量，然后渲染模板（在regenerate_report中完成）
    
    Args:
        project_id: 项目ID
        bid_url: 投标文件URL
        
    Returns:
        Dict[str, Any]: 处理结果
    """
    try:
        # 第一步：立即将数据库中进度更新为0，状态更新为1（处理中）（必须在所有操作之前）
        # 只保留初始化：重置进度为0，状态更新为1
        # 这样无论是通过API调用还是直接调用，都能确保进度和状态被正确初始化
        try:
            await update_parse_task_progress(str(project_id), "initialized", "初始化单个投标文件报告重新生成任务", None)
            await update_parse_task_status(str(project_id), 1, "单个投标文件报告重新生成任务已提交", None)
            logger.info(f"进度已初始化为0%，状态已更新为1（处理中），项目ID: {project_id}")
        except Exception as e:
            logger.error(f"初始化单个投标文件报告重新生成任务进度和状态失败: {e}")
            # 即使失败也继续，因为后续步骤会继续更新进度
        
        logger.info(f"开始重新生成投标文件报告: project_id={project_id}, bid_url={bid_url}")
        
        # 步骤1：获取新的页码范围
        logger.info("步骤1：获取新的页码范围")
        await set_parse_task_progress_direct(str(project_id), 5, "正在获取新的页码范围", None)
        merged_ranges, eval_items = get_new_page_range(project_id, bid_url)
        if not merged_ranges:
            raise Exception(f"未找到有效的页码范围，bid_url={bid_url}")
        
        # 步骤2：获取历史变量和报告内容
        logger.info("步骤2：获取历史变量和报告内容")
        await set_parse_task_progress_direct(str(project_id), 15, "正在获取历史变量和报告内容", None)
        historical_variables_dict, historical_report_content, template_id, historical_variables_list = \
            get_historical_variables_and_report(project_id)
        
        if not template_id:
            raise Exception(f"未找到项目 {project_id} 的模板ID")
        
        # 步骤3：获取排名并删除以第几名开头的变量
        logger.info("步骤3：获取排名并删除以第几名开头的变量")
        await set_parse_task_progress_direct(str(project_id), 20, "正在获取排名并删除以第几名开头的变量", None)
        ranking, historical_variables_list = get_ranking_and_delete_rank_variables(
            project_id=project_id,
            bid_url=bid_url,
            historical_variables_list=historical_variables_list
        )
        logger.info(f"步骤3完成：匹配到排名 {ranking}，已删除以该排名开头的变量并更新数据库")
        
        # 步骤4：识别属于该投标文件的变量
        logger.info("步骤4：识别属于该投标文件的变量")
        await set_parse_task_progress_direct(str(project_id), 30, "正在识别属于该投标文件的变量", template_id)
        bid_file_variable_names = identify_bid_file_variables(
            historical_variables_list,
            bid_url,
            eval_items
        )
        
        # 步骤5：使用新页码范围重新生成变量（包含步骤2、4、5、6：解析内容、截取评审项内容、提取变量、商务打分）
        logger.info("步骤5：使用新页码范围重新生成变量")
        await set_parse_task_progress_direct(str(project_id), 70, "正在使用新页码范围重新生成变量", template_id)
        # 需要先获取 previous_variables（前一个接口提取的变量，已删除排名变量）
        previous_variables = historical_variables_list  # 使用删除排名变量后的历史变量作为基础
        
        new_variables = await regenerate_variables_for_bid_file(
            project_id=project_id,
            bid_url=bid_url,
            merged_ranges=merged_ranges,
            eval_items=eval_items,
            template_id=template_id,
            previous_variables=previous_variables
        )
        # print(f"new variables:\n{new_variables}\n")
        
        logger.info(f"新生成的变量数量: {len(new_variables)}")
        
        # 步骤6：合并变量（新的替换旧的，无新的保留旧的）
        logger.info("步骤6：合并变量")
        await set_parse_task_progress_direct(str(project_id), 80, "正在合并变量", template_id)
        merged_variables = merge_variables(
            historical_variables_list,
            new_variables,
            bid_file_variable_names
        )

        # 更新 bid_file_variable_names：将新生成的变量也加入（新生成的变量都属于指定文件）
        new_variable_names = set()
        for var in new_variables:
            if isinstance(var, dict) and "variable_name" in var:
                var_name = var.get("variable_name", "")
                # 排除关键变量（这些变量不应该被识别为属于投标文件）
                CRITICAL_VARIABLES = {
                    "推荐中标候选人数",
                    "资格评审标准",
                    "商务评分标准",
                    "投标人要求",
                    "评审结果",
                    "分值部分",
                    "推荐中标候选人数规则",
                    "资格评审标准表格",
                    "商务部分评分表",
                    "商务评分标准表格",
                    "复核卡得分"
                }
                if var_name not in CRITICAL_VARIABLES:
                    new_variable_names.add(var_name)
        
        # 合并历史变量和新生成的变量
        bid_file_variable_names = list(set(bid_file_variable_names) | new_variable_names)
        logger.info(f"更新后的属于指定文件的变量数量: {len(bid_file_variable_names)} (历史变量: {len(bid_file_variable_names) - len(new_variable_names)}, 新生成变量: {len(new_variable_names)})")

        # 额外步骤：重新为商务条款变量打分（只处理指定文件提取到的变量，且只处理当前排名对应的变量）
        logger.info(f"步骤6.1：为商务条款变量重新打分（只处理指定文件提取到的变量，且只处理当前排名 {ranking} 对应的变量）")
        try:
            # 定义关键变量（这些变量需要保留，用于打分逻辑）
            CRITICAL_VARIABLES_FOR_SCORING = {
                "推荐中标候选人数",
                "资格评审标准",
                "商务评分标准",
                "投标人要求",
                "评审结果",
                "分值部分",
                "推荐中标候选人数规则",
                "资格评审标准表格",
                "商务部分评分表",
                "商务评分标准表格",
                "复核卡得分"
            }
            
            # 筛选出需要打分的变量：属于指定文件的变量 + 关键变量（用于打分逻辑）
            variables_to_score = []
            
            # 1. 添加关键变量（用于打分逻辑）
            for var in merged_variables:
                if isinstance(var, dict) and var.get("variable_name") in CRITICAL_VARIABLES_FOR_SCORING:
                    variables_to_score.append(var)
            
            # 2. 添加属于指定文件的变量（只处理这些变量，且只处理当前排名对应的变量）
            # 重要：只处理当前排名（ranking）对应的变量，排除其他排名的变量
            for var in merged_variables:
                if isinstance(var, dict):
                    var_name = var.get("variable_name", "")
                    # 只添加属于指定文件的变量，且不在关键变量中（关键变量已在上面添加）
                    if var_name in bid_file_variable_names and var_name not in CRITICAL_VARIABLES_FOR_SCORING:
                        # 检查变量名是否包含排名标识
                        chinese_ranks = ["第一名", "第二名", "第三名", "第四名", "第五名", "第六名", "第七名", "第八名", "第九名", "第十名"]
                        has_rank = False
                        var_rank = None
                        for rank in chinese_ranks:
                            if var_name.startswith(rank) or var_name.startswith(f"分数{rank}"):
                                has_rank = True
                                var_rank = rank
                                break
                        
                        # 如果变量包含排名标识，只处理当前排名对应的变量
                        # 如果变量不包含排名标识（如"商务部分评分表条款"），则处理
                        if has_rank:
                            if var_rank == ranking:
                                variables_to_score.append(var)
                            else:
                                logger.debug(f"跳过其他排名的变量: {var_name} (排名: {var_rank}, 当前排名: {ranking})")
                        else:
                            # 不包含排名标识的变量（如"商务部分评分表条款"），属于指定文件则处理
                            variables_to_score.append(var)
            
            # 统计信息
            bid_file_vars_in_list = [v for v in variables_to_score if v.get('variable_name') in bid_file_variable_names]
            critical_vars_in_list = [v for v in variables_to_score if v.get('variable_name') in CRITICAL_VARIABLES_FOR_SCORING]
            
            # 检查是否有以"第X名"开头的变量
            chinese_ranks = ["第一名", "第二名", "第三名", "第四名", "第五名", "第六名", "第七名", "第八名", "第九名", "第十名"]
            rank_vars = []
            for var in variables_to_score:
                var_name = var.get("variable_name", "")
                for rank in chinese_ranks:
                    if var_name.startswith(rank):
                        rank_vars.append(var_name)
                        break
            
            # 统计当前排名的变量
            current_rank_vars = [v for v in rank_vars if v.startswith(ranking)]
            other_rank_vars = [v for v in rank_vars if not v.startswith(ranking)]
            
            logger.info(f"筛选出需要打分的变量数量: {len(variables_to_score)}")
            logger.info(f"  - 其中属于指定文件的变量: {len(bid_file_vars_in_list)} 个")
            logger.info(f"  - 其中关键变量: {len(critical_vars_in_list)} 个")
            logger.info(f"  - 其中以'第X名'开头的变量: {len(rank_vars)} 个")
            logger.info(f"  - 其中当前排名 {ranking} 的变量: {len(current_rank_vars)} 个")
            if current_rank_vars:
                logger.info(f"  - 当前排名 {ranking} 的变量示例（前10个）: {current_rank_vars[:10]}")
            if other_rank_vars:
                logger.info(f"  - 已排除其他排名的变量数量: {len(other_rank_vars)} 个（这些变量不会被处理）")
            if bid_file_vars_in_list:
                logger.info(f"  - 属于指定文件的变量示例（前10个）: {[v.get('variable_name') for v in bid_file_vars_in_list[:10]]}")
            
            # 只对筛选出的变量进行打分
            scored_variables = await enrich_variables_with_scores(variables_to_score)
            
            # 将打分后的结果更新回 merged_variables
            # 构建打分后的变量映射（变量名 -> 变量）
            scored_variables_dict = {}
            for var in scored_variables:
                if isinstance(var, dict) and "variable_name" in var:
                    scored_variables_dict[var["variable_name"]] = var
            
            # 更新 merged_variables 中对应的变量
            for i, var in enumerate(merged_variables):
                if isinstance(var, dict):
                    var_name = var.get("variable_name", "")
                    # 如果该变量在打分后的结果中，则更新
                    if var_name in scored_variables_dict:
                        merged_variables[i] = scored_variables_dict[var_name]
            
            logger.info(f"商务条款打分完成，已更新 {len(scored_variables_dict)} 个变量的评分")
        except Exception as score_error:
            logger.error(f"商务条款打分失败: {score_error}", exc_info=True)
        
        
        # 步骤7：保存变量到数据库并重新生成报告（包含步骤7和8）
        logger.info("步骤7：保存变量到数据库并重新生成报告")
        await set_parse_task_progress_direct(str(project_id), 90, "正在保存变量并重新生成报告", template_id)
        final_report = await regenerate_report(
            project_id=project_id,
            template_id=template_id,
            merged_variables=merged_variables
        )
        
        # 步骤8：保存最终报告到数据库
        logger.info("步骤8：保存最终报告到数据库")
        await set_parse_task_progress_direct(str(project_id), 95, "正在保存最终报告到数据库", template_id)
        report_service = ReportGenerationService()
        save_success = await report_service.save_final_report(
            project_id=str(project_id),
            final_report=final_report,
            template_id=template_id
        )
        
        if not save_success:
            raise Exception("保存最终报告失败")
        
        # 更新进度和状态：任务完成
        await set_parse_task_progress_direct(str(project_id), 100, "单个投标文件报告重新生成完成", template_id)
        await update_parse_task_status(str(project_id), 2, "单个投标文件报告重新生成完成", template_id)
        
        # logger.info("步骤7：跳过保存最终报告到数据库（测试阶段）")
        
        # # 步骤8：保存到本地文件（作为备份）
        # logger.info("步骤8：保存合并后的变量和报告到本地文件（备份）")
        # variables_file = None
        # report_file = None
        # summary_file = None
        
        # try:
        #     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        #     project_id_str = str(project_id)
            
        #     # 创建保存目录
        #     save_dir = f"re_generate_backup_{project_id_str}"
        #     os.makedirs(save_dir, exist_ok=True)
            
        #     # 保存合并后的变量到JSON文件
        #     variables_file = os.path.join(save_dir, f"merged_variables_{timestamp}.json")
        #     with open(variables_file, 'w', encoding='utf-8') as f:
        #         json.dump(merged_variables, f, ensure_ascii=False, indent=2)
        #     logger.info(f"✅ 合并后的变量已保存到本地文件: {variables_file}")
            
        #     # 保存最终报告到HTML文件
        #     report_file = os.path.join(save_dir, f"final_report_{timestamp}.html")
        #     with open(report_file, 'w', encoding='utf-8') as f:
        #         f.write(final_report)
        #     logger.info(f"✅ 最终报告已保存到本地文件: {report_file}")
            
        #     # 保存处理结果摘要
        #     summary = {
        #         "project_id": project_id,
        #         "bid_url": bid_url,
        #         "timestamp": timestamp,
        #         "new_variables_count": len(new_variables),
        #         "merged_variables_count": len(merged_variables),
        #         "replaced_variables_count": len(bid_file_variable_names),
        #         "report_length": len(final_report),
        #         "variables_file": variables_file,
        #         "report_file": report_file
        #     }
        #     summary_file = os.path.join(save_dir, f"summary_{timestamp}.json")
        #     with open(summary_file, 'w', encoding='utf-8') as f:
        #         json.dump(summary, f, ensure_ascii=False, indent=2)
        #     logger.info(f"✅ 处理结果摘要已保存到: {summary_file}")
            
        # except Exception as e:
        #     logger.warning(f"保存到本地文件失败（不影响主流程）: {e}")
        
        logger.info("报告重新生成完成")
        # logger.info(f"✅ 合并后的变量数量: {len(merged_variables)}（暂未保存到数据库）")
        # logger.info(f"✅ 最终报告长度: {len(final_report)} 字符（暂未保存到数据库）")
        
        return {
            "project_id": project_id,
            "bid_url": bid_url,
            "status": "completed",
            "message": "报告重新生成完成",
            "new_variables_count": len(new_variables),
            "merged_variables_count": len(merged_variables),
            "replaced_variables_count": len(bid_file_variable_names),
            "report_length": len(final_report),
        }, final_report 
        
    except Exception as e:
        logger.error(f"重新生成报告失败: {e}", exc_info=True)
        # 更新进度和状态：任务失败
        try:
            await set_parse_task_progress_direct(str(project_id), -1, f"单个投标文件报告重新生成失败: {str(e)}", None)
            await update_parse_task_status(str(project_id), 3, f"单个投标文件报告重新生成失败: {str(e)}", None)
        except Exception as update_error:
            logger.error(f"更新失败状态时出错: {update_error}")
        
        return {
            "project_id": project_id,
            "bid_url": bid_url,
            "status": "error",
            "message": f"重新生成报告失败: {str(e)}"
        }, ""  # 返回空字符串作为报告内容


if __name__ == "__main__":
    # 项目id
    project_id = 1999999999999981134
    # 投标文件url
    bid_url =  'http://ysdwww.jcebid.com/file/dev/2025/10/4207f8fcd33142e3bf5cb3c655e79f26/APPS/17e3f590ec51b004a1a0edad42ead5ba/5c9189bce8604f29a50416d1a8b6d5ee/二--山西晋丰煤化工有限责任公司造气节能环保提升及.pdf'
    print(f"project_id: {project_id}")
    print(f"bid_url: {bid_url}")
    
    
    # 测试完整流程（需要异步执行，可能需要较长时间）
    print("\n" + "="*80)
    print("开始执行完整流程（可能需要较长时间，请耐心等待...）")
    print("="*80)
    try:
        result, report = asyncio.run(single_file_report_re_generate(project_id, bid_url))
        print(f"\n处理结果: {result}")
        if report:
            print(f"\n新的评标报告内容长度: {len(report)} 字符")
            print(f"报告预览（前500字符）: {report[:500]}...")
    except Exception as e:
        print(f"\n执行失败: {e}")
        import traceback
        traceback.print_exc()
