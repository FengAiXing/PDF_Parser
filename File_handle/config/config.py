# -*- coding: utf-8 -*-
"""
配置模块 - Config

集中管理所有配置：
- 功能开关（启用/禁用解析功能）
- 保存开关（是否保存各类文件）
- 路径配置（各类文件的保存目录）

使用方法：
1. 修改功能开关来启用/禁用对应的解析功能
2. 修改保存开关来控制是否保存对应类型的文件
3. 快速禁用所有保存：将 ENABLE_ALL_SAVES 设为 False
"""

import os
from datetime import datetime


class Config:
    """配置类 - 集中管理所有功能和保存选项"""
    
    # ===============================================================
    # 功能开关（控制解析流程中的各项功能）
    # ===============================================================
    
    # 表格解析 - 识别并解析PDF中的表格（含跨页表格）
    ENABLE_TABLE_PARSING = True
    
    # 图片解析 - 提取PDF中的图片并进行OCR识别
    ENABLE_IMAGE_PARSING = True
    
    # 签章识别 - 从图片中识别签章（红色印章）并去重
    ENABLE_STAMP_DETECTION = False
    
    # 签章解析 - 对识别出的签章进行OCR读取内容
    ENABLE_STAMP_PARSING = False
    
    # ===============================================================
    # 保存总开关（设为 False 可快速禁用所有保存本地文件的功能）
    # ===============================================================
    ENABLE_ALL_SAVES = True
    
    # ===============================================================
    # 各类文件保存开关（可单独控制）
    # ===============================================================
    
    # 最终解析结果 (.txt) - 包含文本+表格+图片的完整解析
    SAVE_FINAL_RESULT = True
    
    # 表格图片 (.png) - 从PDF中裁剪的表格截图
    SAVE_TABLE_IMAGES = True
    
    # 单张表格识别结果 (.txt) - 每个表格的单独识别内容
    SAVE_SINGLE_TABLE_RESULTS = True
    
    # 提取的图片 - 从PDF中提取的图片文件
    SAVE_EXTRACTED_IMAGES = True
    
    # 签章图片 - 识别并去重后的签章图片
    SAVE_STAMP_IMAGES = True
    
    # 单张图片OCR结果 (.txt) - 每张图片的单独识别内容
    SAVE_IMAGE_OCR_RESULTS = True
    
    # ===============================================================
    # 路径配置
    # ===============================================================
    
    # 基础输出目录（所有输出文件的根目录）
    OUTPUT_BASE_DIR = "output_complete"
    
    # 子目录名称模板（{timestamp} 会被替换为时间戳）
    TABLES_DIR_TEMPLATE = "tables_{timestamp}"
    IMAGES_DIR_TEMPLATE = "images_{timestamp}"
    STAMPS_DIR_TEMPLATE = "stamps_{timestamp}"
    SINGLE_TABLE_RESULTS_DIR_TEMPLATE = "single_table_results_{timestamp}"
    IMAGE_OCR_RESULTS_DIR_TEMPLATE = "image_ocr_results_{timestamp}"
    
    # 最终结果文件名模板（{basename} 为原PDF文件名，{timestamp} 为时间戳）
    FINAL_RESULT_FILENAME_TEMPLATE = "{basename}_完整解析含表格_{timestamp}.txt"
    
    # ===============================================================
    # 辅助方法
    # ===============================================================
    
    # ===============================================================
    # 功能开关辅助方法
    # ===============================================================
    
    @classmethod
    def should_parse_tables(cls) -> bool:
        """是否启用表格解析"""
        return cls.ENABLE_TABLE_PARSING
    
    @classmethod
    def should_parse_images(cls) -> bool:
        """是否启用图片解析"""
        return cls.ENABLE_IMAGE_PARSING
    
    @classmethod
    def should_detect_stamps(cls) -> bool:
        """是否启用签章识别"""
        return cls.ENABLE_STAMP_DETECTION
    
    @classmethod
    def should_parse_stamps(cls) -> bool:
        """是否启用签章解析"""
        return cls.ENABLE_STAMP_PARSING
    
    # ===============================================================
    # 保存开关辅助方法
    # ===============================================================
    
    @classmethod
    def should_save_final_result(cls) -> bool:
        """是否保存最终解析结果"""
        return cls.ENABLE_ALL_SAVES and cls.SAVE_FINAL_RESULT
    
    @classmethod
    def should_save_table_images(cls) -> bool:
        """是否保存表格图片"""
        return cls.ENABLE_ALL_SAVES and cls.SAVE_TABLE_IMAGES
    
    @classmethod
    def should_save_single_table_results(cls) -> bool:
        """是否保存单张表格识别结果"""
        return cls.ENABLE_ALL_SAVES and cls.SAVE_SINGLE_TABLE_RESULTS
    
    @classmethod
    def should_save_extracted_images(cls) -> bool:
        """是否保存提取的图片"""
        return cls.ENABLE_ALL_SAVES and cls.SAVE_EXTRACTED_IMAGES
    
    @classmethod
    def should_save_stamp_images(cls) -> bool:
        """是否保存签章图片"""
        return cls.ENABLE_ALL_SAVES and cls.SAVE_STAMP_IMAGES
    
    @classmethod
    def should_save_image_ocr_results(cls) -> bool:
        """是否保存单张图片OCR结果"""
        return cls.ENABLE_ALL_SAVES and cls.SAVE_IMAGE_OCR_RESULTS
    
    @classmethod
    def get_timestamp(cls) -> str:
        """获取当前时间戳"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    @classmethod
    def get_output_paths(cls, pdf_path: str, output_dir: str = None, timestamp: str = None) -> dict:
        """
        获取所有输出路径
        
        Args:
            pdf_path: 原PDF文件路径
            output_dir: 输出目录（默认使用 OUTPUT_BASE_DIR）
            timestamp: 时间戳（默认自动生成）
            
        Returns:
            包含所有输出路径的字典
        """
        if output_dir is None:
            output_dir = cls.OUTPUT_BASE_DIR
        
        if timestamp is None:
            timestamp = cls.get_timestamp()
        
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        return {
            'output_dir': output_dir,
            'timestamp': timestamp,
            'tables_dir': os.path.join(output_dir, cls.TABLES_DIR_TEMPLATE.format(timestamp=timestamp)),
            'images_dir': os.path.join(output_dir, cls.IMAGES_DIR_TEMPLATE.format(timestamp=timestamp)),
            'stamps_dir': os.path.join(output_dir, cls.STAMPS_DIR_TEMPLATE.format(timestamp=timestamp)),
            'single_table_results_dir': os.path.join(output_dir, cls.SINGLE_TABLE_RESULTS_DIR_TEMPLATE.format(timestamp=timestamp)),
            'image_ocr_results_dir': os.path.join(output_dir, cls.IMAGE_OCR_RESULTS_DIR_TEMPLATE.format(timestamp=timestamp)),
            'final_output': os.path.join(output_dir, cls.FINAL_RESULT_FILENAME_TEMPLATE.format(basename=base_name, timestamp=timestamp)),
            'base_name': base_name
        }
    
    @classmethod
    def print_config(cls):
        """打印当前配置（用于调试）"""
        print("\n" + "=" * 60)
        print("【功能配置】")
        print("=" * 60)
        print(f"  表格解析: {'✅' if cls.should_parse_tables() else '❌'}")
        print(f"  图片解析: {'✅' if cls.should_parse_images() else '❌'}")
        print(f"  签章识别: {'✅' if cls.should_detect_stamps() else '❌'}")
        print(f"  签章解析: {'✅' if cls.should_parse_stamps() else '❌'}")
        print("\n【保存配置】")
        print(f"  保存总开关: {'✅ 启用' if cls.ENABLE_ALL_SAVES else '❌ 禁用'}")
        print(f"  保存最终结果: {'✅' if cls.should_save_final_result() else '❌'}")
        print(f"  保存表格图片: {'✅' if cls.should_save_table_images() else '❌'}")
        print(f"  保存单张表格结果: {'✅' if cls.should_save_single_table_results() else '❌'}")
        print(f"  保存提取的图片: {'✅' if cls.should_save_extracted_images() else '❌'}")
        print(f"  保存签章图片: {'✅' if cls.should_save_stamp_images() else '❌'}")
        print(f"  保存单张图片OCR结果: {'✅' if cls.should_save_image_ocr_results() else '❌'}")
        print(f"  输出目录: {cls.OUTPUT_BASE_DIR}")
        print("=" * 60 + "\n")

