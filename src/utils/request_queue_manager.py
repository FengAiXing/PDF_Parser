# -*- coding: utf-8 -*-
"""
请求队列管理器
实现先进先出的排队机制，确保不同请求之间的文件下载和解析步骤串行执行
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class RequestStatus(Enum):
    """请求状态枚举"""
    PENDING = "pending"      # 等待中
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"        # 失败


@dataclass
class QueueRequest:
    """队列请求数据结构"""
    request_id: str
    project_id: str
    task_groups: Dict[str, Any]
    callback: Optional[Callable] = None
    created_at: float = 0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: RequestStatus = RequestStatus.PENDING
    error: Optional[str] = None


class RequestQueueManager:
    """请求队列管理器 - 单例模式，支持candidate_bid_files排队，其他文件并行处理"""
    
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
            self._current_request: Optional[QueueRequest] = None
            self._processing_lock = asyncio.Lock()
            self._request_status: Dict[str, RequestStatus] = {}
            self._logger = logging.getLogger(__name__)
            # 新增：支持并行处理的请求集合
            self._parallel_requests: Dict[str, QueueRequest] = {}
            self._parallel_processing_lock = asyncio.Lock()
    
    async def add_request(self, request_id: str, project_id: str, task_groups: Dict[str, Any], 
                         callback: Optional[Callable] = None) -> str:
        """
        添加请求到队列
        
        Args:
            request_id: 请求ID
            project_id: 项目ID
            task_groups: 任务组
            callback: 回调函数
            
        Returns:
            str: 请求ID
        """
        request = QueueRequest(
            request_id=request_id,
            project_id=project_id,
            task_groups=task_groups,
            callback=callback,
            created_at=time.time()
        )
        
        await self._queue.put(request)
        self._request_status[request_id] = RequestStatus.PENDING
        
        self._logger.info(f"请求 {request_id} 已添加到队列，当前队列长度: {self._queue.qsize()}")
        return request_id
    
    async def get_next_request(self) -> Optional[QueueRequest]:
        """
        获取下一个请求（非阻塞）
        
        Returns:
            QueueRequest: 下一个请求，如果没有则返回None
        """
        try:
            request = self._queue.get_nowait()
            return request
        except asyncio.QueueEmpty:
            return None
    
    async def wait_for_turn(self, request_id: str) -> bool:
        """
        等待轮到指定请求处理
        
        Args:
            request_id: 请求ID
            
        Returns:
            bool: 是否成功获取处理权限
        """
        async with self._processing_lock:
            # 检查是否轮到当前请求
            if self._current_request is None:
                # 获取队列中的第一个请求
                try:
                    next_request = self._queue.get_nowait()
                    if next_request.request_id == request_id:
                        # 是当前请求，开始处理
                        self._current_request = next_request
                        self._current_request.status = RequestStatus.PROCESSING
                        self._current_request.started_at = time.time()
                        self._request_status[request_id] = RequestStatus.PROCESSING
                        self._logger.info(f"请求 {request_id} 开始处理")
                        return True
                    else:
                        # 不是当前请求，重新放回队列前面
                        await self._queue.put(next_request)
                        return False
                except asyncio.QueueEmpty:
                    # 队列为空，返回False
                    return False
            else:
                # 有其他请求正在处理，等待
                return False
    
    async def release_current_request(self, request_id: str, success: bool = True, error: str = None):
        """
        释放当前请求的处理权限
        
        Args:
            request_id: 请求ID
            success: 是否成功
            error: 错误信息
        """
        async with self._processing_lock:
            if self._current_request and self._current_request.request_id == request_id:
                self._current_request.completed_at = time.time()
                self._current_request.status = RequestStatus.COMPLETED if success else RequestStatus.FAILED
                self._current_request.error = error
                self._request_status[request_id] = self._current_request.status
                
                processing_time = self._current_request.completed_at - self._current_request.started_at
                self._logger.info(f"请求 {request_id} 处理完成，耗时: {processing_time:.2f}秒")
                
                self._current_request = None
    
    def get_request_status(self, request_id: str) -> RequestStatus:
        """
        获取请求状态
        
        Args:
            request_id: 请求ID
            
        Returns:
            RequestStatus: 请求状态
        """
        return self._request_status.get(request_id, RequestStatus.PENDING)
    
    def get_queue_size(self) -> int:
        """
        获取队列大小
        
        Returns:
            int: 队列大小
        """
        return self._queue.qsize()
    
    def is_processing(self) -> bool:
        """
        检查是否有请求正在处理
        
        Returns:
            bool: 是否有请求正在处理
        """
        return self._current_request is not None
    
    def get_current_request_id(self) -> Optional[str]:
        """
        获取当前正在处理的请求ID
        
        Returns:
            Optional[str]: 当前请求ID
        """
        return self._current_request.request_id if self._current_request else None
    
    def has_candidate_bid_files(self, task_groups: Dict[str, Any]) -> bool:
        """
        检查任务组是否包含candidate_bid_files类型文件
        
        Args:
            task_groups: 任务组字典
            
        Returns:
            bool: 是否包含candidate_bid_files
        """
        large_file_tasks = task_groups.get('large_file_tasks', [])
        for task in large_file_tasks:
            if task.get('file_type') == 'candidate_bid_files':
                return True
        return False
    
    def get_candidate_bid_files_count(self, task_groups: Dict[str, Any]) -> int:
        """
        获取candidate_bid_files类型文件的数量
        
        Args:
            task_groups: 任务组字典
            
        Returns:
            int: candidate_bid_files文件数量
        """
        large_file_tasks = task_groups.get('large_file_tasks', [])
        count = 0
        for task in large_file_tasks:
            if task.get('file_type') == 'candidate_bid_files':
                count += 1
        return count
    
    async def add_parallel_request(self, request_id: str, project_id: str, task_groups: Dict[str, Any], 
                                  callback: Optional[Callable] = None) -> str:
        """
        添加并行处理请求（非candidate_bid_files类型）
        
        Args:
            request_id: 请求ID
            project_id: 项目ID
            task_groups: 任务组
            callback: 回调函数
            
        Returns:
            str: 请求ID
        """
        request = QueueRequest(
            request_id=request_id,
            project_id=project_id,
            task_groups=task_groups,
            callback=callback,
            created_at=time.time()
        )
        
        async with self._parallel_processing_lock:
            self._parallel_requests[request_id] = request
            self._request_status[request_id] = RequestStatus.PROCESSING
        
        self._logger.info(f"并行请求 {request_id} 已添加，当前并行请求数: {len(self._parallel_requests)}")
        return request_id
    
    async def release_parallel_request(self, request_id: str, success: bool = True, error: str = None):
        """
        释放并行处理请求
        
        Args:
            request_id: 请求ID
            success: 是否成功
            error: 错误信息
        """
        async with self._parallel_processing_lock:
            if request_id in self._parallel_requests:
                request = self._parallel_requests[request_id]
                request.completed_at = time.time()
                request.status = RequestStatus.COMPLETED if success else RequestStatus.FAILED
                request.error = error
                self._request_status[request_id] = request.status
                
                # 计算处理时间，如果started_at为None则使用created_at
                start_time = request.started_at if request.started_at else request.created_at
                processing_time = request.completed_at - start_time
                self._logger.info(f"并行请求 {request_id} 处理完成，耗时: {processing_time:.2f}秒")
                
                del self._parallel_requests[request_id]
    
    def get_parallel_requests_count(self) -> int:
        """
        获取并行处理的请求数量
        
        Returns:
            int: 并行请求数量
        """
        return len(self._parallel_requests)
    
    def is_parallel_processing(self) -> bool:
        """
        检查是否有并行请求正在处理
        
        Returns:
            bool: 是否有并行请求正在处理
        """
        return len(self._parallel_requests) > 0


# 全局队列管理器实例
queue_manager = RequestQueueManager()
