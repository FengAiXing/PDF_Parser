"""
业绩部分内容筛选模块

本模块用于从投标文件中筛选和提取业绩相关的内容。
主要功能包括：
- 识别业绩相关表格
- 提取业绩项目信息
- 过滤和整理业绩数据
"""

import logging
import re
from typing import Dict, List, Any, Optional, Union

logger = logging.getLogger(__name__)


class PerformanceContentFilter:
    """业绩内容筛选器"""
    
    def __init__(self):
        """初始化筛选器"""
        self.logger = logger
    
    def filter_performance_content(self, content: str, ranking: str = "") -> Dict[str, Any]:
        """
        筛选业绩相关内容
        
        Args:
            content: 投标文件内容
            ranking: 排名信息（如"第一名"、"第二名"等）
            
        Returns:
            Dict[str, Any]: 筛选后的业绩内容
        """
        try:
            # 定义头部关键词
            header_keywords = [
                '项目业绩情况',
                '类似项目情况',
                '类似项目业绩情况',
                '类似项目情况表',
                '类似项目业绩情况表',
                '项目业绩情况表',
                '业绩汇总表',
                '工程业绩汇总',
                '项目业绩汇总',
                '工程业绩情况表'
            ]
            
            # 定义尾部关键词
            footer_keywords = [
                '信誉材料',
                '管理机构人员配备',
                '主要人员配备'
            ]
            
            # 查找头部关键词位置
            header_match = None
            header_keyword = None
            for keyword in header_keywords:
                pattern = re.escape(keyword)
                match = re.search(pattern, content)
                if match:
                    header_match = match
                    header_keyword = keyword
                    break
            
            if not header_match:
                self.logger.warning(f"未找到业绩相关头部关键词")
                return {
                    'original_content': content,
                    'performance_content': '',
                    'performance_variable_name': f"{ranking}业绩源文件" if ranking else "业绩源文件",
                    'extraction_success': False,
                    'error_message': '未找到业绩相关头部关键词'
                }
            
            # 查找尾部关键词位置 - 找到文档中第一个出现的尾部关键词
            footer_match = None
            footer_keyword = None
            remaining_content = content[header_match.end():]
            
            # 记录所有匹配的尾部关键词及其位置
            all_footer_matches = []
            for keyword in footer_keywords:
                # 去除标点符号后匹配
                clean_keyword = re.sub(r'[^\w\u4e00-\u9fff]', '', keyword)
                pattern = re.escape(clean_keyword)
                match = re.search(pattern, remaining_content)
                if match:
                    all_footer_matches.append((match.start(), match, keyword))
            
            # 找到位置最靠前的尾部关键词（第一个出现的）
            if all_footer_matches:
                all_footer_matches.sort(key=lambda x: x[0])  # 按位置排序
                footer_match = all_footer_matches[0][1]
                footer_keyword = all_footer_matches[0][2]
            
            if not footer_match:
                self.logger.warning(f"未找到业绩相关尾部关键词")
                return {
                    'original_content': content,
                    'performance_content': '',
                    'performance_variable_name': f"{ranking}业绩源文件" if ranking else "业绩源文件",
                    'extraction_success': False,
                    'error_message': '未找到业绩相关尾部关键词'
                }
            
            # 计算实际位置（相对于原内容的绝对位置）
            footer_start_pos = header_match.end() + footer_match.start()
            footer_end_pos = header_match.end() + footer_match.end()
            
            # 截取业绩部分内容
            performance_content = content[header_match.start():footer_end_pos]
            
            # 构建新的原文件内容（保留关键词，移除中间内容）
            before_performance = content[:header_match.start()]
            after_performance = content[footer_start_pos:]
            cleaned_content = before_performance + header_keyword + footer_keyword + after_performance
            
            # 生成业绩变量名称
            performance_variable_name = f"{ranking}业绩源文件" if ranking else "业绩源文件"
            
            self.logger.info(f"成功截取业绩内容，头部关键词: {header_keyword}, 尾部关键词: {footer_keyword}")
            self.logger.info(f"业绩内容长度: {len(performance_content)}, 清理后内容长度: {len(cleaned_content)}")
            
            return {
                'original_content': cleaned_content,
                'performance_content': performance_content,
                'performance_variable_name': performance_variable_name,
                'header_keyword': header_keyword,
                'footer_keyword': footer_keyword,
                'extraction_success': True,
                'error_message': ''
            }
            
        except Exception as e:
            self.logger.error(f"筛选业绩内容失败: {e}")
            return {
                'original_content': content,
                'performance_content': '',
                'performance_variable_name': f"{ranking}业绩源文件" if ranking else "业绩源文件",
                'extraction_success': False,
                'error_message': f'筛选业绩内容失败: {e}'
            }
    
    def extract_performance_tables(self, content: str) -> List[Dict[str, Any]]:
        """
        提取业绩相关表格
        
        Args:
            content: 投标文件内容
            
        Returns:
            List[Dict[str, Any]]: 业绩表格列表
        """
        try:
            # 从业绩内容中提取表格
            performance_result = self.filter_performance_content(content)
            performance_content = performance_result.get('performance_content', '')
            
            if not performance_content:
                return []
            
            # 查找表格标签
            table_pattern = r'<table[^>]*>.*?</table>'
            tables = re.findall(table_pattern, performance_content, re.DOTALL | re.IGNORECASE)
            
            table_list = []
            for i, table in enumerate(tables):
                table_list.append({
                    'table_index': i + 1,
                    'table_content': table,
                    'table_length': len(table)
                })
            
            self.logger.info(f"从业绩内容中提取到 {len(table_list)} 个表格")
            return table_list
            
        except Exception as e:
            self.logger.error(f"提取业绩表格失败: {e}")
            return []
    
    def validate_performance_data(self, performance_data: Dict[str, Any]) -> bool:
        """
        验证业绩数据的有效性
        
        Args:
            performance_data: 业绩数据
            
        Returns:
            bool: 数据是否有效
        """
        try:
            # 检查必要字段
            required_fields = ['original_content', 'performance_content', 'performance_variable_name']
            for field in required_fields:
                if field not in performance_data:
                    self.logger.warning(f"业绩数据缺少必要字段: {field}")
                    return False
            
            # 检查业绩内容是否为空
            performance_content = performance_data.get('performance_content', '')
            if not performance_content or len(performance_content.strip()) == 0:
                self.logger.warning("业绩内容为空")
                return False
            
            # 检查业绩内容长度是否合理（至少包含一些内容）
            if len(performance_content) < 50:
                self.logger.warning(f"业绩内容过短: {len(performance_content)} 字符")
                return False
            
            # 检查是否包含表格或结构化内容
            has_table = '<table' in performance_content.lower()
            has_structured_content = any(keyword in performance_content for keyword in ['项目', '业绩', '情况', '表'])
            
            if not has_table and not has_structured_content:
                self.logger.warning("业绩内容中未发现表格或结构化内容")
                return False
            
            self.logger.info("业绩数据验证通过")
            return True
            
        except Exception as e:
            self.logger.error(f"验证业绩数据失败: {e}")
            return False
    
    def process_multiple_files(self, files_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        批量处理多个文件的业绩内容筛选
        
        Args:
            files_data: 文件数据字典，格式为 {"第一名": {"content": "...", "file_url": "..."}, ...}
            
        Returns:
            Dict[str, Dict[str, Any]]: 处理结果字典
        """
        try:
            results = {}
            
            for ranking, file_info in files_data.items():
                content = file_info.get('content', '')
                if not content:
                    self.logger.warning(f"{ranking} 文件内容为空，跳过处理")
                    continue
                
                # 筛选业绩内容
                performance_result = self.filter_performance_content(content, ranking)
                
                # 验证结果
                if self.validate_performance_data(performance_result):
                    results[ranking] = {
                        'original_content': performance_result['original_content'],
                        'performance_content': performance_result['performance_content'],
                        'performance_variable_name': performance_result['performance_variable_name'],
                        'header_keyword': performance_result.get('header_keyword', ''),
                        'footer_keyword': performance_result.get('footer_keyword', ''),
                        'file_url': file_info.get('file_url', ''),
                        'status': 'success'
                    }
                    self.logger.info(f"{ranking} 业绩内容筛选成功")
                else:
                    results[ranking] = {
                        'original_content': content,
                        'performance_content': '',
                        'performance_variable_name': f"{ranking}业绩源文件",
                        'status': 'failed',
                        'error': '业绩数据验证失败'
                    }
                    self.logger.warning(f"{ranking} 业绩内容筛选失败")
            
            self.logger.info(f"批量处理完成，成功处理 {len([r for r in results.values() if r.get('status') == 'success'])} 个文件")
            return results
            
        except Exception as e:
            self.logger.error(f"批量处理文件失败: {e}")
            return {}
