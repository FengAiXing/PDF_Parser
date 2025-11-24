# -*- coding: utf-8 -*-
"""
解析任务服务 - 根据数据库中的file_info和file_range数据进行解析
"""
import asyncio
import json
import logging
import os
import re
from typing import Dict, List, Any, Optional, Tuple
from database.file_info_service import get_file_info_and_range_by_project_id
from database.data_process import get_template_type_by_id, update_parse_task_progress, update_parse_task_status, save_task_results_to_database
from src.business.service.content_extraction_service import ContentExtractionService
from src.business.service.task_service import TaskService
from src.utils.pre_variables import preprocess_variables
from src.business.service.report_generation_service import ReportGenerationService

logger = logging.getLogger(__name__)


class ParseTaskService:
    """解析任务服务类"""
    
    def __init__(self):
        """初始化服务"""
        self.content_extraction_service = ContentExtractionService()
        self.task_service = TaskService()
        self.report_service = ReportGenerationService()
    
    def merge_page_ranges(self, ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """
        合并重叠的页码范围（求并集）
        
        Args:
            ranges: 页码范围列表，每个元素为 (start, end) 元组
            
        Returns:
            List[Tuple[int, int]]: 合并后的页码范围列表
            
        示例:
            [(20, 40), (30, 50)] -> [(20, 50)]
            [(20, 30), (60, 90)] -> [(20, 30), (60, 90)]
        """
        if not ranges:
            return []
        
        # 按开始页码排序
        sorted_ranges = sorted(ranges, key=lambda x: x[0])
        merged = [sorted_ranges[0]]
        
        for current in sorted_ranges[1:]:
            last = merged[-1]
            # 如果当前范围与上一个范围重叠或相邻，则合并
            if current[0] <= last[1] + 1:
                # 合并范围
                merged[-1] = (last[0], max(last[1], current[1]))
            else:
                # 不重叠，添加新范围
                merged.append(current)
        
        return merged
    
    async def _extract_pdf_content_by_ranges_with_path(
        self, 
        file_path: str,
        page_ranges: List[Tuple[int, int]],
        temp_dir: str
    ) -> Dict[int, str]:
        """
        根据页码范围提取PDF内容（使用已下载的文件路径）
        
        Args:
            file_path: 已下载的文件路径
            page_ranges: 页码范围列表
            temp_dir: 临时目录
            
        Returns:
            Dict[int, str]: 页码到内容的映射
        """
        try:
            import fitz
            import os
            from src.utils.complex_file.main_processor import ComplexFileProcessor
            
            complex_file_processor = ComplexFileProcessor()
            
            if not os.path.exists(file_path):
                logger.error(f"文件路径不存在: {file_path}")
                return {}
                
            # 先提取指定页码范围到临时PDF，只处理需要的页面
            doc = fitz.open(file_path)
            total_pages = len(doc)
            logger.info(f"打开PDF文件，总页数: {total_pages}, 文件路径: {file_path}")
            
            # 计算需要处理的页面范围（合并所有页码范围）
            target_pages = set()
            for start, end in page_ranges:
                # 转换为0-based索引，range是左闭右开，所以end需要+1
                # 同时确保不超过文档总页数
                actual_end = min(end + 1, total_pages + 1)
                actual_start = max(1, start)  # 确保起始页码至少为1
                for page_num in range(actual_start - 1, actual_end):
                    if 0 <= page_num < total_pages:  # 确保页码有效（0-based索引）
                        target_pages.add(page_num)
                    else:
                        logger.warning(f"跳过无效页码: {page_num + 1} (0-based: {page_num}), 文档总页数: {total_pages}")
            
            if not target_pages:
                logger.warning(f"页码范围无效，未找到需要处理的页面。请求的页码范围: {page_ranges}, 文档总页数: {total_pages}")
                doc.close()
                return {}
                
            # 创建只包含目标页面的临时PDF
            temp_pdf_path = os.path.join(temp_dir, f"temp_pages_{os.path.basename(file_path)}")
            temp_doc = fitz.open()
            
            # 按页码顺序添加页面，添加错误处理
            valid_pages = []
            for page_num in sorted(target_pages):
                try:
                    # 再次验证页面是否存在
                    if page_num < 0 or page_num >= total_pages:
                        logger.warning(f"跳过无效页码: {page_num + 1} (0-based: {page_num}), 文档总页数: {total_pages}")
                        continue
                    
                    # 尝试访问页面以验证其存在
                    _ = doc[page_num]  # 如果页面不存在，这里会抛出异常
                    
                    temp_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                    valid_pages.append(page_num + 1)  # 记录成功插入的页面（1-based）
                except (IndexError, RuntimeError) as e:
                    logger.warning(f"跳过无效或损坏的页面 {page_num + 1} (0-based: {page_num}): {e}")
                    continue
            
            if not valid_pages:
                logger.error(f"没有成功提取任何页面，所有请求的页面都无效")
                temp_doc.close()
                doc.close()
                return {}
            
            temp_doc.save(temp_pdf_path)
            temp_doc.close()
            doc.close()
            
            logger.info(f"已提取页码范围到临时PDF: 成功提取 {len(valid_pages)} 页，原PDF总页数: {total_pages}，请求的页码范围: {page_ranges}")
            
            # 使用复杂文件处理器进行解析（只处理提取的页码范围）
            logger.info(f"使用复杂文件处理器解析文件: {file_path} (仅处理指定页码范围)")
            processed_txt_path = await complex_file_processor.process_candidate_bid_file(temp_pdf_path, temp_dir)
                
            page_content_map = {}
                
            if processed_txt_path and os.path.exists(processed_txt_path):
                # 从处理后的TXT文件中读取内容（包含OCR结果）
                with open(processed_txt_path, 'r', encoding='utf-8') as f:
                    processed_content = f.read()
                
                # 复杂文件处理后的TXT文件每页都有 [当前页码: X] 标记
                # 使用正则表达式提取每页内容
                import re
                # 匹配页码标记：[当前页码: X]
                page_pattern = r'\[当前页码:\s*(\d+)\]\s*\n(.*?)(?=\[当前页码:|\Z)'
                matches = re.finditer(page_pattern, processed_content, re.DOTALL)
                
                # 先提取所有页面的内容
                all_pages_content = {}
                for match in matches:
                    page_num = int(match.group(1))
                    page_content = match.group(2).strip()
                    if page_content:
                        all_pages_content[page_num] = page_content
                
                # 临时PDF的页码是从1开始的连续页码，需要映射回原始页码
                # valid_pages 是1-based的页面列表（实际成功插入的页面）
                temp_page_to_original = {}
                for idx, original_page_num in enumerate(valid_pages):
                    temp_page_to_original[idx + 1] = original_page_num  # temp_page从1开始，映射到原始页码
                
                # 根据临时PDF的页码映射回原始页码
                for temp_page_num, original_page_num in temp_page_to_original.items():
                    if temp_page_num in all_pages_content:
                        page_content_map[original_page_num] = all_pages_content[temp_page_num]
                
                logger.info(f"成功使用复杂文件处理器提取文件 {file_path} 的 {len(page_content_map)} 页内容（包含OCR结果），页码范围: {page_ranges}")
                return page_content_map
            else:
                # 如果复杂文件处理失败，回退到简单PDF文本提取
                logger.warning(f"复杂文件处理失败，回退到简单PDF文本提取: {file_path}")
                doc = fitz.open(file_path)
                
                # 提取每个范围的页面内容
                for start, end in page_ranges:
                    # 转换为0-based索引，range是左闭右开，所以end需要+1
                    # 同时确保不超过文档总页数
                    actual_end = min(end + 1, len(doc) + 1)
                    for page_num in range(start - 1, actual_end):
                        if page_num < len(doc):  # 确保页码有效
                            page = doc[page_num]
                            text = page.get_text()
                            if text.strip():
                                # 页码从1开始
                                page_content_map[page_num + 1] = text
                
                doc.close()
                logger.info(f"成功提取文件 {file_path} 的 {len(page_content_map)} 页内容（简单模式）")
                
                return page_content_map
            
        except Exception as e:
            logger.error(f"提取PDF内容失败: {file_path}, 错误: {e}", exc_info=True)
            return {}
    
    async def extract_pdf_content_by_ranges(
        self, 
        file_url: str, 
        page_ranges: List[Tuple[int, int]]
    ) -> Dict[int, str]:
        """
        根据页码范围提取PDF内容（使用复杂文件解析，包括视觉模型解析）
        
        Args:
            file_url: 文件URL
            page_ranges: 页码范围列表，每个元素为 (start, end) 元组（从封面页开始计数，从1开始）
            
        Returns:
            Dict[int, str]: 页码到内容的映射，key为页码（从1开始），value为内容
        """
        try:
            import fitz
            import os
            import tempfile
            
            # 使用系统的文件下载功能
            from src.utils.async_file_process import AsyncFileProcessor
            from src.utils.complex_file.main_processor import ComplexFileProcessor
            
            file_processor = AsyncFileProcessor()
            complex_file_processor = ComplexFileProcessor()
            
            # 创建临时目录
            temp_dir = file_processor.create_temp_directory()
            
            try:
                # 下载文件
                success, result = await file_processor.download_file(file_url, temp_dir)
                if not success:
                    logger.error(f"文件下载失败: {file_url}")
                    return {}
                
                # 获取文件路径
                file_path = result.split(',')[0] if isinstance(result, str) else result
                
                # 检查是否为本地文件
                if os.path.exists(file_url):
                    file_path = file_url
                elif not os.path.exists(file_path):
                    logger.error(f"文件路径不存在: {file_path}")
                    return {}
                
                # 使用内部方法提取内容
                return await self._extract_pdf_content_by_ranges_with_path(file_path, page_ranges, temp_dir)
                
            finally:
                # 清理临时目录（如果创建了）
                if temp_dir and os.path.exists(temp_dir):
                    try:
                        import shutil
                        shutil.rmtree(temp_dir)
                    except Exception as e:
                        logger.warning(f"清理临时目录失败: {e}")
                    
        except Exception as e:
            logger.error(f"提取PDF内容失败: {file_url}, 错误: {e}", exc_info=True)
            return {}
    
    def extract_content_by_range(
        self, 
        full_content: Dict[int, str], 
        start: int, 
        end: int
    ) -> str:
        """
        从完整内容中截取指定页码范围的内容
        
        Args:
            full_content: 完整内容字典，key为页码，value为内容
            start: 开始页码（从1开始）
            end: 结束页码（从1开始）
            
        Returns:
            str: 截取的内容，带页码标记
        """
        content_parts = []
        missing_pages = []
        
        for page_num in range(start, end + 1):
            if page_num in full_content:
                content_parts.append(f"=== 第{page_num}页 ===\n{full_content[page_num]}")
            else:
                missing_pages.append(page_num)
        
        # 如果有关键页码缺失，记录警告
        if missing_pages:
            logger.warning(
                f"页码范围 {start}-{end} 中缺失以下页码: {missing_pages}。"
                # f"full_content中可用的页码: {sorted(full_content.keys())}"
            )
        
        return "\n\n".join(content_parts)
    
    def _determine_clause_type(self, eval_item: str) -> str:
        """
        判断评审条款类型
        
        Args:
            eval_item: 评审项名称
            
        Returns:
            str: 条款类型 ('performance', 'qualification', 'general')
        """
        eval_item_lower = eval_item.lower()
        if '业绩' in eval_item:
            return 'performance'
        elif '资质' in eval_item or '安全生产许可证' in eval_item:
            # 如果条款是"安全生产许可证"，也识别为资质类型
            return 'qualification'
        else:
            return 'general'
    
    def _get_candidate_count_from_variables(self, variables: List[Dict[str, Any]]) -> int:
        """
        从变量列表中获取推荐中标候选人数量
        
        Args:
            variables: 变量列表
            
        Returns:
            int: 候选人数量，默认为1
        """
        for var in variables:
            if isinstance(var, dict):
                var_name = var.get('variable_name', '')
                if '推荐中标候选人数' in var_name or '推荐人数' in var_name:
                    try:
                        value = var.get('variable_value', '')
                        if isinstance(value, (int, float)):
                            return int(value)
                        elif isinstance(value, str):
                            # 尝试从字符串中提取数字
                            numbers = re.findall(r'\d+', value)
                            if numbers:
                                return int(numbers[0])
                    except (ValueError, TypeError):
                        pass
        return 1  # 默认值
    
    def _get_candidate_names_from_variables(self, variables: List[Dict[str, Any]]) -> Dict[int, str]:
        """
        从变量列表中获取候选人名称
        
        Args:
            variables: 变量列表
            
        Returns:
            Dict[int, str]: 候选人名称字典，格式: {1: "第一名候选人名称", ...}
        """
        candidate_names = {}
        
        # 中文数字映射
        chinese_numbers = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
        
        for var in variables:
            if isinstance(var, dict):
                var_name = var.get('variable_name', '')
                var_value = var.get('variable_value', '')
                
                if not var_value:
                    continue
                
                # 只查找"第一中标候选人名称"、"第二中标候选人名称"等格式的变量
                for rank in range(1, 11):
                    # 中文数字格式（如"第一中标候选人名称"）
                    if rank <= len(chinese_numbers):
                        chinese_rank = chinese_numbers[rank - 1]
                        pattern = f'第{chinese_rank}中标候选人名称'  # 第一中标候选人名称（带"第"字）
                        
                        if var_name == pattern:
                            candidate_names[rank] = str(var_value).strip()
                            logger.info(f"找到候选人名称变量: {var_name} -> 排名{rank}: {candidate_names[rank]}")
                            break
        
        logger.info(f"从变量中提取到 {len(candidate_names)} 个候选人名称: {candidate_names}")
        return candidate_names
    
    def _get_ranking_by_bidder_name(
        self, 
        bidder_name: str, 
        candidate_names: Dict[int, str]
    ) -> str:
        """
        根据投标人名称匹配排名
        
        Args:
            bidder_name: 投标人名称
            candidate_names: 候选人名称字典，格式: {1: "第一中标候选人名称", ...}
            
        Returns:
            str: 排名（如"第一名"、"第二名"等），如果未匹配则返回"第一名"
        """
        if not bidder_name or not candidate_names:
            return "第一名"
        
        # 尝试匹配投标人名称和候选人名称
        for rank, candidate_name in candidate_names.items():
            if not candidate_name:
                continue
            
            # 清理名称中的空格和特殊字符，提高匹配成功率
            bidder_name_clean = bidder_name.strip().replace(" ", "").replace("有限公司", "").replace("股份有限公司", "")
            candidate_name_clean = candidate_name.strip().replace(" ", "").replace("有限公司", "").replace("股份有限公司", "")
            
            # 双向匹配：投标人名称包含在候选人名称中，或候选人名称包含在投标人名称中
            if (bidder_name in candidate_name or 
                candidate_name in bidder_name or
                bidder_name == candidate_name or
                bidder_name_clean in candidate_name_clean or
                candidate_name_clean in bidder_name_clean):
                rank_names = {
                    1: "第一名", 2: "第二名", 3: "第三名", 
                    4: "第四名", 5: "第五名", 6: "第六名",
                    7: "第七名", 8: "第八名", 9: "第九名", 10: "第十名"
                }
                ranking = rank_names.get(rank, "第一名")
                logger.info(f"根据投标人名称匹配到排名: {ranking} (投标人: {bidder_name}, 候选人: {candidate_name})")
                return ranking
        
        # 如果无法匹配，返回默认值
        logger.warning(f"无法根据投标人名称匹配排名，使用默认值: 第一名 (投标人: {bidder_name}, 候选人列表: {list(candidate_names.values())})")
        return "第一名"
    
    async def _extract_variables_by_clause_type(
        self,
        item_content: str,
        eval_item: str,
        clause_type: str,
        bid_url: str,
        candidate_count: int,
        candidate_names: Dict[int, str],
        previous_variables: List[Dict[str, Any]],
        file_data: Dict[str, Any],
        page_range: Tuple[int, int] = None
    ) -> List[Dict[str, Any]]:
        """
        根据条款类型使用对应的提示词提取变量
        
        Args:
            item_content: 评审项的内容（已按页码范围截取）
            eval_item: 评审项名称
            clause_type: 条款类型 ('performance', 'qualification', 'general')
            bid_url: 文件URL
            candidate_count: 候选人数量
            candidate_names: 候选人名称字典
            previous_variables: 前一个接口提取的变量
            file_data: 文件数据
            
        Returns:
            List[Dict[str, Any]]: 提取的变量列表
        """
        try:
            from prompts.pre_variable_prompt import DynamicTableVariableExtractor
            from common.llm_client import LLMClient
            import json
            
            extractor = DynamicTableVariableExtractor()
            llm_client = LLMClient()
            
            # 从previous_variables中提取必要信息
            bidder_requirements = ""
            performance_requirements = ""
            qualification_requirements = ""
            other_requirements = ""
            
            for var in previous_variables:
                if isinstance(var, dict):
                    var_name = var.get('variable_name', '')
                    var_value = var.get('variable_value', '')
                    
                    if '投标人要求' in var_name:
                        bidder_requirements = str(var_value)
                    elif '业绩条款要求' in var_name or '业绩要求' in var_name:
                        performance_requirements = str(var_value)
                    elif '资质条款要求' in var_name or '资质要求' in var_name:
                        qualification_requirements = str(var_value)
                    elif '其他条款要求' in var_name:
                        other_requirements = str(var_value)
            
            # 根据条款类型使用不同的提取策略
            if clause_type == 'performance':
                # 业绩类型：先提取业绩汇总表和单个业绩表格，然后并发提取每个业绩
                # 检查是否包含职位信息，如果包含则尝试获取简历表内容
                has_position = self._has_position_in_clause(eval_item)
                resume_table_content = None
                
                if has_position:
                    # 从file_data中获取简历表内容（在process_parse_task中已提取）
                    resume_table_content = file_data.get('resume_table_content', None)
                    if resume_table_content:
                        logger.info(f"检测到条款包含职位信息: {eval_item}，已获取简历表内容，长度: {len(resume_table_content)} 字符")
                    else:
                        logger.warning(f"检测到条款包含职位信息: {eval_item}，但未找到简历表内容")
                
                return await self._extract_performance_variables(
                    item_content=item_content,
                    eval_item=eval_item,
                    bid_url=bid_url,
                    candidate_count=candidate_count,
                    candidate_names=candidate_names,
                    performance_requirements=performance_requirements or bidder_requirements,
                    file_data=file_data,
                    resume_table_content=resume_table_content
                )
            elif clause_type == 'qualification':
                # 资质类型的提示词
                # 获取当前文件对应的排名，只提取该排名的资质
                bidder_name = file_data.get("bidder_name", "")
                target_ranking = self._get_ranking_by_bidder_name(bidder_name, candidate_names)
                logger.info(f"资质提取：当前文件对应的排名为 {target_ranking}，只提取该排名的资质")
                
                # ⚠️ 重要：检测是否为多职位条款（用'、'分隔）
                has_multiple_positions = extractor._has_multiple_positions(eval_item)
                
                # 初始化变量，避免后续访问时出错
                qualification_personnel_vars = []
                
                if has_multiple_positions:
                    # 多职位条款：直接使用专门的多职位提示词（不使用简历表提取，因为简历表提取不支持'、'分隔的多职位）
                    logger.info(f"检测到多职位条款（用'、'分隔）: {eval_item}，使用多职位专用提示词")
                    # 注意：对于多职位条款，不使用简历表提取，因为：
                    # 1. 简历表提取函数不支持'、'分隔的多职位格式
                    # 2. 多职位提示词已经能够正确提取所有职位信息
                    # 3. 避免重复提取和格式不一致的问题
                    qualification_personnel_vars = []  # 明确设置为空，不使用简历表提取
                    
                    prompt = extractor._generate_position_prompt(
                        candidate_count=candidate_count,
                        clauses=[eval_item],
                        other_requirements=qualification_requirements or bidder_requirements,
                        candidate_names=candidate_names,
                        target_ranking=target_ranking  # 传入目标排名，只提取该排名的信息
                    )
                else:
                    # 检查是否包含职位信息，如果包含则从简历表中提取人员信息
                    from src.utils.dynamic_table_generator import _has_position_in_clause
                    from src.utils.pre_variable_for_step4 import extract_qualification_personnel_from_resume
                    
                    has_position = _has_position_in_clause(eval_item)
                    resume_table_content = None
                    qualification_personnel_vars = []  # 初始化变量
                    
                    if has_position:
                        # 从file_data中获取简历表内容
                        resume_table_content = file_data.get('resume_table_content', None)
                        if resume_table_content:
                            logger.info(f"检测到资格评审标准条款包含职位信息: {eval_item}，已获取简历表内容，长度: {len(resume_table_content)} 字符")
                            # 从简历表中提取人员信息
                            try:
                                qualification_personnel_vars = await extract_qualification_personnel_from_resume(
                                    clause_name=eval_item,
                                    resume_table_content=resume_table_content,
                                    ranking=target_ranking
                                )
                                if qualification_personnel_vars:
                                    logger.info(f"从简历表中提取到 {len(qualification_personnel_vars)} 个人员信息变量")
                            except Exception as e:
                                logger.error(f"从简历表提取人员信息失败: {e}", exc_info=True)
                        else:
                            logger.warning(f"检测到资格评审标准条款包含职位信息: {eval_item}，但未找到简历表内容")
                    
                    prompt = extractor._generate_qualification_prompt(
                        candidate_count=candidate_count,
                        clauses=[eval_item],
                        qualification_requirements=qualification_requirements or bidder_requirements,
                        candidate_names=candidate_names,
                        target_ranking=target_ranking  # 传入目标排名，只提取该排名的资质
                    )
            else:
                # 通用类型的提示词
                # 获取当前文件对应的排名，只提取该排名的信息
                bidder_name = file_data.get("bidder_name", "")
                target_ranking = self._get_ranking_by_bidder_name(bidder_name, candidate_names)
                logger.info(f"通用条款提取：当前文件对应的排名为 {target_ranking}，只提取该排名的信息")
                
                # ⚠️ 重要：检测是否为多职位条款（用'、'分隔）
                has_multiple_positions = extractor._has_multiple_positions(eval_item)
                
                # 初始化变量，避免后续访问时出错
                qualification_personnel_vars = []
                
                if has_multiple_positions:
                    # 多职位条款：直接使用专门的多职位提示词（不使用简历表提取，因为简历表提取不支持'、'分隔的多职位）
                    logger.info(f"检测到多职位条款（用'、'分隔）: {eval_item}，使用多职位专用提示词")
                    # 注意：对于多职位条款，不使用简历表提取，因为：
                    # 1. 简历表提取函数不支持'、'分隔的多职位格式
                    # 2. 多职位提示词已经能够正确提取所有职位信息
                    # 3. 避免重复提取和格式不一致的问题
                    qualification_personnel_vars = []  # 明确设置为空，不使用简历表提取
                    
                    prompt = extractor._generate_position_prompt(
                        candidate_count=candidate_count,
                        clauses=[eval_item],
                        other_requirements=other_requirements or bidder_requirements,
                        candidate_names=candidate_names,
                        target_ranking=target_ranking  # 传入目标排名，只提取该排名的信息
                    )
                else:
                    # 检查是否包含职位信息，如果包含则从简历表中提取人员信息（即使不是qualification类型）
                    # 因为资格评审标准中包含职位的条款不一定包含"资质"关键词
                    from src.utils.dynamic_table_generator import _has_position_in_clause
                    from src.utils.pre_variable_for_step4 import extract_qualification_personnel_from_resume
                    
                    has_position = _has_position_in_clause(eval_item)
                    resume_table_content = None
                    qualification_personnel_vars = []  # 初始化变量
                    
                    if has_position:
                        # 从file_data中获取简历表内容
                        resume_table_content = file_data.get('resume_table_content', None)
                        if resume_table_content:
                            logger.info(f"检测到通用条款包含职位信息: {eval_item}，已获取简历表内容，长度: {len(resume_table_content)} 字符")
                            # 从简历表中提取人员信息（使用资格评审标准的人员提取提示词）
                            try:
                                qualification_personnel_vars = await extract_qualification_personnel_from_resume(
                                    clause_name=eval_item,
                                    resume_table_content=resume_table_content,
                                    ranking=target_ranking
                                )
                                if qualification_personnel_vars:
                                    logger.info(f"从简历表中提取到 {len(qualification_personnel_vars)} 个人员信息变量")
                            except Exception as e:
                                logger.error(f"从简历表提取人员信息失败: {e}", exc_info=True)
                        else:
                            logger.warning(f"检测到通用条款包含职位信息: {eval_item}，但未找到简历表内容")
                    
                    prompt = extractor._generate_general_prompt(
                        candidate_count=candidate_count,
                        clauses=[eval_item],
                        other_requirements=other_requirements or bidder_requirements,
                        candidate_names=candidate_names,
                        target_ranking=target_ranking  # 传入目标排名，只提取该排名的信息
                    )
            
            # 对于资质和通用类型，直接使用LLM提取
            # 添加文件内容到提示词（替换占位符）
            full_prompt = prompt.replace("$content", item_content)
            
            # 调用LLM提取变量（带重试机制）
            content_length = len(item_content)
            page_range_str = f"{page_range[0]}-{page_range[1]}" if page_range else "未知"
            logger.info(f"使用 {clause_type} 类型提示词提取评审项 {eval_item} 的变量")
            logger.info(f"提取内容统计: 内容长度 {content_length:,} 字符, 页码范围: 第{page_range_str}页")
            
            # 重试机制：最多重试1次（总共2次尝试）
            max_retries = 1
            extracted_vars = []
            
            for attempt in range(max_retries + 1):
                try:
                    # 调用LLM
                    response = await llm_client.call_llm(
                        prompt=full_prompt,
                        file_content=item_content,
                        model_type="default"
                    )
                    
                    # 解析JSON响应
                    try:
                        # 尝试从响应中提取JSON
                        json_match = re.search(r'\[.*\]', response, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                            extracted_vars = json.loads(json_str)
                            extracted_vars = extracted_vars if isinstance(extracted_vars, list) else []
                        else:
                            # 尝试直接解析整个响应
                            extracted_vars = json.loads(response)
                            extracted_vars = extracted_vars if isinstance(extracted_vars, list) else []
                        
                        # JSON解析成功，跳出重试循环
                        if attempt > 0:
                            logger.info(f"第{attempt + 1}次重试成功，JSON解析通过")
                        break
                        
                    except json.JSONDecodeError as e:
                        # JSON解析失败
                        if attempt < max_retries:
                            logger.warning(f"第{attempt + 1}次调用JSON解析失败: {e}，准备重试（响应内容前500字符: {response[:500]}）")
                            continue
                        else:
                            # 最后一次尝试也失败
                            logger.error(f"重试后仍然JSON解析失败: {e}，响应内容前500字符: {response[:500]}")
                            extracted_vars = []
                            break
                            
                except Exception as e:
                    # LLM调用异常
                    if attempt < max_retries:
                        logger.warning(f"第{attempt + 1}次调用LLM发生异常: {e}，准备重试")
                        continue
                    else:
                        logger.error(f"重试后仍然发生异常: {e}", exc_info=True)
                        extracted_vars = []
                        break
            
            # 对于资质类型和通用类型（如果包含职位），如果从简历表中提取了人员信息，添加到结果中
            if qualification_personnel_vars:
                # 将简历表提取的人员信息变量添加到结果中
                extracted_vars.extend(qualification_personnel_vars)
                logger.info(f"已将 {len(qualification_personnel_vars)} 个简历表人员信息变量添加到提取结果中（条款类型: {clause_type}）")
            
            # 规范化所有变量的reference_source，确保pages字段存在且格式正确
            for var in extracted_vars:
                if isinstance(var, dict):
                    ref_source = var.get('reference_source', {})
                    if not isinstance(ref_source, dict):
                        ref_source = {}
                    
                    # 如果page_range存在，使用page_range设置pages；否则检查是否有pages字段，没有则留空
                    if page_range and page_range[0] and page_range[1]:
                        ref_source['pages'] = f"{page_range[0]}-{page_range[1]}"
                    elif 'pages' not in ref_source or not ref_source.get('pages'):
                        ref_source['pages'] = ""
                    
                    # 确保其他必需字段存在
                    if 'source_url' not in ref_source:
                        ref_source['source_url'] = bid_url if bid_url else ""
                    if 'evidence_text' not in ref_source:
                        ref_source['evidence_text'] = ""
                    if 'file_type' not in ref_source:
                        ref_source['file_type'] = "candidate_bid_files"
                    
                    var['reference_source'] = ref_source
            
            # 对于资质类型和通用类型，过滤掉不属于当前文件排名的变量
            if clause_type in ['qualification', 'general'] and extracted_vars:
                bidder_name = file_data.get("bidder_name", "")
                target_ranking = self._get_ranking_by_bidder_name(bidder_name, candidate_names)
                filtered_vars = []
                for var in extracted_vars:
                    if isinstance(var, dict):
                        var_name = var.get('variable_name', '')
                        # 只保留当前排名对应的变量
                        if target_ranking in var_name:
                            filtered_vars.append(var)
                        else:
                            logger.debug(f"过滤掉不属于当前文件排名的变量: {var_name} (当前排名: {target_ranking})")
                extracted_vars = filtered_vars
                logger.info(f"{clause_type}提取：过滤后保留 {len(extracted_vars)} 个变量（当前排名: {target_ranking}）")
            
            # 显示提取结果摘要
            if extracted_vars:
                var_names = [var.get('variable_name', '') for var in extracted_vars if isinstance(var, dict)]
                logger.info(f"提取到的变量: {', '.join(var_names[:5])}{'...' if len(var_names) > 5 else ''}")
            else:
                logger.warning(f"未提取到任何变量")
            
            return extracted_vars
                
        except Exception as e:
            logger.error(f"提取变量失败: {e}", exc_info=True)
            return []
    
    def _has_position_in_clause(self, eval_item: str) -> bool:
        """
        判断条款是否包含职位名称
        
        Args:
            eval_item: 评审条款
            
        Returns:
            bool: 如果包含职位名称返回True，否则返回False
        """
        position_keywords = ['项目经理', '工程师', '负责人', '设计负责人', '施工负责人', '技术负责人', '安全负责人']
        return any(keyword in eval_item for keyword in position_keywords)
    
    async def _extract_performance_variables(
        self,
        item_content: str,
        eval_item: str,
        bid_url: str,
        candidate_count: int,
        candidate_names: Dict[int, str],
        performance_requirements: str,
        file_data: Dict[str, Any],
        resume_table_content: str = None
    ) -> List[Dict[str, Any]]:
        """
        提取业绩变量：先提取业绩汇总表和单个业绩表格，然后并发提取每个业绩
        
        Args:
            item_content: 评审项的内容（已按页码范围截取）
            eval_item: 评审项名称
            bid_url: 文件URL
            candidate_count: 候选人数量
            candidate_names: 候选人名称字典
            performance_requirements: 业绩要求
            file_data: 文件数据
            resume_table_content: 简历表内容（可选，用于包含职位的业绩条款）
            
        Returns:
            List[Dict[str, Any]]: 提取的变量列表（包含业绩汇总表、业绩表格和详细业绩）
        """
        try:
            from src.utils.bid_file_processor import BidFileProcessor
            from src.utils.pre_variable_for_step4 import PreVariableForStep4
            from prompts.pre_variable_prompt import DynamicTableVariableExtractor
            from common.llm_client import LLMClient
            import asyncio
            
            processor = BidFileProcessor()
            resume_processor = PreVariableForStep4()
            extractor = DynamicTableVariableExtractor()
            llm_client = LLMClient()
            
            all_extracted_vars = []
            
            # 确定排名：根据投标人名称匹配推荐中标候选人名称来确定排名
            bidder_name = file_data.get("bidder_name", "")
            logger.info(f"准备匹配排名 - 投标人名称: {bidder_name}, 候选人名称字典: {candidate_names}")
            ranking = self._get_ranking_by_bidder_name(bidder_name, candidate_names)
            
            content_length = len(item_content)
            logger.info("=" * 80)
            logger.info(f"处理评审项: {eval_item} (业绩类型)")
            logger.info(f"提取内容统计: 内容长度 {content_length:,} 字符")
            
            # 步骤1：判断是否包含职位信息，如果包含则从简历表中提取业绩表格
            has_position = self._has_position_in_clause(eval_item)
            performance_result = None
            
            if has_position and resume_table_content:
                logger.info(f"检测到条款包含职位信息，从简历表中提取业绩表格，排名: {ranking} (投标人: {bidder_name})")
                performance_result = await resume_processor.extract_performance_tables_from_resume(
                    resume_table_content=resume_table_content,
                    ranking=ranking,
                    clause_name=eval_item
                )
            else:
                # 步骤1：从常规业绩文本中提取业绩汇总表和单个业绩表格
                logger.info(f"开始提取评审项 {eval_item} 的业绩汇总表和业绩表格，排名: {ranking} (投标人: {bidder_name})")
                performance_result = await processor.extract_performance_tables_from_text(
                    performance_text=item_content,
                    ranking=ranking,
                    clause_name=eval_item  # 使用条款名称（如"业绩要求"、"投标人近年类似项目业绩"）
                )
            
            if not performance_result.get('success'):
                logger.warning(f"提取业绩表格失败: {performance_result.get('error')}")
                return []
            
            # 步骤2：将业绩表格转换为变量格式
            performance_table_variables = []
            
            # 添加业绩汇总表变量（使用条款名称）
            summary_table = performance_result.get('performance_summary_table', {})
            if summary_table.get('table_content'):
                # 获取页码范围，如果没有则留空
                items = file_data.get('items', [])
                pages = ""
                if items and items[0].get('start') and items[0].get('end'):
                    pages = f"{items[0].get('start')}-{items[0].get('end')}"
                
                summary_var = {
                    "variable_name": summary_table.get('variable_name', f"{ranking}{eval_item}汇总表"),
                    "variable_value": summary_table.get('table_content', ''),
                    "reference_source": {
                        "source_url": bid_url,
                        "evidence_text": f"{eval_item}汇总表",
                        "pages": pages,
                        "file_type": "candidate_bid_files"
                    }
                }
                all_extracted_vars.append(summary_var)
                logger.info(f"添加业绩汇总表变量: {summary_var['variable_name']}")
            
            # 添加单个业绩表格变量
            individual_performances = performance_result.get('individual_performances', [])
            for perf in individual_performances:
                # 获取页码范围，如果没有则留空
                items = file_data.get('items', [])
                pages = ""
                if items and items[0].get('start') and items[0].get('end'):
                    pages = f"{items[0].get('start')}-{items[0].get('end')}"
                
                table_var = {
                    "variable_name": perf.get('variable_name', ''),
                    "variable_value": perf.get('table_content', ''),
                    "reference_source": {
                        "source_url": bid_url,
                        "evidence_text": "业绩表格" if not has_position else "简历表业绩表格",
                        "pages": pages,
                        "file_type": "candidate_bid_files"
                    }
                }
                performance_table_variables.append(table_var)
                all_extracted_vars.append(table_var)
                logger.info(f"添加业绩表格变量: {table_var['variable_name']}")
            
            # 步骤3：根据业绩表格变量并发提取每个业绩的详细信息
            if performance_table_variables:
                logger.info(f"开始并发提取 {len(performance_table_variables)} 个业绩的详细信息")
                
                # 为每个业绩表格生成提取任务
                async def extract_single_performance(table_var: Dict[str, Any]) -> List[Dict[str, Any]]:
                    """提取单个业绩的详细信息"""
                    try:
                        table_var_name = table_var.get('variable_name', '')
                        # 从表格变量名中提取业绩变量名（如"第一名业绩要求表1" -> "第一名业绩要求1"）
                        # 需要找到"表"的位置，然后替换为条款名称
                        if '表' in table_var_name:
                            # 提取排名部分和序号部分
                            # 例如："第一名业绩要求表1" -> "第一名业绩要求1"
                            match = re.search(r'(.+?)表(\d+)', table_var_name)
                            if match:
                                base_name = match.group(1)  # "第一名业绩要求"
                                index = match.group(2)  # "1"
                                performance_var_name = f"{base_name}{index}"
                            else:
                                # 回退到旧逻辑
                                performance_var_name = table_var_name.replace('表', '')
                        else:
                            performance_var_name = table_var_name
                        
                        # 生成单个业绩的提取提示词
                        prompt = extractor._generate_single_performance_prompt(
                            table_var=table_var,
                            performance_var_name=performance_var_name,
                            clauses=[eval_item],
                            candidate_names=candidate_names
                        )
                        
                        # 添加文件内容到提示词
                        # 如果是从简历表提取的，使用简历表内容；否则使用item_content
                        content_for_extraction = resume_table_content if (has_position and resume_table_content) else item_content
                        full_prompt = prompt.replace("$content", content_for_extraction)
                        
                        # 调用LLM提取（带重试机制）
                        logger.info(f"提取业绩变量: {performance_var_name}")
                        
                        # 重试机制：最多重试1次（总共2次尝试）
                        max_retries = 1
                        extracted_vars = []
                        
                        for attempt in range(max_retries + 1):
                            try:
                                response = await llm_client.call_llm(
                                    prompt=full_prompt,
                                    file_content=content_for_extraction,
                                    model_type="default"
                                )
                                
                                # 解析JSON响应
                                try:
                                    json_match = re.search(r'\[.*\]', response, re.DOTALL)
                                    if json_match:
                                        json_str = json_match.group(0)
                                        extracted_vars = json.loads(json_str)
                                        extracted_vars = extracted_vars if isinstance(extracted_vars, list) else []
                                    else:
                                        extracted_vars = json.loads(response)
                                        extracted_vars = extracted_vars if isinstance(extracted_vars, list) else []
                                    
                                    # JSON解析成功，跳出重试循环
                                    if attempt > 0:
                                        logger.info(f"业绩变量 {performance_var_name} 第{attempt + 1}次重试成功，JSON解析通过")
                                    break
                                    
                                except json.JSONDecodeError as e:
                                    # JSON解析失败
                                    if attempt < max_retries:
                                        logger.warning(f"业绩变量 {performance_var_name} 第{attempt + 1}次调用JSON解析失败: {e}，准备重试（响应内容前500字符: {response[:500]}）")
                                        continue
                                    else:
                                        # 最后一次尝试也失败
                                        logger.error(f"业绩变量 {performance_var_name} 重试后仍然JSON解析失败: {e}，响应内容前500字符: {response[:500]}")
                                        extracted_vars = []
                                        break
                                        
                            except Exception as e:
                                # LLM调用异常
                                if attempt < max_retries:
                                    logger.warning(f"业绩变量 {performance_var_name} 第{attempt + 1}次调用LLM发生异常: {e}，准备重试")
                                    continue
                                else:
                                    logger.error(f"业绩变量 {performance_var_name} 重试后仍然发生异常: {e}", exc_info=True)
                                    extracted_vars = []
                                    break
                        
                        return extracted_vars
                    except Exception as e:
                        logger.error(f"提取业绩变量失败: {e}")
                        return []
                
                # 并发执行所有业绩提取任务
                tasks = [extract_single_performance(table_var) for table_var in performance_table_variables]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 获取页码范围，用于设置业绩详细信息的pages字段
                items = file_data.get('items', [])
                pages = ""
                if items and items[0].get('start') and items[0].get('end'):
                    pages = f"{items[0].get('start')}-{items[0].get('end')}"
                
                # 合并结果并规范化pages字段
                for res in results:
                    if isinstance(res, Exception):
                        logger.error(f"并发提取业绩异常: {res}")
                        continue
                    if res and isinstance(res, list):
                        # 规范化每个变量的reference_source中的pages字段
                        for var in res:
                            if isinstance(var, dict):
                                ref_source = var.get('reference_source', {})
                                if not isinstance(ref_source, dict):
                                    ref_source = {}
                                
                                # 如果pages为空或不存在，使用传入的页码范围；如果pages已有值，保持原值
                                if not ref_source.get('pages'):
                                    ref_source['pages'] = pages
                                
                                # 确保其他必需字段存在
                                if 'source_url' not in ref_source:
                                    ref_source['source_url'] = bid_url if bid_url else ""
                                if 'evidence_text' not in ref_source:
                                    ref_source['evidence_text'] = ""
                                if 'file_type' not in ref_source:
                                    ref_source['file_type'] = "candidate_bid_files"
                                
                                var['reference_source'] = ref_source
                        
                        all_extracted_vars.extend(res)
                
                logger.info(f"成功并发提取 {len([r for r in results if r and not isinstance(r, Exception)])} 个业绩的详细信息")
            
            return all_extracted_vars
            
        except Exception as e:
            logger.error(f"提取业绩变量失败: {e}", exc_info=True)
            return []
    
    
    async def process_parse_task(self, project_id: str) -> Dict[str, Any]:
        """
        处理解析任务
        
        Args:
            project_id: 项目ID
            
        Returns:
            Dict[str, Any]: 处理结果
        """
        # 初始化临时目录列表，用于后续清理
        temp_dirs_to_cleanup = []
        
        try:
            # 第一步：立即将数据库中进度更新为0，状态更新为1（处理中）（必须在所有操作之前）
            # 只保留初始化：重置进度为0，状态更新为1
            # 无论是否通过API调用，都确保进度从0开始，状态为处理中
            progress_updated = await update_parse_task_progress(project_id, "initialized", "初始化任务", None)
            if not progress_updated:
                logger.error(f"⚠️ 初始化进度失败: 项目ID {project_id}，但继续执行")
            
            # 确保状态也更新为1（处理中）
            status_updated = await update_parse_task_status(project_id, 1, "解析任务处理中", None)
            if not status_updated:
                logger.error(f"⚠️ 初始化状态失败: 项目ID {project_id}，但继续执行")
            
            if progress_updated and status_updated:
                logger.info(f"✅ 进度已初始化为0%，状态已更新为1（处理中），项目ID: {project_id}")
            else:
                logger.warning(f"⚠️ 初始化部分失败: 项目ID {project_id} - 进度更新: {progress_updated}, 状态更新: {status_updated}")
            
            # 转换项目ID为整数
            try:
                project_id_int = int(project_id)
            except ValueError:
                project_id_int = abs(hash(project_id)) % (10**10)
            
            # 步骤1：从数据库获取数据（并行处理）
            logger.info(f"步骤1：从数据库获取项目 {project_id} 的数据（并行处理）")
            
            # 并行获取数据库数据和file_info/file_range数据
            from database.database import db_manager
            from database.data_process import get_variables_values_by_id
            from sqlalchemy import text
            
            async def get_db_data():
                """从数据库获取template_id和previous_variables"""
                with db_manager.get_db_session() as session:
                    # 获取template_id
                    query = text("SELECT template_id FROM eval_report WHERE id = :project_id")
                    result = session.execute(query, {"project_id": project_id_int}).fetchone()
                    if not result or not result[0]:
                        raise Exception(f"未找到项目 {project_id} 的模板ID")
                    template_id = str(result[0])
                    
                    # 获取reference_sources中的变量（前一个接口提取的变量）
                    query = text("SELECT reference_sources FROM eval_report WHERE id = :project_id")
                    result = session.execute(query, {"project_id": project_id_int}).fetchone()
                    previous_variables = []
                    if result and result[0]:
                        try:
                            reference_sources = json.loads(result[0])
                            if isinstance(reference_sources, list):
                                previous_variables = reference_sources
                                logger.info(f"从数据库获取到 {len(previous_variables)} 个前一个接口提取的变量")
                                # 记录前20个变量名称用于调试
                                if previous_variables:
                                    prev_var_names = [var.get('variable_name', '') for var in previous_variables[:20] if isinstance(var, dict)]
                                    logger.info(f"前一个接口的变量列表（前20个）: {prev_var_names}")
                                    if len(previous_variables) > 20:
                                        logger.info(f"... 还有 {len(previous_variables) - 20} 个变量")
                            else:
                                logger.warning(f"reference_sources格式不是列表格式: {type(reference_sources)}")
                        except json.JSONDecodeError as e:
                            logger.warning(f"解析reference_sources失败: {e}")
                    else:
                        logger.info("未找到reference_sources数据，将使用空列表")
                    
                    return template_id, previous_variables
            
            async def get_file_info_data():
                """获取file_info和file_range数据（同步函数包装为异步）"""
                # 在事件循环中运行同步函数，避免阻塞
                loop = asyncio.get_event_loop()
                file_data_list = await loop.run_in_executor(
                    None, 
                    get_file_info_and_range_by_project_id, 
                    project_id_int
                )
                return file_data_list
            
            # 并行执行数据库查询和file_info查询
            logger.info("开始并行获取数据库数据和file_info数据")
            (template_id, previous_variables), file_data_list = await asyncio.gather(
                get_db_data(),
                get_file_info_data()
            )
            
            logger.info(f"获取到模板ID: {template_id}")
            logger.info(f"获取到前一个接口提取的变量数量: {len(previous_variables)}")
            
            if not file_data_list:
                raise Exception(f"项目 {project_id} 没有找到file_info和file_range数据")
            
            logger.info(f"获取到 {len(file_data_list)} 条评审项数据")
            
            # 步骤2：按文件分组并合并页码范围
            logger.info("步骤2：按文件分组并合并页码范围")
            # 注意：页码合并完成的进度更新在后面
            
            file_groups = {}
            for item in file_data_list:
                # 跳过没有页码范围的数据
                if item.get("start") is None or item.get("end") is None:
                    logger.warning(f"跳过没有页码范围的数据: file_info_id={item.get('file_info_id')}, eval_item={item.get('eval_item')}")
                    continue
                    
                bid_url = item["bid_url"]
                if bid_url not in file_groups:
                    file_groups[bid_url] = {
                        "bidder_name": item["bidder_name"],
                        "items": []
                    }
                file_groups[bid_url]["items"].append({
                    "file_info_id": item["file_info_id"],
                    "eval_item": item["eval_item"],
                    "start": item["start"],
                    "end": item["end"]
                })
            
            # 检查是否有有效的数据
            if not file_groups:
                raise Exception(f"项目 {project_id} 虽然有file_info和file_range数据，但都没有有效的页码范围（start和end为NULL），请先填充页码范围")
            
            # 为每个文件合并页码范围
            for bid_url, file_data in file_groups.items():
                ranges = [(item["start"], item["end"]) for item in file_data["items"]]
                merged_ranges = self.merge_page_ranges(ranges)
                file_data["merged_ranges"] = merged_ranges
                logger.info(f"文件 {bid_url} 合并后的页码范围: {merged_ranges}")
            
            # 检查点2：页码合并完成
            await update_parse_task_progress(project_id, "ranges_merged", "页码合并完成", template_id)
            logger.info("进度更新：页码合并完成（+10%）")
            
            # 步骤2.5：预变量处理和文件下载并行进行
            logger.info("步骤2.5：预变量处理（推荐人数、候选人名称、投标人要求拆分）和文件下载并行进行")
            # 注意：预处理变量完成会在后面调用
            
            # 准备预处理所需的变量
            preprocessed_variables = previous_variables.copy()
            
            # 定义预变量处理函数
            async def preprocess_variables_task():
                """预变量处理任务"""
                vars = preprocessed_variables.copy()
                
                # 1. 处理推荐中标候选人数
                logger.info("[预处理步骤1] 处理推荐中标候选人数...")
                from src.utils.pre_variables import process_recommended_candidates_count
                vars = await process_recommended_candidates_count(vars)
                
                # 2. 提取候选人名称（需要推荐人数）
                logger.info("[预处理步骤2] 提取候选人名称...")
                from src.utils.pre_variables import extract_candidate_names_by_count
                vars = await extract_candidate_names_by_count(vars)
                
                # 3. 拆分投标人要求（需要商务评分标准、资格评审标准、投标人要求）
                logger.info("[预处理步骤3] 拆分投标人要求...")
                from src.utils.pre_variable_for_step4 import extract_clause_requirements_from_tables
                
                # 获取必要的变量
                variables_map = {}
                for var in vars:
                    if isinstance(var, dict) and "variable_name" in var:
                        variables_map[var["variable_name"]] = var
                
                bidder_requirements_var = variables_map.get("投标人要求")
                qualification_review_standard_table_var = variables_map.get("资格评审标准")
                business_score_clauses_var = variables_map.get("商务评分标准")
                
                bidder_requirements = bidder_requirements_var.get("variable_value", "") if bidder_requirements_var else ""
                qualification_review_standard_table = qualification_review_standard_table_var.get("variable_value", "") if qualification_review_standard_table_var else ""
                business_score_clauses = business_score_clauses_var.get("variable_value", "") if business_score_clauses_var else ""
                
                if bidder_requirements and qualification_review_standard_table and business_score_clauses:
                    step4_result = await extract_clause_requirements_from_tables(
                        business_score_clauses,
                        qualification_review_standard_table,
                        bidder_requirements
                    )
                    
                    if step4_result.get('success', False):
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
                            vars.append(performance_req_var)
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
                            vars.append(qualification_req_var)
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
                            vars.append(other_req_var)
                            logger.info(f"添加其他条款要求变量，长度: {len(step4_result['other_requirements'])} 字符")
                    else:
                        logger.warning(f"投标人要求拆分失败: {step4_result.get('error', '未知错误')}")
                else:
                    logger.warning("缺少必要数据，跳过投标人要求拆分")
                
                return vars
            
            # 定义文件下载任务（仅下载文件，不解析）
            async def download_files_task():
                """文件下载任务（并行下载所有文件）"""
                from src.utils.async_file_process import AsyncFileProcessor
                file_processor = AsyncFileProcessor()
                downloaded_files = {}
                
                for bid_url, file_data in file_groups.items():
                    # 创建临时目录
                    temp_dir = file_processor.create_temp_directory()
                    try:
                        # 下载文件
                        success, result = await file_processor.download_file(bid_url, temp_dir)
                        if success:
                            file_path = result.split(',')[0] if isinstance(result, str) else result
                            # 检查是否为本地文件
                            import os
                            if os.path.exists(bid_url):
                                file_path = bid_url
                            downloaded_files[bid_url] = {
                                "file_path": file_path,
                                "temp_dir": temp_dir
                            }
                            logger.info(f"文件下载完成: {bid_url}")
                            
                            # 检查是否所有文件都下载完成，如果是则立即更新进度
                            if len(downloaded_files) == len(file_groups):
                                all_downloaded = all(
                                    file_info.get("file_path") and os.path.exists(file_info.get("file_path", ""))
                                    for file_info in downloaded_files.values()
                                )
                                if all_downloaded:
                                    await update_parse_task_progress(project_id, "files_downloaded", "所有文件下载完成", template_id)
                                    logger.info("进度更新：所有文件下载完成（+10%）")
                        else:
                            logger.error(f"文件下载失败: {bid_url}")
                    except Exception as e:
                        logger.error(f"下载文件 {bid_url} 时出错: {e}")
                
                return downloaded_files
            
            # 并行执行预变量处理和文件下载
            logger.info("开始并行执行预变量处理和文件下载...")
            preprocessed_variables, downloaded_files = await asyncio.gather(
                preprocess_variables_task(),
                download_files_task()
            )
            
            logger.info(f"预变量处理完成，共 {len(preprocessed_variables)} 个变量")
            logger.info(f"文件下载完成，共 {len(downloaded_files)} 个文件")
            
            # 检查点1：所有文件下载完成（如果下载任务中未更新，这里再次检查）
            # 确保所有文件都下载成功（检查下载的文件数量是否等于文件组数量）
            if downloaded_files and len(downloaded_files) >= len(file_groups):
                # 检查所有文件是否都有有效的文件路径
                all_downloaded = all(
                    file_info.get("file_path") and os.path.exists(file_info.get("file_path", ""))
                    for file_info in downloaded_files.values()
                )
                if all_downloaded:
                    # 检查当前进度，如果还没有更新过文件下载完成，则更新
                    from database.data_process import _get_current_progress
                    current_progress = await _get_current_progress(project_id)
                    if current_progress < 20:  # 如果进度小于20%，说明文件下载完成还没更新
                        await update_parse_task_progress(project_id, "files_downloaded", "所有文件下载完成", template_id)
                        logger.info("进度更新：所有文件下载完成（+10%）")
                else:
                    logger.warning(f"部分文件下载失败，已下载 {len(downloaded_files)}/{len(file_groups)} 个文件")
            else:
                logger.warning(f"文件下载不完整，已下载 {len(downloaded_files) if downloaded_files else 0}/{len(file_groups)} 个文件")
            
            # 记录所有下载的临时目录，用于后续清理
            for bid_url, file_info in downloaded_files.items():
                if file_info.get('temp_dir'):
                    temp_dirs_to_cleanup.append(file_info['temp_dir'])
                    logger.info(f"记录临时目录用于清理: {file_info['temp_dir']}")
            
            # 获取必要的变量
            variables_map = {}
            for var in preprocessed_variables:
                if isinstance(var, dict) and "variable_name" in var:
                    variables_map[var["variable_name"]] = var
            
            bidder_requirements_var = variables_map.get("投标人要求")
            qualification_review_standard_table_var = variables_map.get("资格评审标准")
            business_score_clauses_var = variables_map.get("商务评分标准")
            
            bidder_requirements = bidder_requirements_var.get("variable_value", "") if bidder_requirements_var else ""
            qualification_review_standard_table = qualification_review_standard_table_var.get("variable_value", "") if qualification_review_standard_table_var else ""
            business_score_clauses = business_score_clauses_var.get("variable_value", "") if business_score_clauses_var else ""
            
            if bidder_requirements and qualification_review_standard_table and business_score_clauses:
                from src.utils.pre_variable_for_step4 import extract_clause_requirements_from_tables
                step4_result = await extract_clause_requirements_from_tables(
                    business_score_clauses,
                    qualification_review_standard_table,
                    bidder_requirements
                )
                
                if step4_result.get('success', False):
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
                        preprocessed_variables.append(performance_req_var)
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
                        preprocessed_variables.append(qualification_req_var)
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
                        preprocessed_variables.append(other_req_var)
                        logger.info(f"添加其他条款要求变量，长度: {len(step4_result['other_requirements'])} 字符")
                else:
                    logger.warning(f"投标人要求拆分失败: {step4_result.get('error', '未知错误')}")
            else:
                logger.warning("缺少必要数据，跳过投标人要求拆分")
            
            logger.info(f"预变量处理完成，共 {len(preprocessed_variables)} 个变量")
            
            # 步骤3：根据合并后的页码范围解析文件（使用预处理后的变量和已下载的文件）
            logger.info("步骤3：根据页码范围解析文件（使用预处理后的变量和已下载的文件）")
            # 注意：文件解析完成的进度更新在后面（所有文件都解析完成后）
            
            all_extracted_variables = []
            # 缓存文件内容，避免重复下载
            file_content_cache = {}
            
            # 并行处理所有文件的复杂文件解析
            async def process_single_file(bid_url: str, file_data: Dict[str, Any]) -> List[Dict[str, Any]]:
                """处理单个文件的解析和变量提取"""
                file_extracted_variables = []
                try:
                    logger.info(f"开始处理文件: {bid_url}")
                    
                    # 使用已下载的文件路径（如果已下载）
                    file_info = downloaded_files.get(bid_url)
                    if file_info:
                        # 使用已下载的文件，直接传入文件路径和临时目录
                        file_path = file_info["file_path"]
                        temp_dir = file_info["temp_dir"]
                    
                    # 提取合并后的页码范围内容（复杂文件解析）
                        full_content = await self._extract_pdf_content_by_ranges_with_path(
                            file_path,
                            file_data["merged_ranges"],
                            temp_dir
                        )
                    else:
                        # 如果文件未下载，使用原来的方法
                        full_content = await self.extract_pdf_content_by_ranges(
                        bid_url, 
                        file_data["merged_ranges"]
                    )
                    
                    if not full_content:
                        logger.warning(f"文件 {bid_url} 内容提取失败，跳过")
                        return file_extracted_variables
                    
                    # 缓存文件内容
                    file_content_cache[bid_url] = full_content
                    
                    # 提取简历表内容（用于包含职位的业绩条款）
                    # 先确定排名，用于简历表提取
                    candidate_names_for_resume = self._get_candidate_names_from_variables(preprocessed_variables)
                    ranking_for_resume = self._get_ranking_by_bidder_name(file_data.get("bidder_name", ""), candidate_names_for_resume)
                    
                    resume_table_content = None
                    try:
                        from src.utils.file_range_filter.resume_table_content_filter import ResumeTableContentFilter
                        resume_filter = ResumeTableContentFilter()
                        # 将full_content合并为字符串
                        full_content_str = "\n\n".join([f"=== 第{page}页 ===\n{content}" for page, content in sorted(full_content.items())])
                        resume_result = resume_filter.filter_resume_table_content(full_content_str, ranking_for_resume)
                        if resume_result.get('extraction_success', False):
                            resume_table_content = resume_result.get('resume_table_content', '')
                            logger.info(f"✓ 成功提取简历表内容，长度: {len(resume_table_content)} 字符")
                        else:
                            logger.warning(f"✗ 简历表内容提取失败: {resume_result.get('error_message', '未知错误')}")
                    except Exception as e:
                        logger.warning(f"提取简历表内容时出错: {e}")
                    
                    # 将简历表内容添加到file_data中，以便后续使用
                    file_data['resume_table_content'] = resume_table_content
                    
                    # 为每个评审项提取对应范围的内容并进行变量提取（并发执行）
                    async def process_single_item(item: Dict[str, Any]) -> List[Dict[str, Any]]:
                        """处理单个评审项的变量提取"""
                        item_extracted_variables = []
                        eval_item = item["eval_item"]
                        start = item["start"]
                        end = item["end"]
                        
                        try:
                            logger.info("=" * 80)
                            logger.info(f"处理评审项: {eval_item}")
                            logger.info(f"页码范围: 第{start}页 - 第{end}页 (共{end-start+1}页)")
                            
                            # 截取对应范围的内容（根据评审条款的页码范围）
                            item_content = self.extract_content_by_range(full_content, start, end)
                            content_length = len(item_content)
                            
                            if not item_content.strip():
                                logger.warning(f"评审项 {eval_item} 的内容为空，跳过")
                                return item_extracted_variables
                            
                            # 显示内容预览（前200字符）
                            content_preview = item_content[:200].replace('\n', ' ').strip()
                            logger.info(f"提取内容长度: {content_length:,} 字符")
                            logger.info(f"内容预览: {content_preview}...")
                            
                            # 步骤4：根据评审条款类型使用对应的提示词进行提取
                            # 判断条款类型
                            clause_type = self._determine_clause_type(eval_item)
                            logger.info(f"评审项 {eval_item} 的条款类型: {clause_type}")
                            
                            # 从preprocessed_variables中获取必要信息（使用预处理后的变量）
                            candidate_count = self._get_candidate_count_from_variables(preprocessed_variables)
                            # 调试：检查preprocessed_variables中是否包含候选人名称变量
                            candidate_name_vars = [var for var in preprocessed_variables if isinstance(var, dict) and "中标候选人名称" in var.get("variable_name", "")]
                            logger.info(f"preprocessed_variables中包含 {len(candidate_name_vars)} 个候选人名称变量: {[var.get('variable_name') for var in candidate_name_vars]}")
                            candidate_names = self._get_candidate_names_from_variables(preprocessed_variables)
                            
                            # 生成对应类型的提示词并提取变量（使用预处理后的变量，包含拆分后的业绩要求、资质要求等）
                            extracted_vars = await self._extract_variables_by_clause_type(
                                item_content=item_content,
                                eval_item=eval_item,
                                clause_type=clause_type,
                                bid_url=bid_url,
                                candidate_count=candidate_count,
                                candidate_names=candidate_names,
                                previous_variables=preprocessed_variables,  # 使用预处理后的变量
                                file_data=file_data,
                                page_range=(start, end)  # 传递页码范围
                            )
                            
                            if extracted_vars:
                                # 判断eval_item属于哪一类条款，用于后续打分
                                def _normalize_clause(text: str) -> str:
                                    return text.replace(" ", "").replace("\n", "") if text else ""

                                def _matches_clause(target: str, clause: str) -> bool:
                                    if not target or not clause:
                                        return False
                                    norm_target = _normalize_clause(target)
                                    norm_clause = _normalize_clause(clause)
                                    if not norm_target or not norm_clause:
                                        return False
                                    return norm_target == norm_clause or norm_target in norm_clause or norm_clause in norm_target

                                from src.utils.dynamic_table_generator import _parse_clauses

                                # 先检查是否属于资格评审标准，若是则绝不标记为商务条款
                                is_business_clause = False
                                matches_qualification_clause = False
                                qualification_text = ""
                                for prev_var in previous_variables:
                                    if isinstance(prev_var, dict) and prev_var.get("variable_name") == "资格评审标准":
                                        qualification_text = prev_var.get("variable_value", "")
                                        break

                                if qualification_text:
                                    qualification_clauses_list = _parse_clauses(qualification_text)
                                    for qual_clause in qualification_clauses_list:
                                        if _matches_clause(eval_item, qual_clause):
                                            matches_qualification_clause = True
                                            logger.debug(f"评审项 {eval_item} 匹配资格评审标准条款 {qual_clause}")
                                            break

                                # 如果不属于资格评审，再检查是否匹配商务评分标准
                                if not matches_qualification_clause and business_score_clauses:
                                    business_clauses_list = _parse_clauses(business_score_clauses)
                                    for bus_clause in business_clauses_list:
                                        if _matches_clause(eval_item, bus_clause):
                                            is_business_clause = True
                                            logger.debug(f"评审项 {eval_item} 属于商务评分标准条款 {bus_clause}")
                                            break
                                
                                # 为每个变量添加eval_item信息和来源标记
                                for var in extracted_vars:
                                    if isinstance(var, dict):
                                        var["eval_item"] = eval_item
                                        var["bid_url"] = bid_url
                                        var["bidder_name"] = file_data["bidder_name"]
                                        # 标记变量是否属于商务部分（用于后续添加得分时直接使用）
                                        var["is_business_clause"] = is_business_clause
                                item_extracted_variables.extend(extracted_vars)
                                logger.info(f"评审项 {eval_item} 提取完成: 共 {len(extracted_vars)} 个变量")
                            else:
                                logger.warning(f"评审项 {eval_item} 未提取到变量 (页码范围: {start}-{end}, 内容长度: {len(item_content):,} 字符)")
                            logger.info("=" * 80)
                            
                        except Exception as e:
                            logger.error(f"评审项 {eval_item} 变量提取失败: {e}", exc_info=True)
                            logger.info("=" * 80)
                        
                        return item_extracted_variables
                    
                    # 并发处理该文件的所有评审项
                    if file_data["items"]:
                        logger.info(f"开始并发处理文件 {bid_url} 的 {len(file_data['items'])} 个评审项")
                        item_tasks = [process_single_item(item) for item in file_data["items"]]
                        item_results = await asyncio.gather(*item_tasks, return_exceptions=True)
                        
                        # 合并所有评审项的提取结果
                        for result in item_results:
                            if isinstance(result, Exception):
                                logger.error(f"评审项提取异常: {result}")
                                continue
                            if result and isinstance(result, list):
                                file_extracted_variables.extend(result)
                        
                        logger.info(f"文件 {bid_url} 的所有评审项提取完成，共提取 {len(file_extracted_variables)} 个变量")
                    
                    return file_extracted_variables
                    
                except Exception as e:
                    logger.error(f"处理文件 {bid_url} 失败: {e}", exc_info=True)
                    return []
            
            # 并行处理所有文件
            logger.info(f"开始并行处理 {len(file_groups)} 个文件")
            file_tasks = [
                process_single_file(bid_url, file_data) 
                for bid_url, file_data in file_groups.items()
            ]
            file_results = await asyncio.gather(*file_tasks, return_exceptions=True)
            
            # 合并所有文件提取的变量
            for result in file_results:
                if isinstance(result, Exception):
                    logger.error(f"文件处理异常: {result}")
                    continue
                if result and isinstance(result, list):
                    all_extracted_variables.extend(result)
            
            # 检查点3：所有文件解析完成（占3份，即30%）
            # 确保所有文件都处理完成（包括异常情况），完成后立即更新进度
            # 无论成功或失败，只要所有文件都处理完了（无论结果如何），就应该更新进度
            all_files_processed = len(file_results) == len(file_groups)  # 所有文件都有结果（包括异常）
            if all_files_processed:
                # 立即更新进度（在所有文件解析完成的第一时间）
                await update_parse_task_progress(project_id, "files_parsed", "所有文件解析完成", template_id)
                logger.info("进度更新：所有文件解析完成（+30%）")
            else:
                # 即使有文件处理失败，也应该更新进度（标记为完成，但可能有部分失败）
                logger.warning(f"部分文件处理可能失败，但所有文件都已处理完成，更新进度")
                await update_parse_task_progress(project_id, "files_parsed", "所有文件解析完成（部分可能失败）", template_id)
                logger.info("进度更新：所有文件解析完成（+30%）")
            
            # 对于 candidate_bid_files 类型，第一步可能没有提取到变量（在第四步和第五步中动态生成）
            # 如果没有提取到变量，但存在文件内容，说明是 candidate_bid_files 类型，允许继续处理
            if not all_extracted_variables:
                if file_content_cache:
                    logger.info("第一步未提取到变量，但存在文件内容，可能是 candidate_bid_files 类型，将在后续步骤中动态生成变量")
                else:
                    raise Exception("没有提取到任何变量，且没有文件内容")
            else:
                logger.info(f"第一步变量提取完成，共提取 {len(all_extracted_variables)} 个变量")
            
            # 步骤5：执行第四步和第五步变量提取（从candidate_bid_files中提取候选人详细信息）
            logger.info("步骤5：执行第四步和第五步变量提取（从candidate_bid_files中提取候选人详细信息）")
            
            # 准备merged_contents（包含所有文件内容）
            # 格式：{file_type: {file_url: content}} 或 {file_type: content}
            merged_contents = {}
            candidate_bid_files_content = {}
            
            for bid_url, file_data in file_groups.items():
                # 使用缓存的内容（避免重复下载）
                full_content = file_content_cache.get(bid_url, {})
                if not full_content:
                    # 如果缓存中没有，重新提取
                    full_content = await self.extract_pdf_content_by_ranges(
                        bid_url,
                        file_data["merged_ranges"]
                    )
                    file_content_cache[bid_url] = full_content
                
                # 合并所有页面内容
                all_content = "\n\n".join([
                    f"=== 第{page}页 ===\n{content}" 
                    for page, content in sorted(full_content.items())
                ])
                # 按URL组织内容（用于第四步第五步处理）
                candidate_bid_files_content[bid_url] = all_content
            
            # 构造merged_contents格式（candidate_bid_files类型）
            # 需要转换为preprocess_variables期望的格式：{'files': {排名: {'content': ..., 'preview': ...}}}
            # 为了兼容，我们同时提供两种格式
            merged_contents["candidate_bid_files"] = candidate_bid_files_content
            
            # 同时构造新格式（如果preprocess_variables需要）
            # 注意：这里我们暂时保持旧格式，因为preprocess_variables会处理旧格式
            
            # 合并变量：预处理后的变量 + 当前步骤提取的变量
            logger.info(f"准备合并变量:")
            logger.info(f"  - 预处理后的变量数量: {len(preprocessed_variables)}")
            logger.info(f"  - 当前步骤提取的变量数量: {len(all_extracted_variables)}")
            
            all_variables = preprocessed_variables + all_extracted_variables
            logger.info(f"合并完成，总共 {len(all_variables)} 个变量（预处理后: {len(preprocessed_variables)} + 当前步骤: {len(all_extracted_variables)}）")
            
            # 验证合并后的变量
            if len(all_variables) != len(preprocessed_variables) + len(all_extracted_variables):
                logger.warning(f"变量合并数量不匹配: 期望 {len(preprocessed_variables) + len(all_extracted_variables)}, 实际 {len(all_variables)}")
            
            # 检查点4：第一步变量提取完成（在文件解析和变量合并完成后更新）
            # 注意：这里的变量提取是指第一步的变量提取（从文件解析中提取的变量）
            # 第四步和第五步的变量提取会在preprocess_variables中完成
            await update_parse_task_progress(project_id, "variables_extracted", "变量提取完成", template_id)
            logger.info("进度更新：变量提取完成（+10%）")
            
            # 调用预处理变量函数（跳过已处理的推荐人数、候选人名称和投标人要求拆分）
            # preprocess_variables内部会处理第四步和第五步（从candidate_bid_files提取详细信息）
            processed_variables = await preprocess_variables(
                all_variables,
                merged_contents,
                skip_early_steps=True  # 跳过已处理的早期步骤
            )
            
            # 生成推荐中标候选人名称变量（因为skip_early_steps=True时，preprocess_variables不会调用此函数）
            logger.info("生成推荐中标候选人名称变量...")
            from src.utils.pre_variables import generate_candidates_summary_text
            processed_variables = await generate_candidates_summary_text(processed_variables)
            
            logger.info(f"预处理完成，最终变量数量: {len(processed_variables)}")
            
            # 检查点5：预处理变量完成（在预处理完成的第一时间更新）
            await update_parse_task_progress(project_id, "preprocessing_completed", "预处理变量完成", template_id)
            logger.info("进度更新：预处理变量完成（+10%）")
            
            # 步骤6：保存所有变量到数据库
            logger.info("步骤6：保存所有变量到数据库")
            
            # 验证变量格式并保存
            if not isinstance(processed_variables, list):
                logger.error(f"processed_variables格式错误，期望列表格式，实际类型: {type(processed_variables)}")
                raise Exception("变量格式错误，无法保存到数据库")
            
            # 记录所有变量的名称（用于调试）
            variable_names = [var.get('variable_name', '') for var in processed_variables if isinstance(var, dict)]
            logger.info(f"准备保存的变量列表（前20个）: {variable_names[:20]}")
            if len(variable_names) > 20:
                logger.info(f"... 还有 {len(variable_names) - 20} 个变量")
            
            # 统计未提取到的变量（值为空或null的变量）
            missing_variables = []
            extracted_variables = []
            for var in processed_variables:
                if isinstance(var, dict):
                    var_name = var.get('variable_name', '')
                    var_value = var.get('variable_value', '')
                    # 检查变量值是否为空
                    if not var_value or var_value == 'null' or var_value == 'None' or str(var_value).strip() == '':
                        missing_variables.append(var_name)
                    else:
                        extracted_variables.append(var_name)
            
            # 详细记录未提取的变量
            if missing_variables:
                missing_list = sorted(missing_variables)
                logger.warning(f"⚠️ 未提取到的变量（共 {len(missing_variables)} 个，占总数 {len(processed_variables)} 的 {len(missing_variables)/len(processed_variables)*100:.1f}%）:")
                # 每10个变量一行，便于阅读
                for i in range(0, len(missing_list), 10):
                    batch = missing_list[i:i+10]
                    logger.warning(f"   未提取变量 {i+1}-{min(i+10, len(missing_list))}: {', '.join(batch)}")
            else:
                logger.info(f"✅ 所有变量都已成功提取（共 {len(extracted_variables)} 个）")
            
            logger.info(f"变量提取统计: 已提取 {len(extracted_variables)} 个，未提取 {len(missing_variables)} 个，总计 {len(processed_variables)} 个")
            
            save_success = save_task_results_to_database(project_id, processed_variables, template_id)
            if not save_success:
                raise Exception("保存变量到数据库失败")
            
            logger.info(f"所有变量已成功保存到数据库，共 {len(processed_variables)} 个变量")
            
            # 检查点7：存储到数据库完成（在保存完成的第一时间更新）
            await update_parse_task_progress(project_id, "variables_saved", "存储到数据库完成", template_id)
            logger.info("进度更新：存储到数据库完成（+10%）")
            
            # 步骤7：渲染模板（从数据库读取变量）
            logger.info("步骤7：从数据库读取变量并渲染模板")
            
            # 确保从数据库读取变量进行渲染（不直接使用内存中的变量）
            final_report = await self.report_service.generate_final_report(
                project_id=project_id,
                template_id=template_id
            )
            
            # 保存最终报告
            save_report_success = await self.report_service.save_final_report(
                project_id=project_id,
                final_report=final_report,
                template_id=template_id
            )
            
            if not save_report_success:
                raise Exception("保存最终报告失败")
            
            # 检查点8：报告生成完成（最终100%，直接设置为100%）
            # 报告生成完成是最后一个步骤，直接设置为100%
            await update_parse_task_progress(project_id, "completed", "解析任务完成", template_id)
            await update_parse_task_status(project_id, status=2, message="解析任务完成", template_id=template_id)
            logger.info(f"已更新状态为完成（status=2），项目ID: {project_id}")
            
            return {
                "project_id": project_id,
                "template_id": template_id,
                "status": "completed",
                "message": "解析任务完成",
                "variables_count": len(processed_variables)
            }
            
        except Exception as e:
            logger.error(f"处理解析任务失败: {e}", exc_info=True)
            # 更新进度为错误状态并更新状态为3（失败）
            await update_parse_task_progress(
                project_id, 
                "error_occurred", 
                f"解析任务失败: {str(e)}", 
                None
            )
            await update_parse_task_status(project_id, status=3, message=f"解析任务失败: {str(e)}")
            logger.error(f"已更新状态为失败（status=3），项目ID: {project_id}，错误: {str(e)}")
            raise e
        finally:
            # 清理所有下载的临时文件
            if temp_dirs_to_cleanup:
                logger.info(f"开始清理 {len(temp_dirs_to_cleanup)} 个临时目录...")
                from src.utils.async_file_process import AsyncFileProcessor
                file_processor = AsyncFileProcessor()
                for temp_dir in temp_dirs_to_cleanup:
                    try:
                        if temp_dir and os.path.exists(temp_dir):
                            logger.info(f"正在清理临时目录: {temp_dir}")
                            success = file_processor.cleanup_temp_directory(temp_dir)
                            if success:
                                logger.info(f"成功清理临时目录: {temp_dir}")
                            else:
                                logger.warning(f"清理临时目录失败: {temp_dir}")
                        else:
                            logger.info(f"临时目录不存在或为空，跳过: {temp_dir}")
                    except Exception as cleanup_error:
                        logger.error(f"清理临时目录时发生错误: {temp_dir}, 错误: {cleanup_error}", exc_info=True)
                logger.info("临时文件清理完成")
            else:
                logger.info("没有需要清理的临时目录")


