#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

# 导入服务类
from src.business.service.report_regeneration_service import single_file_report_re_generate

# 使用模式：DIRECT（直接调用）或 HTTP（HTTP调用）
USE_MODE = "DIRECT"  # 改为 "HTTP" 可以使用HTTP调用

# API 服务器配置（仅在HTTP模式下使用）
API_BASE_URL = "http://localhost:8009"  # 根据实际服务器地址修改
API_ENDPOINT = "/single_file_report_re_generate"

async def test_single_file_report_re_generate_direct():
    """测试单个投标文件评标报告重新生成（直接调用函数）"""
    
    project_id = 1999999999999981194
    bid_url = r"C:\Users\gf133\Desktop\变量提取文件\监理\1山西太行建设工程监理有限公司.pdf"
    
    print("=" * 80)
    print("开始测试单个投标文件评标报告重新生成（直接调用函数）")
    print(f"项目ID: {project_id}")
    print(f"投标文件URL: {bid_url}")
    print("=" * 80)
    
    try:
        print(f"\n📤 开始调用 single_file_report_re_generate 函数...")
        print(f"📦 参数: project_id={project_id}, bid_url={bid_url}")
        
        # 直接调用函数
        result = await single_file_report_re_generate(
            project_id=project_id,
            bid_url=bid_url
        )
        
        print(f"\n✅ 调用成功!")
        # print(f"📋 返回结果: {json.dumps(result, ensure_ascii=False, indent=2, default=str)}")
        
        # if "task_id" in result:
        #     task_id = result["task_id"]
        #     print(f"\n🎯 任务ID: {task_id}")
        # else:
        #     print("⚠️ 返回结果中未包含 task_id")
            
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_single_file_report_re_generate_http():
    """测试单个投标文件评标报告重新生成接口（通过HTTP调用）"""
    
    try:
        import httpx
    except ImportError:
        print("❌ 需要安装 httpx 库: pip install httpx")
        sys.exit(1)
    
    project_id = 1999999999999981194
    bid_url = r"C:\Users\gf133\Desktop\变量提取文件\监理\1山西太行建设工程监理有限公司.pdf"
    
    print("=" * 80)
    print("开始测试单个投标文件评标报告重新生成接口（HTTP调用）")
    print(f"API地址: {API_BASE_URL}{API_ENDPOINT}")
    print(f"项目ID: {project_id}")
    print(f"投标文件URL: {bid_url}")
    print("=" * 80)
    
    # 准备请求数据
    request_data = {
        "project_id": project_id,
        "bid_url": bid_url
    }
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            print(f"\n📤 发送POST请求到: {API_BASE_URL}{API_ENDPOINT}")
            print(f"📦 请求数据: {json.dumps(request_data, ensure_ascii=False, indent=2)}")
            
            # 发送HTTP请求
            response = await client.post(
                f"{API_BASE_URL}{API_ENDPOINT}",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"\n📥 响应状态码: {response.status_code}")
            print(f"📥 响应头: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 请求成功!")
                print(f"📋 响应数据: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                if "task_id" in result:
                    task_id = result["task_id"]
                    print(f"\n🎯 任务ID: {task_id}")
                    print(f"💡 提示: 任务正在后台处理，可以通过任务ID查询状态")
                else:
                    print("⚠️ 响应中未包含 task_id")
            else:
                print(f"❌ 请求失败!")
                print(f"错误信息: {response.text}")
                try:
                    error_detail = response.json()
                    print(f"错误详情: {json.dumps(error_detail, ensure_ascii=False, indent=2)}")
                except:
                    print(f"响应内容: {response.text}")
                    
    except httpx.TimeoutException:
        print(f"\n❌ 请求超时: 服务器响应时间过长")
    except httpx.ConnectError:
        print(f"\n❌ 连接失败: 无法连接到服务器 {API_BASE_URL}")
        print(f"💡 请确保服务器正在运行，并且地址正确")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

async def test_single_file_report_re_generate():
    """根据 USE_MODE 选择测试方式"""
    if USE_MODE == "DIRECT":
        await test_single_file_report_re_generate_direct()
    elif USE_MODE == "HTTP":
        await test_single_file_report_re_generate_http()
    else:
        print(f"❌ 无效的 USE_MODE: {USE_MODE}，请使用 'DIRECT' 或 'HTTP'")

if __name__ == "__main__":
    asyncio.run(test_single_file_report_re_generate())

