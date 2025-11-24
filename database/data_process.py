# 对数据库中的数据进行数据处理 

import sys
import os
# 添加项目根目录到Python路径（必须在导入其他模块之前）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from typing import Optional, Dict, Any, List, Union
from database.database import db_manager
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

# 进度阶段定义（简化版）
PROGRESS_STAGES = {
    "initialized": 0,              # 接收到请求，初始化任务（0%）
    "files_processed": 30,         # 文件处理完成
    "tasks_processing": 50,        # 开始处理任务
    "regular_files_processed": 60, # 五种类型文件处理完成
    "complex_files_processing": 65,# 开始处理复杂文件
    "task_completed": 80,          # 单个任务完成（动态查询）
    "all_tasks_completed": 90,     # 所有任务完成
    "all_files_processed": 100,    # 所有文件处理完成（修改为100）
    "report_completed": 100,       # 报告生成并保存完成
    "error_occurred": -1           # 发生错误
}

# 解析任务进度阶段定义（累加式，每个阶段在0基础上累加）
# 每个阶段的值表示该阶段应该累加的进度增量（10%）
PARSE_TASK_PROGRESS_STAGES = {
    "initialized": 0,              # 接收到请求，初始化任务（0%）
    "files_downloaded": 10,        # 文件下载完成（+10%，累计10%）
    "ranges_merged": 10,           # 页码合并完成（+10%，累计20%）
    "files_parsed": 30,            # 文件解析完成（+30%，占3份，累计50%）
    "variables_extracted": 10,     # 变量提取完成（+10%，累计60%）
    "preprocessing_completed": 10, # 预处理变量完成（+10%，累计70%）
    "scores_added": 10,            # 得分添加完成（+10%，累计80%）
    "variables_saved": 10,         # 存储到数据库完成（+10%，累计90%）
    "report_completed": 10,        # 报告生成完成（+10%，累计100%）
    # 保留旧的阶段名称以兼容性（已废弃，但保留避免报错）
    "loading_data": 0,             # 已废弃：正在从数据库加载数据
    "processing_ranges": 10,       # 已废弃：正在处理页码范围（映射到ranges_merged）
    "preprocessing_variables": 10, # 已废弃：正在预处理变量（映射到preprocessing_completed）
    "parsing_files": 30,           # 已废弃：正在解析文件（映射到files_parsed）
    "extracting_candidate_details": 10,  # 已废弃：正在提取候选人详细信息（映射到variables_extracted）
    "saving_variables": 10,        # 已废弃：正在保存变量（映射到variables_saved）
    "rendering_template": 10,      # 已废弃：正在渲染模板（映射到report_completed）
    "error_occurred": -1,          # 发生错误
    # 重新生成报告任务的进度阶段（累加式，每个值表示增量）
    "getting_page_ranges": 5,      # 正在获取新的页码范围 (0% -> 5%)
    "getting_historical_data": 10, # 正在获取历史变量和报告内容 (5% -> 15%)
    "deleting_rank_variables": 5, # 正在获取排名并删除以第几名开头的变量 (15% -> 20%)
    "identifying_variables": 10,  # 正在识别属于该投标文件的变量 (20% -> 30%)
    "regenerating_variables": 40, # 正在使用新页码范围重新生成变量 (30% -> 70%)
    "merging_variables": 10,      # 正在合并变量 (70% -> 80%)
    "regenerating_report": 10,    # 正在保存变量并重新生成报告 (80% -> 90%)
    "saving_report": 5,           # 正在保存最终报告到数据库 (90% -> 95%)
    "processing": 5,              # 开始处理 (0% -> 5%)
    "completed": 100             # 完成 (设置为100%)
}

def get_template_type_by_id(template_id: str) -> Optional[str]:
    """
    根据模板ID从数据库获取模板类型
    
    Args:
        template_id: 模板ID
        
    Returns:
        Optional[str]: 模板类型，如果不存在返回None
    """
    try:
        with db_manager.get_db_session() as session:
            # 执行SQL查询获取模板类型
            query = text("SELECT project_type FROM report_template WHERE id = :template_id")
            result = session.execute(query, {"template_id": template_id}).fetchone()
            
            if result:
                return result[0]
            else:
                logger.warning(f"数据库中未找到ID为 {template_id} 的模板")
                return None
                
    except Exception as e:
        logger.error(f"查询模板类型失败: {e}")
        return None


def get_variables_values_by_id(id: str) -> Dict[str, Any]:
    """
    根据报告ID从数据库获取reference_sources中的变量值，转换为键值对格式
    
    Args:
        id: 报告ID（项目ID）
        
    Returns:
        Dict[str, Any]: 变量名和变量值的键值对字典
    """
    try:
        with db_manager.get_db_session() as session:
            # 尝试将项目ID转换为整数，如果失败则使用哈希值（与save_task_results_to_database保持一致）
            try:
                project_id_int = int(id)
            except ValueError:
                # 对于非数字项目ID，使用哈希值作为数字ID
                project_id_int = abs(hash(id)) % (10**10)  # 生成10位数字
            
            # 查询reference_sources字段
            query = text("SELECT reference_sources FROM eval_report WHERE id = :report_id")
            result = session.execute(query, {"report_id": project_id_int}).fetchone()
            
            if not result or not result[0]:
                logger.warning(f"数据库中未找到ID为 {id} 的报告或reference_sources为空")
                return {}
            
            # 解析JSON数据
            import json
            try:
                reference_sources = json.loads(result[0])
            except json.JSONDecodeError as e:
                logger.error(f"解析reference_sources JSON失败: {e}")
                return {}
            
            # 确保reference_sources是列表格式
            if not isinstance(reference_sources, list):
                logger.error(f"reference_sources格式错误，期望列表格式，实际类型: {type(reference_sources)}")
                return {}
            
            # 提取variable_name和variable_value，转换为键值对
            variables_dict = {}
            for item in reference_sources:
                if isinstance(item, dict) and "variable_name" in item and "variable_value" in item:
                    variable_name = item["variable_name"]
                    variable_value = item["variable_value"]
                    variables_dict[variable_name] = variable_value
            
            logger.info(f"成功提取 {len(variables_dict)} 个变量值")
            return variables_dict
            
    except Exception as e:
        logger.error(f"获取变量值失败: {e}")
        return {}


