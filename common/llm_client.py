# 大模型客户端
# 这个文件用于调用各种AI大模型进行内容分析
# 支持多种模型类型：默认模型、OCR模型、Gemini模型等
# 具体实现由相关同事完成

import logging
import sys
import os
import asyncio
import aiohttp
import uuid
import json
from string import Template
from typing import Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入配置
from config.config import config
from common.api_call_throttle import async_wait_for_api_interval
from config.ai_model_processor import AIModelProcessor

logger = logging.getLogger(__name__)

class LLMClient:
    """大模型客户端类 - 负责调用AI模型进行内容分析（使用AIModelProcessor统一管理）"""
    
    def __init__(self):
        """初始化大模型客户端"""
        # 初始化AIModelProcessor实例（统一管理所有模型调用）
        self.ai_processor = AIModelProcessor()
        
        # 初始化各种模型配置（保留用于兼容性）
        self.model_configs = {
            "default": config.model_config,           # 默认模型 (doubao-seed-1-6-250615)
            "ocr": config.ocr_model_config,           # OCR模型 (doubao-seed-1-6-vision-250815)
            "gemini": config.gemini_model_config,     # Gemini模型 (gemini-2.5-pro)
            "qwen": config.qwen_model_config          # QWEN模型 (qqwen-plus)
        }
        
        # 模型类型映射
        self.model_type_mapping = {
            "default": "default",
            "ocr": "ocr", 
            "gemini": "gemini",
            "qwen": "qwen"
        }
        
        logger.info("大模型客户端初始化完成（使用AIModelProcessor）")
        logger.info(f"支持的模型类型: {list(self.model_configs.keys())}")
    
    def _validate_model_config(self, model_type: str, model_config: Dict[str, str]) -> bool:
        """
        验证单个模型配置是否完整
        
        Args:
            model_type: 模型类型
            model_config: 模型配置字典
            
        Returns:
            bool: 配置是否完整
        """
        required_fields = ["model", "api_url", "api_key"]
        missing_fields = [field for field in required_fields if not model_config.get(field)]
        
        if missing_fields:
            logger.warning(f"模型 {model_type} 配置不完整，缺少字段: {missing_fields}")
            return False
        else:
            logger.debug(f"模型 {model_type} 配置验证通过")
            return True
    
    def get_model_config(self, model_type: str = "default") -> Dict[str, str]:
        """
        获取指定模型类型的配置，并在获取时验证配置
        
        Args:
            model_type: 模型类型
            
        Returns:
            Dict[str, str]: 模型配置字典
        """
        if model_type not in self.model_configs:
            logger.warning(f"未知的模型类型: {model_type}，使用默认模型")
            model_type = "default"
        
        model_config = self.model_configs[model_type]
        
        # 验证配置
        if not self._validate_model_config(model_type, model_config):
            raise ValueError(f"模型 {model_type} 配置不完整，无法使用")
        
        return model_config
    
    async def call_llm(self, prompt: str, file_content: str, model_type: str = "gemini") -> str:
        """
        调用大模型进行内容分析，支持模型降级机制（使用AIModelProcessor统一管理）
        
        Args:
            prompt: 提示词
            file_content: 文件内容
            model_type: 首选模型类型 ("default", "ocr", "gemini", "qwen")
            
        Returns:
            str: 大模型返回的结果
        """
        # 定义模型降级顺序：gemini -> qwen -> default
        fallback_models = ["gemini", "qwen", "default"]
        
        # 如果指定的模型不在降级列表中，将其作为首选
        if model_type not in fallback_models:
            fallback_models = [model_type] + fallback_models
        
        # 构建完整的提示词（使用模板替换）
        # 只有当prompt包含$content占位符时才使用Template.substitute
        if '$content' in prompt:
            prompt_template = Template(prompt)
            full_prompt = prompt_template.substitute(content=file_content)
        else:
            # 如果prompt不包含$content占位符，直接使用原始prompt
            full_prompt = prompt
        
        last_error = None
        
        # 尝试每个模型，直到成功或所有模型都失败
        for i, current_model in enumerate(fallback_models):
            try:
                logger.info(f"尝试调用模型: {current_model}")
                
                # 获取模型配置
                model_config = self.get_model_config(current_model)
                
                # 使用AIModelProcessor调用模型（在异步环境中调用同步方法）
                # 构建完整的提示词（包含system消息）
                system_message = "你是一位专业的招投标文件分析专家，负责准确提取和分析文件中的关键信息。"
                complete_prompt = f"{system_message}\n\n{full_prompt}"
                
                # 在异步环境中调用同步的extract_text方法
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    self.ai_processor.extract_text,
                    complete_prompt,
                    0.2  # temperature
                )
                
                if result:
                    if i > 0:
                        logger.warning(f"模型降级成功: {current_model} (原首选模型: {model_type})")
                    else:
                        logger.info(f"模型调用成功: {current_model}")
                    return result
                else:
                    logger.warning(f"模型 {current_model} 返回空结果，尝试下一个模型")
                    last_error = Exception(f"模型 {current_model} 返回空结果")
                    continue
                    
            except Exception as e:
                last_error = e
                logger.warning(f"模型 {current_model} 调用失败: {str(e)}")
                # 继续尝试下一个模型
                continue
        
        # 所有模型都失败，抛出异常
        raise Exception(f"所有模型调用都失败，最后错误: {str(last_error)}")
    
    def _get_model_headers(self, model_config: Dict[str, str]) -> Dict[str, str]:
        """
        获取模型请求头（保留用于兼容性，实际已由AIModelProcessor处理）
        
        Args:
            model_config: 模型配置
            
        Returns:
            Dict[str, str]: 请求头字典
        """
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {model_config['api_key']}"
        }
