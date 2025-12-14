# -*- coding: utf-8 -*-
"""
配置模块 - config

提供配置和AI模型处理功能：
- Config: 功能开关和保存配置
- AppConfig: 应用程序配置（AI模型、数据库等）
- AIModelProcessor: AI模型处理器
"""

from .config import Config
from .model_config import AppConfig, DatabaseConfig, config
from .ai_model_processor import (
    AIModelProcessor, 
    extract_text, 
    extract_text_from_image,
    openai_chat
)

__all__ = [
    'Config',
    'AppConfig',
    'DatabaseConfig',
    'config',
    'AIModelProcessor',
    'extract_text',
    'extract_text_from_image',
    'openai_chat'
]