def save_task_results_to_database(project_id: str, results: Union[List[Dict[str, Any]], Dict[str, Any]], template_id: str = None) -> bool:
    """
    保存任务处理结果到数据库的eval_report表中
    
    Args:
        project_id: 项目ID
        results: 任务处理结果（变量列表，每个元素包含 variable_name 和 variable_value）
        template_id: 模板ID（可选）

    Returns:
        bool: 保存是否成功
    """
    try:
        with db_manager.get_db_session() as session:
            import json
            
            # 确保results是列表格式
            if isinstance(results, dict):
                # 如果是字典，尝试转换为列表
                # 检查是否是包含变量列表的字典结构
                if "variable_name" in results or "variable_value" in results:
                    # 单个变量字典，转换为列表
                    results = [results]
                else:
                    # 字典格式，需要转换为列表
                    # 尝试从字典中提取变量列表
                    variables_list = []
                    for key, value in results.items():
                        if isinstance(value, list):
                            # 如果值是列表，直接扩展
                            variables_list.extend(value)
                        else:
                            # 否则创建变量字典
                            variables_list.append({
                                "variable_name": key,
                                "variable_value": value
                            })
                    results = variables_list
            
            # 确保results是列表格式，每个元素包含 variable_name 和 variable_value
            if not isinstance(results, list):
                logger.error(f"results格式错误，期望列表格式，实际类型: {type(results)}")
                return False
            
            # 验证列表格式
            validated_results = []
            for item in results:
                if isinstance(item, dict) and "variable_name" in item and "variable_value" in item:
                    validated_results.append(item)
                else:
                    logger.warning(f"跳过无效的变量项: {item}")
            
            # 将结果转换为JSON字符串
            results_json = json.dumps(validated_results, ensure_ascii=False, indent=2)
            
            # 先尝试更新现有记录
            # 如果提供了template_id，也更新它
            if template_id is not None:
                update_query = text("""
                    UPDATE eval_report 
                    SET reference_sources = :results_json, template_id = :template_id
                    WHERE id = :project_id
                """)
            else:
                update_query = text("""
                    UPDATE eval_report 
                    SET reference_sources = :results_json 
                    WHERE id = :project_id
                """)
            
            # 尝试将项目ID转换为整数，如果失败则使用哈希值
            try:
                project_id_int = int(project_id)
            except ValueError:
                # 对于非数字项目ID，使用哈希值作为数字ID
                project_id_int = abs(hash(project_id)) % (10**10)  # 生成10位数字
            
            # 准备更新参数
            update_params = {
                "results_json": results_json,
                "project_id": project_id_int
            }
            # 如果提供了template_id，添加到参数中
            if template_id is not None:
                try:
                    template_id_int = int(template_id)
                    update_params["template_id"] = template_id_int
                except (ValueError, TypeError):
                    update_params["template_id"] = template_id
            
            result = session.execute(update_query, update_params)
            
            if result.rowcount > 0:
                session.commit()
                logger.info(f"成功更新现有记录，项目ID: {project_id}")
                logger.info(f"保存的变量数量: {len(validated_results)}")
                return True
            else:
                # 如果更新失败，尝试创建新记录
                logger.warning(f"未找到项目ID为 {project_id} 的记录，尝试创建新记录")
                
                # 直接使用project_id作为数据库ID，包含所有必需字段
                insert_query = text("""
                    INSERT INTO eval_report 
                    (id, template_id, name, content, reference_sources, generate_time, generate_progress, 
                     status, create_time, update_time, creator, tenant_id, tender_files, bid_files, 
                     bid_opening_form_files, expert_info_form_files, evaluation_summary_files, 
                     other_files) 
                    VALUES (:id, :template_id, :name, :content, :reference_sources, :generate_time, 
                            :generate_progress, :status, NOW(), NOW(), :creator, :tenant_id, 
                            :tender_files, :bid_files, :bid_opening_form_files, :expert_info_form_files, 
                            :evaluation_summary_files, :other_files)
                """)
                
                # 处理template_id：如果提供了则使用，否则为None
                template_id_value = None
                if template_id is not None:
                    try:
                        template_id_value = int(template_id)
                    except (ValueError, TypeError):
                        template_id_value = template_id
                
                session.execute(insert_query, {
                    "id": project_id_int,
                    "template_id": template_id_value,
                    "name": f"项目_{project_id}",
                    "content": None,
                    "reference_sources": results_json,
                    "generate_time": None,
                    "generate_progress": None,
                    "status": 7,
                    "creator": None,
                    "tenant_id": None,
                    "tender_files": None,
                    "bid_files": None,
                    "bid_opening_form_files": None,
                    "expert_info_form_files": None,
                    "evaluation_summary_files": None,
                    "other_files": None,
                })
                
                session.commit()
                logger.info(f"成功创建新记录，使用项目ID: {project_id}")
                logger.info(f"保存的变量数量: {len(validated_results)}")
                return True
                
    except Exception as e:
        logger.error(f"保存任务结果到数据库失败: {e}")
        return False


