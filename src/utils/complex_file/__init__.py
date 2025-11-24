# -*- coding: utf-8 -*-
"""
复杂文件处理模块
专门处理candidate_bid_files类型的文件，包含图片等难以解析的内容
"""

from .main_processor import ComplexFileProcessor
from .ocr_processor import ComplexOCRProcessor
from .pdf_processor import ComplexPDFProcessor
from .content_merger import ComplexContentMerger

__all__ = [
    'ComplexFileProcessor',
    'ComplexOCRProcessor', 
    'ComplexPDFProcessor',
    'ComplexContentMerger'
]
