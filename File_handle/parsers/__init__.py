# -*- coding: utf-8 -*-
"""
解析器模块 - parsers

提供各种解析器：
- CoarseParser: 粗解析器 - 快速提取文本内容
- VisionParser: 视觉模型解析器 - 使用视觉模型处理图片
- TableParser: 表格解析器 - 识别表格和跨页表格
"""

from .coarse_parser import CoarseParser
from .vision_parser import VisionParser
from .table_parser import TableParser

__all__ = ['CoarseParser', 'VisionParser', 'TableParser']