def save_final_report_to_database(project_id: str, final_report: str, template_id: str = None) -> bool:
    """
    保存最终报告到数据库的eval_report表中的content字段
    
    Args:
        project_id: 项目ID
        final_report: 最终报告内容
        template_id: 模板ID（可选）
        
    Returns:
        bool: 保存是否成功
    """
    try:
        # 将project_id转换为整数
        try:
            project_id_int = int(project_id)
        except ValueError:
            logger.error(f"项目ID '{project_id}' 无法转换为整数")
            return False
            
        with db_manager.get_db_session() as session:
            # 先尝试更新现有记录的content字段和status字段
            # 如果提供了template_id，也更新它
            if template_id is not None:
                update_query = text("""
                    UPDATE eval_report 
                    SET content = :final_report, status = 8, template_id = :template_id
                    WHERE id = :project_id
                """)
            else:
                update_query = text("""
                    UPDATE eval_report 
                    SET content = :final_report, status = 8 
                    WHERE id = :project_id
                """)
            
            # 准备更新参数
            update_params = {
                "final_report": final_report,
                "project_id": project_id_int
            }
            # 如果提供了template_id，添加到参数中
            if template_id is not None:
                try:
                    template_id_int = int(template_id)
                    update_params["template_id"] = template_id_int
                except (ValueError, TypeError):
                    update_params["template_id"] = template_id
            
            result = session.execute(update_query, update_params)
            
            if result.rowcount > 0:
                session.commit()
                logger.info(f"成功更新最终报告到数据库，项目ID: {project_id}")
                logger.info(f"报告内容长度: {len(final_report)} 字符")
                return True
            else:
                # 如果更新失败，尝试创建新记录
                logger.warning(f"未找到项目ID为 {project_id} 的记录，尝试创建新记录")
                
                # 直接使用project_id作为数据库ID，包含所有必需字段
                insert_query = text("""
                    INSERT INTO eval_report 
                    (id, template_id, name, content, reference_sources, generate_time, generate_progress, 
                     status, create_time, update_time, creator, tenant_id, tender_files, bid_files, 
                     bid_opening_form_files, expert_info_form_files, evaluation_summary_files, 
                     other_files) 
                    VALUES (:id, :template_id, :name, :content, :reference_sources, :generate_time, 
                            :generate_progress, :status, NOW(), NOW(), :creator, :tenant_id, 
                            :tender_files, :bid_files, :bid_opening_form_files, :expert_info_form_files, 
                            :evaluation_summary_files, :other_files)
                """)
                
                # 处理template_id：如果提供了则使用，否则尝试从现有记录获取，再不行则为None
                template_id_value = None
                if template_id is not None:
                    try:
                        template_id_value = int(template_id)
                    except (ValueError, TypeError):
                        template_id_value = template_id
                else:
                    # 尝试从现有记录获取template_id
                    try:
                        query_existing = text("SELECT template_id FROM eval_report WHERE id = :project_id")
                        existing_result = session.execute(query_existing, {"project_id": project_id_int}).fetchone()
                        if existing_result and existing_result[0] is not None:
                            template_id_value = existing_result[0]
                    except Exception:
                        pass  # 如果查询失败，使用None
                
                session.execute(insert_query, {
                    "id": project_id_int,
                    "template_id": template_id_value,
                    "name": f"项目_{project_id}",
                    "content": final_report,
                    "reference_sources": None,
                    "generate_time": None,
                    "generate_progress": None,
                    "status": 8,
                    "creator": None,
                    "tenant_id": None,
                    "tender_files": None,
                    "bid_files": None,
                    "bid_opening_form_files": None,
                    "expert_info_form_files": None,
                    "evaluation_summary_files": None,
                    "other_files": None,
                })
                
                session.commit()
                logger.info(f"成功创建新记录并保存最终报告，使用项目ID: {project_id}")
                logger.info(f"报告内容长度: {len(final_report)} 字符")
                return True
                
    except Exception as e:
        logger.error(f"保存最终报告到数据库失败: {e}")
        return False


