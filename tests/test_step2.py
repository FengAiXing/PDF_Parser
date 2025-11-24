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

try:
    import httpx
except ImportError:
    print("❌ 需要安装 httpx 库: pip install httpx")
    sys.exit(1)

# ============================================================================
# 配置区域 - 修改这里来更改测试参数
# ============================================================================
# 项目ID配置（修改这里来测试不同的项目）
PROJECT_ID = "1999999999999981194"

# API 服务器配置
API_BASE_URL = "http://localhost:8009"  # 根据实际服务器地址修改
API_ENDPOINT = "/bid_report_generate"
# ============================================================================

async def test_parse_task(project_id: str = None):
    """测试解析任务接口（通过HTTP调用）"""
    if project_id is None:
        project_id = PROJECT_ID
    
    print("=" * 80)
    print("开始测试解析任务接口（HTTP调用）")
    print(f"API地址: {API_BASE_URL}{API_ENDPOINT}")
    print(f"项目ID: {project_id}")
    print("=" * 80)
    
    # 准备请求数据
    request_data = {
        "project_id": project_id
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

async def test_parse_task_direct(project_id: str = None):
    """测试解析任务（直接调用系统方法）"""
    if project_id is None:
        project_id = PROJECT_ID
    
    print("=" * 80)
    print("开始测试解析任务（直接调用系统方法）")
    print(f"项目ID: {project_id}")
    print("=" * 80)
    
    try:
        # 导入必要的模块
        from src.business.service.parse_task_service import ParseTaskService
        from database.data_process import update_parse_task_progress, update_parse_task_status
        
        print(f"\n📦 初始化解析任务服务...")
        parse_task_service = ParseTaskService()
        
        # 初始化进度和状态（模拟API层的初始化）
        print(f"\n🔄 初始化任务进度和状态...")
        try:
            progress_updated = await update_parse_task_progress(project_id, "initialized", "初始化任务", None)
            status_updated = await update_parse_task_status(project_id, 1, "解析任务已提交", None)
            
            if progress_updated and status_updated:
                print(f"✅ 进度和状态初始化成功")
            else:
                print(f"⚠️ 进度和状态初始化部分失败: 进度更新={progress_updated}, 状态更新={status_updated}")
        except Exception as e:
            print(f"⚠️ 初始化进度和状态时出错: {e}")
            print(f"💡 继续执行任务处理...")
        
        # 直接调用解析任务服务
        print(f"\n🚀 开始执行解析任务...")
        print(f"📋 调用 ParseTaskService.process_parse_task(project_id='{project_id}')")
        
        result = await parse_task_service.process_parse_task(project_id=project_id)
        
        print(f"\n✅ 任务执行完成!")
        print(f"📋 处理结果: {json.dumps(result, ensure_ascii=False, indent=2, default=str)}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    # ============================================================================
    # 使用说明：
    # 1. 修改文件顶部的 PROJECT_ID 来更改要测试的项目ID
    # 2. 通过注释/取消注释来选择使用哪种测试方式
    # ============================================================================
    
    # 方式1：通过HTTP接口调用（需要启动服务器）
    # asyncio.run(test_parse_task())
    
    # 方式2：直接调用系统方法（不需要启动服务器）
    asyncio.run(test_parse_task_direct())

