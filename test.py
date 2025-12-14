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

# 配置参数
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\服务文件\一--阳泉煤矿签章版投标文件4.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\装备制造大学司钻（井下）作业实操考核系统.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\服务文件\阳泉燕龛块炭加工招标文件.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\麦捷煤业智能通风技术规格书.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\招标资料要求.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\单页pdf\阳泉市南庄煤炭集团有限责任公司西上庄煤矿高压柴油发电机组采购招标文件\阳泉市南庄煤炭集团有限责任公司西上庄煤矿高压柴油发电机组采购招标文件_13.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\跨页表格测试\PDF合并1-2.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\跨页表格测试\PDF合并10-16.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\跨页表格测试\PDF合并36-39.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\跨页表格测试\PDF合并4142.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\跨页表格测试\PDF合并54-58.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\跨页表格测试\PDF合并10-16.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\跨页表格测试\PDF合并69-75.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\阳泉市南庄煤炭集团有限责任公司西上庄煤矿高压柴油发电机组采购招标文件.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\货物项目技术资料要求高压柴油发电机组 - 新.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\中央进风大巷矸石带式输送机电控设备技术规格书202.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\单页pdf\阳泉市南庄煤炭集团有限责任公司西上庄煤矿高压柴油发电机组采购招标文件\阳泉市南庄煤炭集团有限责任公司西上庄煤矿高压柴油发电机组采购招标文件_38.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\异常文件\[招标文件-后审]2024年清徐县老旧小区改造项目施工 - 004 - 招标文件.pdf"
PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\所有招标文件\1沁水县鑫海能源有限责任公司郑庄矿井食堂工程招标文件.pdf"
# PDF_PATH = r"C:\Users\gf133\Desktop\变量提取文件\灵石县第七中学校新建工程一批室内装修材料采购项目——招标\灵石县第七中学校新建工程一批室内装修材料采购项目——招标\灵石县第七中学校新建工程一批室内装修材料采购项目——招标.pdf"

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