async def update_report_progress(project_id: str, stage: str = None, custom_message: str = None, template_id: str = None) -> bool:
    """
    异步更新报告生成进度（统一方法）

    Args:
        project_id: 项目ID
        stage: 进度阶段（使用PROGRESS_STAGES中的key，可选）
        custom_message: 自定义消息（可选）
        template_id: 模板ID（可选）

    Returns:
        bool: 更新是否成功
    """
    try:
        progress = None
        message = custom_message or "进度更新"

        if stage:
            # 使用预定义的进度阶段
            if stage not in PROGRESS_STAGES:
                logger.error(f"无效的进度阶段: {stage}")
                return False
            
            # 特殊处理：initialized阶段强制设置为0（无论数据库中是什么值）
            if stage == "initialized":
                progress = 0
            elif stage == "error_occurred":
                progress = -1
            else:
                progress = int(PROGRESS_STAGES[stage])
            message = custom_message or f"阶段: {stage}"
        else:
            # 使用简单的递增进度（50% -> 100%）
            # 查询当前进度，然后递增
            current_progress = await _get_current_progress(project_id)
            if current_progress < 50:
                progress = 50
            elif current_progress < 100:
                progress = min(current_progress + 10, 100)  # 每次递增10%，最大100%
            else:
                progress = 100
            message = custom_message or "任务进度更新"

        with db_manager.get_db_session() as session:
            # 尝试将项目ID转换为整数，如果失败则使用哈希值
            try:
                project_id_int = int(project_id)
            except ValueError:
                # 对于非数字项目ID，使用哈希值作为数字ID
                project_id_int = abs(hash(project_id)) % (10**10)  # 生成10位数字
            
            # 安全检查：确保进度只能递增（除非是错误状态、初始化状态或明确完成）
            if stage and stage != "error_occurred" and stage != "initialized" and stage != "all_files_processed" and stage != "report_completed":
                # 在当前会话中查询当前进度
                query_current = text("SELECT generate_progress FROM eval_report WHERE id = :project_id")
                current_result = session.execute(query_current, {"project_id": project_id_int}).fetchone()
                if current_result and current_result[0] is not None:
                    current_progress = int(current_result[0])
                    if current_progress > progress:
                        logger.warning(f"进度倒退检测：当前进度 {current_progress}% > 新进度 {progress}%，保持当前进度")
                        progress = current_progress
            
            # 安全检查：只有明确完成阶段才能设置为100%
            if progress >= 100 and stage not in ["all_files_processed", "report_completed", "error_occurred"]:
                logger.warning(f"检测到进度达到100%但阶段不是完成状态（stage={stage}），限制为99%")
                progress = 99
                status_value = 7  # 保持处理中状态
            # 根据进度值确定状态
            elif stage == "error_occurred" or progress == -1:
                status_value = 9  # 失败状态
            elif progress >= 100:
                status_value = 8  # 完成状态
            elif progress > 0:
                status_value = 7  # 处理中状态
            else:
                status_value = 7  # 初始状态也视为处理中
                
            # 构建更新查询，如果提供了template_id则更新它
            if template_id is not None:
                update_query = text("""
                                    UPDATE eval_report
                                    SET generate_progress = :progress,
                                        status = :status,
                                        message = :message,
                                        template_id = :template_id,
                                        generate_time = NOW(),
                                        update_time = NOW()
                                    WHERE id = :project_id
                                    """)
            else:
                update_query = text("""
                                    UPDATE eval_report
                                    SET generate_progress = :progress,
                                        status = :status,
                                        message = :message,
                                        generate_time = NOW(),
                                        update_time = NOW()
                                    WHERE id = :project_id
                                    """)

            # 尝试将项目ID转换为整数，如果失败则使用哈希值
            try:
                project_id_int = int(project_id)
            except ValueError:
                # 对于非数字项目ID，使用哈希值作为数字ID
                project_id_int = abs(hash(project_id)) % (10**10)  # 生成10位数字
            
            # 准备更新参数
            update_params = {
                "progress": progress,
                "status": status_value,
                "message": message,
                "project_id": project_id_int
            }
            # 如果提供了template_id，添加到参数中
            if template_id is not None:
                # 尝试将template_id转换为整数，如果失败则保持原值
                try:
                    template_id_int = int(template_id)
                    update_params["template_id"] = template_id_int
                except (ValueError, TypeError):
                    update_params["template_id"] = template_id
            
            result = session.execute(update_query, update_params)

            if result.rowcount > 0:
                session.commit()
                logger.info(f"进度更新: 项目{project_id} - {progress}% - {message}")
                return True
            else:
                # 如果项目记录不存在，创建新记录
                logger.warning(f"未找到项目记录: {project_id}，尝试创建新记录")
                
                # 创建基础的项目记录
                insert_query = text("""
                    INSERT INTO eval_report 
                    (id, template_id, name, content, reference_sources, generate_time, generate_progress, 
                     status, message, create_time, update_time, creator, tenant_id, tender_files, bid_files, 
                     bid_opening_form_files, expert_info_form_files, evaluation_summary_files, 
                     other_files) 
                    VALUES (:id, :template_id, :name, :content, :reference_sources, NOW(), 
                            :generate_progress, :status, :message, NOW(), NOW(), :creator, :tenant_id, 
                            :tender_files, :bid_files, :bid_opening_form_files, :expert_info_form_files, 
                            :evaluation_summary_files, :other_files)
                """)
                
                # 尝试将项目ID转换为整数，如果失败则使用哈希值
                try:
                    project_id_int = int(project_id)
                except ValueError:
                    # 对于非数字项目ID，使用哈希值作为数字ID
                    project_id_int = abs(hash(project_id)) % (10**10)  # 生成10位数字
                
                # 处理template_id：如果提供了则使用，否则尝试从现有记录获取，再不行则为None
                template_id_value = None
                if template_id is not None:
                    try:
                        template_id_value = int(template_id)
                    except (ValueError, TypeError):
                        template_id_value = template_id
                else:
                    # 尝试从现有记录获取template_id
                    try:
                        query_existing = text("SELECT template_id FROM eval_report WHERE id = :project_id")
                        existing_result = session.execute(query_existing, {"project_id": project_id_int}).fetchone()
                        if existing_result and existing_result[0] is not None:
                            template_id_value = existing_result[0]
                    except Exception:
                        pass  # 如果查询失败，使用None
                
                session.execute(insert_query, {
                    "id": project_id_int,
                    "template_id": template_id_value,
                    "name": f"项目{project_id}",
                    "content": "",
                    "reference_sources": "",
                    "generate_progress": progress,
                    "status": status_value,  # 使用计算出的状态值
                    "message": message,
                    "creator": "system",
                    "tenant_id": "default",  # 使用字符串类型
                    "tender_files": "",
                    "bid_files": "",
                    "bid_opening_form_files": "",
                    "expert_info_form_files": "",
                    "evaluation_summary_files": "",
                    "other_files": "",
                })
                
                session.commit()
                logger.info(f"成功创建新记录，使用项目ID: {project_id}")
                logger.info(f"进度更新: 项目{project_id} - {progress}% - {message}")
                return True

    except Exception as e:
        logger.error(f"更新进度失败: {e}")
        return False


async def update_report_status(project_id: str, status: int, message: str = None, template_id: str = None) -> bool:
    """
    更新报告生成状态
    
    Args:
        project_id: 项目ID
        status: 状态码（7=处理中，8=完成，9=失败）
        message: 状态消息（可选）
        template_id: 模板ID（可选）
        
    Returns:
        bool: 更新是否成功
    """
    try:
        with db_manager.get_db_session() as session:
            # 构建更新查询，如果提供了template_id则更新它
            if template_id is not None:
                update_query = text("""
                    UPDATE eval_report
                    SET status = :status,
                        message = :message,
                        template_id = :template_id,
                        update_time = NOW()
                    WHERE id = :project_id
                """)
            else:
                update_query = text("""
                    UPDATE eval_report
                    SET status = :status,
                        message = :message,
                        update_time = NOW()
                    WHERE id = :project_id
                """)
            
            # 尝试将项目ID转换为整数，如果失败则使用哈希值
            try:
                project_id_int = int(project_id)
            except ValueError:
                # 对于非数字项目ID，使用哈希值作为数字ID
                project_id_int = abs(hash(project_id)) % (10**10)  # 生成10位数字
            
            # 准备更新参数
            update_params = {
                "status": status,
                "message": message or f"状态更新为: {status}",
                "project_id": project_id_int
            }
            # 如果提供了template_id，添加到参数中
            if template_id is not None:
                try:
                    template_id_int = int(template_id)
                    update_params["template_id"] = template_id_int
                except (ValueError, TypeError):
                    update_params["template_id"] = template_id
            
            result = session.execute(update_query, update_params)
            
            if result.rowcount > 0:
                session.commit()
                logger.info(f"成功更新项目 {project_id} 的状态为 {status}，消息: {message}")
                return True
            else:
                logger.warning(f"未找到项目ID为 {project_id} 的记录，无法更新状态")
                return False
                
    except Exception as e:
        logger.error(f"更新报告状态失败: {e}")
        return False


