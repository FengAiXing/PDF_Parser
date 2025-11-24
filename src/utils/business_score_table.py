"""
商务评分表格生成器
用于生成评标报告中的商务评分表格（详细评审客观分得分情况表格）
"""

from typing import List, Dict, Any
import re
from src.utils.dynamic_table_generator import (
    _extract_clauses_from_variables,
    _parse_clauses,
    _get_clause_from_variable_name,
    _is_variable_from_business,
    _is_variable_from_qualification,
    _has_position_in_clause
)


def create_detailed_score_table(candidate_count: int, extracted_variables: List[Dict[str, Any]], evaluation_structure: List[Dict[str, Any]] = None) -> str:
    """
    根据推荐中标候选人数量和提取的变量生成并填充详细评审客观分得分情况表格
    
    注意：此表格只显示商务评分标准中的条款变量，不显示资格评审标准的变量
    
    本函数根据商务部分评分表中的条款动态生成表格列，逻辑如下：
    1. 从商务部分评分表中提取条款（如：投标人业绩、三体系认证等）
    2. 对于每个条款，在"详细评审客观类评标条款"列下添加该条款，并跨一列（因为需要留一列填充变量值）
    3. 对于三体系认证，特殊处理：拆分为三个子项（质量管理体系、环境管理体系、职业健康安全管理体系），分数为总分的三分之一
    4. 对于其他条款，直接跨两行显示
    5. 候选人列下方填充对应的变量值
    
    参数：
        candidate_count: 推荐中标候选人数量
        extracted_variables: 从AI提取的变量列表，格式：
            [
                {"variable_name": "三第一名投标人业绩1", "variable_value": "业绩内容...", ...},  # 第五次模型调用返回
                {"variable_name": "分数第一名投标人业绩", "variable_value": "8.5", ...},  # 第三次模型调用返回（分数）
                {"variable_name": "分数第一名三体系认证", "variable_value": "3.0", ...},  # 第三次模型调用返回（三体系认证分数）
                ...
            ]
        evaluation_structure: 评审项结构（已废弃，为了兼容性保留参数）
    
    返回：
        完整的HTML表格字符串（如果候选人超过3个，会生成多个表格）
    """
    # 提取资格评审标准和商务评分标准的条款
    import logging
    logger = logging.getLogger(__name__)
    
    clauses = _extract_clauses_from_variables(extracted_variables)
    qualification_clauses = clauses.get("qualification", [])
    business_clauses = clauses.get("business", [])
    
    logger.info(f"商务评分标准条款数量: {len(business_clauses)}")
    
    # 过滤变量：只保留属于商务评分标准的变量
    filtered_variables = []
    skipped_count = 0
    for var in extracted_variables:
        var_name = var.get("variable_name", "")
        
        # 优先处理"分数第"开头的变量（这些明显是商务评分标准的变量）
        # 注意：不再使用"三第"前缀，直接匹配"第X名"开头
        if var_name.startswith("分数第"):
            # 特殊处理：如果变量名包含"三体系"或"管理体系"，直接添加（因为这些条款已经从business_clauses中过滤掉了）
            system_keywords = ["三体系", "管理体系"]
            has_system_keyword = any(keyword in var_name for keyword in system_keywords)
            
            if has_system_keyword:
                # 体系相关变量直接添加，不需要检查business_clauses
                filtered_variables.append(var)
                logger.debug(f"商务评分变量（体系相关，分数开头）: {var_name}")
            elif business_clauses:
                # 如果设置了商务评分标准，检查条款是否匹配
                if _is_variable_from_business(var_name, business_clauses, candidate_count):
                    filtered_variables.append(var)
                    logger.debug(f"商务评分变量（分数开头）: {var_name}")
                else:
                    skipped_count += 1
                    logger.debug(f"跳过不匹配的商务变量: {var_name}")
            else:
                # 如果没有设置商务评分标准，直接添加（向后兼容）
                filtered_variables.append(var)
                logger.debug(f"向后兼容商务变量（分数开头）: {var_name}")
        # 检查是否是"第X名"开头的变量（商务评分标准变量，不再使用"三"前缀）
        elif any(var_name.startswith(rank) for rank in ["第一名", "第二名", "第三名", "第四名", "第五名", "第六名", "第七名", "第八名", "第九名", "第十名"]):
            if business_clauses:
                # 如果设置了商务评分标准，检查条款是否匹配
                if _is_variable_from_business(var_name, business_clauses, candidate_count):
                    filtered_variables.append(var)
                    logger.debug(f"商务评分变量（第X名开头）: {var_name}")
                else:
                    skipped_count += 1
                    logger.debug(f"跳过不匹配的商务变量: {var_name}")
            else:
                # 如果没有设置商务评分标准，直接添加（向后兼容）
                filtered_variables.append(var)
                logger.debug(f"向后兼容商务变量（第X名开头）: {var_name}")
        elif _is_variable_from_business(var_name, business_clauses, candidate_count):
            # 检查其他变量是否属于商务评分标准
            filtered_variables.append(var)
            logger.debug(f"商务评分变量: {var_name}")
        # 如果没有设置商务评分标准，则显示所有以"分数第"或"第X名"开头的变量（向后兼容）
        elif not business_clauses:
            # 检查是否属于资格评审标准，如果是则跳过
            if _is_variable_from_qualification(var_name, qualification_clauses, candidate_count):
                skipped_count += 1
                logger.debug(f"跳过资格评审变量: {var_name}")
    
    logger.info(f"商务评分表格: 过滤后变量数量 {len(filtered_variables)} (跳过 {skipped_count} 个资格评审变量)")
    
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
    
    # 辅助函数：从商务部分评分表中提取所有条款名称（从过滤后的变量中）
    def extract_clauses_from_score_variables() -> List[str]:
        """
        从以'分数'开头的变量中提取所有评标条款名称
        
        返回：
            条款名称列表（去重并保持顺序）
        """
        clauses = []
        seen_clauses = set()
        
        # 从第一名的分数变量中提取条款（使用过滤后的变量）
        for var in filtered_variables:
            var_name = var.get("variable_name", "")
            # 只处理以"分数第"开头的变量（商务评分标准的分数变量）
            if var_name.startswith("分数第"):
                # 提取条款名称：去掉"分数第X名"前缀
                # 匹配"分数第X名"模式
                match = re.match(r'分数(第[一二三四五六\d]+名)', var_name)
                if match:
                    prefix_len = len(match.group(1)) + 2  # "分数" + "第X名"
                    clause_name = var_name[prefix_len:]  # 去掉"分数第X名"前缀
                else:
                    # 回退到旧逻辑
                    clause_name = var_name[len("分数第一名"):]  # 去掉"分数第一名"前缀
                
                # 如果条款名称还没有记录，添加到列表
                if clause_name and clause_name not in seen_clauses:
                    clauses.append(clause_name)
                    seen_clauses.add(clause_name)
        
        return clauses
    
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
        
        # 收集候选人名称（从第三次模型调用的结果中获取）
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
        
        # 从商务评分标准中获取条款列表（而不是从变量推断）
        clauses = business_clauses.copy() if business_clauses else []
        
        # 过滤掉包含"三体系"、"管理体系"等关键词的条款（这些条款将从变量中自动检测）
        system_keywords = ["三体系", "管理体系"]
        clauses = [clause for clause in clauses if not any(keyword in clause for keyword in system_keywords)]
        
        logger.debug(f"商务评分标准条款列表（已过滤三体系/管理体系）: {clauses}")
        
        # 从"分数第"开头的变量中提取包含"三体系"、"管理体系"等关键词的条款
        system_clauses_from_vars = set()
        for var in filtered_variables:
            var_name = var.get("variable_name", "")
            if var_name.startswith("分数第"):
                # 检查是否包含体系相关关键词
                has_system_keyword = any(keyword in var_name for keyword in system_keywords)
                if has_system_keyword:
                    # 提取条款名称：去掉"分数第X名"前缀
                    match = re.match(r'分数(第[一二三四五六七八九十\d]+名)', var_name)
                    if match:
                        prefix_len = len(match.group(1)) + 2  # "分数" + "第X名"
                        clause_name = var_name[prefix_len:]  # 去掉"分数第X名"前缀
                        if clause_name:
                            system_clauses_from_vars.add(clause_name)
                            logger.info(f"从变量中检测到体系相关条款: {clause_name} (变量: {var_name})")
        
        logger.info(f"从变量中检测到 {len(system_clauses_from_vars)} 个体系相关条款: {list(system_clauses_from_vars)}")
        
        # 调试：检查是否有"分数第一名三体系认证"这样的变量
        for var in filtered_variables:
            var_name = var.get("variable_name", "")
            if "三体系认证" in var_name and var_name.startswith("分数第"):
                logger.info(f"找到三体系认证变量: {var_name} = {var.get('variable_value', '')}")
        
        # 生成HTML表格
        html = []
        html.append('<table style="width: 100%; table-layout: fixed; border-collapse: collapse; margin: 0;">')

        # 表头第一行：序号 + 详细评审客观类评标条款（合并2列） + 评审情况（合并table_candidate_count列）
        html.append('<tr>')
        html.append(
            '<td rowspan="2" style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体; font-size: 14px;background-color: rgb(192,192,192);"><strong>序号</strong></span></td>')
        html.append(
            '<td rowspan="2" colspan="2" style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体; font-size: 14px;background-color: rgb(192,192,192);"><strong>详细评审客观类评标条款</strong></span></td>')
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

        # 数据行：根据商务评分标准的条款列表生成
        main_idx = 1  # 序号计数器
        
        # 先处理条款列表中的其他条款（业绩、其他认证等）
        for clause_name in clauses:
            # 检查是否是业绩类条款（包含"业绩"的条款）
            is_performance_item = "业绩" in clause_name
            
            if is_performance_item:
                # 业绩类条款特殊处理：收集该条款的所有业绩编号
                # 判断该业绩条款是否包含职位信息
                has_position = _has_position_in_clause(clause_name)
                
                performance_numbers = set()
                for i in range(start_rank, end_rank + 1):
                    rank_name = get_rank_name(i)
                    # 从过滤后的变量中查找该条款的所有业绩变量
                    # 匹配模式：第X名 + 条款名称 + 数字（不再使用"三"前缀）
                    for var in filtered_variables:
                        var_name = var.get("variable_name", "")
                        # 匹配模式：排名 + 条款名称 + 数字
                        pattern = f"{rank_name}{re.escape(clause_name)}(\\d+)"
                        match = re.search(pattern, var_name)
                        if match:
                            perf_num = int(match.group(1))
                            if var.get("variable_value", "").strip():
                                # 商务评分标准业绩填充规则：
                                # - 包含职位的业绩条款：都填充（保持不变）
                                # - 不包含职位的业绩条款：只填充序号2及以上的业绩，不填充序号1的
                                if has_position:
                                    # 包含职位，都填充
                                    performance_numbers.add(perf_num)
                                else:
                                    # 不包含职位，只填充序号2及以上的
                                    if perf_num >= 2:
                                        performance_numbers.add(perf_num)
                
                # 按编号排序
                sorted_perf_nums = sorted(performance_numbers)
                
                if sorted_perf_nums:
                    # 序号和条款名称跨所有业绩行
                    rowspan_count = len(sorted_perf_nums)
                    
                    # 为每个业绩编号生成一行（显示为"业绩1"、"业绩2"等）
                    for idx, perf_num in enumerate(sorted_perf_nums):
                        html.append('<tr>')
                        
                        # 第一行：添加序号和条款名称（跨所有行）
                        if idx == 0:
                            html.append(
                                f'<td rowspan="{rowspan_count}" style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体; font-size: 14px;">{main_idx}</span></td>')
                            html.append(
                                f'<td rowspan="{rowspan_count}" style="border: 1px solid #000; padding: 8px; text-align: center;"><span id="商务部分评分表" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{clause_name}</span></td>')
                        
                        # 业绩编号显示：如果不包含职位，将序号减去1以确保从1开始
                        if has_position:
                            # 包含职位，显示原始序号
                            display_perf_num = perf_num
                        else:
                            # 不包含职位，序号减去1（业绩2显示为业绩1，业绩3显示为业绩2，以此类推）
                            display_perf_num = perf_num - 1
                        
                        html.append(
                            f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">业绩{display_perf_num}</span></td>')
                        
                        # 各候选人对应的业绩内容（使用原始变量名，但显示时序号减去1）
                        for i in range(start_rank, end_rank + 1):
                            rank_name = get_rank_name(i)
                            var_name = f"{rank_name}{clause_name}{perf_num}"  # 使用原始序号查找变量
                            content = get_variable_value(var_name)
                            cell_id = var_name
                            html.append(
                                f'<td style="border: 1px solid #000; padding: 8px; text-align: left;"><span id="{cell_id}" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{content}</span></td>')
                        html.append('</tr>')
                    
                    main_idx += 1
            # 注意：三体系认证和管理体系认证已经在上面处理过了，这里不再处理
            elif "三体系" in clause_name or "管理体系" in clause_name:
                # 如果条款列表中还有三体系/管理体系相关条款（不应该出现），跳过
                logger.warning(f"跳过条款列表中的体系相关条款（应该从变量中检测）: {clause_name}")
                continue
                
            elif ("认证" in clause_name or "体系" in clause_name):
                # 认证/体系类条款：按管理体系认证的分数变量填充
                html.append('<tr>')
                html.append(
                    f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体; font-size: 14px;">{main_idx}</span></td>')
                # 条款名称来自商务部分评分表，使用"商务部分评分表"作为id，跨两列
                html.append(
                    f'<td colspan="2" style="border: 1px solid #000; padding: 8px; text-align: center;"><span id="商务部分评分表" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{clause_name}</span></td>')

                # 各候选人对应的分数：使用"分数{rank_name}管理体系认证"变量
                for i in range(start_rank, end_rank + 1):
                    rank_name = get_rank_name(i)
                    score_var_name = f"分数{rank_name}管理体系认证"
                    score_value = get_variable_value(score_var_name)
                    # 数值格式化：非0 → 有效，得X分；0或空 → 无效，得0分
                    try:
                        score_float = float(score_value) if score_value not in (None, "") else 0.0
                        if score_float > 0:
                            display = f"有效，得{score_float:g}分"
                        else:
                            display = "无效，得0分"
                    except (ValueError, TypeError):
                        display = "无效，得0分"
                    cell_id = score_var_name
                    html.append(
                        f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span id="{cell_id}" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{display}</span></td>')
                html.append('</tr>')

            else:
                # 其他条款（非业绩、非三体系认证）：直接使用"第X名+条款名称"变量填充
                html.append('<tr>')
                html.append(
                    f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体; font-size: 14px;">{main_idx}</span></td>')
                # 条款名称来自商务部分评分表，使用"商务部分评分表"作为id
                html.append(
                    f'<td colspan="2" style="border: 1px solid #000; padding: 8px; text-align: center;"><span id="商务部分评分表" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{clause_name}</span></td>')
                
                # 各候选人对应的内容（直接使用"第X名+条款名称"变量，如"第一名银行资信"、"第一名综合实力"）
                for i in range(start_rank, end_rank + 1):
                    rank_name = get_rank_name(i)
                    # 直接使用"第X名+条款名称"变量
                    content_var_name = f"{rank_name}{clause_name}"
                    content_value = get_variable_value(content_var_name)
                    # 使用变量名作为id
                    cell_id = content_var_name
                    
                    html.append(
                        f'<td style="border: 1px solid #000; padding: 8px; text-align: left;"><span id="{cell_id}" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{content_value}</span></td>')
                html.append('</tr>')
            
            main_idx += 1
        
        # 最后处理从变量中检测到的体系相关条款（三体系、管理体系等）- 放在表格最后
        for clause_name in sorted(system_clauses_from_vars):
            # 检查是否有对应的分数变量（至少有一个排名有值）
            has_score = False
            for i in range(start_rank, end_rank + 1):
                rank_name = get_rank_name(i)
                score_var_name = f"分数{rank_name}{clause_name}"
                score_value = get_variable_value(score_var_name)
                if score_value and score_value.strip():
                    try:
                        if float(score_value) > 0:
                            has_score = True
                            break
                    except (ValueError, TypeError):
                        pass
            
            if not has_score:
                logger.debug(f"跳过体系相关条款 {clause_name}（没有有效的分数变量）")
                continue
            
            # 生成三行表格（质量管理体系、环境管理体系、职业健康安全管理体系）
            sub_items = ["质量管理体系", "环境管理体系", "职业健康安全管理体系"]
            
            # 第一行：序号和主标题（跨3行）
            html.append('<tr>')
            html.append(
                f'<td rowspan="3" style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="font-family: 宋体; font-size: 14px;">{main_idx}</span></td>')
            # 条款名称使用变量名中的原始名称
            html.append(
                f'<td rowspan="3" style="border: 1px solid #000; padding: 8px; text-align: center;"><span id="商务部分评分表" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{clause_name}</span></td>')
            
            # 第一个子项
            html.append(
                f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{sub_items[0]}</span></td>')
            
            # 各候选人对应的分数（第一个子项）- 总分的三分之一
            for i in range(start_rank, end_rank + 1):
                rank_name = get_rank_name(i)
                score_var_name = f"分数{rank_name}{clause_name}"
                total_score = get_variable_value(score_var_name)
                
                # 计算每个子项的分数（总分除以3）
                try:
                    total_score_float = float(total_score) if total_score else 0.0
                    sub_score = total_score_float / 3.0
                    # 保留一位小数
                    if sub_score > 0:
                        sub_score_str = f"有效，得{sub_score:.1f}分"
                    else:
                        sub_score_str = "无效"
                except (ValueError, TypeError):
                    sub_score_str = "无效"
                
                # 生成id：使用变量名作为id
                cell_id = score_var_name
                html.append(
                    f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span id="{cell_id}" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{sub_score_str}</span></td>')
            html.append('</tr>')
            
            # 第二行：第二个子项
            html.append('<tr>')
            html.append(
                f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{sub_items[1]}</span></td>')
            
            # 各候选人对应的分数（第二个子项）
            for i in range(start_rank, end_rank + 1):
                rank_name = get_rank_name(i)
                score_var_name = f"分数{rank_name}{clause_name}"
                total_score = get_variable_value(score_var_name)
                
                # 计算每个子项的分数（总分除以3）
                try:
                    total_score_float = float(total_score) if total_score else 0.0
                    sub_score = total_score_float / 3.0
                    # 保留一位小数
                    if sub_score > 0:
                        sub_score_str = f"有效，得{sub_score:.1f}分"
                    else:
                        sub_score_str = "无效"
                except (ValueError, TypeError):
                    sub_score_str = "无效"
                
                # 生成id：使用变量名作为id
                cell_id = score_var_name
                html.append(
                    f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span id="{cell_id}" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{sub_score_str}</span></td>')
            html.append('</tr>')
            
            # 第三行：第三个子项
            html.append('<tr>')
            html.append(
                f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{sub_items[2]}</span></td>')
            
            # 各候选人对应的分数（第三个子项）
            for i in range(start_rank, end_rank + 1):
                rank_name = get_rank_name(i)
                score_var_name = f"分数{rank_name}{clause_name}"
                total_score = get_variable_value(score_var_name)
                
                # 计算每个子项的分数（总分除以3）
                try:
                    total_score_float = float(total_score) if total_score else 0.0
                    sub_score = total_score_float / 3.0
                    # 保留一位小数
                    if sub_score > 0:
                        sub_score_str = f"有效，得{sub_score:.1f}分"
                    else:
                        sub_score_str = "无效"
                except (ValueError, TypeError):
                    sub_score_str = "无效"
                
                # 生成id：使用变量名作为id
                cell_id = score_var_name
                html.append(
                    f'<td style="border: 1px solid #000; padding: 8px; text-align: center;"><span id="{cell_id}" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{sub_score_str}</span></td>')
            html.append('</tr>')
            
            main_idx += 1

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

