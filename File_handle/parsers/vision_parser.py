# -*- coding: utf-8 -*-
"""
视觉模型解析器 - VisionParser

使用视觉大模型进行精确解析：
- 从图片中提取文本内容（OCR）
- 识别印章、签名等特殊内容
- 支持批量并发处理
- 支持自定义提示词
- 基于AIModelProcessor统一管理视觉模型调用
"""

import os
import sys
import logging
import time
import asyncio
import concurrent.futures
from typing import Optional, Tuple, Dict, List

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.ai_model_processor import AIModelProcessor


class VisionParser:
    """视觉模型解析器 - 使用视觉大模型进行精确解析"""
    
    # 默认提示词（统一使用 AIModelProcessor 中的提示词）
    # 通过属性访问，避免重复定义
    @property
    def DEFAULT_TEXT_PROMPT(self):
        """含圆章判断的提示词"""
        return AIModelProcessor.DEFAULT_IMAGE_PROMPT
    
    @property
    def DEFAULT_TEXT_PROMPT_NO_STAMP(self):
        """不含圆章判断的提示词"""
        return AIModelProcessor.DEFAULT_IMAGE_PROMPT_NO_STAMP
    
    @property
    def DEFAULT_STAMP_PROMPT(self):
        """签章专用提示词"""
        return AIModelProcessor.DEFAULT_STAMP_PROMPT
    
    def __init__(self, 
                 model_name: str = "doubao-seed-1-6-vision-250815",
                 max_retries: int = 2,
                 timeout: int = 60,
                 retry_delay: int = 2,
                 detail: str = 'high'):
        """
        初始化视觉模型解析器
        
        Args:
            model_name: 视觉模型名称
            max_retries: 最大重试次数
            timeout: 超时时间（秒）
            retry_delay: 重试延迟（秒）
            detail: 精度模式 ('high' 或 'low')
        """
        self.logger = logging.getLogger(__name__)
        self.model_name = model_name
        self.max_retries = max_retries
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.detail = detail
        
        # 初始化AIModelProcessor
        self.ai_processor = AIModelProcessor(
            pic_model_name=model_name,
            pic_max_retries=max_retries,
            pic_read_timeout=timeout,
            pic_connect_timeout=5,
            retry_delay=retry_delay,
            detail=detail
        )
        
        self.logger.info(f"视觉模型解析器初始化完成: model={model_name}, detail={detail}")
    
    def parse_image(self, 
                   image_path: str, 
                   prompt: str = None) -> Tuple[Optional[str], str]:
        """
        解析单张图片
        
        Args:
            image_path: 图片路径
            prompt: 自定义提示词，为None时使用默认文本提示词
            
        Returns:
            (识别结果, 图片路径)
        """
        if prompt is None:
            prompt = self.DEFAULT_TEXT_PROMPT
        
        try:
            # 使用AIModelProcessor统一调用视觉模型
            result, path = self.ai_processor.extract_text_from_image(
                image_path=image_path,
                prompt=prompt
            )
            
            if result is None:
                request_id = f"failed_{int(time.time())}_{hash(image_path) % 10000}"
                self.logger.error(f"图片解析失败: {image_path}, Request ID: {request_id}")
                return f"ERROR: 调用失败 (Request ID: {request_id})", image_path
            
            return result, path
            
        except Exception as e:
            request_id = f"exception_{int(time.time())}_{hash(image_path) % 10000}"
            self.logger.error(f"视觉模型调用异常: {image_path}, 错误: {e}, Request ID: {request_id}")
            return f"ERROR: {str(e)} (Request ID: {request_id})", image_path
    
    def parse_stamp_image(self, image_path: str) -> Tuple[Optional[str], str]:
        """
        解析印章图片
        
        Args:
            image_path: 图片路径
            
        Returns:
            (识别结果, 图片路径)
        """
        return self.parse_image(image_path, self.DEFAULT_STAMP_PROMPT)
    
    def batch_parse_images(self, 
                          image_paths: List[str],
                          max_workers: int = 100,
                          prompt: str = None) -> Dict[str, str]:
        """
        批量解析图片（并发）
        
        Args:
            image_paths: 图片路径列表
            max_workers: 最大并发数
            prompt: 自定义提示词
            
        Returns:
            图片路径到识别结果的映射
        """
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_image = {
                executor.submit(self.parse_image, img_path, prompt): img_path 
                for img_path in image_paths
            }
            
            for future in concurrent.futures.as_completed(future_to_image):
                img_path = future_to_image[future]
                try:
                    text, path = future.result()
                    if text:
                        results[path] = text
                except Exception as e:
                    self.logger.error(f"批量解析失败: {img_path}, 错误: {e}")
                    results[img_path] = f"ERROR: {str(e)}"
        
        self.logger.info(f"批量解析完成: 共{len(image_paths)}张图片")
        return results
    
    async def batch_parse_images_async(self, 
                                      image_paths: List[str],
                                      max_workers: int = 100,
                                      prompt: str = None) -> Dict[str, str]:
        """
        异步批量解析图片（支持真正的异步并发）
        
        Args:
            image_paths: 图片路径列表
            max_workers: 最大并发数
            prompt: 自定义提示词
            
        Returns:
            图片路径到识别结果的映射
        """
        results = {}
        
        # 使用asyncio.Semaphore控制并发数
        semaphore = asyncio.Semaphore(max_workers)
        
        async def process_single_image(img_path: str) -> Tuple[str, str]:
            async with semaphore:
                try:
                    # 在线程池中执行解析，避免阻塞事件循环
                    loop = asyncio.get_event_loop()
                    text, path = await loop.run_in_executor(
                        None, 
                        self.parse_image, 
                        img_path, 
                        prompt
                    )
                    return path, text
                except Exception as e:
                    self.logger.error(f"异步解析失败: {img_path}, 错误: {e}")
                    return img_path, f"ERROR: {str(e)}"
        
        # 并发处理所有图片
        tasks = [process_single_image(img_path) for img_path in image_paths]
        parse_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for parse_result in parse_results:
            if isinstance(parse_result, Exception):
                self.logger.error(f"异步解析异常: {parse_result}")
            elif parse_result and len(parse_result) == 2:
                path, text = parse_result
                if text:
                    results[path] = text
        
        self.logger.info(f"异步批量解析完成: 共{len(image_paths)}张图片")
        return results
    
    def parse_images_with_pages(self, 
                               images_with_pages: List[Tuple[str, int]],
                               max_workers: int = 100,
                               prompt: str = None) -> Dict[int, List[Tuple[str, str]]]:
        """
        批量解析图片并按页码分组
        
        Args:
            images_with_pages: 图片信息列表，每个元素为 (图片路径, 页码)
            max_workers: 最大并发数
            prompt: 自定义提示词
            
        Returns:
            页码到识别结果列表的映射，每个结果为 (图片路径, 识别文本)
        """
        # 批量解析所有图片
        image_paths = [img_path for img_path, _ in images_with_pages]
        parse_results = self.batch_parse_images(image_paths, max_workers, prompt)
        
        # 按页码分组
        results_by_page = {}
        for img_path, page_num in images_with_pages:
            text = parse_results.get(img_path, "")
            if page_num not in results_by_page:
                results_by_page[page_num] = []
            results_by_page[page_num].append((img_path, text))
        
        self.logger.info(f"按页码分组完成: 共{len(results_by_page)}页")
        return results_by_page

    async def parse_images_with_pages_async(self, 
                                           images_with_pages: List,
                                           max_workers: int = 100,
                                           prompt: str = None) -> Dict[int, List[Tuple[str, str, float]]]:
        """
        异步批量解析图片并按页码分组，使用 batch_parse_images_async。
        
        Args:
            images_with_pages: 图片信息列表，支持两种格式：
                - (path, page) - 不含位置信息
                - (path, page, y0) - 含位置信息
        
        Returns:
            页码到结果列表的映射: {page_num: [(image_path, ocr_text, y0), ...]}
        """
        # 并发解析所有图片
        image_paths = [item[0] for item in images_with_pages]
        parse_results = await self.batch_parse_images_async(
            image_paths,
            max_workers=max_workers,
            prompt=prompt
        )

        # 按页码分组，保留 y0 信息
        results_by_page = {}
        for item in images_with_pages:
            img_path = item[0]
            page_num = item[1]
            y0 = item[2] if len(item) > 2 else 0
            
            text = parse_results.get(img_path, "")
            if page_num not in results_by_page:
                results_by_page[page_num] = []
            results_by_page[page_num].append((img_path, text, y0))

        self.logger.info(f"按页码分组完成(异步): 共{len(results_by_page)}页")
        return results_by_page
    
    def parse_with_custom_prompts(self, 
                                 image_path: str, 
                                 prompts: List[str]) -> List[Tuple[str, str]]:
        """
        使用多个提示词解析同一张图片
        
        Args:
            image_path: 图片路径
            prompts: 提示词列表
            
        Returns:
            结果列表，每个元素为 (提示词, 识别结果)
        """
        results = []
        
        for prompt in prompts:
            try:
                text, _ = self.parse_image(image_path, prompt)
                results.append((prompt, text))
            except Exception as e:
                self.logger.error(f"使用自定义提示词解析失败: {image_path}, 提示词: {prompt[:50]}..., 错误: {e}")
                results.append((prompt, f"ERROR: {str(e)}"))
        
        return results
    
    def get_parser_info(self) -> Dict[str, any]:
        """
        获取解析器配置信息
        
        Returns:
            配置信息字典
        """
        return {
            'model_name': self.model_name,
            'max_retries': self.max_retries,
            'timeout': self.timeout,
            'retry_delay': self.retry_delay,
            'detail': self.detail,
            'default_text_prompt': self.DEFAULT_TEXT_PROMPT,
            'default_stamp_prompt': self.DEFAULT_STAMP_PROMPT
        }

