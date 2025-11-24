# -*- coding: utf-8 -*-
"""
JSON文件解析工具
用于解析用户传入的JSON格式文件配置，提取文件URL和类型信息
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class JSONFileParser:
    """JSON文件解析器类 - 负责解析文件配置JSON"""
    
    def __init__(self):
        """初始化JSON文件解析器"""
        # 支持的文件类型
        self.supported_file_types = {
            'tender_file',           # 招标文件
            'candidate_bid_files',   # 候选人投标文件
            'opening_record_file',   # 开标过程记录文件
            'review_experts_file',   # 评审专家信息表
            'evaluation_summary_file',  # 评标汇总表
            'other_files'            # 其他相关文件
        }
        
        # 支持的文件格式
        self.supported_file_formats = {
            'pdf', 'PDF',
            'xlsx', 'XLSX', 
            'xls', 'XLS'
        }
        
        # 文件格式扩展名映射（与task_classifier.py保持一致）
        self.file_extension_map = {
            '.pdf': 'pdf',
            '.xlsx': 'xlsx',
            '.xls': 'xls',
        }
    
    def parse_files_config(self, json_data: Union[str, dict]) -> Dict[str, Union[str, List[Dict[str, str]]]]:
        """
        解析JSON格式的文件配置，支持多文件格式
        
        Args:
            json_data: JSON字符串或字典对象
            
        Returns:
            Dict[str, Union[str, List[Dict[str, str]]]]: 解析后的文件配置字典
                - 单文件: 键为文件类型，值为URL字符串
                - 多文件: 键为文件类型，值为文件信息列表，每个元素包含url和format字段
            
        Raises:
            ValueError: JSON格式错误或文件配置无效
            TypeError: 输入数据类型错误
        """
        try:
            # 如果是字符串，解析为字典
            if isinstance(json_data, str):
                files_config = json.loads(json_data)
            elif isinstance(json_data, dict):
                files_config = json_data
            else:
                raise TypeError(f"不支持的数据类型: {type(json_data)}，期望str或dict")
            
            # 验证文件配置格式
            self._validate_files_config(files_config)
            
            # 解析和标准化文件配置
            parsed_config = self._parse_files_structure(files_config)
            
            logger.info(f"成功解析文件配置，包含 {len(parsed_config)} 个文件类型")
            return parsed_config
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            raise ValueError(f"JSON格式错误: {e}")
        except Exception as e:
            logger.error(f"文件配置解析失败: {e}")
            raise ValueError(f"文件配置解析失败: {e}")
    
    def _validate_files_config(self, files_config: Dict[str, Any]) -> None:
        """
        验证文件配置的有效性
        
        Args:
            files_config: 文件配置字典
            
        Raises:
            ValueError: 配置无效时抛出异常
        """
        if not isinstance(files_config, dict):
            raise ValueError("文件配置必须是字典格式")
        
        if not files_config:
            raise ValueError("文件配置不能为空")
        
        # 检查是否包含支持的文件类型
        valid_types = [file_type for file_type in files_config.keys() 
                      if file_type in self.supported_file_types]
        
        if not valid_types:
            raise ValueError(f"未找到支持的文件类型。支持的类型: {list(self.supported_file_types)}")
        
        # 验证每个文件类型的值
        for file_type, file_data in files_config.items():
            if file_type in self.supported_file_types:
                if not isinstance(file_data, (str, list, dict)):
                    raise ValueError(f"文件类型 '{file_type}' 的值必须是字符串、列表或字典")
                
                # 验证不同格式的数据
                if isinstance(file_data, str):
                    # 字符串格式
                    if file_data and file_data.strip():
                        self._validate_urls(file_data, file_type)
                
                elif isinstance(file_data, list):
                    # 列表格式
                    if file_data:
                        for item in file_data:
                            if isinstance(item, str):
                                if item.strip():
                                    self._validate_urls(item, file_type)
                            elif isinstance(item, dict):
                                if 'url' in item and item['url'].strip():
                                    self._validate_urls(item['url'], file_type)
                            else:
                                raise ValueError(f"文件类型 '{file_type}' 的列表项必须是字符串或包含url字段的字典")
                
                elif isinstance(file_data, dict):
                    # 字典格式
                    if 'url' in file_data:
                        # 单文件对象
                        if file_data['url'] and file_data['url'].strip():
                            self._validate_urls(file_data['url'], file_type)
                    elif 'files' in file_data:
                        # 多文件对象
                        files_list = file_data['files']
                        if isinstance(files_list, list):
                            for file_item in files_list:
                                if isinstance(file_item, dict) and 'url' in file_item:
                                    if file_item['url'] and file_item['url'].strip():
                                        self._validate_urls(file_item['url'], file_type)
                                else:
                                    raise ValueError(f"文件类型 '{file_type}' 的files列表项必须包含url字段")
                        else:
                            raise ValueError(f"文件类型 '{file_type}' 的files字段必须是列表")
                    else:
                        raise ValueError(f"文件类型 '{file_type}' 的字典必须包含url或files字段")
    
    def _validate_urls(self, file_urls: str, file_type: str) -> None:
        """
        验证URL格式的有效性，支持HTTP/HTTPS URL和本地文件路径
        
        Args:
            file_urls: 文件URL字符串（可能包含多个URL，用逗号分隔）
            file_type: 文件类型
            
        Raises:
            ValueError: URL格式无效时抛出异常
        """
        urls = [url.strip() for url in file_urls.split(',') if url.strip()]
        
        if not urls:
            raise ValueError(f"文件类型 '{file_type}' 的URL不能为空")
        
        for url in urls:
            try:
                # 检查是否为本地文件路径
                if os.path.exists(url):
                    # 本地文件路径，验证文件是否存在
                    if not os.path.isfile(url):
                        raise ValueError(f"本地文件路径不是文件: {url}")
                    continue
                
                # 检查是否为HTTP/HTTPS URL
                parsed_url = urlparse(url)
                if parsed_url.scheme in ['http', 'https']:
                    if not parsed_url.netloc:
                        raise ValueError(f"无效的URL格式: {url}")
                    continue
                
                # 其他情况，尝试作为本地路径处理
                if os.path.exists(url):
                    if not os.path.isfile(url):
                        raise ValueError(f"本地文件路径不是文件: {url}")
                else:
                    raise ValueError(f"无效的URL格式或文件不存在: {url}")
                    
            except Exception as e:
                raise ValueError(f"文件类型 '{file_type}' 的URL格式错误: {url}, 错误: {e}")
    
    def _parse_files_structure(self, files_config: Dict[str, Any]) -> Dict[str, Union[str, List[Dict[str, str]]]]:
        """
        解析文件结构，支持单文件和多文件格式
        
        Args:
            files_config: 原始文件配置
            
        Returns:
            Dict[str, Union[str, List[Dict[str, str]]]]: 解析后的文件配置
        """
        parsed_config = {}
        
        for file_type, file_data in files_config.items():
            if file_type in self.supported_file_types:
                if not file_data:
                    logger.warning(f"文件类型 '{file_type}' 的数据为空，跳过")
                    continue
                
                # 处理不同的数据格式
                if isinstance(file_data, str):
                    # 简单字符串格式（向后兼容）
                    if file_data.strip():
                        parsed_config[file_type] = file_data.strip()
                        logger.debug(f"添加单文件: {file_type} -> {file_data.strip()}")
                
                elif isinstance(file_data, list):
                    # 列表格式，支持多文件
                    if file_data:
                        file_list = []
                        for file_item in file_data:
                            if isinstance(file_item, str):
                                # 简单URL字符串
                                file_info = {
                                    'url': file_item.strip(),
                                    'format': self._detect_file_format(file_item.strip())
                                }
                                file_list.append(file_info)
                            elif isinstance(file_item, dict):
                                # 复杂文件对象
                                if 'url' in file_item:
                                    file_info = {
                                        'url': file_item['url'].strip(),
                                        'format': file_item.get('format', self._detect_file_format(file_item['url']))
                                    }
                                    # 验证文件格式
                                    if file_info['format'] in self.supported_file_formats:
                                        file_list.append(file_info)
                                    else:
                                        logger.warning(f"不支持的文件格式: {file_info['format']}，跳过文件: {file_info['url']}")
                                else:
                                    logger.warning(f"文件对象缺少url字段: {file_item}")
                            else:
                                logger.warning(f"不支持的文件项类型: {type(file_item)}")
                        
                        if file_list:
                            if len(file_list) == 1:
                                # 只有一个文件，使用简单格式
                                parsed_config[file_type] = file_list[0]['url']
                            else:
                                # 多个文件，使用列表格式
                                parsed_config[file_type] = file_list
                            logger.debug(f"添加文件列表: {file_type} -> {len(file_list)} 个文件")
                
                elif isinstance(file_data, dict):
                    # 字典格式，可能是单文件或多文件
                    if 'url' in file_data:
                        # 单文件对象
                        file_info = {
                            'url': file_data['url'].strip(),
                            'format': file_data.get('format', self._detect_file_format(file_data['url']))
                        }
                        if file_info['format'] in self.supported_file_formats:
                            parsed_config[file_type] = file_info['url']
                            logger.debug(f"添加单文件对象: {file_type} -> {file_info['url']}")
                        else:
                            logger.warning(f"不支持的文件格式: {file_info['format']}，跳过文件: {file_info['url']}")
                    elif 'files' in file_data:
                        # 多文件对象
                        files_list = file_data['files']
                        if isinstance(files_list, list) and files_list:
                            file_list = []
                            for file_item in files_list:
                                if isinstance(file_item, dict) and 'url' in file_item:
                                    file_info = {
                                        'url': file_item['url'].strip(),
                                        'format': file_item.get('format', self._detect_file_format(file_item['url']))
                                    }
                                    if file_info['format'] in self.supported_file_formats:
                                        file_list.append(file_info)
                                    else:
                                        logger.warning(f"不支持的文件格式: {file_info['format']}，跳过文件: {file_info['url']}")
                                else:
                                    logger.warning(f"无效的文件项: {file_item}")
                            
                            if file_list:
                                if len(file_list) == 1:
                                    parsed_config[file_type] = file_list[0]['url']
                                else:
                                    parsed_config[file_type] = file_list
                                logger.debug(f"添加多文件对象: {file_type} -> {len(file_list)} 个文件")
                        else:
                            logger.warning(f"文件类型 '{file_type}' 的files字段为空或无效")
                    else:
                        logger.warning(f"文件类型 '{file_type}' 的字典格式无效，缺少url或files字段")
                
                else:
                    logger.warning(f"不支持的文件数据类型: {type(file_data)} for {file_type}")
            else:
                logger.warning(f"不支持的文件类型: {file_type}，跳过")
        
        return parsed_config
    
    def _detect_file_format(self, url: str) -> str:
        """
        从URL中检测文件格式
        
        Args:
            url: 文件URL
            
        Returns:
            str: 检测到的文件格式
        """
        try:
            # 从URL路径中提取文件扩展名
            parsed_url = urlparse(url)
            path = parsed_url.path.lower()
            
            for ext, format_name in self.file_extension_map.items():
                if path.endswith(ext):
                    return format_name
            
            # 检查是否为Word文档，如果是则抛出异常
            if path.endswith('.docx') or path.endswith('.doc'):
                raise ValueError(f"不支持Word文档格式: {url}")
            
            # 默认返回pdf格式
            return 'pdf'
        except Exception:
            return 'pdf'
    
    def _clean_files_config(self, files_config: Dict[str, Any]) -> Dict[str, str]:
        """
        清理和标准化文件配置
        
        Args:
            files_config: 原始文件配置
            
        Returns:
            Dict[str, str]: 清理后的文件配置
        """
        cleaned_config = {}
        
        for file_type, file_urls in files_config.items():
            if file_type in self.supported_file_types:
                if file_urls and str(file_urls).strip():
                    # 清理URL字符串
                    cleaned_urls = str(file_urls).strip()
                    cleaned_config[file_type] = cleaned_urls
                    logger.debug(f"添加文件类型: {file_type}, URL: {cleaned_urls}")
                else:
                    logger.warning(f"文件类型 '{file_type}' 的URL为空，跳过")
            else:
                logger.warning(f"不支持的文件类型: {file_type}，跳过")
        
        return cleaned_config
    
    def get_file_type_info(self, file_type: str) -> Dict[str, Any]:
        """
        获取文件类型的详细信息
        
        Args:
            file_type: 文件类型
            
        Returns:
            Dict[str, Any]: 文件类型信息
        """
        file_type_descriptions = {
            'tender_file': {
                'name': '招标文件',
                'description': '项目招标的正式文件，包含项目要求、评标标准等',
                'is_regular': True
            },
            'candidate_bid_files': {
                'name': '候选人投标文件',
                'description': '投标人提交的投标文件，通常文件较大',
                'is_regular': False
            },
            'opening_record_file': {
                'name': '开标过程记录文件',
                'description': '记录开标过程的文件',
                'is_regular': True
            },
            'review_experts_file': {
                'name': '评审专家信息表',
                'description': '评标委员会专家信息文件',
                'is_regular': True
            },
            'evaluation_summary_file': {
                'name': '评标汇总表',
                'description': '评标结果汇总文件',
                'is_regular': True
            },
            'other_files': {
                'name': '其他相关文件',
                'description': '其他补充文件',
                'is_regular': True
            }
        }
        
        return file_type_descriptions.get(file_type, {
            'name': '未知文件类型',
            'description': '不支持的文件类型',
            'is_regular': False
        })
    
    def get_supported_file_types(self) -> List[str]:
        """
        获取支持的文件类型列表
        
        Returns:
            List[str]: 支持的文件类型列表
        """
        return list(self.supported_file_types)
    
    def is_regular_file_type(self, file_type: str) -> bool:
        """
        判断文件类型是否为常规文件
        
        Args:
            file_type: 文件类型
            
        Returns:
            bool: 是否为常规文件类型
        """
        regular_types = {
            'tender_file',
            'opening_record_file', 
            'review_experts_file',
            'evaluation_summary_file',
            'other_files'
        }
        return file_type in regular_types
    
    def is_large_file_type(self, file_type: str) -> bool:
        """
        判断文件类型是否为大文件
        
        Args:
            file_type: 文件类型
            
        Returns:
            bool: 是否为大文件类型
        """
        large_types = {'candidate_bid_files'}
        return file_type in large_types


def validate_file_urls(file_urls: str) -> List[str]:
    """
    验证和清理文件URL列表
    
    Args:
        file_urls: 文件URL字符串（逗号分隔）
        
    Returns:
        List[str]: 清理后的URL列表
    """
    if not file_urls or not file_urls.strip():
        return []
    
    urls = [url.strip() for url in file_urls.split(',') if url.strip()]
    parser = JSONFileParser()
    
    for url in urls:
        try:
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValueError(f"无效的URL格式: {url}")
        except Exception as e:
            raise ValueError(f"URL验证失败: {url}, 错误: {e}")
    
    return urls


if __name__ == "__main__":
    # 测试代码
    test_json = {
        "tender_file": "https://example.com/tender.pdf",
        "candidate_bid_files": "https://example.com/bid1.pdf,https://example.com/bid2.pdf",
        "opening_record_file": "https://example.com/opening.pdf",
        "review_experts_file": "https://example.com/experts.pdf",
        "evaluation_summary_file": "https://example.com/summary.pdf",
        "other_files": "https://example.com/other.pdf"
    }
    
    parser = JSONFileParser()
    result = parser.parse_files_config(test_json)
    print("解析结果:")
    for file_type, urls in result.items():
        print(f"  {file_type}: {urls}")