async def update_parse_task_progress(project_id: str, stage: str = None, custom_message: str = None, template_id: str = None) -> bool:
    """
    异步更新解析任务进度（统一方法，支持累加式进度更新）
    状态码：1=处理中，2=完成，3=失败

    Args:
        project_id: 项目ID
        stage: 进度阶段（使用PARSE_TASK_PROGRESS_STAGES中的key，可选）
        custom_message: 自定义消息（可选）
        template_id: 模板ID（可选）

    Returns:
        bool: 更新是否成功
    """
    # 初始化所有变量，确保在所有代码路径中都有值
    progress = None
    message = custom_message or "进度更新"
    use_atomic_update = False  # 默认不使用原子更新
    increment = 0  # 默认增量为0
    
    try:
        if stage:
            # 使用预定义的进度阶段（累加模式）
            if stage not in PARSE_TASK_PROGRESS_STAGES:
                logger.error(f"无效的进度阶段: {stage}")
                return False
            
            # 获取该阶段应该累加的增量值
            try:
                increment = int(PARSE_TASK_PROGRESS_STAGES[stage])
            except (ValueError, TypeError) as e:
                logger.error(f"无法将进度阶段 {stage} 的值转换为整数: {e}")
                return False
            
            # 累加进度（在0基础上累加）
            if stage == "error_occurred":
                progress = -1
                use_atomic_update = False  # 直接设置进度值，不使用原子更新
            elif stage == "initialized":
                # 初始化阶段：强制设置为0（无论数据库中是什么值）
                progress = 0
                use_atomic_update = False  # 直接设置进度值，不使用原子更新
            elif stage == "completed":
                # 完成阶段：直接设置为100%（无论当前进度是多少）
                progress = 100
                use_atomic_update = False  # 直接设置进度值，不使用原子更新
            else:
                # 累加模式：使用原子更新，避免并发问题
                # 不在应用层计算进度，而是使用数据库原子操作
                # 这样即使有并发请求，也能正确累加进度
                progress = None  # 标记为使用原子更新
                use_atomic_update = True
            
            message = custom_message or f"阶段: {stage}"
        else:
            # 使用简单的递增进度（0% -> 100%）
            # 也使用原子更新，避免并发问题
            increment = 10  # 默认每次递增10%
            progress = None  # 标记为使用原子更新
            use_atomic_update = True
            message = custom_message or "任务进度更新"

        with db_manager.get_db_session() as session:
            # 尝试将项目ID转换为整数，如果失败则使用哈希值
            try:
                project_id_int = int(project_id)
            except ValueError:
                # 对于非数字项目ID，使用哈希值作为数字ID
                project_id_int = abs(hash(project_id)) % (10**10)  # 生成10位数字
            
            # 在更新前，先查询当前状态和进度，用于调试
            if stage == "initialized":
                check_query = text("SELECT generate_progress, status FROM eval_report WHERE id = :project_id")
                check_result = session.execute(check_query, {"project_id": project_id_int}).fetchone()
                if check_result:
                    current_progress, current_status = check_result[0], check_result[1]
                    logger.info(f"🔍 初始化前检查: 项目{project_id} (ID: {project_id_int}) - 当前进度={current_progress}%, 当前状态={current_status}")
                else:
                    logger.warning(f"⚠️ 初始化前检查: 项目{project_id} (ID: {project_id_int}) - 记录不存在")
            
            # 如果使用原子更新（累加模式）
            if use_atomic_update and progress is None:
                # 使用数据库原子操作：UPDATE ... SET progress = LEAST(progress + increment, 100)
                # 这样可以避免并发时的竞态条件
                if template_id is not None:
                    update_query = text("""
                                        UPDATE eval_report
                                        SET generate_progress = LEAST(COALESCE(generate_progress, 0) + :increment, 100),
                                            status = CASE 
                                                WHEN LEAST(COALESCE(generate_progress, 0) + :increment, 100) >= 100 THEN 2
                                                WHEN LEAST(COALESCE(generate_progress, 0) + :increment, 100) >= 0 THEN 1
                                                ELSE 1
                                            END,
                                            message = :message,
                                            template_id = :template_id,
                                            generate_time = NOW(),
                                            update_time = NOW()
                                        WHERE id = :project_id
                                        """)
                else:
                    update_query = text("""
                                        UPDATE eval_report
                                        SET generate_progress = LEAST(COALESCE(generate_progress, 0) + :increment, 100),
                                            status = CASE 
                                                WHEN LEAST(COALESCE(generate_progress, 0) + :increment, 100) >= 100 THEN 2
                                                WHEN LEAST(COALESCE(generate_progress, 0) + :increment, 100) >= 0 THEN 1
                                                ELSE 1
                                            END,
                                            message = :message,
                                            generate_time = NOW(),
                                            update_time = NOW()
                                        WHERE id = :project_id
                                        """)
                
                # 准备更新参数
                update_params = {
                    "increment": increment,
                    "message": message,
                    "project_id": project_id_int
                }
                if template_id is not None:
                    try:
                        template_id_int = int(template_id)
                    except ValueError:
                        template_id_int = template_id
                    update_params["template_id"] = template_id_int
                
                result = session.execute(update_query, update_params)
                
                if result.rowcount > 0:
                    # 提交事务
                    session.commit()
                    
                    # 刷新会话以确保能看到最新的数据
                    session.expire_all()
                    
                    # 查询更新后的实际进度值，确保更新成功
                    query_updated = text("SELECT generate_progress FROM eval_report WHERE id = :project_id")
                    updated_result = session.execute(query_updated, {"project_id": project_id_int}).fetchone()
                    updated_progress = updated_result[0] if updated_result and updated_result[0] is not None else None
                    
                    logger.info(f"成功更新进度，增量: {increment}%，更新后进度: {updated_progress}%，项目ID: {project_id_int}")
                    return True
                else:
                    session.rollback()
                    logger.warning(f"更新进度失败，未找到项目ID: {project_id_int}，可能记录不存在")
                    return False
            else:
                # 直接设置进度值（用于 initialized、completed、error_occurred 等特殊阶段）
                # 根据进度和阶段设置状态值
                if stage == "error_occurred" or progress == -1:
                    status_value = 3  # 失败状态
                elif stage == "initialized":
                    # 初始化阶段：强制设置为处理中状态（1），无论当前进度是多少
                    status_value = 1  # 处理中状态
                elif stage == "completed" or progress >= 100:
                    status_value = 2  # 完成状态
                elif progress >= 0:
                    status_value = 1  # 处理中状态
                else:
                    status_value = 1  # 初始状态也视为处理中
                    
                # 构建更新查询，如果提供了template_id则更新它
                # 对于initialized阶段，使用强制更新，确保进度被设置为0
                if stage == "initialized":
                    # 强制更新：无论当前进度是多少，都设置为0
                    if template_id is not None:
                        update_query = text("""
                                            UPDATE eval_report
                                            SET generate_progress = 0,
                                                status = :status,
                                                message = :message,
                                                template_id = :template_id,
                                                generate_time = NOW(),
                                                update_time = NOW()
                                            WHERE id = :project_id
                                            """)
                    else:
                        update_query = text("""
                                            UPDATE eval_report
                                            SET generate_progress = 0,
                                                status = :status,
                                                message = :message,
                                                generate_time = NOW(),
                                                update_time = NOW()
                                            WHERE id = :project_id
                                            """)
                else:
                    if template_id is not None:
                        update_query = text("""
                                            UPDATE eval_report
                                            SET generate_progress = :progress,
                                                status = :status,
                                                message = :message,
                                                template_id = :template_id,
                                                generate_time = NOW(),
                                                update_time = NOW()
                                            WHERE id = :project_id
                                            """)
                    else:
                        update_query = text("""
                                            UPDATE eval_report
                                            SET generate_progress = :progress,
                                                status = :status,
                                                message = :message,
                                                generate_time = NOW(),
                                                update_time = NOW()
                                            WHERE id = :project_id
                                            """)
                
                # 准备更新参数
                # 对于initialized阶段，progress参数不需要（直接使用0）
                if stage == "initialized":
                    update_params = {
                        "status": status_value,
                        "message": message,
                        "project_id": project_id_int
                    }
                else:
                    update_params = {
                        "progress": progress,
                        "status": status_value,
                        "message": message,
                        "project_id": project_id_int
                    }
                # 如果提供了template_id，添加到参数中
                if template_id is not None:
                    # 尝试将template_id转换为整数，如果失败则保持原值
                    try:
                        template_id_int = int(template_id)
                        update_params["template_id"] = template_id_int
                    except (ValueError, TypeError):
                        update_params["template_id"] = template_id
                
                result = session.execute(update_query, update_params)

                if result.rowcount > 0:
                    session.commit()
                    logger.info(f"✅ 解析任务进度更新成功: 项目{project_id} (ID: {project_id_int}) - 进度{progress}% - 状态{status_value} - 消息: {message}")
                    # 验证更新是否真的成功（在新会话中验证，避免使用已提交的会话）
                    # 注意：如果stage是initialized，需要强制确保进度为0
                    try:
                        import asyncio
                        # 等待一小段时间确保数据库事务已提交
                        await asyncio.sleep(0.1)
                        with db_manager.get_db_session() as verify_session:
                            verify_query = text("SELECT generate_progress, status FROM eval_report WHERE id = :project_id")
                            verify_result = verify_session.execute(verify_query, {"project_id": project_id_int}).fetchone()
                            if verify_result:
                                actual_progress, actual_status = verify_result[0], verify_result[1]
                                logger.info(f"✅ 验证更新结果: 实际进度={actual_progress}%, 实际状态={actual_status}")
                                if actual_progress != progress or actual_status != status_value:
                                    logger.error(f"❌ 更新验证失败: 期望进度={progress}%, 实际进度={actual_progress}%, 期望状态={status_value}, 实际状态={actual_status}")
                                    # 如果验证失败，尝试再次更新（使用FORCE UPDATE确保覆盖）
                                    logger.warning(f"⚠️ 尝试强制重新更新以修复不一致状态")
                                    retry_update_query = text("""
                                        UPDATE eval_report
                                        SET generate_progress = :progress,
                                            status = :status,
                                            message = :message,
                                            update_time = NOW()
                                        WHERE id = :project_id
                                    """)
                                    retry_result = verify_session.execute(retry_update_query, {
                                        "progress": progress,
                                        "status": status_value,
                                        "message": message,
                                        "project_id": project_id_int
                                    })
                                    if retry_result.rowcount > 0:
                                        verify_session.commit()
                                        logger.info(f"✅ 强制重新更新成功: 项目{project_id} (ID: {project_id_int})")
                                        # 再次验证
                                        await asyncio.sleep(0.1)
                                        verify_result2 = verify_session.execute(verify_query, {"project_id": project_id_int}).fetchone()
                                        if verify_result2:
                                            actual_progress2, actual_status2 = verify_result2[0], verify_result2[1]
                                            logger.info(f"✅ 重新更新后验证: 实际进度={actual_progress2}%, 实际状态={actual_status2}")
                                            if actual_progress2 != progress or actual_status2 != status_value:
                                                logger.error(f"❌ 重新更新后仍然不一致: 期望进度={progress}%, 实际进度={actual_progress2}%, 期望状态={status_value}, 实际状态={actual_status2}")
                                                # 可能是数据库触发器或其他机制在更新，记录警告
                                                logger.warning(f"⚠️ 可能存在数据库触发器或其他机制在更新进度和状态")
                    except Exception as verify_error:
                        logger.warning(f"⚠️ 验证更新结果时出错: {verify_error}")
                    return True
                else:
                    # 如果项目记录不存在，尝试创建新记录
                    logger.warning(f"⚠️ 未找到项目记录: {project_id} (ID: {project_id_int})，尝试创建新记录")
                    
                    # 先检查记录是否真的不存在（可能因为ID转换问题导致更新失败）
                    try:
                        check_query = text("SELECT id, generate_progress, status FROM eval_report WHERE id = :project_id")
                        existing_record = session.execute(check_query, {"project_id": project_id_int}).fetchone()
                        if existing_record:
                            # 记录存在但更新失败，可能是其他原因，记录警告并返回False
                            logger.error(f"项目记录存在但更新失败: {project_id} (ID: {project_id_int})，当前进度: {existing_record[1]}, 状态: {existing_record[2]}")
                            return False
                    except Exception as check_error:
                        logger.warning(f"检查记录是否存在时出错: {check_error}")
                
                # 创建基础的项目记录
                insert_query = text("""
                    INSERT INTO eval_report 
                    (id, template_id, name, content, reference_sources, generate_time, generate_progress, 
                     status, message, create_time, update_time, creator, tenant_id, tender_files, bid_files, 
                     bid_opening_form_files, expert_info_form_files, evaluation_summary_files, 
                     other_files) 
                    VALUES (:id, :template_id, :name, :content, :reference_sources, NOW(), 
                            :generate_progress, :status, :message, NOW(), NOW(), :creator, :tenant_id, 
                            :tender_files, :bid_files, :bid_opening_form_files, :expert_info_form_files, 
                            :evaluation_summary_files, :other_files)
                """)
                
                # 处理template_id：如果提供了则使用，否则尝试从现有记录获取，再不行则为None
                template_id_value = None
                if template_id is not None:
                    try:
                        template_id_value = int(template_id)
                    except (ValueError, TypeError):
                        template_id_value = template_id
                
                try:
                    session.execute(insert_query, {
                        "id": project_id_int,
                        "template_id": template_id_value,
                        "name": f"项目{project_id}",
                        "content": "",
                        "reference_sources": "",
                        "generate_progress": progress,
                        "status": status_value,  # 使用计算出的状态值
                        "message": message,
                        "creator": "system",
                        "tenant_id": "default",  # 使用字符串类型
                        "tender_files": "",
                        "bid_files": "",
                        "bid_opening_form_files": "",
                        "expert_info_form_files": "",
                        "evaluation_summary_files": "",
                        "other_files": "",
                    })
                    session.commit()
                    logger.info(f"成功创建新记录，使用项目ID: {project_id} (数据库ID: {project_id_int})")
                    logger.info(f"解析任务进度更新: 项目{project_id} - {progress}% - {message} - 状态{status_value}")
                    return True
                except Exception as insert_error:
                    # 如果插入失败（可能是主键冲突），尝试再次更新
                    logger.warning(f"创建新记录失败: {insert_error}，尝试再次更新现有记录")
                    session.rollback()
                    try:
                        # 再次尝试更新
                        retry_result = session.execute(update_query, update_params)
                        if retry_result.rowcount > 0:
                            session.commit()
                            logger.info(f"重试更新成功: 项目{project_id} (ID: {project_id_int}) - {progress}% - {message} - 状态{status_value}")
                            return True
                        else:
                            logger.error(f"重试更新仍然失败: 项目{project_id} (ID: {project_id_int})")
                            return False
                    except Exception as retry_error:
                        logger.error(f"重试更新时发生异常: {retry_error}")
                        return False

    except Exception as e:
        logger.error(f"更新解析任务进度失败: {e}")
        return False


