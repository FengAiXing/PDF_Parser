"""
资质部分内容筛选模块

本模块用于从投标文件中筛选和提取资质相关的内容。
主要功能包括：
- 识别资质相关表格和文档
- 提取资质证书信息
- 过滤和整理资质数据
"""

import logging
import re
from typing import Dict, List, Any, Optional, Union

logger = logging.getLogger(__name__)


class QualificationContentFilter:
    """资质内容筛选器"""
    
    def __init__(self):
        """初始化筛选器"""
        self.logger = logger
    
    def filter_qualification_content(self, content: str, ranking: str = "") -> Dict[str, Any]:
        """
        筛选资质相关内容
        
        Args:
            content: 投标文件内容（应该是已移除业绩部分的文件）
            ranking: 排名信息（如"第一名"、"第二名"等）
            
        Returns:
            Dict[str, Any]: 筛选后的资质内容
        """
        try:
            # 定义头部关键词
            header_keywords = [
                '基本情况表'
            ]
            
            # 定义尾部关键词（业绩相关关键词）
            footer_keywords = [
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
                self.logger.warning(f"未找到资质相关头部关键词")
                return {
                    'original_content': content,
                    'qualification_content': '',
                    'qualification_variable_name': f"{ranking}资质源文件" if ranking else "资质源文件",
                    'extraction_success': False,
                    'error_message': '未找到资质相关头部关键词'
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
                self.logger.warning(f"未找到资质相关尾部关键词")
                return {
                    'original_content': content,
                    'qualification_content': '',
                    'qualification_variable_name': f"{ranking}资质源文件" if ranking else "资质源文件",
                    'extraction_success': False,
                    'error_message': '未找到资质相关尾部关键词'
                }
            
            # 计算实际位置（相对于原内容的绝对位置）
            footer_start_pos = header_match.end() + footer_match.start()
            footer_end_pos = header_match.end() + footer_match.end()
            
            # 截取资质部分内容
            qualification_content = content[header_match.start():footer_end_pos]
            
            # 构建新的原文件内容（保留关键词，移除中间内容）
            before_qualification = content[:header_match.start()]
            after_qualification = content[footer_start_pos:]
            cleaned_content = before_qualification + header_keyword + footer_keyword + after_qualification
            
            # 生成资质变量名称
            qualification_variable_name = f"{ranking}资质源文件" if ranking else "资质源文件"
            
            self.logger.info(f"成功截取资质内容，头部关键词: {header_keyword}, 尾部关键词: {footer_keyword}")
            self.logger.info(f"资质内容长度: {len(qualification_content)}, 清理后内容长度: {len(cleaned_content)}")
            
            return {
                'original_content': cleaned_content,
                'qualification_content': qualification_content,
                'qualification_variable_name': qualification_variable_name,
                'header_keyword': header_keyword,
                'footer_keyword': footer_keyword,
                'extraction_success': True,
                'error_message': ''
            }
            
        except Exception as e:
            self.logger.error(f"筛选资质内容失败: {e}")
            return {
                'original_content': content,
                'qualification_content': '',
                'qualification_variable_name': f"{ranking}资质源文件" if ranking else "资质源文件",
                'extraction_success': False,
                'error_message': f'筛选资质内容失败: {e}'
            }
    
    def extract_qualification_certificates(self, content: str) -> List[Dict[str, Any]]:
        """
        提取资质证书信息
        
        Args:
            content: 投标文件内容
            
        Returns:
            List[Dict[str, Any]]: 资质证书列表
        """
        try:
            # 从资质内容中提取证书信息
            qualification_result = self.filter_qualification_content(content)
            qualification_content = qualification_result.get('qualification_content', '')
            
            if not qualification_content:
                return []
            
            # 查找证书相关关键词
            certificate_keywords = [
                '营业执照', '资质证书', '安全生产许可证', '质量管理体系认证',
                '环境管理体系认证', '职业健康安全管理体系认证', 'ISO认证',
                '三体系认证', '资质等级', '证书编号', '有效期'
            ]
            
            certificates = []
            for keyword in certificate_keywords:
                # 查找包含该关键词的段落
                pattern = rf'.*{re.escape(keyword)}.*'
                matches = re.findall(pattern, qualification_content, re.DOTALL | re.IGNORECASE)
                
                for match in matches:
                    # 清理匹配内容
                    cleaned_match = re.sub(r'\s+', ' ', match.strip())
                    if len(cleaned_match) > 10:  # 过滤太短的内容
                        certificates.append({
                            'keyword': keyword,
                            'content': cleaned_match,
                            'content_length': len(cleaned_match)
                        })
            
            self.logger.info(f"从资质内容中提取到 {len(certificates)} 个证书信息")
            return certificates
            
        except Exception as e:
            self.logger.error(f"提取资质证书失败: {e}")
            return []
    
    def validate_qualification_data(self, qualification_data: Dict[str, Any]) -> bool:
        """
        验证资质数据的有效性
        
        Args:
            qualification_data: 资质数据
            
        Returns:
            bool: 数据是否有效
        """
        try:
            # 检查必要字段
            required_fields = ['original_content', 'qualification_content', 'qualification_variable_name']
            for field in required_fields:
                if field not in qualification_data:
                    self.logger.warning(f"资质数据缺少必要字段: {field}")
                    return False
            
            # 检查资质内容是否为空
            qualification_content = qualification_data.get('qualification_content', '')
            if not qualification_content or len(qualification_content.strip()) == 0:
                self.logger.warning("资质内容为空")
                return False
            
            # 检查资质内容长度是否合理（至少包含一些内容）
            if len(qualification_content) < 50:
                self.logger.warning(f"资质内容过短: {len(qualification_content)} 字符")
                return False
            
            # 检查是否包含资质相关关键词
            qualification_keywords = ['基本情况', '营业执照', '资质', '证书', '认证', '许可证']
            has_qualification_content = any(keyword in qualification_content for keyword in qualification_keywords)
            
            if not has_qualification_content:
                self.logger.warning("资质内容中未发现资质相关信息")
                return False
            
            self.logger.info("资质数据验证通过")
            return True
            
        except Exception as e:
            self.logger.error(f"验证资质数据失败: {e}")
            return False
    
    def process_multiple_files(self, files_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        批量处理多个文件的资质内容筛选
        
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
                
                # 筛选资质内容
                qualification_result = self.filter_qualification_content(content, ranking)
                
                # 验证结果
                if self.validate_qualification_data(qualification_result):
                    results[ranking] = {
                        'original_content': qualification_result['original_content'],
                        'qualification_content': qualification_result['qualification_content'],
                        'qualification_variable_name': qualification_result['qualification_variable_name'],
                        'header_keyword': qualification_result.get('header_keyword', ''),
                        'footer_keyword': qualification_result.get('footer_keyword', ''),
                        'file_url': file_info.get('file_url', ''),
                        'status': 'success'
                    }
                    self.logger.info(f"{ranking} 资质内容筛选成功")
                else:
                    results[ranking] = {
                        'original_content': content,
                        'qualification_content': '',
                        'qualification_variable_name': f"{ranking}资质源文件",
                        'status': 'failed',
                        'error': '资质数据验证失败'
                    }
                    self.logger.warning(f"{ranking} 资质内容筛选失败")
            
            self.logger.info(f"批量处理完成，成功处理 {len([r for r in results.values() if r.get('status') == 'success'])} 个文件")
            return results
            
        except Exception as e:
            self.logger.error(f"批量处理文件失败: {e}")
            return {}
