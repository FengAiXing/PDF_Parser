# 任务处理服务
import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from common.task_classifier import TaskClassifier, TaskType
from common.variable_templates import VariableTemplateManager
from prompts.prompt_templates import PromptTemplateManager
from common.llm_client import LLMClient
from src.business.service.content_extraction_service import ContentExtractionService
from src.utils.request_queue_manager import queue_manager


class TaskService:
    """任务处理服务类"""
    
    def __init__(self):
        """初始化服务"""
        self.task_classifier = TaskClassifier()
        self.variable_manager = VariableTemplateManager()
        self.prompt_manager = PromptTemplateManager()
        self.llm_client = LLMClient()
        self.content_extraction_service = ContentExtractionService()
    
    def classify_tasks(self, files_config: Dict[str, str]) -> Dict[str, List[Dict[str, str]]]:
        """
        根据文件类型分类任务
        
        Args:
            files_config: 文件配置字典
            
        Returns:
            Dict[str, List[Dict[str, str]]]: 分类后的任务组
        """
        return self.task_classifier.classify_files(files_config)
    
    def ensure_all_template_variables(self, extracted_variables: List[Dict[str, Any]], template_id: str) -> List[Dict[str, Any]]:
        """
        确保所有模板变量都出现在结果中，缺失的变量设置为null
        
        Args:
            extracted_variables: 已提取的变量列表
            template_id: 模板ID
            
        Returns:
            List[Dict[str, Any]]: 包含所有模板变量的完整列表
        """
        # 获取所有文件类型的变量（当前实现不区分模板类型）
        all_template_variables = set()
        file_types = [
            "tender_file",
            "candidate_bid_files", 
            "opening_record_file",
            "review_experts_file",
            "evaluation_summary_file",
            "other_files"
        ]
        
        for file_type in file_types:
            variables = self.variable_manager.get_variables_for_file_type(file_type)
            for var in variables:
                all_template_variables.add(var.name)
        
        # 去重处理：保留有值的变量，移除重复的空值变量
        unique_variables = {}
        for var in extracted_variables:
            if isinstance(var, dict) and "variable_name" in var:
                var_name = var["variable_name"]
                var_value = var.get("variable_value", "")
                
                # 如果变量不存在，或者当前变量有值而之前的为空值，则更新
                if var_name not in unique_variables or (var_value and not unique_variables[var_name].get("variable_value")):
                    unique_variables[var_name] = var
        
        # 重新构建变量列表
        extracted_variables = list(unique_variables.values())
        
        # 获取已提取的变量名称（包括有值的和空值的）
        extracted_variable_names = set(unique_variables.keys())
        
        # 找出缺失的变量（只添加真正缺失的变量，避免重复）
        missing_variables = all_template_variables - extracted_variable_names
        
        # 为缺失的变量创建空条目
        for missing_var_name in missing_variables:
            null_variable = {
                "variable_name": missing_var_name,
                "variable_value": "",
                "reference_source": {
                    "source_url": "",
                    "evidence_text": "",
                    "pages": "",
                    "file_type": ""
                }
            }
            extracted_variables.append(null_variable)
        
        # 详细记录未提取的变量
        if missing_variables:
            missing_list = sorted(list(missing_variables))
            logging.warning(f"⚠️ 未提取到的变量（共 {len(missing_variables)} 个）:")
            # 每10个变量一行，便于阅读
            for i in range(0, len(missing_list), 10):
                batch = missing_list[i:i+10]
                logging.warning(f"   未提取变量 {i+1}-{min(i+10, len(missing_list))}: {', '.join(batch)}")
        else:
            logging.info(f"✅ 所有模板变量都已提取")
        
        logging.info(f"确保所有模板变量完整性: 已提取 {len(extracted_variable_names)} 个，补充 {len(missing_variables)} 个null变量")
        
        return extracted_variables
    
    async def process_task_groups(
        self, 
        task_groups: Dict[str, List[Dict[str, str]]], 
        project_id: str, 
        template_id: str,
        merged_contents: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        处理各类任务组（并发处理）- 支持排队机制
        
        Args:
            task_groups: 分类后的任务组
            project_id: 项目ID
            template_id: 模板ID
            merged_contents: 已下载和合并的文件内容（可选）
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 如果merged_contents为None，说明需要先进行文件解析和合并
        if merged_contents is None:
            logging.info(f"项目 {project_id} 需要先进行文件解析和合并")
            # 这里会触发排队机制
            from src.business.service.file_process_service import FileProcessService
            file_service = FileProcessService()
            merged_contents = await file_service.parse_and_merge_files(task_groups, project_id)
        
        # 文件解析和合并完成后，后续步骤可以并行执行
        logging.info(f"项目 {project_id} 文件解析完成，开始后续并行处理")
        # 并发处理常规任务和大文件任务
        tasks_to_run = []
        
        if "regular_tasks" in task_groups and task_groups["regular_tasks"]:
            tasks_to_run.append(
                self.process_regular_tasks(
                    task_groups["regular_tasks"], 
                    project_id, 
                    template_id,
                    merged_contents
                )
            )
        
        if "large_file_tasks" in task_groups and task_groups["large_file_tasks"]:
            tasks_to_run.append(
                self.process_large_file_tasks(
                    task_groups["large_file_tasks"], 
                    project_id, 
                    template_id,
                    merged_contents
                )
            )
        
        # 并发执行所有任务组
        if tasks_to_run:
            try:
                # 使用 return_exceptions=True 来立即捕获异常
                results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
                
                # 检查是否有异常
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        # 发现异常，立即更新进度并抛出异常
                        from database.data_process import update_report_progress
                        await update_report_progress(project_id, "error_occurred", f"任务处理失败: {str(result)}")
                        raise result
                
                # 所有任务完成后，更新进度为90%
                from database.data_process import update_report_progress
                await update_report_progress(project_id, "all_tasks_completed", "所有任务处理完成")
            except Exception as e:
                # 任务失败时更新进度为错误状态
                from database.data_process import update_report_progress
                await update_report_progress(project_id, "error_occurred", f"任务处理失败: {str(e)}")
                raise e

            # 提取所有变量，只保留变量内容
            all_variables = []
            result_index = 0
            
            if "regular_tasks" in task_groups and task_groups["regular_tasks"]:
                regular_results = results[result_index]
                result_index += 1
                
                # 从常规任务结果中提取变量
                for task_result in regular_results:
                    if isinstance(task_result, dict) and "extracted_result" in task_result:
                        extracted_vars = task_result["extracted_result"]
                        if isinstance(extracted_vars, list):
                            all_variables.extend(extracted_vars)
            
            if "large_file_tasks" in task_groups and task_groups["large_file_tasks"]:
                large_results = results[result_index]
                
                # 从大文件任务结果中提取变量
                for task_result in large_results:
                    if isinstance(task_result, dict) and "extracted_result" in task_result:
                        extracted_vars = task_result["extracted_result"]
                        if isinstance(extracted_vars, list):
                            all_variables.extend(extracted_vars)
            
            # 确保所有模板变量都出现在结果中
            all_variables = self.ensure_all_template_variables(all_variables, template_id)
            
            # 第2、3、4次模型调用：预处理变量（提取候选人数量、名称和详细信息）
            logging.info("开始执行第2、3、4次模型调用（预处理变量）...")
            from src.utils.pre_variables import preprocess_variables
            all_variables = await preprocess_variables(all_variables, merged_contents)
            logging.info(f"第2、3、4次模型调用完成，最终变量数量: {len(all_variables)}")
            
            return all_variables
        
        return {}
    
    async def process_regular_tasks_only_first_step(
        self,
        tasks: List[Dict[str, str]],
        project_id: str,
        template_id: str,
        merged_contents: Dict[str, str] = None
    ) -> List[Dict[str, Any]]:
        """
        处理常规任务，只进行第一步变量提取（不进行后续的preprocess_variables处理）
        
        Args:
            tasks: 常规任务列表
            project_id: 项目ID
            template_id: 模板ID
            merged_contents: 已下载和合并的文件内容（可选）
            
        Returns:
            List[Dict[str, Any]]: 所有文件的变量提取结果列表
        """
        # 并发处理所有常规任务
        tasks_coroutines = [
            self.process_single_regular_task(task, project_id, template_id, merged_contents)
            for task in tasks
        ]
        
        # 等待所有任务完成
        try:
            results = await asyncio.gather(*tasks_coroutines)
            
            # 提取所有变量
            all_variables = []
            for result in results:
                if isinstance(result, dict) and "extracted_result" in result:
                    extracted_vars = result["extracted_result"]
                    if isinstance(extracted_vars, list):
                        all_variables.extend(extracted_vars)
            
            logging.info(f"常规任务第一步变量提取完成，共提取 {len(all_variables)} 个变量")
            return all_variables
            
        except Exception as e:
            logging.error(f"常规任务第一步变量提取失败: {str(e)}")
            from database.data_process import update_report_progress
            await update_report_progress(project_id, "error_occurred", f"常规任务处理失败: {str(e)}")
            raise e
    
    async def process_regular_tasks(
        self, 
        tasks: List[Dict[str, str]], 
        project_id: str, 
        template_id: str,
        merged_contents: Dict[str, str] = None
    ) -> List[Dict[str, Any]]:
        """
        处理常规任务（并发处理）
        
        Args:
            tasks: 常规任务列表
            project_id: 项目ID
            template_id: 模板ID
            merged_contents: 已下载和合并的文件内容（可选）
            
        Returns:
            List[Dict[str, Any]]: 处理结果列表
        """
        # 并发处理所有常规任务
        tasks_coroutines = [
            self.process_single_regular_task(task, project_id, template_id, merged_contents)
            for task in tasks
        ]
        
        # 等待所有任务完成 - 遇到任何异常立即中断
        try:
            results = await asyncio.gather(*tasks_coroutines)
            return results
        except Exception as e:
            # 任何任务失败都立即中断整个流程
            logging.error(f"常规任务处理失败: {str(e)}")
            # 更新进度为错误状态
            from database.data_process import update_report_progress
            await update_report_progress(project_id, "error_occurred", f"常规任务处理失败: {str(e)}")
            raise e
    
    async def process_single_regular_task(
        self, 
        task: Dict[str, str], 
        project_id: str, 
        template_id: str,
        merged_contents: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        处理单个常规任务
        
        Args:
            task: 单个任务信息
            project_id: 项目ID
            template_id: 模板ID
            merged_contents: 已下载和合并的文件内容（可选）
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 获取文件类型和URL
            file_type = task["file_type"]
            file_url = task["file_url"]
            
            logging.info(f"[常规任务] 开始处理文件: {file_url} (类型: {file_type})")
            
            # 第一步：获取需要提取的变量
            logging.info(f"[步骤1] 获取文件类型 {file_type} 的变量定义...")
            variables = self.variable_manager.get_variables_for_file_type(file_type)
            logging.info(f"[步骤1] 完成 - 获取到 {len(variables)} 个变量定义")
            
            # 如果变量列表为空，跳过此文件（如candidate_bid_files在第四次模型调用时单独处理）
            if not variables:
                logging.info(f"[跳过] 文件类型 {file_type} 没有变量定义，跳过处理")
                return {
                    "file_type": file_type,
                    "file_url": file_url,
                    "extracted_result": [],
                    "variables_definition": [],
                    "template_name": template_id
                }
            
            # 第二步：生成提示词（默认包含来源追踪）
            logging.info(f"[步骤2] 生成提示词...")
            prompt = self.prompt_manager.generate_prompt(file_type, variables, file_url)
            logging.info(f"[步骤2] 完成 - 提示词生成成功 (长度: {len(prompt)} 字符)")
            
            # 第三步：下载文件并提取内容（已集成模型提取功能）
            # 优先使用预下载的内容，避免重复下载
            logging.info(f"[步骤3] 开始文件处理和内容提取...")
            # 使用ContentExtractionService进行内容提取
            from src.business.service.content_extraction_service import ContentExtractionService
            content_service = ContentExtractionService()
            file_content = await content_service._download_and_extract_content(file_url, file_type, variables, merged_contents)
            logging.info(f"[步骤3] 完成 - 文件内容提取成功")
            
            # 第四步：解析模型提取的JSON结果
            logging.info(f"[步骤4] 解析模型提取结果...")
            try:
                normalized_result = json.loads(file_content)
                logging.info(f"[步骤4] 完成 - JSON解析成功，提取到 {len(normalized_result)} 个变量")
            except json.JSONDecodeError as e:
                logging.error(f"[步骤4] 失败 - JSON解析错误: {e}")
                logging.error(f"文件内容前500字符: {file_content[:500]}")
                # JSON解析失败时返回空结果
                normalized_result = []
            
            # 转换variables为可序列化的字典格式
            logging.info(f"[步骤5] 转换变量格式...")
            variables_dict = []
            for var in variables:
                variables_dict.append({
                    "name": var.name,
                    "english_name": var.english_name,
                    "description": var.description,
                    "data_type": var.data_type,
                    "extraction_rule": var.extraction_rule,
                    "keywords": var.keywords,
                    "examples": var.examples
                })
            logging.info(f"[步骤5] 完成 - 变量格式转换成功")
            
            logging.info(f"[常规任务] 处理完成: {file_url}")

            # 触发点2：实时查询并更新进度
            # 注意：这里不更新进度，因为进度更新应该在更高层级统一管理
            # 避免多次调用导致进度混乱
            pass

            return {
                "file_type": file_type,
                "file_url": file_url,
                "extracted_result": normalized_result,
                "status": "success"
            }
            
        except Exception as e:
            logging.error(f"[常规任务] 处理失败: {task.get('file_url', 'unknown')} - {str(e)}")
            # 更新进度为错误状态
            from database.data_process import update_report_progress
            await update_report_progress(project_id, "error_occurred", f"常规任务处理失败: {str(e)}")
            # 直接抛出异常，中断整个流程
            raise e
    
    async def process_large_file_tasks(
        self, 
        tasks: List[Dict[str, str]], 
        project_id: str, 
        template_id: str,
        merged_contents: Dict[str, str] = None
    ) -> List[Dict[str, Any]]:
        """
        处理大文件任务（候选人投标文件）- 完全并发处理，支持超时控制
        
        Args:
            tasks: 大文件任务列表
            project_id: 项目ID
            template_id: 模板ID
            merged_contents: 已下载和合并的文件内容（可选）
            
        Returns:
            List[Dict[str, Any]]: 处理结果列表
        """
        # 完全并发处理所有大文件任务，不限制并发数，支持超时控制
        tasks_coroutines = [
            self._process_single_large_file_task_with_timeout(task, project_id, template_id, merged_contents)
            for task in tasks
        ]
        
        # 等待所有任务完成 - 遇到任何异常立即中断
        try:
            results = await asyncio.gather(*tasks_coroutines, return_exceptions=True)
            
            # 检查是否有异常
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logging.error(f"大文件任务处理失败: {tasks[i]}, 错误: {result}")
                    # 更新进度为错误状态
                    from database.data_process import update_report_progress
                    await update_report_progress(project_id, "error_occurred", f"大文件任务处理失败: {str(result)}")
                    raise result
            
            return results
        except Exception as e:
            # 任何任务失败都立即中断整个流程
            logging.error(f"大文件任务处理失败: {str(e)}")
            # 更新进度为错误状态
            from database.data_process import update_report_progress
            await update_report_progress(project_id, "error_occurred", f"大文件任务处理失败: {str(e)}")
            raise e
    
    async def _process_single_large_file_task_with_timeout(
        self, 
        task: Dict[str, str], 
        project_id: str, 
        template_id: str,
        merged_contents: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        处理单个大文件任务，支持超时控制
        
        Args:
            task: 单个任务信息
            project_id: 项目ID
            template_id: 模板ID
            merged_contents: 已下载和合并的文件内容（可选）
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 使用asyncio.wait_for添加超时控制，避免单个文件阻塞整个流程
            result = await asyncio.wait_for(
                self.process_single_large_file_task(task, project_id, template_id, merged_contents),
                timeout=3600  # 1小时超时
            )
            return result
        except asyncio.TimeoutError:
            logging.error(f"大文件任务处理超时: {task.get('file_url', 'unknown')}")
            # 更新进度为错误状态
            from database.data_process import update_report_progress
            await update_report_progress(project_id, "error_occurred", f"大文件任务处理超时: {task.get('file_url', 'unknown')}")
            raise Exception(f"大文件任务处理超时: {task.get('file_url', 'unknown')}")
        except Exception as e:
            logging.error(f"大文件任务处理失败: {task.get('file_url', 'unknown')}, 错误: {e}")
            # 更新进度为错误状态
            from database.data_process import update_report_progress
            await update_report_progress(project_id, "error_occurred", f"大文件任务处理失败: {str(e)}")
            raise e
    
    async def process_single_large_file_task(
        self, 
        task: Dict[str, str], 
        project_id: str, 
        template_id: str,
        merged_contents: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        处理单个大文件任务 - 优化的大文件处理流程
        
        Args:
            task: 单个任务信息
            project_id: 项目ID
            template_id: 模板ID
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        try:
            # 获取文件类型和URL
            file_type = task["file_type"]
            file_url = task["file_url"]
            
            logging.info(f"[大文件任务] 开始处理文件: {file_url} (类型: {file_type})")
            
            # 第一步：获取需要提取的变量
            logging.info(f"[步骤1] 获取文件类型 {file_type} 的变量定义...")
            variables = self.variable_manager.get_variables_for_file_type(file_type)
            logging.info(f"[步骤1] 完成 - 获取到 {len(variables)} 个变量定义")
            
            # 如果变量列表为空，跳过此文件（如candidate_bid_files在第四次模型调用时单独处理）
            if not variables:
                logging.info(f"[跳过] 文件类型 {file_type} 没有变量定义，跳过处理")
                return {
                    "file_type": file_type,
                    "file_url": file_url,
                    "extracted_result": [],
                    "variables_definition": [],
                    "template_name": template_id
                }
            
            # 第二步：生成提示词（默认包含来源追踪）
            logging.info(f"[步骤2] 生成提示词...")
            prompt = self.prompt_manager.generate_prompt(file_type, variables, file_url)
            logging.info(f"[步骤2] 完成 - 提示词生成成功 (长度: {len(prompt)} 字符)")
            
            # 第三步：下载文件并提取内容（已集成模型提取功能）
            # 优先使用预下载的内容，避免重复下载（注：大文件目前仍需下载以支持关键字截取）
            logging.info(f"[步骤3] 开始大文件处理和内容提取...")
            # 使用ContentExtractionService进行内容提取
            from src.business.service.content_extraction_service import ContentExtractionService
            content_service = ContentExtractionService()
            file_content = await content_service._download_and_extract_content(file_url, file_type, variables, merged_contents)
            logging.info(f"[步骤3] 完成 - 大文件内容提取成功")
            
            # 第四步：解析模型提取的JSON结果
            logging.info(f"[步骤4] 解析模型提取结果...")
            try:
                normalized_result = json.loads(file_content)
                logging.info(f"[步骤4] 完成 - JSON解析成功，提取到 {len(normalized_result)} 个变量")
            except json.JSONDecodeError as e:
                logging.error(f"[步骤4] 失败 - JSON解析错误: {e}")
                logging.error(f"文件内容前500字符: {file_content[:500]}")
                # JSON解析失败时返回空结果
                normalized_result = []
            
            # 转换variables为可序列化的字典格式
            logging.info(f"[步骤5] 转换变量格式...")
            variables_dict = []
            for var in variables:
                variables_dict.append({
                    "name": var.name,
                    "english_name": var.english_name,
                    "description": var.description,
                    "data_type": var.data_type,
                    "extraction_rule": var.extraction_rule,
                    "keywords": var.keywords,
                    "examples": var.examples
                })
            logging.info(f"[步骤5] 完成 - 变量格式转换成功")
            
            # 记录优化信息
            if file_type == "candidate_bid_files":
                logging.info(f"[优化] 使用了关键字截取优化处理")
            
            logging.info(f"[大文件任务] 处理完成: {file_url}")

            # 触发点2：实时查询并更新进度（大文件任务）
            # 注意：这里不更新进度，因为进度更新应该在更高层级统一管理
            # 避免多次调用导致进度混乱
            pass

            return {
                "file_type": file_type,
                "file_url": file_url,
                "extracted_result": normalized_result,
                "content_optimization": file_type == "candidate_bid_files",
                "status": "success"
            }
            
        except Exception as e:
            logging.error(f"[大文件任务] 处理失败: {task.get('file_url', 'unknown')} - {str(e)}")
            # 更新进度为错误状态
            from database.data_process import update_report_progress
            await update_report_progress(project_id, "error_occurred", f"大文件任务处理失败: {str(e)}")
            # 直接抛出异常，中断整个流程
            raise e
    
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理任务（支持多种任务类型）
        
        Args:
            task: 任务信息，包含task_id、task_type、parameters等
            
        Returns:
            Dict: 处理结果
        """
        task_type = task["task_type"]
        
        if task_type == "bid_report":
            return await self.process_bid_report_task(task)
        elif task_type == "parse_task":
            return await self.process_parse_task(task)
        elif task_type == "single_file_report_re_generate":
            return await self.process_single_file_report_re_generate_task(task)
        else:
            # 其他任务类型的处理逻辑
            return await self._process_unknown_task(task)
    
    async def process_bid_report_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理评标报告生成任务
        
        Args:
            task: 任务信息，包含task_id、parameters等
            
        Returns:
            Dict: 处理结果
        """
        parameters = task["parameters"]
        
        project_id = parameters["project_id"]
        template_id = parameters["template_id"]
        files_config = parameters["files_config"]
        
        try:
            # 调用业务服务生成报告
            from src.business.service.bid_report_service import BidReportService
            bid_report_service = BidReportService()
            result = await bid_report_service.generate_bid_report(
                project_id=project_id,
                template_id=template_id,
                files_config=files_config
            )
            
            return result
            
        except Exception as e:
            # 确保进度状态被更新到数据库
            from database.data_process import update_report_progress
            await update_report_progress(project_id, "error_occurred", f"任务处理失败: {str(e)}", template_id)
            # 重新抛出异常，让任务处理器处理
            raise e
    
    async def process_parse_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理解析任务
        
        Args:
            task: 任务信息，包含task_id、parameters等
            
        Returns:
            Dict: 处理结果
        """
        parameters = task["parameters"]
        
        project_id = parameters["project_id"]
        
        try:
            # 调用解析任务服务
            from src.business.service.parse_task_service import ParseTaskService
            parse_task_service = ParseTaskService()
            result = await parse_task_service.process_parse_task(
                project_id=project_id
            )
            
            return result
            
        except Exception as e:
            # 确保进度状态被更新到数据库（parse_task_service已经处理了状态和进度更新，这里只是作为备用）
            from database.data_process import update_parse_task_progress, update_parse_task_status
            await update_parse_task_progress(project_id, "error_occurred", f"解析任务处理失败: {str(e)}", None)
            await update_parse_task_status(project_id, status=3, message=f"解析任务处理失败: {str(e)}")
            # 重新抛出异常，让任务处理器处理
            raise e

    async def process_single_file_report_re_generate_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个投标文件评标报告重新生成任务
        
        Args:
            task: 任务信息，包含task_id、parameters等
            
        Returns:
            Dict: 处理结果
        """
        parameters = task["parameters"]
        
        project_id = parameters["project_id"]
        bid_url = parameters["bid_url"]
        
        try:
            # 注意：进度和状态已在API接口接收请求时初始化（进度0%，状态1）
            # 已注释：进度和状态更新
            # 这里不再重复初始化，直接开始处理
            # from database.data_process import update_parse_task_progress, update_parse_task_status
            
            # 调用重新生成服务
            from src.business.service.report_regeneration_service import single_file_report_re_generate
            result, report = await single_file_report_re_generate(
                project_id=project_id,
                bid_url=bid_url
            )
            
            # 更新进度和状态：任务完成
            # 已注释：进度和状态更新
            # await update_parse_task_progress(str(project_id), "completed", "单个投标文件报告重新生成完成", None)
            # await update_parse_task_status(str(project_id), 2, "单个投标文件报告重新生成完成", None)
            
            # 返回结果，包含result和report
            return {
                "result": result,
                "report": report
            }
            
        except Exception as e:
            # 更新进度和状态：任务失败
            # 已注释：进度和状态更新
            # from database.data_process import update_parse_task_progress, update_parse_task_status
            # await update_parse_task_progress(str(project_id), "error_occurred", f"单个投标文件报告重新生成失败: {str(e)}", None)
            # await update_parse_task_status(str(project_id), 3, f"单个投标文件报告重新生成失败: {str(e)}", None)
            
            # 记录错误日志
            logging.error(f"单个投标文件报告重新生成失败: {str(e)}", exc_info=True)
            # 重新抛出异常，让任务处理器处理
            raise e
    
    async def _process_unknown_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理未知任务类型
        
        Args:
            task: 任务信息
            
        Returns:
            Dict: 处理结果
        """
        # 模拟处理过程
        await asyncio.sleep(1)
        
        return {
            "message": f"任务类型 {task['task_type']} 处理完成",
            "data": task["parameters"]
        }
    