async def update_parse_task_status(project_id: str, status: int, message: str = None, template_id: str = None) -> bool:
    """
    更新解析任务状态
    状态码：1=处理中，2=完成，3=失败
    
    Args:
        project_id: 项目ID
        status: 状态码（1=处理中，2=完成，3=失败）
        message: 状态消息（可选）
        template_id: 模板ID（可选）
        
    Returns:
        bool: 更新是否成功
    """
    try:
        with db_manager.get_db_session() as session:
            # 构建更新查询，如果提供了template_id则更新它
            if template_id is not None:
                update_query = text("""
                    UPDATE eval_report
                    SET status = :status,
                        message = :message,
                        template_id = :template_id,
                        update_time = NOW()
                    WHERE id = :project_id
                """)
            else:
                update_query = text("""
                    UPDATE eval_report
                    SET status = :status,
                        message = :message,
                        update_time = NOW()
                    WHERE id = :project_id
                """)
            
            # 尝试将项目ID转换为整数，如果失败则使用哈希值
            try:
                project_id_int = int(project_id)
            except ValueError:
                # 对于非数字项目ID，使用哈希值作为数字ID
                project_id_int = abs(hash(project_id)) % (10**10)  # 生成10位数字
            
            # 准备更新参数
            update_params = {
                "status": status,
                "message": message or f"状态更新为: {status}",
                "project_id": project_id_int
            }
            # 如果提供了template_id，添加到参数中
            if template_id is not None:
                try:
                    template_id_int = int(template_id)
                    update_params["template_id"] = template_id_int
                except (ValueError, TypeError):
                    update_params["template_id"] = template_id
            
            result = session.execute(update_query, update_params)
            
            if result.rowcount > 0:
                session.commit()
                logger.info(f"成功更新解析任务项目 {project_id} 的状态为 {status}，消息: {message}")
                return True
            else:
                logger.warning(f"未找到项目ID为 {project_id} 的记录，无法更新状态")
                return False
                
    except Exception as e:
        logger.error(f"更新解析任务状态失败: {e}")
        return False


