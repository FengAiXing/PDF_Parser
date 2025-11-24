#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：仅测试模板渲染功能
从数据库读取变量数据并渲染模板，不进行文件提取
"""

import asyncio
import sys
import os
import logging
import json
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.business.service.report_generation_service import ReportGenerationService
from database.data_process import get_variables_values_by_id


async def test_render_template_only():
    """
    测试仅渲染模板功能
    从数据库读取变量数据，然后渲染模板
    """
    # 使用 test1.py 中的项目ID和模板ID
    project_id = "1999999999999981162"
    template_id = "3"
    
    print("=" * 80)
    print("开始测试模板渲染功能（仅渲染，不提取）")
    print(f"项目ID: {project_id}")
    print(f"模板ID: {template_id}")
    print("=" * 80)
    
    # 创建报告生成服务
    report_service = ReportGenerationService()
    
    try:
        # 第一步：检查数据库中的变量数据
        print("\n[步骤1] 检查数据库中的变量数据...")
        variables_dict = get_variables_values_by_id(project_id)
        
        if not variables_dict:
            print(f"❌ 错误：数据库中未找到项目ID为 {project_id} 的变量数据")
            print("请确保该项目的变量数据已经保存到数据库中")
            return
        
        print(f"✅ 成功从数据库读取 {len(variables_dict)} 个变量")
        print(f"变量列表（前10个）:")
        for i, (var_name, var_value) in enumerate(list(variables_dict.items())[:10], 1):
            value_preview = str(var_value)[:50] + "..." if len(str(var_value)) > 50 else str(var_value)
            print(f"  {i}. {var_name}: {value_preview}")
        if len(variables_dict) > 10:
            print(f"  ... 还有 {len(variables_dict) - 10} 个变量")
        
        # 第二步：生成最终报告（从数据库读取数据并渲染）
        print(f"\n[步骤2] 开始渲染模板...")
        final_report = await report_service.generate_final_report(
            project_id=project_id,
            template_id=template_id
        )
        
        print(f"✅ 模板渲染完成！")
        print(f"报告内容长度: {len(final_report)} 字符")
        
        # 第三步：保存结果到文件
        print(f"\n[步骤3] 保存渲染结果到文件...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"render_result_{project_id}_.html"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(final_report)
        
        print(f"✅ 结果已保存到: {output_file}")
        
        # 第四步：显示报告预览（前500字符）
        # print(f"\n[步骤4] 报告内容预览（前500字符）:")
        # print("-" * 80)
        # preview = final_report[:500]
        # print(preview)
        # if len(final_report) > 500:
        #     print(f"... (还有 {len(final_report) - 500} 字符)")
        # print("-" * 80)
        
        # 第五步：统计信息
        # print(f"\n[步骤5] 统计信息:")
        # print(f"  总变量数: {len(variables_dict)}")
        # print(f"  报告长度: {len(final_report)} 字符")
        # print(f"  报告长度: {len(final_report) / 1024:.2f} KB")
        
        # 检查是否包含动态表格
        # 方法1：检查变量字典中是否包含表格变量（动态表格会被添加到variables_dict中）
        # 方法2：检查最终报告中是否包含表格的HTML特征（如table标签）
        has_qualification_table_in_dict = "中标候选人资质资格业绩等评审情况表格" in variables_dict
        has_score_table_in_dict = "中标候选人详细评审客观分得分情况表格" in variables_dict
        
        # 检查最终报告中是否包含表格HTML（更准确的方式）
        has_qualification_table_in_report = "<table" in final_report and ("资质" in final_report or "资格" in final_report or "业绩" in final_report)
        has_score_table_in_report = "<table" in final_report and ("详细评审" in final_report or "客观分" in final_report)
        
        # 综合判断
        has_qualification_table = has_qualification_table_in_dict or has_qualification_table_in_report
        has_score_table = has_score_table_in_dict or has_score_table_in_report
        
        # print(f"\n[步骤6] 动态表格检查:")
        # print(f"  变量字典检查:")
        # print(f"    资质表格: {'✅' if has_qualification_table_in_dict else '❌'}")
        # print(f"    得分表格: {'✅' if has_score_table_in_dict else '❌'}")
        # print(f"  报告内容检查:")
        # print(f"    资质表格: {'✅' if has_qualification_table_in_report else '❌'} (查找HTML table标签)")
        # print(f"    得分表格: {'✅' if has_score_table_in_report else '❌'} (查找HTML table标签)")
        
        # if has_qualification_table:
        #     print(f"  ✅ 综合判断：包含资质资格业绩评审情况表格")
        # else:
        #     print(f"  ⚠️  综合判断：未包含资质资格业绩评审情况表格")
        
        # if has_score_table:
        #     print(f"  ✅ 综合判断：包含详细评审客观分得分情况表格")
        # else:
        #     print(f"  ⚠️  综合判断：未包含详细评审客观分得分情况表格")
        
        # # 额外检查：统计报告中的table标签数量
        # table_count = final_report.count("<table")
        # if table_count > 0:
        #     print(f"\n  报告中共包含 {table_count} 个表格（table标签）")
        
        print("\n" + "=" * 80)
        print("测试完成！")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "=" * 80)
        print("测试失败！")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_render_template_only())

