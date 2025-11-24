# API调用间隔管理模块
# 用于控制模型API调用的时间间隔，防止并发请求被API供应商拒绝

import time
import threading
import logging
from typing import Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# API调用延迟配置（秒）- 防止并发请求被API供应商拒绝
api_call_min_interval = 0.1  # 最小调用间隔（100毫秒），确保每次API调用之间有足够的时间间隔

# 全局API调用时间戳记录（线程安全）
_last_api_call_time: Dict[str, float] = {}  # 存储不同类型API的最后调用时间 {'text': timestamp, 'pic': timestamp, 'judge': timestamp}
_api_call_lock = threading.Lock()  # 线程锁，确保时间戳记录的线程安全

# 用于串行化API调用的锁字典（每个API类型一个锁，确保严格按顺序调用）
_api_call_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)


def wait_for_api_interval(api_type: str = 'text'):
    """
    等待API调用间隔，确保每次调用之间有足够的时间间隔（支持并发场景）
    
    使用锁机制确保即使是并发调用，也能严格保持间隔
    
    Args:
        api_type (str): API类型 ('text', 'pic', 'judge')
            - 'text': 文本模型调用
            - 'pic': 视觉模型调用（OCR、图片识别等）
            - 'judge': 判断类模型调用
    
    Returns:
        None
    """
    global _last_api_call_time, _api_call_lock, _api_call_locks
    
    # 获取该API类型的专用锁，确保同一类型的API调用串行执行
    api_lock = _api_call_locks[api_type]
    
    with api_lock:
        # 在锁内再次检查时间间隔，确保严格按顺序
        with _api_call_lock:
            current_time = time.time()
            if api_type in _last_api_call_time:
                elapsed = current_time - _last_api_call_time[api_type]
                if elapsed < api_call_min_interval:
                    sleep_time = api_call_min_interval - elapsed
                    logger.debug(f"API调用间隔控制: {api_type} 类型，需要等待 {sleep_time:.3f} 秒")
                    time.sleep(sleep_time)
                    current_time = time.time()
            
            _last_api_call_time[api_type] = current_time


async def async_wait_for_api_interval(api_type: str = 'text'):
    """
    异步等待API调用间隔，确保每次调用之间有足够的时间间隔（支持并发场景）
    
    使用asyncio锁机制确保即使是并发调用，也能严格保持间隔
    
    Args:
        api_type (str): API类型 ('text', 'pic', 'judge')
            - 'text': 文本模型调用
            - 'pic': 视觉模型调用（OCR、图片识别等）
            - 'judge': 判断类模型调用
    
    Returns:
        None
    """
    import asyncio
    global _last_api_call_time, _api_call_lock
    
    # 为异步场景创建锁字典（每个API类型一个锁）
    if not hasattr(async_wait_for_api_interval, '_async_locks'):
        async_wait_for_api_interval._async_locks = defaultdict(asyncio.Lock)
    
    async_lock = async_wait_for_api_interval._async_locks[api_type]
    
    async with async_lock:
        # 在锁内检查时间间隔，确保严格按顺序
        current_time = time.time()
        if api_type in _last_api_call_time:
            elapsed = current_time - _last_api_call_time[api_type]
            if elapsed < api_call_min_interval:
                sleep_time = api_call_min_interval - elapsed
                logger.debug(f"API调用间隔控制（异步）: {api_type} 类型，需要等待 {sleep_time:.3f} 秒")
                await asyncio.sleep(sleep_time)
                current_time = time.time()
        
        # 使用线程锁保护时间戳更新（因为asyncio和threading可能混用）
        with _api_call_lock:
            _last_api_call_time[api_type] = current_time


def reset_api_call_times():
    """
    重置所有API调用时间戳（用于测试或特殊情况）
    
    Returns:
        None
    """
    global _last_api_call_time, _api_call_lock
    
    with _api_call_lock:
        _last_api_call_time.clear()
        logger.info("已重置所有API调用时间戳")


def get_last_api_call_time(api_type: str) -> Optional[float]:
    """
    获取指定API类型的最后调用时间
    
    Args:
        api_type (str): API类型
    
    Returns:
        Optional[float]: 最后调用时间戳，如果不存在返回None
    """
    global _last_api_call_time, _api_call_lock
    
    with _api_call_lock:
        return _last_api_call_time.get(api_type)

