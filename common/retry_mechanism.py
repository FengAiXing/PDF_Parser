# 重试机制模块
# 提供通用的LLM调用重试装饰器，支持JSON解析失败和空结果重试

import asyncio
import logging
import json
import re
from functools import wraps
from typing import Callable, Any, Optional, Dict, List
from common.llm_client import LLMClient

logger = logging.getLogger(__name__)

class LLMRetryMechanism:
    """LLM重试机制类"""
    
    def __init__(self, max_retries: int = 1):
        """
        初始化重试机制
        
        Args:
            max_retries: 最大重试次数，默认为1次
        """
        self.max_retries = max_retries
        self.llm_client = LLMClient()
    
    def retry_on_json_parse_failure(self, 
                                  prompt_func: Callable[[], str] = None,
                                  file_content_func: Callable[[], str] = None,
                                  model_type: str = "gemini"):
        """
        装饰器：当JSON解析失败时重新调用LLM
        
        Args:
            prompt_func: 获取prompt的函数，如果为None则从被装饰函数的参数中获取
            file_content_func: 获取file_content的函数，如果为None则从被装饰函数的参数中获取
            model_type: 模型类型
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 尝试执行原函数
                try:
                    result = await func(*args, **kwargs)
                    
                    # 检查结果是否为空或解析失败
                    if self._should_retry(result, args, kwargs):
                        logger.warning(f"检测到需要重试的情况，准备重新调用LLM")
                        return await self._retry_llm_call(
                            func, args, kwargs, prompt_func, file_content_func, model_type
                        )
                    
                    return result
                    
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    logger.warning(f"JSON解析失败，准备重试: {e}")
                    return await self._retry_llm_call(
                        func, args, kwargs, prompt_func, file_content_func, model_type
                    )
                except Exception as e:
                    # 其他异常不重试，直接抛出
                    raise e
            
            return wrapper
        return decorator
    
    def _should_retry(self, result: Any, args: tuple, kwargs: dict) -> bool:
        """
        判断是否需要重试
        
        Args:
            result: 函数执行结果
            args: 函数参数
            kwargs: 函数关键字参数
            
        Returns:
            bool: 是否需要重试
        """
        # 如果结果为空或None
        if result is None or result == "":
            return True
        
        # 如果结果是字典且包含错误信息
        if isinstance(result, dict):
            if result.get('success') == False or 'error' in result:
                return True
        
        # 如果结果是列表且为空
        if isinstance(result, list) and len(result) == 0:
            return True
        
        return False
    
    async def _retry_llm_call(self, 
                            func: Callable,
                            args: tuple, 
                            kwargs: dict,
                            prompt_func: Callable[[], str] = None,
                            file_content_func: Callable[[], str] = None,
                            model_type: str = "gemini") -> Any:
        """
        重试LLM调用
        
        Args:
            func: 原函数
            args: 原函数参数
            kwargs: 原函数关键字参数
            prompt_func: 获取prompt的函数
            file_content_func: 获取file_content的函数
            model_type: 模型类型
            
        Returns:
            Any: 重试后的结果
        """
        for retry_count in range(self.max_retries):
            try:
                logger.info(f"第{retry_count + 1}次重试调用LLM")
                
                # 获取prompt和file_content
                if prompt_func:
                    prompt = prompt_func()
                else:
                    prompt = self._extract_prompt_from_args(args, kwargs)
                
                if file_content_func:
                    file_content = file_content_func()
                else:
                    file_content = self._extract_file_content_from_args(args, kwargs)
                
                # 调用LLM
                llm_result = await self.llm_client.call_llm(
                    prompt=prompt,
                    file_content=file_content,
                    model_type=model_type
                )
                
                # 重新执行原函数，但使用新的LLM结果
                new_args = self._replace_llm_result_in_args(args, kwargs, llm_result)
                result = await func(*new_args[0], **new_args[1])
                
                # 检查重试结果
                if not self._should_retry(result, args, kwargs):
                    logger.info(f"重试成功，获得有效结果")
                    return result
                else:
                    logger.warning(f"重试第{retry_count + 1}次仍然失败，结果: {result}")
                    
            except Exception as e:
                logger.error(f"重试第{retry_count + 1}次时发生异常: {e}")
                if retry_count == self.max_retries - 1:
                    # 最后一次重试失败，抛出异常
                    raise e
        
        # 所有重试都失败
        raise Exception(f"重试{self.max_retries}次后仍然失败")
    
    def _extract_prompt_from_args(self, args: tuple, kwargs: dict) -> str:
        """从函数参数中提取prompt"""
        # 尝试从kwargs中获取
        if 'prompt' in kwargs:
            return kwargs['prompt']
        
        # 尝试从args中获取（假设prompt是第一个参数）
        if len(args) > 0 and isinstance(args[0], str):
            return args[0]
        
        raise ValueError("无法从参数中提取prompt")
    
    def _extract_file_content_from_args(self, args: tuple, kwargs: dict) -> str:
        """从函数参数中提取file_content"""
        # 尝试从kwargs中获取
        if 'file_content' in kwargs:
            return kwargs['file_content']
        
        # 尝试从args中获取（假设file_content是第二个参数）
        if len(args) > 1 and isinstance(args[1], str):
            return args[1]
        
        # 如果只有一个参数，可能是file_content
        if len(args) == 1 and isinstance(args[0], str):
            return args[0]
        
        raise ValueError("无法从参数中提取file_content")
    
    def _replace_llm_result_in_args(self, args: tuple, kwargs: dict, new_llm_result: str) -> tuple:
        """替换参数中的LLM结果"""
        # 这里需要根据具体的函数签名来调整
        # 通常LLM结果会作为第一个参数传入
        new_args = (new_llm_result,) + args[1:] if len(args) > 1 else (new_llm_result,)
        return (new_args, kwargs)

# 创建默认的重试机制实例
default_retry_mechanism = LLMRetryMechanism(max_retries=1)

def retry_on_json_parse_failure(prompt_func: Callable[[], str] = None,
                               file_content_func: Callable[[], str] = None,
                               model_type: str = "gemini"):
    """
    便捷的装饰器函数，用于JSON解析失败时重试LLM调用
    
    Args:
        prompt_func: 获取prompt的函数
        file_content_func: 获取file_content的函数
        model_type: 模型类型
    """
    return default_retry_mechanism.retry_on_json_parse_failure(
        prompt_func, file_content_func, model_type
    )
