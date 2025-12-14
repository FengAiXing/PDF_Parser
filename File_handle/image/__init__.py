# -*- coding: utf-8 -*-
"""
图片处理模块 - image

提供图片相关功能：
- ImageExtractor: 图片提取器 - 从PDF提取图片
- StampDetector: 签章识别器 - 识别并去重签章图片
"""

from .image_extractor import ImageExtractor
from .stamp_detector import StampDetector

__all__ = ['ImageExtractor', 'StampDetector']

