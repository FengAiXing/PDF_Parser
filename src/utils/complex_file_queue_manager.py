# -*- coding: utf-8 -*-
"""
复杂文件处理队列管理器
实现真正的排队机制，确保candidate_bid_files按请求顺序依次处理
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum


class ComplexFileStatus(Enum):
    """复杂文件处理状态枚举"""
    PENDING = "pending"      # 等待中
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"        # 失败


@dataclass
class ComplexFileTask:
    """复杂文件处理任务数据结构"""
    task_id: str
    pdf_path: str
    output_dir: str
    callback: Optional[Callable] = None
    status: ComplexFileStatus = ComplexFileStatus.PENDING
    created_at: float = 0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None


class ComplexFileQueueManager:
    """复杂文件处理队列管理器 - 单例模式，确保candidate_bid_files排队处理"""
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._queue = asyncio.Queue()
            self._current_task: Optional[ComplexFileTask] = None
            self._processing_lock = asyncio.Lock()
            self._logger = logging.getLogger(__name__)
            self._task_results: Dict[str, Any] = {}
            self._task_errors: Dict[str, str] = {}
            self._background_task = None
            self._started = False
    
    async def _ensure_started(self):
        """确保后台处理任务已启动"""
        if not self._started:
            self._background_task = asyncio.create_task(self._process_queue())
            self._started = True
            self._logger.info("复杂文件队列管理器后台任务已启动")
    
    async def add_task(self, task_id: str, pdf_path: str, output_dir: str, 
                      callback: Optional[Callable] = None) -> str:
        """
        添加复杂文件处理任务到队列
        
        Args:
            task_id: 任务ID
            pdf_path: PDF文件路径
            output_dir: 输出目录
            callback: 回调函数
            
        Returns:
            str: 任务ID
        """
        # 确保后台任务已启动
        await self._ensure_started()
        
        task = ComplexFileTask(
            task_id=task_id,
            pdf_path=pdf_path,
            output_dir=output_dir,
            callback=callback,
            created_at=time.time()
        )
        
        await self._queue.put(task)
        self._logger.info(f"复杂文件处理任务 {task_id} 已添加到队列，当前队列长度: {self._queue.qsize()}")
        return task_id
    
    async def wait_for_task_completion(self, task_id: str, timeout: int = 3600) -> Optional[str]:
        """
        等待任务完成并返回结果
        
        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）
            
        Returns:
            Optional[str]: 处理结果文件路径，失败时返回None
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 检查任务是否完成
            if task_id in self._task_results:
                result = self._task_results.pop(task_id, None)
                self._task_errors.pop(task_id, None)  # 清理错误信息
                return result
            
            # 检查任务是否失败
            if task_id in self._task_errors:
                error = self._task_errors.pop(task_id, None)
                self._logger.error(f"复杂文件处理任务 {task_id} 失败: {error}")
                return None
            
            # 短暂等待后重试
            await asyncio.sleep(0.1)
        
        self._logger.error(f"复杂文件处理任务 {task_id} 超时")
        return None
    
    async def _process_queue(self):
        """后台处理队列中的任务"""
        while True:
            try:
                # 等待队列中的任务
                task = await self._queue.get()
                
                async with self._processing_lock:
                    self._current_task = task
                    task.status = ComplexFileStatus.PROCESSING
                    task.started_at = time.time()
                
                self._logger.info(f"开始处理复杂文件任务: {task.task_id}")
                
                # 处理任务
                result = await self._process_single_task(task)
                
                # 存储结果
                if result:
                    self._task_results[task.task_id] = result
                    task.status = ComplexFileStatus.COMPLETED
                    task.completed_at = time.time()
                    processing_time = task.completed_at - task.started_at
                    self._logger.info(f"复杂文件处理任务 {task.task_id} 完成，耗时: {processing_time:.2f}秒")
                else:
                    error_msg = f"复杂文件处理失败: {task.pdf_path}"
                    self._task_errors[task.task_id] = error_msg
                    task.status = ComplexFileStatus.FAILED
                    task.error = error_msg
                    self._logger.error(f"复杂文件处理任务 {task.task_id} 失败: {error_msg}")
                
                # 执行回调
                if task.callback:
                    try:
                        await task.callback(task.task_id, result, task.error)
                    except Exception as e:
                        self._logger.error(f"执行回调函数失败: {e}")
                
                async with self._processing_lock:
                    self._current_task = None
                
                # 标记任务完成
                self._queue.task_done()
                
            except Exception as e:
                self._logger.error(f"处理复杂文件任务失败: {e}")
                if self._current_task:
                    self._current_task.status = ComplexFileStatus.FAILED
                    self._task_errors[self._current_task.task_id] = str(e)
                    if self._current_task.callback:
                        try:
                            await self._current_task.callback(self._current_task.task_id, None, str(e))
                        except Exception as callback_error:
                            self._logger.error(f"执行失败回调函数失败: {callback_error}")
                    self._current_task = None
    
    async def _process_single_task(self, task: ComplexFileTask) -> Optional[str]:
        """处理单个复杂文件任务"""
        try:
            from src.utils.complex_file.main_processor import ComplexFileProcessor
            processor = ComplexFileProcessor()
            
            result = await processor.process_candidate_bid_file(
                task.pdf_path, 
                task.output_dir
            )
            
            return result
                
        except Exception as e:
            self._logger.error(f"复杂文件处理失败: {e}")
            raise e
    
    def get_queue_size(self) -> int:
        """获取队列大小"""
        return self._queue.qsize()
    
    def is_processing(self) -> bool:
        """检查是否有任务正在处理"""
        return self._current_task is not None
    
    def get_current_task_id(self) -> Optional[str]:
        """获取当前正在处理的任务ID"""
        return self._current_task.task_id if self._current_task else None


# 全局队列管理器实例（延迟初始化）
complex_file_queue_manager = None

def get_complex_file_queue_manager():
    """获取全局队列管理器实例"""
    global complex_file_queue_manager
    if complex_file_queue_manager is None:
        complex_file_queue_manager = ComplexFileQueueManager()
    return complex_file_queue_manager
