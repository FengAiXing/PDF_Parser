# -*- coding: utf-8 -*-
"""
文件解析包 - File_handle

提供粗解析和精确解析（视觉模型）两种模式
每个功能模块都可以独立调用

模块结构：
- config/: 配置模块 (Config)
- parsers/: 解析器模块 (CoarseParser, VisionParser)
- image/: 图片处理模块 (ImageExtractor, StampDetector)
- table/: 表格处理模块 (TableParser, CrossPageTableDetector, CrossPageTableMerger)
- utils/: 工具模块 (DocumentAssembler, HeaderFooterCleaner, TextMerger, PDFHandler, ExcelHandler)
- file_processor: 文件处理器 - 完整的PDF解析功能（文本+表格+图片）
- main_parser: 主解析器 - 统一调用接口
"""

# 从子模块导入
from .config import Config
from .parsers import CoarseParser, VisionParser
from .image import ImageExtractor, StampDetector
from .table import CrossPageTableDetector, CrossPageTableMerger
from .parsers import TableParser
from .utils import DocumentAssembler, HeaderFooterCleaner, TextMerger, PDFHandler, ExcelHandler

# 从当前目录导入
from .file_processor import FileProcessor
from .main_parser import MainParser

__all__ = [
    # 配置
    'Config',
    # 解析器
    'CoarseParser',
    'VisionParser',
    # 图片处理
    'ImageExtractor',
    'StampDetector',
    # 表格处理
    'TableParser',
    'CrossPageTableDetector',
    'CrossPageTableMerger',
    # 工具
    'DocumentAssembler',
    'HeaderFooterCleaner',
    'TextMerger',
    'PDFHandler',
    'ExcelHandler',
    # 主处理器
    'FileProcessor',
    'MainParser'
]

__version__ = '1.0.0'
