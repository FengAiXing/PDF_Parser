"""
初步评审表格生成器
用于生成评标报告中的初步评审表格（资质、资格业绩等评审情况表格）
"""

from typing import List, Dict, Any
import re
from src.utils.dynamic_table_generator import (
    _extract_clauses_from_variables,
    _parse_clauses,
    _get_clause_from_variable_name,
    _is_variable_from_qualification
)


def create_qualification_review_table(candidate_count: int, extracted_variables: List[Dict[str, Any]]) -> str:
    """
    根据推荐中标候选人数量和提取的变量生成并填充资质、资格业绩等评审情况表格
    
    注意：此表格只显示资格评审标准中的条款变量，不显示商务评分标准的变量
    
    参数：
        candidate_count: 推荐中标候选人数量
        extracted_variables: 从AI提取的变量列表，格式：
            [
                {"variable_name": "第一名资质", "variable_value": "...", "reference_source": {...}},
                {"variable_name": "第一名项目负责人", "variable_value": "...", "reference_source": {...}},
                {"variable_name": "第一名业绩要求1", "variable_value": "...", "reference_source": {...}},
                ...
            ]
    
    返回：
        完整的HTML表格字符串（如果候选人超过3个，会生成多个表格）
    """
    # 提取资格评审标准和商务评分标准的条款
    import logging
    logger = logging.getLogger(__name__)
    
    clauses = _extract_clauses_from_variables(extracted_variables)
    qualification_clauses = clauses.get("qualification", [])
    business_clauses = clauses.get("business", [])
    
    logger.info(f"资格评审标准条款数量: {len(qualification_clauses)}")
    logger.info(f"商务评分标准条款数量: {len(business_clauses)}")
    
    # 过滤变量：只保留属于资格评审标准的变量
    filtered_variables = []
    skipped_count = 0
    for var in extracted_variables:
        var_name = var.get("variable_name", "")
        # 跳过详细评审表格的变量（三体系、管理体系等）
        detailed_review_keywords = ["供应商", "三体系", "信用评价", "管理体系"]
        is_detailed_review_var = any(keyword in var_name for keyword in detailed_review_keywords)
        if is_detailed_review_var:
            continue
        
        # 跳过"分数第"开头的变量（这些是商务评分标准的分数变量）
        if var_name.startswith("分数第"):
            skipped_count += 1
            continue
        
        # 检查是否属于资格评审标准
        if _is_variable_from_qualification(var_name, qualification_clauses, candidate_count):
            filtered_variables.append(var)
            logger.debug(f"资格评审变量: {var_name}")
        # 如果没有设置资格评审标准，则显示所有非商务评分标准的变量（向后兼容）
        elif not qualification_clauses:
            # 检查是否明显属于商务评分标准（如"分数第X名"开头的变量）
            if not var_name.startswith("分数第"):
                filtered_variables.append(var)
                logger.debug(f"向后兼容变量: {var_name}")
    
    logger.info(f"资格评审表格: 过滤后变量数量 {len(filtered_variables)} (跳过 {skipped_count} 个商务评分变量)")
    # 辅助函数：获取排名名称
    def get_rank_name(rank: int) -> str:
        rank_names = {1: "第一名", 2: "第二名", 3: "第三名", 4: "第四名", 5: "第五名", 6: "第六名"}
        return rank_names.get(rank, f"第{rank}名")
    
    # 辅助函数：从过滤后的变量列表中获取指定变量的值
    def get_variable_value(var_name: str) -> str:
        for var in filtered_variables:
            if var.get("variable_name") == var_name:
                value = var.get("variable_value", "")
                # 将\n转换为<br>以便在HTML中显示
                if value:
                    return value.replace('\n', '<br>')
                return ""
        return ""
    
    
    # 内部函数：生成单个表格（最多3个候选人）
    def generate_single_table(start_rank: int, end_rank: int) -> str:
        """
        生成包含指定排名范围的单个表格
        
        参数：
            start_rank: 起始排名（从1开始）
            end_rank: 结束排名（包含）
        
        返回：
            单个表格的HTML字符串
        """
        table_candidate_count = end_rank - start_rank + 1
        
        # 1. 计算当前表格候选人的业绩数量（从过滤后的变量中）
        max_performance = 0
        for i in range(start_rank, end_rank + 1):
            rank_name = get_rank_name(i)
            for var in filtered_variables:
                var_name = var.get("variable_name", "")
                if var_name.startswith(rank_name) and "业绩" in var_name:
                    # 匹配模式：排名 + 条款名称 + 数字
                    match = re.search(rf'{re.escape(rank_name)}(.+?)(\d+)$', var_name)
                    if match:
                        perf_num = int(match.group(2))
                        if var.get("variable_value", "").strip():
                            max_performance = max(max_performance, perf_num)
        
        # 2. 从资格评审标准中获取条款列表（而不是从变量推断）
        # 将业绩条款放在最前面
        all_items = []
        performance_items = []
        other_items = []
        
        if qualification_clauses:
            for clause in qualification_clauses:
                if "业绩" in clause:
                    performance_items.append(clause)
                else:
                    other_items.append(clause)
            # 业绩条款放在最前面，其他条款放在后面
            all_items = performance_items + other_items
        
        logger.debug(f"资格评审标准条款列表（业绩优先）: {all_items}")
        
        # 3. 收集候选人名称（从第三次模型调用的结果中获取）
        candidate_names = []
        chinese_ordinals = ["第一", "第二", "第三", "第四", "第五", "第六"]
        
        for i in range(start_rank, end_rank + 1):
            rank_name = get_rank_name(i)
            
            # 尝试获取候选人公司名称
            if i <= len(chinese_ordinals):
                candidate_var_name = f"{chinese_ordinals[i-1]}中标候选人名称"
            else:
                candidate_var_name = f"第{i}中标候选人名称"
            
            # 从变量列表中查找候选人名称
            candidate_name = None
            for var in extracted_variables:
                if var.get("variable_name") == candidate_var_name:
                    candidate_name = var.get("variable_value", "").strip()
                    break
            
            # 如果找到候选人名称则使用，否则使用排名作为后备
            if candidate_name:
                candidate_names.append(candidate_name)
            else:
                candidate_names.append(rank_name)
        
        # 4. 生成HTML表格
        html = []
        html.append('<table style="width: 100%; table-layout: fixed; border-collapse: collapse; margin: 0;">')

        # 表头第一行：序号 + 初步评审内容 + 评审情况（合并列）
        html.append('<tr>')
        html.append(
            '<td rowspan="2" style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体; font-size: 14px;background-color: rgb(192,192,192);"><strong>序号</strong></span></td>')
        html.append(
            '<td rowspan="2" style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体; font-size: 14px;background-color: rgb(192,192,192);"><strong>初步评审内容</strong></span></td>')
        html.append(
            f'<td colspan="{table_candidate_count}" style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体; font-size: 14px;background-color: rgb(192,192,192);"><strong>评审情况</strong></span></td>')
        html.append('</tr>')
        
        # 表头第二行：各候选人名称
        html.append('<tr>')
        for i in range(start_rank, end_rank + 1):
            rank_name = get_rank_name(i)
            candidate_name = candidate_names[i-start_rank] if i-start_rank < len(candidate_names) else rank_name
            # 生成候选人名称的id（使用不包含"名"字的格式）
            rank_name_for_id = rank_name.replace("名", "")  # 将"第一名"转换为"第一"
            candidate_id = f"{rank_name_for_id}中标候选人名称"
            html.append(
                f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span id="{candidate_id}" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{candidate_name}</span></td>')
        html.append('</tr>')

        # 数据行：根据资格评审标准的条款列表生成行
        row_idx = 1
        for clause in all_items:
            # 检查是否是业绩类条款（包含"业绩"的条款）
            is_performance_item = "业绩" in clause
            
            if is_performance_item:
                # 业绩类条款特殊处理：收集该条款的所有业绩编号
                # 资格评审标准：只填充序号为1的业绩
                performance_numbers = set()
                # 从变量中提取条款名称（用于显示）
                clause_name_from_var = None
                for i in range(start_rank, end_rank + 1):
                    rank_name = get_rank_name(i)
                    # 从过滤后的变量中查找该条款的所有业绩变量
                    for var in filtered_variables:
                        var_name = var.get("variable_name", "")
                        # 匹配模式：排名 + 条款名称 + 数字
                        # 例如："第一名业绩要求1"、"第一名投标人近年类似项目业绩2"
                        pattern = f"{rank_name}{re.escape(clause)}(\\d+)"
                        match = re.search(pattern, var_name)
                        if match:
                            perf_num = int(match.group(1))
                            # 资格评审标准：只保留序号为1的业绩
                            if perf_num == 1 and var.get("variable_value", "").strip():
                                performance_numbers.add(perf_num)
                                # 从变量名中提取条款名称（去掉排名和数字）
                                if clause_name_from_var is None:
                                    clause_name_from_var = _get_clause_from_variable_name(var_name, candidate_count)
                                    # 去掉"要求"两个字
                                    if clause_name_from_var:
                                        clause_name_from_var = clause_name_from_var.replace("要求", "")
                
                # 按编号排序
                sorted_perf_nums = sorted(performance_numbers)
                
                # 为每个业绩编号生成一行（使用从变量中提取的条款名称）
                for perf_num in sorted_perf_nums:
                    # 检查当前业绩编号在当前表格内是否至少有一个候选人有值
                    has_any_content = False
                    for i in range(start_rank, end_rank + 1):
                        rank_name = get_rank_name(i)
                        var_name = f"{rank_name}{clause}{perf_num}"
                        content = get_variable_value(var_name)
                        if content.strip():  # 如果有任何一个候选人有值
                            has_any_content = True
                            break
                    
                    # 如果当前表格内所有候选人都没有值，跳过这一行
                    if not has_any_content:
                        continue
                    
                    html.append('<tr>')
                    # 序号
                    html.append(
                        f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体; font-size: 14px;">{row_idx}</span></td>')
                    # 评审内容名称（使用从变量中提取的条款名称+编号，如"监理工程师业绩1"）
                    # 如果无法从变量中提取，使用默认的"业绩"
                    display_name = clause_name_from_var if clause_name_from_var else "业绩"
                    html.append(
                        f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{display_name}{perf_num}</span></td>')

                    # 各候选人对应的业绩内容
                    for i in range(start_rank, end_rank + 1):
                        rank_name = get_rank_name(i)
                        var_name = f"{rank_name}{clause}{perf_num}"
                        content = get_variable_value(var_name)
                        # 生成id：使用变量名作为id
                        cell_id = var_name
                        html.append(
                            f'<td style="border: 1px solid #000; padding: 8px; text-align: left;"><span id="{cell_id}" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{content}</span></td>')
                    html.append('</tr>')
                    row_idx += 1
            else:
                # 其他评审项：资质、项目负责人等（非业绩类条款）
                # 从变量中提取条款名称（用于显示）
                clause_name_from_var = None
                for i in range(start_rank, end_rank + 1):
                    rank_name = get_rank_name(i)
                    var_name = f"{rank_name}{clause}"
                    # 尝试从变量名中提取条款名称
                    if clause_name_from_var is None:
                        clause_name_from_var = _get_clause_from_variable_name(var_name, candidate_count)
                        # 去掉"要求"两个字
                        if clause_name_from_var:
                            clause_name_from_var = clause_name_from_var.replace("要求", "")
                
                # 如果无法从变量中提取，使用原始条款名称（去掉"要求"）
                display_clause = clause_name_from_var if clause_name_from_var else clause.replace("要求", "")
                
                # 先检查是否至少有一个候选人有值
                has_any_content = False
                for i in range(start_rank, end_rank + 1):
                    rank_name = get_rank_name(i)
                    var_name = f"{rank_name}{clause}"
                    content = get_variable_value(var_name)
                    if content.strip():
                        has_any_content = True
                        break
                
                # 如果所有候选人都没有值，跳过这一行
                if not has_any_content:
                    continue
                
                html.append('<tr>')
                # 序号
                html.append(
                    f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体; font-size: 14px;">{row_idx}</span></td>')
                # 评审内容名称（使用从变量中提取的条款名称，去掉"要求"）
                html.append(
                    f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{display_clause}</span></td>')

                # 各候选人对应的评审内容
                for i in range(start_rank, end_rank + 1):
                    rank_name = get_rank_name(i)
                    var_name = f"{rank_name}{clause}"
                    content = get_variable_value(var_name)
                    # 生成id：使用变量名作为id
                    cell_id = var_name
                    html.append(
                        f'<td style="border: 1px solid #000; padding: 8px; text-align: left;"><span id="{cell_id}" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{content}</span></td>')
                html.append('</tr>')
                row_idx += 1

        # 表格结束
        html.append('</table>')
        return '\n'.join(html)
    
    # 主逻辑：根据候选人数量决定是否生成多个表格
    if candidate_count <= 3:
        # 候选人数量不超过3个，生成单个表格
        return generate_single_table(1, candidate_count)
    else:
        # 候选人数量超过3个，生成多个表格
        all_tables = []
        
        # 每3个候选人生成一个表格
        for start_rank in range(1, candidate_count + 1, 3):
            end_rank = min(start_rank + 2, candidate_count)
            table_html = generate_single_table(start_rank, end_rank)
            all_tables.append(table_html)
        
        # 用换行符和间距连接多个表格
        return '\n\n<br><br>\n\n'.join(all_tables)

