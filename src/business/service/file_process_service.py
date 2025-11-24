# 文件处理服务
import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Any, Optional, Union
from src.utils.async_file_process import AsyncFileProcessor
from src.utils.dotsocr_process import DotsOCRProcessor
from src.utils.json_process import JSONFileParser
from src.utils.complex_file import ComplexFileProcessor
from src.utils.request_queue_manager import queue_manager


class FileProcessService:
    """文件处理服务类"""
    
    def __init__(self):
        """初始化服务"""
        self.dotsocr_processor = DotsOCRProcessor()
        self.json_parser = JSONFileParser()
        self.file_processor = AsyncFileProcessor()  # 使用异步文件处理器
        self.complex_file_processor = ComplexFileProcessor(max_workers=4)
    
    def parse_files_config(self, files_config: Union[Dict[str, str], str, dict]) -> Dict[str, str]:
        """
        解析文件配置，支持多种输入格式
        
        Args:
            files_config: 文件配置（字典、JSON字符串或JSON对象）
            
        Returns:
            Dict[str, str]: 解析后的文件配置字典
            
        Raises:
            ValueError: 文件配置格式错误时抛出异常
        """
        try:
            # 如果已经是字典格式，直接返回
            if isinstance(files_config, dict):
                return self.json_parser.parse_files_config(files_config)
            
            # 如果是字符串，解析为JSON
            elif isinstance(files_config, str):
                return self.json_parser.parse_files_config(files_config)
            
            else:
                raise ValueError(f"不支持的文件配置类型: {type(files_config)}")
                
        except Exception as e:
            raise ValueError(f"文件配置解析失败: {e}")
    
    async def parse_and_merge_files(self, task_groups: Dict[str, List[Dict[str, Any]]], project_id: str) -> Dict[str, str]:
        """
        解析和合并文件内容 - 新逻辑：candidate_bid_files排队，其他文件并行处理
        
        Args:
            task_groups: 分类后的任务组
            project_id: 项目ID
            
        Returns:
            Dict[str, str]: 按文件类型合并后的内容字典
        """
        request_id = f"{project_id}_{int(time.time())}"
        
        try:
            # 检查是否包含candidate_bid_files类型文件
            has_candidate_files = queue_manager.has_candidate_bid_files(task_groups)
            candidate_files_count = queue_manager.get_candidate_bid_files_count(task_groups)
            
            if has_candidate_files:
                # 包含candidate_bid_files，需要排队处理
                logging.info(f"请求 {request_id} 包含 {candidate_files_count} 个candidate_bid_files，需要排队处理...")
                
                # 添加请求到队列
                await queue_manager.add_request(request_id, project_id, task_groups)
                
                # 等待轮到当前请求处理
                while not await queue_manager.wait_for_turn(request_id):
                    await asyncio.sleep(0.1)  # 短暂等待
                
                logging.info(f"请求 {request_id} 获得处理权限，开始文件解析和合并")
                
                # 调用文件处理模块进行解析和合并
                merged_contents = await self.parse_and_merge_files_by_type(task_groups, project_id)
                
                # 释放处理权限
                await queue_manager.release_current_request(request_id, success=True)
                
                logging.info(f"文件解析和合并完成，项目ID: {project_id}")
                logging.info(f"处理的文件类型: {list(merged_contents.keys())}")
                
                return merged_contents
            else:
                # 不包含candidate_bid_files，可以并行处理
                logging.info(f"请求 {request_id} 不包含candidate_bid_files，开始并行处理...")
                
                # 添加并行处理请求
                await queue_manager.add_parallel_request(request_id, project_id, task_groups)
                
                try:
                    # 调用文件处理模块进行解析和合并
                    merged_contents = await self.parse_and_merge_files_by_type(task_groups, project_id)
                    
                    # 释放并行处理权限
                    await queue_manager.release_parallel_request(request_id, success=True)
                    
                    logging.info(f"并行文件解析和合并完成，项目ID: {project_id}")
                    logging.info(f"处理的文件类型: {list(merged_contents.keys())}")
                    
                    return merged_contents
                    
                except Exception as e:
                    # 释放并行处理权限（失败）
                    await queue_manager.release_parallel_request(request_id, success=False, error=str(e))
                    raise e
            
        except Exception as e:
            logging.error(f"文件解析和合并失败: {e}")
            # 异常情况下也要尝试清理临时文件
            try:
                # 这里无法直接访问downloaded_files，但会在parse_and_merge_files_by_type中处理
                pass
            except Exception as cleanup_error:
                logging.error(f"清理临时文件时发生错误: {cleanup_error}")
            raise Exception(f"文件解析和合并失败: {e}")
    
    
    
    async def parse_and_merge_files_by_type(self, task_groups: Dict[str, List[Dict]], project_id: str) -> Dict[str, str]:
        """
        根据任务组解析和合并文件内容 - 新逻辑：先下载所有文件，再解析
        
        Args:
            task_groups: 任务组字典
            project_id: 项目ID
            
        Returns:
            Dict[str, str]: 按文件类型合并后的内容字典
        """
        merged_contents = {}
        
        # 第一步：下载所有文件（并发下载）
        logging.info(f"开始下载所有文件，项目ID: {project_id}")
        all_tasks = []
        
        # 收集所有任务
        regular_tasks = task_groups.get('regular_tasks', [])
        large_file_tasks = task_groups.get('large_file_tasks', [])
        all_tasks.extend(regular_tasks)
        all_tasks.extend(large_file_tasks)
        
        if not all_tasks:
            logging.warning(f"没有找到需要处理的文件，项目ID: {project_id}")
            return merged_contents
        
        # 并发下载所有文件
        download_coroutines = [
            self._download_single_file(task, project_id)
            for task in all_tasks
        ]
        
        logging.info(f"开始并发下载 {len(download_coroutines)} 个文件")
        download_results = await asyncio.gather(*download_coroutines, return_exceptions=True)
        
        # 处理下载结果
        downloaded_files = []
        final_merged_contents = {}
        
        try:
            for i, result in enumerate(download_results):
                if isinstance(result, Exception):
                    logging.error(f"文件下载失败: {all_tasks[i]}, 错误: {result}")
                    raise result
                elif result:
                    downloaded_files.append(result)
            
            logging.info(f"文件下载完成，共下载 {len(downloaded_files)} 个文件")
            
            # 第二步：解析所有已下载的文件（并发解析）
            logging.info(f"开始解析所有已下载的文件")
            parse_coroutines = [
                self._parse_single_downloaded_file(file_info, project_id)
                for file_info in downloaded_files
            ]
            
            parse_results = await asyncio.gather(*parse_coroutines, return_exceptions=True)
            
            # 处理解析结果
            for i, result in enumerate(parse_results):
                if isinstance(result, Exception):
                    logging.error(f"文件解析失败: {downloaded_files[i]}, 错误: {result}")
                    raise result
                elif result:
                    file_type = result['file_type']
                    if file_type not in merged_contents:
                        merged_contents[file_type] = []
                    merged_contents[file_type].append(result)
            
            # 将每个文件类型的内容合并为字符串，同时保持文件URL映射信息
            # 特殊处理：candidate_bid_files不合并，每个文件单独保存
            for file_type, file_contents in merged_contents.items():
                # 对于candidate_bid_files类型，不合并，保持每个文件独立
                if file_type == 'candidate_bid_files':
                    # 新流程：只保存文件路径信息，不保存内容
                    # 每个文件单独保存，命名为"文件1"、"文件2"等
                    candidate_files = {}
                    for i, file_info in enumerate(file_contents):
                        file_key = f"文件{i+1}"
                        file_url = file_info['file_url']
                        file_name = os.path.basename(file_url)
                        file_path = file_info.get('file_path', '')
                        temp_dir = file_info.get('temp_dir')
                        
                        # 新流程：只保存文件路径，不保存内容
                        candidate_files[file_key] = {
                            'file_path': file_path,  # 保存文件路径，供后续使用
                            'temp_dir': temp_dir,   # 保存临时目录，供后续清理使用
                            'file_url': file_url,
                            'file_name': file_name,
                            'file_format': file_info['file_format'],
                            'content': '',  # 不进行内容提取，留空
                            'preview': ''   # 不进行预览，留空
                        }
                    
                    # 保存候选人投标文件信息
                    final_merged_contents[file_type] = {
                        'files': candidate_files,  # 字典：{"文件1": {...}, "文件2": {...}}
                        'file_count': len(file_contents)
                    }
                    logging.info(f"文件类型 {file_type} 处理完成，包含 {len(file_contents)} 个独立文件（仅保存文件路径，不进行完整处理）")
                else:
                    # 其他文件类型按原来的方式合并
                    merged_text_parts = []
                    file_url_mapping = {}  # 用于跟踪内容片段到原始URL的映射
                    
                    for i, file_info in enumerate(file_contents):
                        file_url = file_info['file_url']
                        file_name = os.path.basename(file_url)
                        
                        # 为每个文件内容添加唯一标识符
                        file_identifier = f"FILE_{i+1}_{file_name.replace('.', '_')}"
                        
                        # 在文件内容中明确标注文件URL，让LLM直接使用
                        content_header = f"""
=== 文件 {i+1} ===
文件名: {file_name}
文件格式: {file_info['file_format']}
文件URL: {file_url}
文件标识符: {file_identifier}
=== 文件内容开始 ===
"""
                        content_footer = f"\n=== 文件内容结束 ===\n"
                        
                        # 使用原始完整内容
                        content_with_metadata = f"{content_header}{file_info['content']}{content_footer}"
                        
                        merged_text_parts.append(content_with_metadata)
                        merged_text_parts.append("")  # 添加空行分隔
                        
                        # 记录文件标识符到URL的映射
                        file_url_mapping[file_identifier] = file_url
                    
                    # 保存合并后的内容和URL映射
                    final_merged_contents[file_type] = {
                        'content': "\n".join(merged_text_parts),
                        'file_url_mapping': file_url_mapping,
                        'file_count': len(file_contents)
                    }
                    logging.info(f"文件类型 {file_type} 合并完成，包含 {len(file_contents)} 个文件，URL映射已保存")
                    
        except Exception as e:
            # 任何异常都要清理临时文件
            logging.error(f"文件处理过程中发生异常，开始清理临时文件: {e}")
            raise e
        finally:
            # 无论成功还是失败，都要清理临时文件
            await self._cleanup_all_temp_files(downloaded_files)
            logging.info(f"临时文件清理完成")
        
        return final_merged_contents
    
    async def _cleanup_all_temp_files(self, downloaded_files: List[Dict[str, Any]]):
        """
        清理所有临时下载的文件（除了candidate_bid_files，因为后续还需要使用）
        
        Args:
            downloaded_files: 已下载的文件信息列表
        """
        try:
            for file_info in downloaded_files:
                file_type = file_info.get('file_type')
                temp_dir = file_info.get('temp_dir')
                
                # 不清理candidate_bid_files的临时文件，因为后续还需要使用
                if file_type == 'candidate_bid_files':
                    logging.info(f"保留candidate_bid_files的临时文件: {temp_dir}")
                    continue
                
                if temp_dir:
                    logging.info(f"清理临时目录: {temp_dir}")
                    self.file_processor.cleanup_temp_directory(temp_dir)
            
            logging.info(f"临时文件清理完成（已保留candidate_bid_files的临时文件）")
        except Exception as e:
            logging.error(f"清理临时文件时发生错误: {e}")
            # 清理失败不应该中断主流程，只记录错误

    async def cleanup_candidate_bid_files_temp_dirs(self, merged_contents: Optional[Dict[str, Any]]):
        """
        在业务流程完全结束后，清理candidate_bid_files对应的临时目录

        Args:
            merged_contents: 文件合并结果，包含candidate_bid_files的文件临时目录信息
        """
        if not merged_contents:
            return

        try:
            candidate_data = merged_contents.get('candidate_bid_files')
            if not candidate_data or not isinstance(candidate_data, dict):
                logging.info("没有candidate_bid_files需要清理")
                return

            files_info = candidate_data.get('files')
            if not files_info or not isinstance(files_info, dict):
                logging.info("candidate_bid_files没有可清理的文件记录")
                return

            temp_dirs = set()
            for file_key, file_info in files_info.items():
                if not isinstance(file_info, dict):
                    continue
                temp_dir = file_info.get('temp_dir')
                file_path = file_info.get('file_path')

                if temp_dir:
                    temp_dirs.add(temp_dir)
                    continue

                # 兜底：若未记录temp_dir但文件在临时目录中，则尝试使用其父目录
                if file_path:
                    parent_dir = os.path.dirname(file_path)
                    if parent_dir and "temp_bid_report_" in parent_dir:
                        temp_dirs.add(parent_dir)

            if not temp_dirs:
                logging.info("未找到需要清理的candidate_bid_files临时目录")
                return

            cleaned = 0
            for temp_dir in temp_dirs:
                try:
                    if temp_dir and os.path.exists(temp_dir):
                        if self.file_processor.cleanup_temp_directory(temp_dir):
                            cleaned += 1
                        else:
                            logging.warning(f"candidate_bid_files临时目录清理失败: {temp_dir}")
                    else:
                        logging.info(f"candidate_bid_files临时目录不存在或已清理: {temp_dir}")
                except Exception as cleanup_error:
                    logging.error(f"清理candidate_bid_files临时目录时出错: {temp_dir}, 错误: {cleanup_error}")

            logging.info(f"candidate_bid_files临时目录清理完成，共尝试 {len(temp_dirs)} 个目录，成功 {cleaned} 个")

        except Exception as e:
            logging.error(f"清理candidate_bid_files临时目录过程中发生错误: {e}", exc_info=True)
    
    async def _download_single_file(self, task: Dict[str, str], project_id: str) -> Optional[Dict[str, Any]]:
        """
        下载单个文件 - 只负责下载，不解析内容
        
        Args:
            task: 单个任务信息
            project_id: 项目ID
            
        Returns:
            Dict: 下载结果，包含文件路径等信息
        """
        file_type = task['file_type']
        file_url = task['file_url']
        file_format = task['file_format']
        temp_dir = None
        
        try:
            # 检查是否为本地文件
            if os.path.exists(file_url):
                # 本地文件，直接返回路径
                logging.info(f"检测到本地文件，直接使用: {file_type} - {file_url}")
                return {
                    'file_type': file_type,
                    'file_url': file_url,
                    'file_format': file_format,
                    'file_path': file_url,
                    'temp_dir': None
                }
            else:
                # 远程文件，需要下载
                temp_dir = self.file_processor.create_temp_directory()
                success, result = await self.file_processor.download_file(file_url, temp_dir)
                
                if success:
                    file_path = result.split(',')[0]  # 取第一个文件路径
                    logging.info(f"文件下载成功: {file_type} - {file_url}")
                    return {
                        'file_type': file_type,
                        'file_url': file_url,
                        'file_format': file_format,
                        'file_path': file_path,
                        'temp_dir': temp_dir
                    }
                else:
                    logging.error(f"文件下载失败: {file_type} - {file_url}")
                    raise Exception(f"文件下载失败: {file_type} - {file_url}")
                    
        except Exception as e:
            logging.error(f"下载文件时发生错误: {file_type} - {file_url}, 错误: {e}")
            # 清理临时目录
            if temp_dir:
                self.file_processor.cleanup_temp_directory(temp_dir)
            raise e
    
    async def _parse_single_downloaded_file(self, file_info: Dict[str, Any], project_id: str) -> Optional[Dict[str, Any]]:
        """
        解析单个已下载的文件
        
        Args:
            file_info: 已下载的文件信息
            project_id: 项目ID
            
        Returns:
            Dict: 解析结果
        """
        file_type = file_info['file_type']
        file_url = file_info['file_url']
        file_format = file_info['file_format']
        file_path = file_info['file_path']
        temp_dir = file_info.get('temp_dir')
        
        try:
            # 检查是否为candidate_bid_files类型
            # 新流程：candidate_bid_files只保留文件路径，不进行完整处理
            # 完整处理将在后续步骤中使用pymupdf只提取第一页的投标人名称
            if file_type == 'candidate_bid_files':
                logging.info(f"检测到candidate_bid_files类型，跳过完整处理，仅保留文件路径: {file_url}")
                
                # 动态检测实际文件格式（不需要提取内容，直接根据文件扩展名）
                actual_file_format = self.file_processor._detect_file_format_from_path(file_path)
                
                # 只返回文件路径信息，不进行OCR等完整处理
                # 后续在complex_file_service中会使用pymupdf只提取第一页
                return {
                    'file_type': file_type,
                    'file_url': file_url,
                    'file_format': actual_file_format,
                    'file_path': file_path,  # 保存文件路径，供后续使用
                    'temp_dir': temp_dir,   # 保存临时目录，供后续清理使用
                    'content': ''  # 不进行内容提取，留空
                }
            
            # 其他文件类型需要提取内容
            try:
                content = self.file_processor.extract_file_content(file_path)
                
                if content:
                    # 动态检测实际文件格式
                    actual_file_format = self.file_processor._detect_file_format_from_path(file_path)
                    
                    # 其他文件类型使用常规处理器
                    logging.info(f"成功处理文件: {file_type} - {file_url} (格式: {actual_file_format})")
                    
                    return {
                        'file_type': file_type,
                        'file_url': file_url,
                        'file_format': actual_file_format,
                        'content': content
                    }
                else:
                    logging.error(f"文件内容提取失败: {file_type} - {file_url}")
                    raise Exception(f"文件内容提取失败: {file_type} - {file_url}")
                    
            except ValueError as e:
                # 不支持的文件格式，记录错误并跳过该文件
                logging.error(f"不支持的文件格式: {file_type} - {file_url}, 错误: {e}")
                raise Exception(f"不支持的文件格式: {file_type} - {file_url}, 错误: {e}")
                
        except Exception as e:
            logging.error(f"解析文件时发生错误: {file_type} - {file_url}, 错误: {e}")
            # 解析失败时也要清理临时文件（但candidate_bid_files需要保留）
            if temp_dir and file_type != 'candidate_bid_files':
                logging.info(f"解析失败，清理临时目录: {temp_dir}")
                self.file_processor.cleanup_temp_directory(temp_dir)
            raise e
        finally:
            # 清理临时目录（仅当创建了临时目录时，但candidate_bid_files需要保留供后续使用）
            if temp_dir and file_type != 'candidate_bid_files':
                self.file_processor.cleanup_temp_directory(temp_dir)
    
    async def _process_single_regular_file(self, task: Dict[str, str], project_id: str) -> Optional[Dict[str, Any]]:
        """
        处理单个常规文件 - 完全异步
        
        Args:
            task: 单个任务信息
            project_id: 项目ID
            
        Returns:
            Dict: 处理结果
        """
        file_type = task['file_type']
        file_url = task['file_url']
        file_format = task['file_format']
        temp_dir = None
        
        try:
            # 检查是否为本地文件
            if os.path.exists(file_url):
                # 本地文件，直接处理
                file_path = file_url
                logging.info(f"检测到本地文件，直接处理: {file_type} - {file_url}")
            else:
                # 远程文件，需要下载
                temp_dir = self.file_processor.create_temp_directory()
                success, result = await self.file_processor.download_file(file_url, temp_dir)
                
                if success:
                    file_path = result.split(',')[0]  # 取第一个文件路径
                else:
                    logging.error(f"文件下载失败: {file_type} - {file_url}")
                    raise Exception(f"文件下载失败: {file_type} - {file_url}")
            
            # 提取文件内容 - 让extractor自动检测文件类型
            try:
                content = self.file_processor.extract_file_content(file_path)
                
                if content:
                    # 动态检测实际文件格式
                    actual_file_format = self.file_processor._detect_file_format_from_path(file_path)
                    
                    logging.info(f"成功处理常规文件: {file_type} - {file_url} (格式: {actual_file_format})")
                    
                    return {
                        'file_type': file_type,
                        'file_url': file_url,
                        'file_format': actual_file_format,
                        'content': content
                    }
                else:
                    logging.error(f"文件内容提取失败: {file_type} - {file_url}")
                    raise Exception(f"文件内容提取失败: {file_type} - {file_url}")
                    
            except ValueError as e:
                # 不支持的文件格式，记录错误并跳过该文件
                logging.error(f"不支持的文件格式: {file_type} - {file_url}, 错误: {e}")
                raise Exception(f"不支持的文件格式: {file_type} - {file_url}, 错误: {e}")
                
        except Exception as e:
            logging.error(f"处理常规文件时发生错误: {file_type} - {file_url}, 错误: {e}")
            raise e
        finally:
            # 清理临时目录（仅当创建了临时目录时）
            if 'temp_dir' in locals() and temp_dir:
                self.file_processor.cleanup_temp_directory(temp_dir)
    
    async def _process_single_large_file_parallel(self, task: Dict[str, str], project_id: str) -> Optional[Dict[str, Any]]:
        """
        处理单个大文件 - 完全并行处理，支持超时控制
        
        Args:
            task: 单个任务信息
            project_id: 项目ID
            
        Returns:
            Dict: 处理结果
        """
        file_type = task['file_type']
        file_url = task['file_url']
        file_format = task['file_format']
        temp_dir = None
        
        try:
            # 检查是否为本地文件
            if os.path.exists(file_url):
                # 本地文件，直接处理
                file_path = file_url
                logging.info(f"检测到本地文件，直接处理: {file_type} - {file_url}")
            else:
                # 远程文件，需要下载
                temp_dir = self.file_processor.create_temp_directory()
                success, result = await self.file_processor.download_file(file_url, temp_dir)
                
                if success:
                    file_path = result.split(',')[0]  # 取第一个文件路径
                else:
                    logging.error(f"文件下载失败: {file_type} - {file_url}")
                    raise Exception(f"文件下载失败: {file_type} - {file_url}")
            
            # 提取文件内容 - 根据文件类型选择处理方式
            try:
                # 检查是否为candidate_bid_files类型，使用PDF过滤器
                if file_type == 'candidate_bid_files':
                    logging.info(f"检测到candidate_bid_files类型，使用PDF过滤器: {file_url}")
                    
                    # 如果是本地文件且没有temp_dir，创建一个临时目录
                    if temp_dir is None:
                        temp_dir = self.file_processor.create_temp_directory()
                        logging.info(f"为本地文件创建临时目录: {temp_dir}")
                    
                    # 首先尝试使用PDF过滤器
                    filtered_file_path = await self._apply_pdf_filter(file_path, temp_dir)
                    pdf_filtered = False
                    
                    if filtered_file_path:
                        # PDF过滤成功，原文件已被替换
                        logging.info(f"PDF过滤成功，原文件已被替换: {file_path}")
                        pdf_filtered = True
                    
                    # 使用并行复杂文件处理器处理candidate_bid_files
                    result_path = await self._process_complex_file_parallel(file_path, temp_dir)
                    
                    if result_path and os.path.exists(result_path):
                        # 读取处理后的文本内容
                        with open(result_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 无论PDF是否筛选过，都需要执行关键字截取
                        logging.info(f"开始对candidate_bid_files进行关键字提取: {file_url}")
                        from src.utils.file_range_filter.keyword_extractor import KeywordExtractor
                        keyword_extractor = KeywordExtractor()
                        extracted_content = keyword_extractor.extract_content_by_keywords(content, file_type, file_url)
                        
                        # 动态检测实际文件格式
                        actual_file_format = self.file_processor._detect_file_format_from_path(file_path)
                        
                        logging.info(f"成功处理candidate_bid_files: {file_type} - {file_url} (格式: {actual_file_format})")
                        logging.info(f"关键字提取完成，提取内容长度: {len(extracted_content)} 字符")
                        
                        return {
                            'file_type': file_type,
                            'file_url': file_url,
                            'file_format': actual_file_format,
                            'content': content,  # 原始完整内容
                            'extracted_content': extracted_content  # 关键字提取后的内容
                        }
                    else:
                        logging.error(f"复杂文件处理失败: {file_type} - {file_url}")
                        raise Exception(f"复杂文件处理失败: {file_type} - {file_url}")
                else:
                    # 其他大文件类型使用常规处理器
                    content = self.file_processor.extract_file_content(file_path)
                    
                    if content:
                        # 动态检测实际文件格式
                        actual_file_format = self.file_processor._detect_file_format_from_path(file_path)
                        
                        logging.info(f"成功处理大文件: {file_type} - {file_url} (格式: {actual_file_format})")
                        
                        return {
                            'file_type': file_type,
                            'file_url': file_url,
                            'file_format': actual_file_format,
                            'content': content
                        }
                    else:
                        logging.error(f"文件内容提取失败: {file_type} - {file_url}")
                        raise Exception(f"文件内容提取失败: {file_type} - {file_url}")
                        
            except ValueError as e:
                # 不支持的文件格式，记录错误并跳过该文件
                logging.error(f"不支持的文件格式: {file_type} - {file_url}, 错误: {e}")
                raise Exception(f"不支持的文件格式: {file_type} - {file_url}, 错误: {e}")
                
        except Exception as e:
            logging.error(f"处理大文件时发生错误: {file_type} - {file_url}, 错误: {e}")
            raise e
        finally:
            # 清理临时目录（仅当创建了临时目录时）
            if 'temp_dir' in locals() and temp_dir:
                self.file_processor.cleanup_temp_directory(temp_dir)
    
    async def _apply_pdf_filter(self, file_path: str, temp_dir: str) -> Optional[str]:
        """
        异步应用PDF过滤器，专门针对candidate_bid_files类型的PDF文件
        先去除签章，然后筛选后的PDF会替换原来的PDF文件
        
        Args:
            file_path: 原始PDF文件路径
            temp_dir: 临时目录
            
        Returns:
            替换后的PDF文件路径，如果过滤失败返回None
        """
        try:
            from src.utils.async_pdf_processor import AsyncPDFProcessor
            
            processor = AsyncPDFProcessor()
            
            # 异步处理PDF：先去签章，再筛选内容
            result = await processor.process_pdf_async(file_path, temp_dir)
            
            return result
            
        except Exception as e:
            logging.error(f"PDF过滤过程中发生错误: {file_path}, 错误: {e}")
            return None
    
    
    async def _process_complex_file_parallel(self, file_path: str, temp_dir: str) -> Optional[str]:
        """
        使用全局队列管理器处理复杂文件，确保排队处理
        
        Args:
            file_path: 文件路径
            temp_dir: 临时目录
            
        Returns:
            处理结果文件路径
        """
        try:
            from src.utils.complex_file_queue_manager import get_complex_file_queue_manager
            
            # 获取队列管理器实例
            queue_manager = get_complex_file_queue_manager()
            
            # 创建任务ID
            task_id = f"complex_{int(time.time())}_{hash(file_path) % 10000}"
            
            # 添加任务到全局队列
            await queue_manager.add_task(task_id, file_path, temp_dir)
            
            # 等待任务完成
            result = await queue_manager.wait_for_task_completion(task_id, timeout=3600)
            
            if result is None:
                raise Exception(f"复杂文件处理失败: {file_path}")
            
            return result
            
        except Exception as e:
            logging.error(f"复杂文件处理失败: {file_path}, 错误: {e}")
            raise e

    async def _process_single_large_file(self, task: Dict[str, str], project_id: str) -> Optional[Dict[str, Any]]:
        """
        处理单个大文件 - 完全异步
        
        Args:
            task: 单个任务信息
            project_id: 项目ID
            
        Returns:
            Dict: 处理结果
        """
        file_type = task['file_type']
        file_url = task['file_url']
        file_format = task['file_format']
        temp_dir = None
        
        try:
            # 检查是否为本地文件
            if os.path.exists(file_url):
                # 本地文件，直接处理
                file_path = file_url
                logging.info(f"检测到本地文件，直接处理: {file_type} - {file_url}")
            else:
                # 远程文件，需要下载
                temp_dir = self.file_processor.create_temp_directory()
                success, result = await self.file_processor.download_file(file_url, temp_dir)
                
                if success:
                    file_path = result.split(',')[0]  # 取第一个文件路径
                else:
                    logging.error(f"文件下载失败: {file_type} - {file_url}")
                    raise Exception(f"文件下载失败: {file_type} - {file_url}")
            
            # 提取文件内容 - 根据文件类型选择处理方式
            try:
                # 检查是否为candidate_bid_files类型，使用PDF过滤器
                if file_type == 'candidate_bid_files':
                    logging.info(f"检测到candidate_bid_files类型，使用PDF过滤器: {file_url}")
                    
                    # 如果是本地文件且没有temp_dir，创建一个临时目录
                    if temp_dir is None:
                        temp_dir = self.file_processor.create_temp_directory()
                        logging.info(f"为本地文件创建临时目录: {temp_dir}")
                    
                    # 首先尝试使用PDF过滤器
                    filtered_file_path = await self._apply_pdf_filter(file_path, temp_dir)
                    pdf_filtered = False
                    
                    logging.info(f"PDF过滤器返回值: {filtered_file_path}")
                    
                    if filtered_file_path:
                        # PDF过滤成功，原文件已被替换
                        logging.info(f"PDF过滤成功，原文件已被替换: {file_path}")
                        pdf_filtered = True
                    else:
                        logging.info(f"PDF过滤失败或未进行过滤: {file_path}")
                    
                    # 使用复杂文件处理器处理candidate_bid_files
                    result_path = await self.complex_file_processor.process_candidate_bid_file(file_path, temp_dir)
                    
                    if result_path and os.path.exists(result_path):
                        # 读取处理后的文本内容
                        with open(result_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 无论PDF是否筛选过，都需要执行关键字截取
                        logging.info(f"开始对candidate_bid_files进行关键字提取: {file_url}")
                        from src.utils.file_range_filter.keyword_extractor import KeywordExtractor
                        keyword_extractor = KeywordExtractor()
                        extracted_content = keyword_extractor.extract_content_by_keywords(content, file_type, file_url)
                        
                        # 动态检测实际文件格式
                        actual_file_format = self.file_processor._detect_file_format_from_path(file_path)
                        
                        logging.info(f"成功处理candidate_bid_files: {file_type} - {file_url} (格式: {actual_file_format})")
                        logging.info(f"关键字提取完成，提取内容长度: {len(extracted_content)} 字符")
                        
                        return {
                            'file_type': file_type,
                            'file_url': file_url,
                            'file_format': actual_file_format,
                            'content': content,  # 原始完整内容
                            'extracted_content': extracted_content  # 关键字提取后的内容
                        }
                    else:
                        logging.error(f"复杂文件处理失败: {file_type} - {file_url}")
                        raise Exception(f"复杂文件处理失败: {file_type} - {file_url}")
                else:
                    # 其他大文件类型使用常规处理器
                    content = self.file_processor.extract_file_content(file_path)
                    
                    if content:
                        # 动态检测实际文件格式
                        actual_file_format = self.file_processor._detect_file_format_from_path(file_path)
                        
                        logging.info(f"成功处理大文件: {file_type} - {file_url} (格式: {actual_file_format})")
                        
                        return {
                            'file_type': file_type,
                            'file_url': file_url,
                            'file_format': actual_file_format,
                            'content': content
                        }
                    else:
                        logging.error(f"文件内容提取失败: {file_type} - {file_url}")
                        raise Exception(f"文件内容提取失败: {file_type} - {file_url}")
                        
            except ValueError as e:
                # 不支持的文件格式，记录错误并跳过该文件
                logging.error(f"不支持的文件格式: {file_type} - {file_url}, 错误: {e}")
                raise Exception(f"不支持的文件格式: {file_type} - {file_url}, 错误: {e}")
                
        except Exception as e:
            logging.error(f"处理大文件时发生错误: {file_type} - {file_url}, 错误: {e}")
            raise e
        finally:
            # 清理临时目录（仅当创建了临时目录时）
            if 'temp_dir' in locals() and temp_dir:
                self.file_processor.cleanup_temp_directory(temp_dir)
    
    def save_parsed_content_to_database(self, merged_contents: Dict[str, str], project_id: str) -> bool:
        """
        保存解析结果到数据库 - 业务逻辑方法
        
        Args:
            merged_contents: 合并后的内容字典
            project_id: 项目ID
            
        Returns:
            是否保存成功
        """
        try:
            # 后续考虑是否需要
            # 目前返回True表示保存成功
            logging.info(f"保存解析结果到数据库，项目ID: {project_id}")
            logging.info(f"保存的内容类型: {list(merged_contents.keys())}")
            return True
        except Exception as e:
            logging.error(f"保存到数据库失败: {e}")
            return False
    
    
    
    

