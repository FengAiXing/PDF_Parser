# -*- coding: utf-8 -*-
"""
PDF完整解析脚本（包含表格识别）
按页组织内容：表格和图片识别结果替换到对应页面位置
"""

import os
import sys
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from File_handle import FileProcessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

PDF_PATH = r"your_file.pdf"  # 请替换为实际的PDF文件路径
OUTPUT_DIR = "output_complete"
MAX_WORKERS = 100


def main():
    """主函数：完整解析PDF（文本 + 表格 + 图片），按页组织"""
    if not os.path.exists(PDF_PATH):
        print(f"❌ 错误：找不到文件 {PDF_PATH}")
        return
    
    try:
        processor = FileProcessor(
            vision_model="doubao-seed-1-6-vision-250815",
            max_workers=MAX_WORKERS
        )
        
        processor.process_pdf_full(
            pdf_path=PDF_PATH,
            output_dir=OUTPUT_DIR,
            save_table_images=True,
            save_single_table_results=True,
            remove_header_footer=True,
            use_smart_removal=True
        )
        
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
