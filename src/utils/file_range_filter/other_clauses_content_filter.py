"""
其他条款部分内容筛选模块

本模块用于从投标文件中筛选和提取其他评审条款相关的内容。
主要功能包括：
- 识别其他条款相关文档
- 提取其他条款信息
- 过滤和整理其他条款数据
"""

import logging
import re
from typing import Dict, List, Any, Optional, Union

logger = logging.getLogger(__name__)


class OtherClausesContentFilter:
    """其他条款内容筛选器"""
    
    def __init__(self):
        """初始化筛选器"""
        self.logger = logger
    
    def filter_other_clauses_content(self, content: str, ranking: str = "") -> Dict[str, Any]:
        """
        筛选其他条款相关内容
        
        Args:
            content: 投标文件内容（应该是已移除业绩、资质、简历表部分的文件）
            ranking: 排名信息（如"第一名"、"第二名"等）
            
        Returns:
            Dict[str, Any]: 筛选后的其他条款内容
        """
        try:
            # 定义头部关键词
            header_keywords = [
                '信誉材料'
            ]
            
            # 定义尾部关键词（需要前后50字符内有'技术文件'或'技术部分'）
            footer_keywords = [
                '第三部分'
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
                self.logger.warning(f"未找到其他条款相关头部关键词")
                return {
                    'original_content': content,
                    'other_clauses_content': '',
                    'other_clauses_variable_name': f"{ranking}其他条款源文件" if ranking else "其他条款源文件",
                    'extraction_success': False,
                    'error_message': '未找到其他条款相关头部关键词'
                }
            
            # 查找尾部关键词位置 - 需要前后50字符内有'技术文件'或'技术部分'
            footer_match = None
            footer_keyword = None
            remaining_content = content[header_match.end():]
            
            # 记录所有匹配的尾部关键词及其位置
            all_footer_matches = []
            for keyword in footer_keywords:
                # 查找所有'第三部分'的位置
                pattern = re.escape(keyword)
                matches = re.finditer(pattern, remaining_content)
                third_part_count = 0
                for match in matches:
                    third_part_count += 1
                    # 先检查前后50字符内是否有'技术文件'或'技术部分'
                    start_pos_50 = max(0, match.start() - 50)
                    end_pos_50 = min(len(remaining_content), match.end() + 50)
                    context_text_50 = remaining_content[start_pos_50:end_pos_50]
                    
                    # 检查是否包含技术文件或技术部分（支持带空格的变体，如"技 术 文 件"）
                    # 使用正则表达式匹配，允许字符之间有0个或多个空格
                    tech_file_pattern = re.compile(r'技\s*术\s*文\s*件')
                    tech_part_pattern = re.compile(r'技\s*术\s*部\s*分')
                    
                    has_tech_file_50 = bool(tech_file_pattern.search(context_text_50))
                    has_tech_part_50 = bool(tech_part_pattern.search(context_text_50))
                    
                    if has_tech_file_50 or has_tech_part_50:
                        all_footer_matches.append((match.start(), match, keyword))
                        matched_text = tech_file_pattern.search(context_text_50).group(0) if has_tech_file_50 else tech_part_pattern.search(context_text_50).group(0)
                        self.logger.info(f"找到符合条件的'第三部分'（位置: {match.start()}, 前后50字符内包含'{matched_text}'）")
                    else:
                        # 如果50字符内没有，尝试扩大范围到200字符
                        start_pos_200 = max(0, match.start() - 200)
                        end_pos_200 = min(len(remaining_content), match.end() + 200)
                        context_text_200 = remaining_content[start_pos_200:end_pos_200]
                        has_tech_file_200 = bool(tech_file_pattern.search(context_text_200))
                        has_tech_part_200 = bool(tech_part_pattern.search(context_text_200))
                        
                        if has_tech_file_200 or has_tech_part_200:
                            # 找到但距离较远，仍然使用，但记录警告
                            all_footer_matches.append((match.start(), match, keyword))
                            matched_text = tech_file_pattern.search(context_text_200).group(0) if has_tech_file_200 else tech_part_pattern.search(context_text_200).group(0)
                            self.logger.warning(f"找到'第三部分'但'技术文件'/'技术部分'距离较远（位置: {match.start()}, 前后200字符内包含'{matched_text}'，将使用此位置）")
                        else:
                            # 记录未匹配的第三部分，用于调试
                            context_preview = context_text_50[:100] + "..." if len(context_text_50) > 100 else context_text_50
                            self.logger.debug(f"找到'第三部分'但前后200字符内无技术文件/技术部分（位置: {match.start()}, 上下文预览: {context_preview}）")
                
                if third_part_count > 0:
                    self.logger.info(f"在'信誉材料'之后找到 {third_part_count} 个'第三部分'，其中 {len(all_footer_matches)} 个符合条件（前后200字符内有技术文件/技术部分）")
            
            # 找到位置最靠前的尾部关键词（第一个出现的）
            if all_footer_matches:
                all_footer_matches.sort(key=lambda x: x[0])  # 按位置排序
                footer_match = all_footer_matches[0][1]
                footer_keyword = all_footer_matches[0][2]
            
            if not footer_match:
                # 增强调试信息：检查是否在"信誉材料"之前有"第三部分"
                before_header = content[:header_match.start()]
                third_part_before = list(re.finditer(re.escape('第三部分'), before_header))
                if third_part_before:
                    self.logger.warning(f"在'信誉材料'之前找到 {len(third_part_before)} 个'第三部分'，但搜索范围是'信誉材料'之后的内容")
                
                # 检查"信誉材料"之后是否有"第三部分"（不检查技术文件/技术部分）
                third_part_after = list(re.finditer(re.escape('第三部分'), remaining_content))
                if third_part_after:
                    self.logger.warning(f"在'信誉材料'之后找到 {len(third_part_after)} 个'第三部分'，但都不满足条件（前后50字符内无技术文件/技术部分）")
                    # 检查这些"第三部分"附近是否有其他相关关键词
                    for match in third_part_after[:3]:  # 只检查前3个
                        start_pos = max(0, match.start() - 100)
                        end_pos = min(len(remaining_content), match.end() + 100)
                        context_text = remaining_content[start_pos:end_pos]
                        self.logger.debug(f"'第三部分'位置 {match.start()} 前后100字符内容预览: {context_text[:200]}...")
                else:
                    self.logger.warning(f"在'信誉材料'之后未找到任何'第三部分'")
                
                self.logger.warning(f"未找到其他条款相关尾部关键词（第三部分且前后50字符内有技术文件或技术部分）")
                return {
                    'original_content': content,
                    'other_clauses_content': '',
                    'other_clauses_variable_name': f"{ranking}其他条款源文件" if ranking else "其他条款源文件",
                    'extraction_success': False,
                    'error_message': '未找到其他条款相关尾部关键词（第三部分且前后50字符内有技术文件或技术部分）'
                }
            
            # 计算实际位置（相对于原内容的绝对位置）
            footer_start_pos = header_match.end() + footer_match.start()
            footer_end_pos = header_match.end() + footer_match.end()
            
            # 截取其他条款部分内容
            other_clauses_content = content[header_match.start():footer_end_pos]
            
            # 构建新的原文件内容（保留关键词，移除中间内容）
            before_other_clauses = content[:header_match.start()]
            after_other_clauses = content[footer_start_pos:]
            cleaned_content = before_other_clauses + header_keyword + footer_keyword + after_other_clauses
            
            # 生成其他条款变量名称
            other_clauses_variable_name = f"{ranking}其他条款源文件" if ranking else "其他条款源文件"
            
            self.logger.info(f"成功截取其他条款内容，头部关键词: {header_keyword}, 尾部关键词: {footer_keyword}")
            self.logger.info(f"其他条款内容长度: {len(other_clauses_content)}, 清理后内容长度: {len(cleaned_content)}")
            
            return {
                'original_content': cleaned_content,
                'other_clauses_content': other_clauses_content,
                'other_clauses_variable_name': other_clauses_variable_name,
                'header_keyword': header_keyword,
                'footer_keyword': footer_keyword,
                'extraction_success': True,
                'error_message': ''
            }
            
        except Exception as e:
            self.logger.error(f"筛选其他条款内容失败: {e}")
            return {
                'original_content': content,
                'other_clauses_content': '',
                'other_clauses_variable_name': f"{ranking}其他条款源文件" if ranking else "其他条款源文件",
                'extraction_success': False,
                'error_message': f'筛选其他条款内容失败: {e}'
            }
    
    def validate_other_clauses_data(self, other_clauses_data: Dict[str, Any]) -> bool:
        """
        验证其他条款数据的有效性
        
        Args:
            other_clauses_data: 其他条款数据
            
        Returns:
            bool: 数据是否有效
        """
        try:
            # 检查必要字段
            required_fields = ['original_content', 'other_clauses_content', 'other_clauses_variable_name']
            for field in required_fields:
                if field not in other_clauses_data:
                    self.logger.warning(f"其他条款数据缺少必要字段: {field}")
                    return False
            
            # 检查其他条款内容是否为空
            other_clauses_content = other_clauses_data.get('other_clauses_content', '')
            if not other_clauses_content or len(other_clauses_content.strip()) == 0:
                self.logger.warning("其他条款内容为空")
                return False
            
            # 检查其他条款内容长度是否合理（至少包含一些内容）
            if len(other_clauses_content) < 50:
                self.logger.warning(f"其他条款内容过短: {len(other_clauses_content)} 字符")
                return False
            
            self.logger.info("其他条款数据验证通过")
            return True
            
        except Exception as e:
            self.logger.error(f"验证其他条款数据失败: {e}")
            return False