async def set_parse_task_progress_direct(project_id: str, progress_value: int, message: str = None, template_id: str = None) -> bool:
    """
    直接设置解析任务进度值（不使用累加模式）
    
    Args:
        project_id: 项目ID
        progress_value: 进度值（0-100）
        message: 状态消息（可选）
        template_id: 模板ID（可选）
        
    Returns:
        bool: 更新是否成功
    """
    try:
        with db_manager.get_db_session() as session:
            # 尝试将项目ID转换为整数，如果失败则使用哈希值
            try:
                project_id_int = int(project_id)
            except ValueError:
                project_id_int = abs(hash(project_id)) % (10**10)
            
            # 根据进度值确定状态
            if progress_value < 0:
                status_value = 3  # 失败状态
            elif progress_value >= 100:
                status_value = 2  # 完成状态
            elif progress_value >= 0:
                status_value = 1  # 处理中状态
            else:
                status_value = 1  # 默认处理中
            
            # 构建更新查询
            if template_id is not None:
                update_query = text("""
                    UPDATE eval_report
                    SET generate_progress = :progress,
                        status = :status,
                        message = :message,
                        template_id = :template_id,
                        generate_time = NOW(),
                        update_time = NOW()
                    WHERE id = :project_id
                """)
            else:
                update_query = text("""
                    UPDATE eval_report
                    SET generate_progress = :progress,
                        status = :status,
                        message = :message,
                        generate_time = NOW(),
                        update_time = NOW()
                    WHERE id = :project_id
                """)
            
            update_params = {
                "progress": progress_value,
                "status": status_value,
                "message": message or f"进度更新为: {progress_value}%",
                "project_id": project_id_int
            }
            
            if template_id is not None:
                try:
                    template_id_int = int(template_id)
                    update_params["template_id"] = template_id_int
                except (ValueError, TypeError):
                    update_params["template_id"] = template_id
            
            result = session.execute(update_query, update_params)
            
            if result.rowcount > 0:
                session.commit()
                logger.info(f"直接设置进度成功: 项目{project_id} (ID: {project_id_int}) - 进度{progress_value}% - 状态{status_value} - 消息: {message}")
                return True
            else:
                logger.warning(f"未找到项目记录: {project_id} (ID: {project_id_int})，无法更新进度")
                return False
                
    except Exception as e:
        logger.error(f"直接设置进度失败: {e}")
        return False


