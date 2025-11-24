# -*- coding: utf-8 -*-
"""
复杂文件OCR处理器
专门处理candidate_bid_files类型文件中的图片内容，使用视觉模型进行识别
"""

import os
import logging
import time
import asyncio
import sys
from typing import Optional, Tuple, Dict, List
import concurrent.futures

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from config.ai_model_processor import AIModelProcessor


class ComplexOCRProcessor:
    """复杂文件OCR处理器（使用AIModelProcessor统一管理）"""
    
    def __init__(self, model_name: str = "doubao-seed-1-6-vision-250815", 
                 max_retries: int = 2, timeout: int = 60, retry_delay: int = 2):
        self.model_name = model_name
        self.max_retries = max_retries
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.logger = logging.getLogger(__name__)
        
        # 使用AIModelProcessor统一管理视觉模型调用
        self.ai_processor = AIModelProcessor(
            pic_model_name=model_name,
            pic_max_retries=max_retries,
            pic_read_timeout=timeout,
            pic_connect_timeout=5,
            retry_delay=retry_delay,
            detail='high'  # 使用高精度模式
        )
        
        # 针对candidate_bid_files的专用提示词
        self.prompt_vision_text = "你是专业的投标文件OCR识别专家。请严格按照以下要求提取图片中的所有文本内容：\n\n1. 输出格式要求：\n   - 纯文本输出，无多余空格、换行符或特殊符号\n   - 表格数据用|分隔列，用换行分隔行\n   - 保持原始文本的逻辑顺序和结构\n\n2. 内容完整性要求：\n   - 必须识别所有可见文字，不得遗漏任何内容\n   - 数字、日期、金额等关键信息必须准确识别\n   - 不得简化、修改或编造任何内容\n\n3. 输出要求：\n   - 直接输出识别结果，不要添加任何解释性文字\n   - 不要使用格式标记或特殊符号\n   - 确保输出简洁清晰，便于后续处理"
        
        self.prompt_vision_stamp = "你是专业的投标文件印章识别专家。请严格按照以下要求提取图片中的所有文本内容：\n\n1. 输出格式要求：\n   - 纯文本输出，无多余空格、换行符或特殊符号\n   - 保持原始文本的逻辑顺序和结构\n\n2. 内容完整性要求：\n   - 必须识别所有可见文字，不得遗漏任何内容\n   - 印章文字、签名等关键信息必须准确识别\n   - 不得简化、修改或编造任何内容\n\n3. 输出要求：\n   - 直接输出识别结果，不要添加任何解释性文字\n   - 不要使用格式标记或特殊符号\n   - 确保输出简洁清晰，便于后续处理"
    
    def extract_text_from_image(self, image_path: str, 
                              prompt: str = None, 
                              model_name: str = None) -> Tuple[Optional[str], str]:
        """
        从图片中提取文字内容 - 专门针对candidate_bid_files（使用AIModelProcessor）
        
        Args:
            image_path: 图片路径
            prompt: 自定义提示词
            model_name: 模型名称（已由AIModelProcessor管理，此参数保留用于兼容性）
            
        Returns:
            (识别结果, 图片路径)
        """
        if prompt is None:
            prompt = self.prompt_vision_text
        
        try:
            # 使用AIModelProcessor统一调用视觉模型
            # AIModelProcessor内部已经处理了图片编码、压缩、重试等逻辑
            result, path = self.ai_processor.extract_text_from_image(
                image_path=image_path,
                prompt=prompt
            )
            
            # 如果返回None，添加错误信息
            if result is None:
                request_id = f"failed_{int(time.time())}_{hash(image_path) % 10000}"
                self.logger.error(f"复杂文件视觉大模型调用失败: {image_path}, Request ID: {request_id}")
                return f"ERROR: 调用失败 (Request ID: {request_id})", image_path
            
            return result, path
            
        except Exception as e:
            request_id = f"exception_{int(time.time())}_{hash(image_path) % 10000}"
            self.logger.error(f"复杂文件视觉大模型调用异常: {image_path}, 错误: {e}, Request ID: {request_id}")
            return f"ERROR: {str(e)} (Request ID: {request_id})", image_path
    
    def extract_stamp_from_image(self, image_path: str) -> Tuple[Optional[str], str]:
        """
        从图片中提取印章和签名信息
        
        Args:
            image_path: 图片路径
            
        Returns:
            (识别结果, 图片路径)
        """
        return self.extract_text_from_image(image_path, self.prompt_vision_stamp)
    
    def batch_extract_text(self, image_paths: List[str], 
                          max_workers: int = 20,
                          prompt: str = None) -> Dict[str, str]:
        """
        批量提取图片文字 - 专门针对candidate_bid_files
        
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
                executor.submit(self.extract_text_from_image, img_path, prompt): img_path 
                for img_path in image_paths
            }
            
            for future in concurrent.futures.as_completed(future_to_image):
                img_path = future_to_image[future]
                try:
                    text, path = future.result()
                    if text:
                        results[path] = text
                except Exception as e:
                    self.logger.error(f"复杂文件批量OCR处理失败: {img_path}, 错误: {e}")
        
        return results
    
    async def batch_extract_text_async(self, image_paths: List[str], 
                                     max_workers: int = 20,
                                     prompt: str = None) -> Dict[str, str]:
        """
        异步批量提取图片文字 - 专门针对candidate_bid_files，支持真正的异步并发
        
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
                    # 在线程池中执行OCR处理，避免阻塞事件循环
                    loop = asyncio.get_event_loop()
                    text, path = await loop.run_in_executor(
                        None, 
                        self.extract_text_from_image, 
                        img_path, 
                        prompt
                    )
                    return path, text
                except Exception as e:
                    self.logger.error(f"异步OCR处理失败: {img_path}, 错误: {e}")
                    return img_path, None
        
        # 并发处理所有图片
        tasks = [process_single_image(img_path) for img_path in image_paths]
        ocr_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        for ocr_result in ocr_results:
            if isinstance(ocr_result, Exception):
                self.logger.error(f"异步OCR处理异常: {ocr_result}")
            elif ocr_result and len(ocr_result) == 2:
                path, text = ocr_result
                if text:
                    results[path] = text
        
        return results
    
    def extract_bid_specific_content(self, image_path: str) -> Dict[str, str]:
        """
        专门提取投标文件中的特定内容
        
        Args:
            image_path: 图片路径
            
        Returns:
            包含各种投标文件信息的字典
        """
        # 使用通用文本提取
        text_result, _ = self.extract_text_from_image(image_path)
        
        # 使用印章识别
        stamp_result, _ = self.extract_stamp_from_image(image_path)
        
        return {
            'text_content': text_result,
            'stamp_info': stamp_result,
            'image_path': image_path
        }
