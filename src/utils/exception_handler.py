# 异常处理工具类
# 提供统一的异常捕获和处理机制，确保所有异常都能正确更新status和保存message

import sys
import os
import traceback
import logging
from typing import Optional, Any, Callable
from functools import wraps

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.data_process import update_report_progress

logger = logging.getLogger(__name__)


class ExceptionHandler:
    """异常处理工具类 - 提供统一的异常捕获和处理机制"""
    
    @staticmethod
    def handle_exception(project_id: str, error_message: str, exception: Exception = None) -> bool:
        """
        处理异常，更新数据库状态并记录日志
        
        Args:
            project_id: 项目ID
            error_message: 错误信息
            exception: 异常对象（可选）
            
        Returns:
            bool: 处理是否成功
        """
        try:
            # 记录详细错误信息
            if exception:
                error_details = f"{error_message}\n异常类型: {type(exception).__name__}\n异常信息: {str(exception)}"
                error_details += f"\n堆栈跟踪:\n{traceback.format_exc()}"
            else:
                error_details = error_message
            
            # 更新数据库状态
            import asyncio
            try:
                # 使用异步方式更新状态
                loop = asyncio.get_event_loop()
                success = loop.run_until_complete(
                    update_report_progress(project_id, "error_occurred", error_details)
                )
            except RuntimeError:
                # 如果没有事件循环，创建新的
                success = asyncio.run(
                    update_report_progress(project_id, "error_occurred", error_details)
                )
            
            if success:
                logger.error(f"异常处理成功，项目ID: {project_id}, 错误信息: {error_message}")
            else:
                logger.error(f"异常处理失败，项目ID: {project_id}, 错误信息: {error_message}")
            
            return success
            
        except Exception as e:
            logger.error(f"异常处理过程中发生错误: {e}")
            return False
    
    @staticmethod
    def get_exception_context(exception: Exception) -> str:
        """
        获取异常的详细上下文信息
        
        Args:
            exception: 异常对象
            
        Returns:
            str: 详细的异常信息
        """
        try:
            context = f"异常类型: {type(exception).__name__}\n"
            context += f"异常信息: {str(exception)}\n"
            context += f"堆栈跟踪:\n{traceback.format_exc()}"
            return context
        except Exception as e:
            logger.error(f"获取异常上下文失败: {e}")
            return f"无法获取异常上下文: {str(exception)}"


def exception_handler_decorator(project_id: str = None):
    """
    异常处理装饰器，自动捕获和处理异常
    
    Args:
        project_id: 项目ID，如果为None则从函数参数中获取
        
    Returns:
        decorator: 装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 获取项目ID
                current_project_id = project_id
                if current_project_id is None:
                    # 尝试从函数参数中获取project_id
                    if args and len(args) > 0:
                        if isinstance(args[0], dict) and 'project_id' in args[0]:
                            current_project_id = args[0]['project_id']
                        elif hasattr(args[0], 'project_id'):
                            current_project_id = getattr(args[0], 'project_id')
                    elif 'project_id' in kwargs:
                        current_project_id = kwargs['project_id']
                
                if current_project_id:
                    error_message = f"函数 {func.__name__} 执行失败: {str(e)}"
                    ExceptionHandler.handle_exception(current_project_id, error_message, e)
                else:
                    logger.error(f"函数 {func.__name__} 执行失败，但无法获取项目ID: {str(e)}")
                
                # 重新抛出异常，保持原有的异常处理流程
                raise e
        
        return wrapper
    return decorator


def safe_execute(func: Callable, project_id: str, *args, **kwargs) -> tuple[bool, Any]:
    """
    安全执行函数，捕获异常并更新数据库状态
    
    Args:
        func: 要执行的函数
        project_id: 项目ID
        *args: 函数参数
        **kwargs: 函数关键字参数
        
    Returns:
        tuple[bool, Any]: (是否成功, 返回值或异常信息)
    """
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        error_message = f"函数 {func.__name__} 执行失败: {str(e)}"
        ExceptionHandler.handle_exception(project_id, error_message, e)
        return False, str(e)


class ExceptionContext:
    """异常上下文管理器，用于在with语句中自动处理异常"""
    
    def __init__(self, project_id: str, operation_name: str = "操作"):
        self.project_id = project_id
        self.operation_name = operation_name
        self.exception_occurred = False
        self.exception_info = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.exception_occurred = True
            self.exception_info = exc_val
            
            error_message = f"{self.operation_name}执行失败: {str(exc_val)}"
            ExceptionHandler.handle_exception(self.project_id, error_message, exc_val)
            
            # 返回False表示异常已被处理，不需要重新抛出
            return False
        
        return True
    
    def get_exception_info(self) -> Optional[str]:
        """获取异常信息"""
        if self.exception_occurred and self.exception_info:
            return str(self.exception_info)
        return None


# 便捷函数
def handle_exception_simple(project_id: str, error_message: str) -> bool:
    """
    简单的异常处理函数
    
    Args:
        project_id: 项目ID
        error_message: 错误信息
        
    Returns:
        bool: 处理是否成功
    """
    return ExceptionHandler.handle_exception(project_id, error_message)


def create_exception_context(project_id: str, operation_name: str = "操作") -> ExceptionContext:
    """
    创建异常上下文管理器
    
    Args:
        project_id: 项目ID
        operation_name: 操作名称
        
    Returns:
        ExceptionContext: 异常上下文管理器
    """
    return ExceptionContext(project_id, operation_name)


if __name__ == "__main__":
    # 测试异常处理功能
    def test_function():
        raise ValueError("测试异常")
    
    # 使用装饰器
    @exception_handler_decorator("test_project_123")
    def decorated_function():
        raise ValueError("装饰器测试异常")
    
    # 使用上下文管理器
    with create_exception_context("test_project_456", "测试操作"):
        raise RuntimeError("上下文管理器测试异常")
    
    # 使用安全执行
    success, result = safe_execute(test_function, "test_project_789")
    print(f"安全执行结果: {success}, {result}")