async def _get_current_progress(project_id: str) -> int:
    """
    获取当前进度

    Args:
        project_id: 项目ID

    Returns:
        int: 当前进度百分比
    """
    try:
        with db_manager.get_db_session() as session:
            query = text("""
                         SELECT generate_progress
                         FROM eval_report
                         WHERE id = :project_id
                         """)
            
            # 尝试将项目ID转换为整数，如果失败则使用哈希值
            try:
                project_id_int = int(project_id)
            except ValueError:
                # 对于非数字项目ID，使用哈希值作为数字ID
                project_id_int = abs(hash(project_id)) % (10**10)  # 生成10位数字
            
            result = session.execute(query, {"project_id": project_id_int}).fetchone()

            if result and result[0] is not None:
                return int(result[0])
            else:
                return 0

    except Exception as e:
        logger.error(f"获取当前进度失败: {e}")
        return 0


async def _calculate_dynamic_progress(project_id: str) -> int:
    """
    实时查询任务状态并计算进度（统一方法）

    Args:
        project_id: 项目ID

    Returns:
        int: 进度百分比 (50-100)
    """
    try:
        # 查询当前任务处理状态
        with db_manager.get_db_session() as session:
            # 查询任务处理结果中的变量数量
            query = text("""
                         SELECT reference_sources
                         FROM eval_report
                         WHERE id = :project_id
                         """)
            
            # 尝试将项目ID转换为整数，如果失败则使用哈希值
            try:
                project_id_int = int(project_id)
            except ValueError:
                # 对于非数字项目ID，使用哈希值作为数字ID
                project_id_int = abs(hash(project_id)) % (10**10)  # 生成10位数字
            
            result = session.execute(query, {"project_id": project_id_int}).fetchone()

            if result and result[0]:
                # 解析任务结果，计算进度
                import json
                try:
                    task_results = json.loads(result[0])
                    # 根据任务结果动态计算进度
                    return await _calculate_progress_from_results(task_results)
                except:
                    return 80  # 默认进度
            else:
                return 80  # 默认进度

    except Exception as e:
        logger.error(f"计算动态进度失败: {e}")
        return 80


async def _calculate_progress_from_results(task_results: dict) -> int:
    """
    根据任务结果计算进度

    Args:
        task_results: 任务处理结果

    Returns:
        int: 进度百分比 (50-100)
    """
    try:
        # 简单的进度计算逻辑
        # 可以根据实际需求调整
        if isinstance(task_results, dict):
            # 根据结果中的任务数量或变量数量计算进度
            total_variables = 0
            completed_variables = 0

            for task_type, tasks in task_results.items():
                if isinstance(tasks, list):
                    for task in tasks:
                        if task.get("status") == "success":
                            completed_variables += 1
                        total_variables += 1

            if total_variables > 0:
                progress = 50 + int((completed_variables / total_variables) * 50)  # 修改为50，使最大进度可达100
                return min(progress, 100)  # 修改为100

        return 80  # 默认进度

    except Exception as e:
        logger.error(f"计算进度失败: {e}")
        return 80

if __name__ == "__main__":
    print(get_variables_values_by_id("1971057890226995202"))
