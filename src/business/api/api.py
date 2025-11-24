# FastAPI接口定义
import sys
import os
from typing import Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.infrastructure.worker.task_processor import task_processor
from src.business.service.bid_report_service import BidReportService
from src.business.service.report_regeneration_service import single_file_report_re_generate as single_file_report_re_generate_service

router = APIRouter()

class BidReportRequest(BaseModel):
    """评标报告生成请求模型"""
    project_id: str
    template_id: str
    files: Dict[str, str]

class TaskResponse(BaseModel):
    """任务响应模型"""
    task_id: str
    code: int
    message: str

class ParseTaskRequest(BaseModel):
    """解析任务请求模型"""
    project_id: str

class SingleFileReportReGenerateRequest(BaseModel):
    """单个投标文件评标报告重新生成请求模型"""
    project_id: int
    bid_url: str

@router.post("/parse_task", response_model=TaskResponse, summary="解析任务")
async def parse_task(request: BidReportRequest, background_tasks: BackgroundTasks):
    """
    评标报告生成接口 - 立即返回模式
    
    接收参数并验证成功后立即返回任务ID，后台异步处理

    Args:
        request: 评标报告生成请求，包含：
            - project_id: 项目唯一标识符
            - template_id: 报告模板ID
            - files: 文件配置字典，包含以下键：
                - tender_file: 招标文件URL地址
                - candidate_bid_files: 候选人投标文件URL地址，多个文件用逗号分隔
                - opening_record_file: 开标过程记录文件URL地址
                - review_experts_file: 评审专家信息表URL地址
                - evaluation_summary_file: 评标汇总表URL地址
                - other_files: 其他相关文件URL地址，多个文件用逗号分隔（可选字段，可不传或为空）

    Returns:
        TaskResponse: 任务响应，包含task_id和状态信息

    Raises:
        HTTPException: 参数验证失败时抛出
    """
    try:
        # 验证必需的文件类型（other_files不是必需的）
        required_files = [
            'tender_file',
            'candidate_bid_files',
            'opening_record_file',
            'review_experts_file',
            'evaluation_summary_file'
        ]

        for file_type in required_files:
            if file_type not in request.files:
                raise HTTPException(
                    status_code=400,
                    detail=f"缺少必需的文件类型: {file_type}"
                )

        # 验证各文件类型的值
        for file_type, file_urls in request.files.items():
            # 特殊处理：other_files可以为空或不存在
            if file_type == 'other_files':
                if not isinstance(file_urls, str):
                    raise HTTPException(
                        status_code=400,
                        detail=f"文件类型 {file_type} 的URL地址格式错误"
                    )
                # other_files为空时，设置为空字符串，后续处理会跳过
                if not file_urls.strip():
                    request.files[file_type] = ""
                    continue
            
            # 其他文件类型不能为空
            if not isinstance(file_urls, str) or not file_urls.strip():
                raise HTTPException(
                    status_code=400,
                    detail=f"文件类型 {file_type} 的URL地址不能为空"
                )

        # 第一步：立即将数据库中进度更新为0（必须在所有操作之前）
        from database.data_process import update_report_progress
        import logging
        try:
            # 使用进度更新函数初始化进度为0，确保在开始处理前完成
            await update_report_progress(request.project_id, "initialized", "初始化评标报告生成任务", request.template_id)
            logging.info(f"进度已初始化为0%，项目ID: {request.project_id}")
        except Exception as e:
            # 如果初始化失败，记录错误但不影响任务创建
            logging.error(f"初始化评标报告生成任务进度失败: {e}")
            # 即使失败也继续，因为service中会再次尝试初始化

        # 注意：删除旧file_info和file_range数据的逻辑在Service层执行（在保存新数据之前）
        # 这样可以避免重复删除，无论是通过API调用还是直接调用service都会执行删除

        # 创建任务
        task_id = task_processor.create_task(
            task_type="bid_report",
            project_id=request.project_id,
            template_id=request.template_id,
            files_config=request.files
        )

        # 设置业务处理器（异步任务处理器会自动处理）
        from src.business.service.task_service import TaskService
        service = TaskService()
        task_processor.business_processor = service.process_task

        # 立即返回任务ID和状态
        return TaskResponse(
            task_id=task_id,
            code=200,
            message="评标报告生成任务已提交，请使用task_id查询进度"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"处理请求时发生错误: {str(e)}"
        )

@router.get("/task_status/{task_id}", summary="查询任务状态")
async def get_task_status(task_id: str):
    """查询任务状态"""
    task_status = task_processor.get_task_status(task_id)
    if not task_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task_status

@router.get("/task_result/{task_id}", summary="获取任务结果")
async def get_task_result(task_id: str):
    """获取任务结果"""
    result = task_processor.get_task_result(task_id)
    if not result:
        task_status = task_processor.get_task_status(task_id)
        if not task_status:
            raise HTTPException(status_code=404, detail="任务不存在")
        else:
            raise HTTPException(status_code=400, detail="任务尚未完成")
    
    return result

@router.get("/tasks", summary="列出所有任务")
async def list_tasks(status: str = None):
    """列出所有任务"""
    tasks = task_processor.list_tasks(status)
    return {"tasks": tasks, "count": len(tasks)}

