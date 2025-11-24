#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型处理队列管理器
用于在复杂文件解析完成（约50%）之后，将后续模型调用阶段串行化：
只有当前请求达到100%（报告完成或失败释放）后，才允许下一个请求开始模型处理。
"""

import asyncio
import logging
import time
from typing import Optional


class ModelProcessingQueueManager:
    """模型阶段处理队列（全局单例，FIFO）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._logger = logging.getLogger(__name__)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._processing_lock = asyncio.Lock()
        self._current_request_id: Optional[str] = None
        self._current_started_at: Optional[float] = None

    async def add_request(self, request_id: str) -> str:
        """
        添加待处理请求到模型阶段队列。
        """
        await self._queue.put(request_id)
        self._logger.info(f"[模型队列] 入队: {request_id}")
        return request_id

    async def wait_for_turn(self, request_id: str) -> bool:
        """
        轮询式尝试占用处理权。只有队首请求可以占用。
        """
        async with self._processing_lock:
            if self._current_request_id is None:
                # 若队首是自己，则占用
                try:
                    next_id = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    return False

                if next_id == request_id:
                    self._current_request_id = request_id
                    self._current_started_at = time.time()
                    self._logger.info(f"[模型队列] 开始处理: {request_id}")
                    return True
                else:
                    # 非自己，放回队列尾部，等待下一轮
                    await self._queue.put(next_id)
                    return False
            else:
                # 已有请求在处理
                return False

    async def release_current(self, success: bool = True):
        """
        释放当前占用，允许后续请求继续。
        """
        async with self._processing_lock:
            if self._current_request_id is None:
                return
            elapsed = 0.0
            if self._current_started_at:
                elapsed = time.time() - self._current_started_at
            rid = self._current_request_id
            self._current_request_id = None
            self._current_started_at = None
            status = "成功" if success else "失败"
            self._logger.info(f"[模型队列] 释放: {rid}，状态: {status}，耗时: {elapsed:.2f}s")


# 全局实例
model_queue_manager = ModelProcessingQueueManager()



