# 评标报告生成业务服务
import asyncio
import json
import logging
import re
import os
from typing import Dict, List, Any, Optional, Union, Tuple
from src.business.service.file_process_service import FileProcessService
from src.business.service.task_service import TaskService
from src.business.service.report_generation_service import ReportGenerationService
from src.business.service.complex_file_service import ComplexFileService
from database.data_process import save_final_report_to_database
from database.file_info_service import save_file_info_and_range, batch_save_file_info_and_range, update_reference_sources, update_file_range_page_range, delete_file_info_and_range_by_project_id
from src.utils.file_range_filter.performance_content_filter import PerformanceContentFilter
from src.utils.file_range_filter.qualification_content_filter import QualificationContentFilter
from src.utils.file_range_filter.other_clauses_content_filter import OtherClausesContentFilter

class BidReportService:
    """评标报告生成业务服务类""" 
    def __init__(self):
        """初始化服务"""
        self.file_service = FileProcessService()
        self.task_service = TaskService()
        self.report_service = ReportGenerationService()
        self.complex_file_service = ComplexFileService()
    
    async def generate_bid_report(
        self, 
        project_id: str, 
        template_id: str, 
        files_config: Union[Dict[str, str], str, dict]
    ) -> Dict[str, Any]:
        """
        生成评标报告的主入口方法
        
        Args:
            project_id: 项目ID
            template_id: 模板ID
            files_config: 文件配置（可以是字典、JSON字符串或JSON对象）
            
        Returns:
            Dict[str, Any]: 生成结果
        """
        from database.data_process import update_report_status
        merged_contents: Optional[Dict[str, Any]] = None
        try:
            # 开始时更新状态为处理中（status=7）
            await update_report_status(project_id, status=7, message="开始处理", template_id=template_id)
            logging.info(f"已更新状态为处理中（status=7），项目ID: {project_id}")
            # 第一步：解析文件配置（支持多种输入格式）
            parsed_files_config = self.file_service.parse_files_config(files_config)
            logging.info(f"第一步完成 - 文件配置解析: {len(parsed_files_config)} 个文件")
            
            # 第二步：任务分类
            task_groups = self.task_service.classify_tasks(parsed_files_config)
            logging.info(f"第二步完成 - 任务分类: {list(task_groups.keys())}")
            
            # 第三步：解析和合并文件内容（下载文件并提取原始内容）
            merged_contents = await self.file_service.parse_and_merge_files(task_groups, project_id)
            logging.info(f"第三步完成 - 文件内容合并: {list(merged_contents.keys())}")
            
            # 第四步：保存解析结果到数据库（目前只记录日志，预留功能）
            save_success = self.file_service.save_parsed_content_to_database(merged_contents, project_id)
            if not save_success:
                raise Exception("解析结果保存到数据库失败")
            logging.info(f"第四步完成 - 解析结果已保存到数据库")

            # 触发点1：文件处理完成
            from database.data_process import update_report_progress
            await update_report_progress(project_id, "files_processed", "文件处理完成", template_id)

            # 第五步：分离处理流程（并发处理）
            regular_tasks = task_groups.get("regular_tasks", [])
            large_file_tasks = task_groups.get("large_file_tasks", [])
            regular_variables = []
            clauses = {"qualification": [], "business": []}
            complex_file_results = []
            
            # 并发处理五种类型文件和复杂文件
            tasks_to_run = []
            
            # 5.1 处理五种类型文件（只进行第一步变量提取）
            if regular_tasks:
                logging.info(f"开始处理五种类型文件，共 {len(regular_tasks)} 个文件")
                tasks_to_run.append(
                    self.task_service.process_regular_tasks_only_first_step(
                        regular_tasks, project_id, template_id, merged_contents
                    )
                )
            
            # 5.2 处理复杂文件（candidate_bid_files）- 提取投标人名称
            if large_file_tasks:
                logging.info(f"开始处理复杂文件，共 {len(large_file_tasks)} 个文件")
                complex_file_urls = [task["file_url"] for task in large_file_tasks]
                tasks_to_run.append(
                    self.complex_file_service.process_complex_files(
                        complex_file_urls, project_id, merged_contents
                    )
                )
            
            # 并发执行所有任务
            if tasks_to_run:
                await update_report_progress(project_id, "tasks_processing", "开始并发处理所有文件", template_id)
                results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
                
                # 处理结果
                result_index = 0
                
                # 处理五种类型文件的结果
                if regular_tasks:
                    if isinstance(results[result_index], Exception):
                        error_msg = f"五种类型文件处理失败: {results[result_index]}"
                        logging.error(error_msg)
                        await update_report_status(project_id, status=9, message=error_msg, template_id=template_id)
                        raise results[result_index]
                    regular_variables = results[result_index]
                    result_index += 1
                    
                    logging.info(f"五种类型文件第一步变量提取完成: {len(regular_variables)} 个变量")
                    
                    # 提取资格评审标准和商务评分标准的条款
                    clauses = self._extract_clauses_from_variables(regular_variables)
                    logging.info(f"提取到条款 - 资格评审标准: {len(clauses.get('qualification', []))} 个, 商务评分标准: {len(clauses.get('business', []))} 个")
                    
                    # 保存五种类型文件的提取结果到reference_sources
                    await update_report_progress(project_id, "regular_files_processed", "五种类型文件处理完成", template_id)
                    save_success = update_reference_sources(project_id, regular_variables)
                    if not save_success:
                        error_msg = f"reference_sources保存失败，项目ID: {project_id}"
                        logging.warning(error_msg)
                        await update_report_status(project_id, status=9, message=error_msg, template_id=template_id)
                
                # 处理复杂文件的结果
                if large_file_tasks:
                    if isinstance(results[result_index], Exception):
                        error_msg = f"复杂文件处理失败: {results[result_index]}"
                        logging.error(error_msg)
                        await update_report_status(project_id, status=9, message=error_msg, template_id=template_id)
                        raise results[result_index]
                    complex_file_results = results[result_index]
                    
                    logging.info(f"复杂文件投标人名称提取完成: {len(complex_file_results)} 个文件")
                    
                    # 根据条款和投标文件生成file_info和file_range数据
                    if clauses.get("qualification") or clauses.get("business"):
                        try:
                            await self._generate_and_save_file_info_and_range(
                                project_id, complex_file_results, clauses
                            )
                            logging.info(f"file_info和file_range数据保存完成")
                        except Exception as e:
                            error_msg = f"file_info和file_range数据保存失败: {str(e)}"
                            logging.error(error_msg)
                            await update_report_status(project_id, status=9, message=error_msg, template_id=template_id)
                            raise
                    else:
                        logging.warning("未找到任何条款，跳过file_info和file_range数据生成")
            
            # 原有的后续处理流程（如果需要继续生成报告）
            # 注意：这里只处理了第一步变量提取，后续的preprocess_variables等步骤不再执行
            # 更新进度到100%表示完成（all_files_processed已经是100%）
            await update_report_progress(project_id, "all_files_processed", "所有文件处理完成", template_id)
            
            # 成功完成时更新状态为完成（status=8）
            # update_report_progress会自动将状态更新为8（因为进度>=100），但为了确保实时更新，这里也显式更新
            await update_report_status(project_id, status=8, message="文件处理完成，已保存到数据库", template_id=template_id)
            logging.info(f"已更新状态为完成（status=8），项目ID: {project_id}")
            
            return {
                "project_id": project_id,
                "template_id": template_id,
                "status": "completed",
                "message": "文件处理完成，已保存到数据库"
            }

            
        except Exception as e:
            # 失败时更新状态为错误（status=9）
            await update_report_status(project_id, status=9, message=f"报告生成流程失败: {str(e)}", template_id=template_id)
            logging.error(f"已更新状态为错误（status=9），项目ID: {project_id}，错误: {str(e)}")
            # 直接抛出异常，中断整个流程
            raise e
        finally:
            try:
                await self.file_service.cleanup_candidate_bid_files_temp_dirs(merged_contents)
            except Exception as cleanup_error:
                logging.error(f"清理candidate_bid_files临时目录失败: {cleanup_error}", exc_info=True)
    
    def _extract_clauses_from_variables(self, variables: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        从变量列表中提取资格评审标准和商务评分标准的条款
        
        Args:
            variables: 变量列表
            
        Returns:
            Dict[str, List[str]]: 包含qualification和business两个键的字典
        """
        clauses = {
            "qualification": [],
            "business": []
        }
        
        for var in variables:
            if isinstance(var, dict) and "variable_name" in var:
                var_name = var.get("variable_name", "")
                var_value = var.get("variable_value", "")
                
                if var_name == "资格评审标准" and var_value:
                    # 解析资格评审标准的条款（可能是用|、|、或逗号分隔）
                    qualification_clauses = self._parse_clauses(var_value)
                    clauses["qualification"] = qualification_clauses
                
                elif var_name == "商务评分标准" and var_value:
                    # 解析商务评分标准的条款
                    business_clauses = self._parse_clauses(var_value)
                    clauses["business"] = business_clauses
        
        return clauses
    
    def _parse_clauses(self, clauses_text: str) -> List[str]:
        """
        解析条款文本，提取条款列表
        
        Args:
            clauses_text: 条款文本（可能用|、|、或逗号分隔）
            
        Returns:
            List[str]: 条款列表
        """
        if not clauses_text or not clauses_text.strip():
            return []
        
        # 尝试多种分隔符
        separators = ["|", "、", "，", ","]
        clauses = [clauses_text]
        
        for sep in separators:
            if sep in clauses_text:
                clauses = [c.strip() for c in clauses_text.split(sep) if c.strip()]
                break
        
        return clauses
    
    def _find_page_for_position(self, full_text: str, position: int) -> Optional[int]:
        """
        根据文本位置找到对应的页码
        
        Args:
            full_text: 完整文本（包含页码标记）
            position: 文本位置（字符索引）
            
        Returns:
            Optional[int]: 页码（从1开始），如果找不到返回None
        """
        try:
            # 查找所有页码标记，支持多种格式
            page_markers = []
            
            # 格式1: === 第X页 ===
            for match in re.finditer(r'=== 第(\d+)页 ===', full_text):
                page_num = int(match.group(1))
                page_markers.append((match.start(), page_num))
            
            # 格式2: [当前页码: X]
            for match in re.finditer(r'\[当前页码:\s*(\d+)\]', full_text):
                page_num = int(match.group(1))
                page_markers.append((match.start(), page_num))
            
            # 格式3: ===== 第X页 =====
            for match in re.finditer(r'=====\s*第(\d+)页\s*=====', full_text):
                page_num = int(match.group(1))
                page_markers.append((match.start(), page_num))
            
            if not page_markers:
                logging.warning("文本中未找到页码标记")
                return None
            
            # 按位置排序
            page_markers.sort(key=lambda x: x[0])
            
            # 找到位置所在的页面
            for i, (marker_pos, page_num) in enumerate(page_markers):
                if position >= marker_pos:
                    if i + 1 < len(page_markers):
                        next_marker_pos = page_markers[i + 1][0]
                        if position < next_marker_pos:
                            return page_num
                    else:
                        # 最后一个页面
                        return page_num
            
            # 如果位置在第一个标记之前，返回第一页
            if page_markers:
                return page_markers[0][1]
            
            return None
            
        except Exception as e:
            logging.error(f"查找页码失败: {e}")
            return None
    
    def _remove_first_n_pages(self, content: str, n: int = 10) -> str:
        """
        去除PDF内容的前N页
        
        Args:
            content: PDF文本内容（带页码标记）
            n: 要跳过的页数，默认10页
            
        Returns:
            str: 去除前N页后的内容（保留原始页码编号）
        """
        if not content:
            return content
        
        # 查找第一个页码标记的位置（第(n+1)页，即第11页）
        # 支持多种页码标记格式
        patterns = [
            (r'=== 第(\d+)页 ===', r'=== 第{}页 ==='),  # 格式1: === 第X页 ===
            (r'\[当前页码:\s*(\d+)\]', r'[当前页码: {}]'),  # 格式2: [当前页码: X]
            (r'=====\s*第(\d+)页\s*=====', r'===== 第{}页 ====='),  # 格式3: ===== 第X页 =====
        ]
        
        # 查找第(n+1)页的起始位置
        start_pos = None
        for pattern, _ in patterns:
            # 查找所有页码标记
            for match in re.finditer(pattern, content):
                page_num = int(match.group(1))
                if page_num == n + 1:  # 第11页
                    start_pos = match.start()
                    logging.info(f"找到第{n+1}页起始位置: {start_pos}")
                    break
            if start_pos is not None:
                break
        
        if start_pos is None:
            logging.warning(f"未找到第{n+1}页，可能PDF页数不足{n+1}页")
            return ""
        
        # 提取第(n+1)页及以后的内容
        result = content[start_pos:]
        logging.info(f"已去除前{n}页，保留第{n+1}页及以后的内容")
        return result
    
    async def _get_file_content_with_pages(self, file_url: str, file_path: Optional[str] = None) -> Optional[str]:
        """
        获取文件的原始文本内容（带页码标记），去除前10页
        
        Args:
            file_url: 文件URL或本地文件路径
            file_path: 已处理的文件路径（如果已知，优先使用）
            
        Returns:
            Optional[str]: 文件文本内容（已去除前10页），如果失败返回None
        """
        try:
            from src.utils.async_file_process import AsyncFileProcessor
            
            file_processor = AsyncFileProcessor()
            
            # 优先使用已提供的文件路径
            if file_path and os.path.exists(file_path):
                logging.info(f"使用已处理的文件路径: {file_path}")
                content = file_processor._extract_pdf_content(file_path)
                if content:
                    # 去除前10页
                    content = self._remove_first_n_pages(content, 10)
                return content
            
            # 检查是否为本地文件
            if os.path.exists(file_url):
                logging.info(f"检测到本地文件，直接使用: {file_url}")
                content = file_processor._extract_pdf_content(file_url)
                if content:
                    # 去除前10页
                    content = self._remove_first_n_pages(content, 10)
                return content
            
            # 远程文件，需要下载
            temp_dir = file_processor.create_temp_directory()
            try:
                # 下载文件
                success, result = await file_processor.download_file(file_url, temp_dir)
                if not success:
                    logging.warning(f"文件下载失败: {file_url}")
                    return None
                
                # 获取文件路径
                downloaded_path = result.split(',')[0] if isinstance(result, str) else result
                
                if not os.path.exists(downloaded_path):
                    logging.warning(f"下载的文件路径不存在: {downloaded_path}")
                    return None
                
                # 提取PDF内容（带页码标记）
                content = file_processor._extract_pdf_content(downloaded_path)
                if content:
                    # 去除前10页
                    content = self._remove_first_n_pages(content, 10)
                return content
                
            finally:
                # 清理临时目录
                if temp_dir and os.path.exists(temp_dir):
                    try:
                        import shutil
                        shutil.rmtree(temp_dir)
                    except Exception as e:
                        logging.warning(f"清理临时目录失败: {e}")
                        
        except Exception as e:
            logging.error(f"获取文件内容失败: {file_url}, 错误: {e}")
            return None
    
    def _should_ignore_clause(self, eval_item: str) -> bool:
        """
        判断是否应该忽略该条款（不处理页码范围）
        
        Args:
            eval_item: 评审条款
            
        Returns:
            bool: 如果应该忽略返回True，否则返回False
        """
        ignore_keywords = ['管理体系', '三体系', '体系认证']
        return any(keyword in eval_item for keyword in ignore_keywords)
    
    def _extract_page_range_from_content(
        self, 
        content: str, 
        eval_item: str
    ) -> Optional[Tuple[int, int]]:
        """
        从内容中提取条款对应的页码范围
        
        Args:
            content: 文件文本内容（带页码标记）
            eval_item: 评审条款
            
        Returns:
            Optional[Tuple[int, int]]: (start_page, end_page)，如果提取失败返回None
        """
        try:
            # 检查是否应该忽略该条款
            if self._should_ignore_clause(eval_item):
                logging.info(f"忽略条款 {eval_item}（包含管理体系/三体系/体系认证关键词）")
                return None
            
            # 判断条款类型
            has_qualification = "资质" in eval_item
            has_performance = "业绩" in eval_item
            has_resume = "简历" in eval_item or "resume" in eval_item.lower()
            has_supervisor = "监理" in eval_item  # 检查是否包含"监理"
            has_safety_license = "安全生产许可证" in eval_item  # 检查是否包含"安全生产许可证"
            
            # 根据条款类型选择对应的filter
            # 如果条款是"安全生产许可证"，使用资质部分的filter
            if has_qualification or has_safety_license:
                filter_obj = QualificationContentFilter()
                result = filter_obj.filter_qualification_content(content)
                if has_safety_license:
                    logging.info(f"条款 {eval_item} 包含'安全生产许可证'，使用资质filter获取页码范围")
            elif has_performance:
                filter_obj = PerformanceContentFilter()
                result = filter_obj.filter_performance_content(content)
            elif has_resume:
                # 简历表条款，返回None（简历表有专门的处理逻辑）
                return None
            elif has_supervisor:
                # 包含"监理"的条款，使用简历表的filter来获取页码范围
                from src.utils.file_range_filter.resume_table_content_filter import ResumeTableContentFilter
                filter_obj = ResumeTableContentFilter()
                result = filter_obj.filter_resume_table_content(content)
                logging.info(f"条款 {eval_item} 包含'监理'，使用简历表filter获取页码范围")
            else:
                # 其他条款：使用其他条款截取函数
                filter_obj = OtherClausesContentFilter()
                result = filter_obj.filter_other_clauses_content(content)
            
            # 检查是否成功截取
            if not result.get("extraction_success", False):
                logging.warning(f"条款 {eval_item} 的内容截取失败: {result.get('error_message', '未知错误')}")
                return None
            
            # 获取头部和尾部关键词的位置
            header_keyword = result.get("header_keyword", "")
            footer_keyword = result.get("footer_keyword", "")
            
            if not header_keyword or not footer_keyword:
                logging.warning(f"未找到头部或尾部关键词")
                return None
            
            # 在原始内容中查找关键词位置
            header_match = re.search(re.escape(header_keyword), content)
            if not header_match:
                logging.warning(f"未找到头部关键词: {header_keyword}")
                return None
            
            # 查找尾部关键词（在头部关键词之后）
            remaining_content = content[header_match.end():]
            footer_match = re.search(re.escape(footer_keyword), remaining_content)
            if not footer_match:
                logging.warning(f"未找到尾部关键词: {footer_keyword}")
                return None
            
            # 计算实际位置
            header_start_pos = header_match.start()
            footer_end_pos = header_match.end() + footer_match.end()
            
            # 根据位置找到页码
            start_page = self._find_page_for_position(content, header_start_pos)
            end_page = self._find_page_for_position(content, footer_end_pos)
            
            if start_page is None or end_page is None:
                logging.warning(f"无法确定页码范围，start_page: {start_page}, end_page: {end_page}")
                return None
            
            logging.info(f"成功提取条款 {eval_item} 的页码范围: {start_page}-{end_page}")
            return (start_page, end_page)
            
        except Exception as e:
            logging.error(f"提取页码范围失败: {eval_item}, 错误: {e}")
            return None
    
    async def _generate_and_save_file_info_and_range(
        self,
        project_id: str,
        complex_file_results: List[Dict[str, Any]],
        clauses: Dict[str, List[str]]
    ):
        """
        根据条款和投标文件生成file_info和file_range数据并保存到数据库
        如果条款包含"资质"、"业绩"或其他条款关键词，则使用关键词截取并更新页码范围
        
        Args:
            project_id: 项目ID
            complex_file_results: 复杂文件处理结果列表
            clauses: 条款字典，包含qualification和business两个键
        """
        try:
            # 合并所有条款
            all_clauses = clauses.get("qualification", []) + clauses.get("business", [])
            
            # 过滤掉包含管理体系/三体系/体系认证的条款
            filtered_clauses = [
                clause for clause in all_clauses 
                if not self._should_ignore_clause(clause)
            ]
            
            if not filtered_clauses:
                logging.warning("未找到任何需要处理的条款（已过滤管理体系/三体系/体系认证相关条款），跳过file_info和file_range数据生成")
                return
            
            # 记录被过滤的条款
            ignored_clauses = [clause for clause in all_clauses if self._should_ignore_clause(clause)]
            if ignored_clauses:
                logging.info(f"已忽略以下条款（包含管理体系/三体系/体系认证关键词）: {ignored_clauses}")
            
            all_clauses = filtered_clauses
            
            # 转换为整数类型的project_id
            try:
                project_id_int = int(project_id)
            except ValueError:
                project_id_int = abs(hash(project_id)) % (10**10)
            
            # 在保存新数据之前，先删除该项目ID关联的旧file_info和file_range数据
            try:
                deleted = delete_file_info_and_range_by_project_id(project_id_int)
                if deleted:
                    logging.info(f"成功删除项目 {project_id} 的旧file_info和file_range数据")
                else:
                    logging.warning(f"删除项目 {project_id} 的旧file_info和file_range数据失败，但继续执行")
            except Exception as e:
                # 如果删除失败，记录错误但不影响后续处理
                logging.error(f"删除项目 {project_id} 的旧file_info和file_range数据失败: {e}")
                # 即使失败也继续，因为可能是第一次运行，没有旧数据需要删除
            
            # 为每个投标文件和每个条款组合生成数据
            file_data_list = []
            for file_result in complex_file_results:
                bid_url = file_result.get("file_url")
                bidder_name = file_result.get("bidder_name", "未知")
                
                if not bid_url:
                    continue
                
                # 为每个条款创建一个eval_item
                eval_items = all_clauses.copy()
                
                file_data_list.append({
                    "bid_url": bid_url,
                    "bider_name": bidder_name,
                    "eval_items": eval_items
                })
            
            # 批量保存到数据库
            if file_data_list:
                success = batch_save_file_info_and_range(project_id_int, file_data_list)
                if success:
                    logging.info(f"成功保存 {len(file_data_list)} 条file_info记录和对应的file_range记录")
                    
                    # 对包含资质/业绩/其他条款关键词的条款，尝试提取页码范围并更新
                    await self._update_page_ranges_for_clauses(
                        project_id_int, complex_file_results, all_clauses, clauses
                    )
                else:
                    logging.error("批量保存file_info和file_range数据失败")
                    
        except Exception as e:
            logging.error(f"生成和保存file_info和file_range数据失败: {e}")
            raise e
    
    def _has_position_in_clause(self, eval_item: str) -> bool:
        """
        判断条款是否包含职位名称
        
        Args:
            eval_item: 评审条款
            
        Returns:
            bool: 如果包含职位名称返回True，否则返回False
        """
        # 定义所有可能的职位关键词（按长度从长到短排序，优先匹配长词）
        position_keywords = [
            '项目经理兼设计负责人', '项目经理兼施工负责人', '项目经理兼技术负责人',
            '设计负责人', '施工负责人', '技术负责人', '安全负责人', '质量负责人',
            '项目经理', '项目负责人', '总工程师', '总监理', '工程师'
        ]
        return any(keyword in eval_item for keyword in position_keywords)
    
    async def _update_page_ranges_for_clauses(
        self,
        project_id: int,
        complex_file_results: List[Dict[str, Any]],
        all_clauses: List[str],
        clauses: Dict[str, List[str]] = None
    ):
        """
        更新包含资质/业绩/其他条款关键词的条款的页码范围
        
        Args:
            project_id: 项目ID（整数）
            complex_file_results: 复杂文件处理结果列表
            all_clauses: 所有条款列表
            clauses: 条款字典，包含qualification和business两个键（可选）
        """
        try:
            from database.file_info_service import get_file_info_and_range_by_project_id
            from src.utils.file_range_filter.resume_table_content_filter import ResumeTableContentFilter
            
            # 获取所有已保存的file_info和file_range数据
            file_data_list = get_file_info_and_range_by_project_id(project_id)
            
            if not file_data_list:
                logging.warning("未找到file_info和file_range数据，跳过页码范围更新")
                return
            
            # 检查是否需要简历表：
            # 1. 商务部分是否有2个或以上包含"业绩"的条款
            # 2. 资格评审标准条款中是否有包含职位名称的条款
            business_clauses = clauses.get("business", []) if clauses else []
            qualification_clauses = clauses.get("qualification", []) if clauses else []
            
            performance_clauses = [clause for clause in business_clauses if "业绩" in clause]
            need_resume_table_for_performance = len(performance_clauses) >= 2
            
            # 检查资格评审标准条款中是否包含职位名称
            qualification_with_position = [
                clause for clause in qualification_clauses 
                if self._has_position_in_clause(clause)
            ]
            need_resume_table_for_qualification = len(qualification_with_position) > 0
            
            need_resume_table = need_resume_table_for_performance or need_resume_table_for_qualification
            
            if need_resume_table:
                if need_resume_table_for_performance:
                    logging.info(f"商务部分包含 {len(performance_clauses)} 个业绩条款，需要截取简历表")
                if need_resume_table_for_qualification:
                    logging.info(f"资格评审标准包含 {len(qualification_with_position)} 个职位相关条款，需要截取简历表: {qualification_with_position}")
            
            # 按文件URL和条款建立映射
            file_info_map = {}  # {(bid_url, eval_item): file_info_id}
            for item in file_data_list:
                key = (item["bid_url"], item["eval_item"])
                file_info_map[key] = item["file_info_id"]
            
            # 为每个文件处理条款
            for file_result in complex_file_results:
                bid_url = file_result.get("file_url")
                if not bid_url:
                    continue
                
                # 优先使用已处理的文件路径（如果存在）
                file_path = file_result.get("file_path")
                
                # 获取文件内容
                logging.info(f"开始获取文件内容: {bid_url}")
                content = await self._get_file_content_with_pages(bid_url, file_path)
                if not content:
                    logging.warning(f"无法获取文件内容: {bid_url}，跳过页码范围提取")
                    continue
                
                # 如果需要简历表，先截取简历表并获取页码范围
                resume_table_page_range = None
                if need_resume_table:
                    resume_filter = ResumeTableContentFilter()
                    resume_result = resume_filter.filter_resume_table_content(content)
                    if resume_result.get("extraction_success", False):
                        header_keyword = resume_result.get("header_keyword", "")
                        footer_keyword = resume_result.get("footer_keyword", "")
                        if header_keyword and footer_keyword:
                            # 在原始内容中查找关键词位置
                            header_match = re.search(re.escape(header_keyword), content)
                            if header_match:
                                remaining_content = content[header_match.end():]
                                footer_match = re.search(re.escape(footer_keyword), remaining_content)
                                if footer_match:
                                    header_start_pos = header_match.start()
                                    footer_end_pos = header_match.end() + footer_match.end()
                                    start_page = self._find_page_for_position(content, header_start_pos)
                                    end_page = self._find_page_for_position(content, footer_end_pos)
                                    if start_page is not None and end_page is not None:
                                        resume_table_page_range = (start_page, end_page)
                                        logging.info(f"成功提取简历表页码范围: {start_page}-{end_page}")
                
                # 处理每个条款
                for eval_item in all_clauses:
                    # 检查是否应该忽略该条款
                    if self._should_ignore_clause(eval_item):
                        logging.info(f"忽略条款 {eval_item}（包含管理体系/三体系/体系认证关键词）")
                        continue
                    
                    # 检查条款类型：资质、业绩、简历表或其他条款
                    has_qualification = "资质" in eval_item
                    has_performance = "业绩" in eval_item
                    has_resume = "简历" in eval_item or "resume" in eval_item.lower()
                    
                    # 如果是简历表，跳过（简历表有专门的处理逻辑）
                    if has_resume:
                        continue
                    
                    # 对于资质、业绩或其他条款，都需要提取页码范围
                    # 查找对应的file_info_id
                    key = (bid_url, eval_item)
                    if key not in file_info_map:
                        logging.warning(f"未找到file_info记录: {bid_url}, {eval_item}")
                        continue
                    
                    file_info_id = file_info_map[key]
                    
                    # 判断是否使用简历表页码范围
                    use_resume_range = False
                    # 如果条款包含职位名称或人员配备相关关键词，无论是什么类型，都使用简历表页码范围
                    if need_resume_table and resume_table_page_range:
                        # 检查是否包含职位名称
                        has_position = self._has_position_in_clause(eval_item)
                        # 检查是否包含人员配备相关关键词
                        personnel_keywords = ['人员配备', '配备人员', '主要人员配备']
                        has_personnel_keyword = any(keyword in eval_item for keyword in personnel_keywords)
                        
                        if has_position or has_personnel_keyword:
                            use_resume_range = True
                            # 判断条款类型用于日志
                            if has_performance:
                                clause_type = "业绩"
                            elif has_qualification:
                                clause_type = "资格评审标准"
                            else:
                                clause_type = "其他"
                            
                            if has_position:
                                logging.info(f"{clause_type}条款 {eval_item} 包含职位名称，使用简历表页码范围")
                            if has_personnel_keyword:
                                logging.info(f"{clause_type}条款 {eval_item} 包含人员配备关键词，使用简历表页码范围")
                    
                    if use_resume_range:
                        # 使用简历表页码范围
                        start_page, end_page = resume_table_page_range
                        success = update_file_range_page_range(file_info_id, start_page, end_page)
                        if success:
                            logging.info(f"成功更新条款 {eval_item} 的页码范围（使用简历表）: {start_page}-{end_page}")
                        else:
                            logging.warning(f"更新条款 {eval_item} 的页码范围失败")
                    else:
                        # 正常提取页码范围
                        page_range = self._extract_page_range_from_content(content, eval_item)
                        
                        if page_range:
                            start_page, end_page = page_range
                            # 更新数据库
                            success = update_file_range_page_range(file_info_id, start_page, end_page)
                            if success:
                                logging.info(f"成功更新条款 {eval_item} 的页码范围: {start_page}-{end_page}")
                            else:
                                logging.warning(f"更新条款 {eval_item} 的页码范围失败")
                        else:
                            logging.info(f"条款 {eval_item} 无法提取页码范围，保持为NULL")
                        
        except Exception as e:
            logging.error(f"更新页码范围失败: {e}")
            # 不抛出异常，避免影响主流程