@router.post("/bid_report_generate", response_model=TaskResponse, summary="评标报告生成")
async def generate_bid_report(request: ParseTaskRequest, background_tasks: BackgroundTasks):
    """
    解析任务接口 - 立即返回模式
    
    根据项目ID从数据库获取file_info和file_range数据，根据页码范围解析文件并进行变量提取
    
    Args:
        request: 解析任务请求，包含：
            - project_id: 项目唯一标识符
    
    Returns:
        TaskResponse: 任务响应，包含task_id和状态信息
    
    Raises:
        HTTPException: 参数验证失败时抛出
    """
    try:
        # 验证项目ID
        if not request.project_id or not request.project_id.strip():
            raise HTTPException(
                status_code=400,
                detail="项目ID不能为空"
            )
        
        # 第一步：立即将数据库中进度更新为0，状态更新为1（处理中）（必须在所有操作之前）
        # 只保留初始化：重置进度为0，状态更新为1
        from database.data_process import update_parse_task_progress, update_parse_task_status
        import logging
        try:
            # 使用进度更新函数初始化进度为0，确保在开始处理前完成
            progress_updated = await update_parse_task_progress(request.project_id, "initialized", "初始化任务", None)
            if not progress_updated:
                logging.error(f"⚠️ API层初始化进度失败: 项目ID {request.project_id}")
            
            # 同时更新状态为1（处理中）
            status_updated = await update_parse_task_status(request.project_id, 1, "解析任务已提交", None)
            if not status_updated:
                logging.error(f"⚠️ API层初始化状态失败: 项目ID {request.project_id}")
            
            if progress_updated and status_updated:
                logging.info(f"✅ API层初始化成功: 进度已初始化为0%，状态已更新为1（处理中），项目ID: {request.project_id}")
            else:
                logging.warning(f"⚠️ API层初始化部分失败: 项目ID {request.project_id} - 进度更新: {progress_updated}, 状态更新: {status_updated}")
        except Exception as e:
            # 如果初始化失败，记录错误但不影响任务创建
            logging.error(f"初始化解析任务进度和状态失败: {e}", exc_info=True)
            # 即使失败也继续，因为service中会再次尝试初始化
        
        # 创建任务
        task_id = task_processor.create_task(
            task_type="parse_task",
            project_id=request.project_id
        )
        
        # 设置业务处理器（异步任务处理器会自动处理）
        from src.business.service.task_service import TaskService
        service = TaskService()
        task_processor.business_processor = service.process_task
        
        # 立即返回任务ID和状态
        return TaskResponse(
            task_id=task_id,
            code=200,
            message="解析任务已提交，请使用task_id查询进度"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"处理请求时发生错误: {str(e)}"
        )



## 2025.11.07
## 新增接口： 某个投标文件的评标报告重新生成接口
## 需求:用户指定评审点的页码范围，重新生成评标报告

## 接受参数：project_id, bid_id
## 数据库检索出对应的评审项及其页码范围以及历史评标报告内容
## 使用新的页码范围，重新生成评标报告
## 新的评标报告内容与历史评估报告内容进行对比合并(新的替换掉旧项,无新的就保留旧项)
## 将新的评标报告内容保存到数据库
@router.post("/single_file_report_re_generate", response_model=TaskResponse, summary="单个投标文件评标报告重新生成")
async def single_file_report_re_generate_api(request: SingleFileReportReGenerateRequest, background_tasks: BackgroundTasks):
    """
    单个投标文件评标报告重新生成接口 - 立即返回模式
    
    接收参数并验证成功后立即返回任务ID，后台异步处理
    
    Args:
        request: 单个投标文件评标报告重新生成请求，包含：
            - project_id: 项目ID (整数类型)
            - bid_url: 投标文件URL (字符串类型)

    Returns:
        TaskResponse: 任务响应，包含task_id和状态信息
    
    Raises:
        HTTPException: 参数验证失败时抛出

    """
    try:
        # 验证项目ID（project_id是int类型，不需要strip）
        if not request.project_id:
            raise HTTPException(
                status_code=400,
                detail="项目ID不能为空"
            )
        
        # 验证投标文件URL
        if not request.bid_url or not request.bid_url.strip():
            raise HTTPException(
                status_code=400,
                detail="投标文件URL不能为空"
            )
        
        # 第一步：立即将数据库中进度更新为0，状态更新为1（处理中）（必须在所有操作之前）
        # 只保留初始化：重置进度为0，状态更新为1
        from database.data_process import update_parse_task_progress, update_parse_task_status
        import logging
        try:
            # 使用进度更新函数初始化进度为0，确保在开始处理前完成
            await update_parse_task_progress(str(request.project_id), "initialized", "初始化单个投标文件报告重新生成任务", None)
            # 同时更新状态为1（处理中）
            await update_parse_task_status(str(request.project_id), 1, "单个投标文件报告重新生成任务已提交", None)
            logging.info(f"进度已初始化为0%，状态已更新为1（处理中），项目ID: {request.project_id}")
        except Exception as e:
            # 如果初始化失败，记录错误但不影响任务创建
            logging.error(f"初始化单个投标文件报告重新生成任务进度和状态失败: {e}")
            # 即使失败也继续，因为service中会再次尝试初始化
        
        # 创建任务
        task_id = task_processor.create_task(
            task_type="single_file_report_re_generate",
            project_id=request.project_id,
            bid_url=request.bid_url
        )
        
        # 设置业务处理器（异步任务处理器会自动处理）
        from src.business.service.task_service import TaskService
        service = TaskService()
        task_processor.business_processor = service.process_task
        
        # 立即返回任务ID和状态
        return TaskResponse(
            task_id=task_id,
            code=200,
            message="单个投标文件评标报告重新生成任务已提交，请使用task_id查询进度"
        )
            
  
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"处理请求时发生错误: {str(e)}"
        )