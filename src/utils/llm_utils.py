"""
LLM工具函数模块

本模块提供LLM调用的公共工具函数，包括重试机制和JSON解析验证。
"""

import logging
import json
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)


async def call_llm_with_retry(
    llm_client, 
    prompt: str, 
    file_content: str = "", 
    max_retries: int = 3,
    step_name: str = "未知步骤"
) -> str:
    """
    带重试机制的LLM调用函数
    
    Args:
        llm_client: LLM客户端
        prompt: 提示词
        file_content: 文件内容
        max_retries: 最大重试次数
        step_name: 步骤名称（用于日志）
    
    Returns:
        str: LLM返回的结果
    
    Raises:
        Exception: 达到最大重试次数后仍失败时抛出异常
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"[{step_name}] 第{attempt + 1}次尝试调用LLM...")
            result = await llm_client.call_llm(
                prompt=prompt,
                file_content=file_content
            )
            
            logger.info(f"[{step_name}] 第{attempt + 1}次尝试成功")
            return result
                    
        except Exception as e:
            logger.error(f"[{step_name}] 第{attempt + 1}次尝试LLM调用失败: {e}")
            if attempt < max_retries - 1:
                logger.info(f"[{step_name}] 准备进行第{attempt + 2}次重试...")
                await asyncio.sleep(1)  # 等待1秒后重试
                continue
            else:
                logger.error(f"[{step_name}] 达到最大重试次数，抛出异常")
                raise e
    
    # 理论上不会执行到这里，但为了类型检查
    raise Exception(f"[{step_name}] LLM调用失败")


async def call_llm_with_retry_for_json_parse(
    llm_client, 
    prompt: str, 
    file_content: str = "", 
    step_name: str = "未知步骤",
    task_type: str = "",
    ranking: str = ""
) -> Optional[str]:
    """
    带重试机制的LLM调用，专门用于JSON解析失败时的重试
    
    此函数在调用LLM后会自动验证返回结果是否为有效的JSON格式。
    如果JSON解析失败，会自动重试（最多重试1次）。
    
    Args:
        llm_client: LLM客户端
        prompt: 提示词
        file_content: 文件内容
        step_name: 步骤名称
        task_type: 任务类型（用于日志）
        ranking: 排名（用于日志）
        
    Returns:
        Optional[str]: LLM返回结果，失败时返回None
    """
    max_retries = 1
    
    for attempt in range(max_retries + 1):
        try:
            result = await call_llm_with_retry(
                llm_client=llm_client,
                prompt=prompt,
                file_content=file_content,
                step_name=step_name
            )
            
            # 检查结果是否为空
            if not result or result.strip() == "":
                if attempt < max_retries:
                    logger.warning(f"[{task_type}] {ranking} 第{attempt + 1}次调用返回空结果，准备重试")
                    continue
                else:
                    logger.error(f"[{task_type}] {ranking} 重试后仍然返回空结果")
                    return None
            
            # 尝试解析JSON以验证结果有效性
            try:
                clean_result = result.strip()
                if clean_result.startswith("```json"):
                    clean_result = clean_result[7:]
                elif clean_result.startswith("```"):
                    clean_result = clean_result[3:]
                if clean_result.endswith("```"):
                    clean_result = clean_result[:-3]
                clean_result = clean_result.strip()
                
                # 尝试解析JSON
                json.loads(clean_result)
                logger.info(f"[{task_type}] {ranking} 第{attempt + 1}次调用成功，JSON格式有效")
                return result
                
            except json.JSONDecodeError as e:
                if attempt < max_retries:
                    logger.warning(f"[{task_type}] {ranking} 第{attempt + 1}次调用JSON解析失败: {e}，准备重试")
                    continue
                else:
                    logger.error(f"[{task_type}] {ranking} 重试后仍然JSON解析失败: {e}")
                    return None
                    
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"[{task_type}] {ranking} 第{attempt + 1}次调用发生异常: {e}，准备重试")
                continue
            else:
                logger.error(f"[{task_type}] {ranking} 重试后仍然发生异常: {e}")
                return None
    
    return None

