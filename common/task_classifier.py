# 任务分类器
from typing import Dict, List, Any
from enum import Enum

class TaskType(Enum):
    """任务类型枚举"""
    REGULAR = "regular"  # 常规任务
    LARGE_FILE = "large_file"  # 大文件任务

class TaskClassifier:
    """任务分类器类 - 负责将文件按类型分类为常规任务和大文件任务"""
    
    def __init__(self):
        """初始化任务分类器"""
        # 定义常规任务的文件类型
        self.regular_file_types = {
            'tender_file',           # 招标文件
            'opening_record_file',   # 开标过程记录文件
            'review_experts_file',   # 评审专家信息表
            'evaluation_summary_file', # 评标汇总表
            'other_files'            # 其他相关文件
        }
        
        # 定义大文件任务的文件类型
        self.large_file_types = {
            'candidate_bid_files'    # 候选人投标文件
        }
    
    def classify_files(self, files_config: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        根据文件类型分类任务，支持多文件格式
        
        Args:
            files_config: 文件配置字典，支持单文件和多文件格式
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: 分类后的任务组
                - regular_tasks: 常规任务列表
                - large_file_tasks: 大文件任务列表
        """
        regular_tasks = []
        large_file_tasks = []
        
        for file_type, file_data in files_config.items():
            if file_type in self.regular_file_types:
                # 处理常规任务
                self._process_regular_tasks(file_type, file_data, regular_tasks)
            
            elif file_type in self.large_file_types:
                # 处理大文件任务
                self._process_large_file_tasks(file_type, file_data, large_file_tasks)
        
        return {
            "regular_tasks": regular_tasks,
            "large_file_tasks": large_file_tasks
        }
    
    def _process_regular_tasks(self, file_type: str, file_data: Any, regular_tasks: List[Dict[str, Any]]) -> None:
        """
        处理常规任务
        
        Args:
            file_type: 文件类型
            file_data: 文件数据
            regular_tasks: 常规任务列表
        """
        if isinstance(file_data, str):
            # 简单字符串格式，支持逗号分隔的多个文件
            if file_data and file_data.strip():
                # 检查是否包含逗号分隔的多个文件
                if ',' in file_data:
                    # 多个文件，分别处理
                    urls = [url.strip() for url in file_data.split(',') if url.strip()]
                    for url in urls:
                        regular_tasks.append({
                            "file_type": file_type,
                            "file_url": url,
                            "file_format": self._detect_file_format(url),
                            "task_type": TaskType.REGULAR.value
                        })
                else:
                    # 单个文件
                    regular_tasks.append({
                        "file_type": file_type,
                        "file_url": file_data.strip(),
                        "file_format": self._detect_file_format(file_data.strip()),
                        "task_type": TaskType.REGULAR.value
                    })
        
        elif isinstance(file_data, list):
            # 多文件列表格式
            for file_item in file_data:
                if isinstance(file_item, dict) and 'url' in file_item:
                    regular_tasks.append({
                        "file_type": file_type,
                        "file_url": file_item['url'],
                        "file_format": file_item.get('format', self._detect_file_format(file_item['url'])),
                        "task_type": TaskType.REGULAR.value
                    })
                elif isinstance(file_item, str):
                    regular_tasks.append({
                        "file_type": file_type,
                        "file_url": file_item,
                        "file_format": self._detect_file_format(file_item),
                        "task_type": TaskType.REGULAR.value
                    })
    
    def _process_large_file_tasks(self, file_type: str, file_data: Any, large_file_tasks: List[Dict[str, Any]]) -> None:
        """
        处理大文件任务
        
        Args:
            file_type: 文件类型
            file_data: 文件数据
            large_file_tasks: 大文件任务列表
        """
        if isinstance(file_data, str):
            # 简单字符串格式（逗号分隔）
            if file_data and file_data.strip():
                urls = [url.strip() for url in file_data.split(',') if url.strip()]
                for url in urls:
                    large_file_tasks.append({
                        "file_type": file_type,
                        "file_url": url,
                        "file_format": self._detect_file_format(url),
                        "task_type": TaskType.LARGE_FILE.value
                    })
        
        elif isinstance(file_data, list):
            # 多文件列表格式
            for file_item in file_data:
                if isinstance(file_item, dict) and 'url' in file_item:
                    large_file_tasks.append({
                        "file_type": file_type,
                        "file_url": file_item['url'],
                        "file_format": file_item.get('format', self._detect_file_format(file_item['url'])),
                        "task_type": TaskType.LARGE_FILE.value
                    })
                elif isinstance(file_item, str):
                    large_file_tasks.append({
                        "file_type": file_type,
                        "file_url": file_item,
                        "file_format": self._detect_file_format(file_item),
                        "task_type": TaskType.LARGE_FILE.value
                    })
    
    def _detect_file_format(self, url: str) -> str:
        """
        从URL中检测文件格式
        
        Args:
            url: 文件URL
            
        Returns:
            str: 检测到的文件格式
            
        Raises:
            ValueError: 不支持的文件格式
        """
        try:
            import os
            # 对于本地文件路径，直接使用os.path.splitext
            if os.path.exists(url):
                file_extension = os.path.splitext(url)[1].lower()
            else:
                # 对于URL，使用urllib.parse
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                file_extension = os.path.splitext(parsed_url.path)[1].lower()
            
            # 文件格式扩展名映射
            file_extension_map = {
                '.pdf': 'pdf',
                '.xlsx': 'xlsx',
                '.xls': 'xls',
            }
            
            # 检查支持的格式
            if file_extension in file_extension_map:
                return file_extension_map[file_extension]
            
            # 不支持的文件格式，抛出异常
            supported_formats = list(file_extension_map.keys())
            raise ValueError(f"不支持的文件格式: {file_extension}。支持的格式: {supported_formats}")
            
        except ValueError:
            # 重新抛出ValueError
            raise
        except Exception as e:
            # 其他异常，抛出格式检测失败错误
            raise ValueError(f"文件格式检测失败: {url}, 错误: {str(e)}")
