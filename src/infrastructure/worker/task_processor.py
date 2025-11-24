# -*- coding: utf-8 -*-
"""
异步任务处理器

基础设施层的任务调度和队列管理组件
负责监听任务队列、分发任务给业务层处理
支持真正的异步并发处理
"""

import logging
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Callable, Optional
import weakref

logger = logging.getLogger(__name__)

class AsyncTaskProcessor:
    """
    异步任务处理器类
    
    负责从任务队列中获取任务并分发给相应的业务处理器
    支持真正的异步并发处理，每个请求独立处理
    """
    
    def __init__(self, business_processor: Optional[Callable] = None, max_concurrent_tasks: int = 100):
        """
        初始化异步任务处理器
        
        Args:
            business_processor: 业务处理器函数
            max_concurrent_tasks: 最大并发任务数（设置为较大值，支持真正的并发）
        """
        self.business_processor = business_processor
        self.max_concurrent_tasks = max_concurrent_tasks
        # 任务存储（生产环境建议使用Redis）
        self._tasks: Dict[str, Dict[str, Any]] = {}
        # 正在处理的任务
        self._processing_tasks: Dict[str, asyncio.Task] = {}
        # 移除信号量限制，让每个任务完全独立处理
        # self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        # 任务队列
        self._task_queue = asyncio.Queue()
        # 启动标志
        self._is_running = False
        # 后台任务
        self._background_task = None
    
    def create_task(self, task_type: str, **kwargs) -> str:
        """
        创建新任务
        
        Args:
            task_type: 任务类型
            **kwargs: 任务参数
            
        Returns:
            str: 任务ID
        """
        task_id = str(uuid.uuid4())
        
        self._tasks[task_id] = {
            "task_id": task_id,
            "task_type": task_type,
            "code": 200,  # 200: 成功（待处理）
            "progress": 0,
            "message": "任务已创建，等待处理...",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "result": None,
            "error": None,
            "parameters": kwargs
        }
        
        # 立即启动异步处理
        asyncio.create_task(self._process_task_async(task_id))
        logger.info(f"创建任务 {task_id} ({task_type})，立即开始异步处理")
        return task_id
    
    def update_task_status(self, task_id: str, code: int, progress: int = None, 
                          message: str = None, result: Any = None, error: str = None):
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            code: 任务状态码
            progress: 进度百分比 (0-100)
            message: 状态消息
            result: 任务结果
            error: 错误信息
        """
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task["code"] = code
            task["updated_at"] = datetime.now().isoformat()
            
            if progress is not None:
                task["progress"] = progress
            if message is not None:
                task["message"] = message
            if result is not None:
                task["result"] = result
            if error is not None:
                task["error"] = error
            
            logger.info(f"任务 {task_id} 状态更新: {code}")
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict: 任务状态信息，如果任务不存在返回None
        """
        return self._tasks.get(task_id)
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict: 任务结果，如果任务不存在或未完成返回None
        """
        task = self._tasks.get(task_id)
        if task and task["code"] == 200:  # 成功完成
            return {
                "success": True,
                "message": "任务已完成",
                "data": task["result"]
            }
        return None
    
    def list_tasks(self, status: str = None) -> list:
        """
        列出所有任务
        
        Args:
            status: 过滤状态，None表示所有状态
            
        Returns:
            list: 任务列表
        """
        tasks = list(self._tasks.values())
        if status:
            # 支持字符串和数字状态码
            if isinstance(status, str):
                status_map = {"success": 200, "error": 500, "not_found": 404}
                status_code = status_map.get(status, status)
            else:
                status_code = status
            tasks = [task for task in tasks if task["code"] == status_code]
        return tasks
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """
        清理旧任务
        
        Args:
            max_age_hours: 最大保留时间（小时）
        """
        from datetime import timedelta
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        to_remove = []
        for task_id, task in self._tasks.items():
            created_at = datetime.fromisoformat(task["created_at"])
            if created_at < cutoff_time and task["code"] in [200, 500]:  # 成功完成或失败
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del self._tasks[task_id]
            logger.info(f"清理旧任务 {task_id}")
    
    async def _process_task_async(self, task_id: str):
        """
        异步处理单个任务 - 完全独立处理，不限制并发
        
        Args:
            task_id: 任务ID
        """
        try:
            # 获取任务信息
            if task_id not in self._tasks:
                logger.warning(f"任务 {task_id} 不存在")
                return
            
            task = self._tasks[task_id]
            logger.info(f"开始异步处理任务 {task_id}")
            
            # 标记任务为处理中
            self.update_task_status(
                task_id=task_id,
                code=200,  # 处理中
                message="任务处理中..."
            )
            
            # 如果有业务处理器，则调用它处理任务
            if self.business_processor:
                # 检查业务处理器是否为异步函数
                if asyncio.iscoroutinefunction(self.business_processor):
                    # 异步处理
                    result = await self.business_processor(task)
                else:
                    # 同步处理，在线程池中运行
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, self.business_processor, task)
                
                # 更新任务状态为完成
                self.update_task_status(
                    task_id=task_id,
                    code=200,  # 成功完成
                    progress=100,
                    message="任务处理完成",
                    result=result
                )
                
                logger.info(f"任务 {task_id} 异步处理完成")
            else:
                raise Exception("未配置业务处理器")
                
        except Exception as e:
            # 更新任务状态为失败
            self.update_task_status(
                task_id=task_id,
                code=500,  # 网络错误/服务器错误
                message=f"处理失败: {str(e)}",
                error=str(e)
            )
            
            logger.error(f"异步处理任务 {task_id} 失败: {e}")
        finally:
            # 从正在处理的任务中移除
            if task_id in self._processing_tasks:
                del self._processing_tasks[task_id]
    
    async def process_task_async(self, task: Dict[str, Any]):
        """
        异步处理单个任务（兼容性方法）
        
        Args:
            task: 任务信息字典
        """
        task_id = task["task_id"]
        await self._process_task_async(task_id)

# 全局异步任务处理器实例
# 从配置中获取最大并发任务数，默认为10
try:
    from config.config import NUM_WORKERS
    max_concurrent_tasks = NUM_WORKERS * 3  # 每个worker可以处理3个并发任务
except ImportError:
    max_concurrent_tasks = 10

# 使用新的异步任务处理器
task_processor = AsyncTaskProcessor(max_concurrent_tasks=max_concurrent_tasks)
