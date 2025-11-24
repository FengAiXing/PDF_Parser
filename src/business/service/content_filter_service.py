# 内容截取服务
import logging
import asyncio
from typing import Dict, List, Any, Optional
from src.utils.file_range_filter.performance_content_filter import PerformanceContentFilter
from src.utils.file_range_filter.qualification_content_filter import QualificationContentFilter
from src.utils.file_range_filter.resume_table_content_filter import ResumeTableContentFilter
from src.utils.bid_file_processor import BidFileProcessor

logger = logging.getLogger(__name__)


class ContentFilterService:
    """内容截取服务类"""
    
    def __init__(self):
        """初始化服务"""
        self.performance_filter = PerformanceContentFilter()
        self.qualification_filter = QualificationContentFilter()
        self.resume_table_filter = ResumeTableContentFilter()
        self.bid_file_processor = BidFileProcessor()
    
    async def filter_ranked_files_content(self, ranked_files: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        对重命名为有排名的文件进行内容截取处理
        
        Args:
            ranked_files: 重命名后的文件字典，格式为 {"第一名": {content, file_url, ...}, "第二名": {...}}
            
        Returns:
            Dict[str, Dict[str, Any]]: 处理后的文件字典，包含截取的内容
        """
        try:
            logger.info(f"开始对 {len(ranked_files)} 个排名文件进行内容截取处理")
            
            processed_files = {}
            
            # 第一步：先截取所有文件的业绩内容（串行处理，因为这是同步操作）
            performance_texts = {}  # 用于批量并发提取业绩表格
            
            for ranking, file_info in ranked_files.items():
                logger.info(f"开始处理 {ranking} 的文件内容截取")
                
                # 获取文件内容
                content = file_info.get('content', '')
                if not content:
                    logger.warning(f"{ranking} 文件内容为空，跳过处理")
                    processed_files[ranking] = file_info
                    continue
                
                # 创建处理结果字典
                processed_file = file_info.copy()
                
                # 第一步：截取业绩内容
                logger.info(f"开始截取 {ranking} 的业绩内容")
                performance_result = self.performance_filter.filter_performance_content(content, ranking)
                
                if performance_result.get('extraction_success', False):
                    processed_file['performance_content'] = performance_result['performance_content']
                    processed_file['performance_variable_name'] = performance_result['performance_variable_name']
                    processed_file['performance_header_keyword'] = performance_result.get('header_keyword', '')
                    processed_file['performance_footer_keyword'] = performance_result.get('footer_keyword', '')
                    logger.info(f"✓ {ranking} 业绩内容截取成功，长度: {len(performance_result['performance_content'])} 字符")
                    
                    # 收集业绩文本，准备批量并发提取
                    performance_texts[ranking] = performance_result['performance_content']
                else:
                    processed_file['performance_content'] = ''
                    processed_file['performance_variable_name'] = f"{ranking}业绩源文件"
                    processed_file['performance_error'] = performance_result.get('error_message', '业绩内容截取失败')
                    processed_file['performance_summary_table'] = {'variable_name': f"{ranking}业绩汇总表", 'table_content': ''}
                    processed_file['individual_performances'] = []
                    logger.warning(f"✗ {ranking} 业绩内容截取失败: {performance_result.get('error_message', '未知错误')}")
                
                # 使用业绩截取后的清理内容进行后续处理
                current_content = performance_result.get('original_content', content)
                
                # 第二步：截取资质内容
                logger.info(f"开始截取 {ranking} 的资质内容")
                qualification_result = self.qualification_filter.filter_qualification_content(current_content, ranking)
                
                if qualification_result.get('extraction_success', False):
                    processed_file['qualification_content'] = qualification_result['qualification_content']
                    processed_file['qualification_variable_name'] = qualification_result['qualification_variable_name']
                    processed_file['qualification_header_keyword'] = qualification_result.get('header_keyword', '')
                    processed_file['qualification_footer_keyword'] = qualification_result.get('footer_keyword', '')
                    logger.info(f"✓ {ranking} 资质内容截取成功，长度: {len(qualification_result['qualification_content'])} 字符")
                else:
                    processed_file['qualification_content'] = ''
                    processed_file['qualification_variable_name'] = f"{ranking}资质源文件"
                    processed_file['qualification_error'] = qualification_result.get('error_message', '资质内容截取失败')
                    logger.warning(f"✗ {ranking} 资质内容截取失败: {qualification_result.get('error_message', '未知错误')}")
                
                # 使用资质截取后的清理内容进行后续处理
                current_content = qualification_result.get('original_content', current_content)
                
                # 第三步：截取简历表内容
                logger.info(f"开始截取 {ranking} 的简历表内容")
                resume_table_result = self.resume_table_filter.filter_resume_table_content(current_content, ranking)
                
                if resume_table_result.get('extraction_success', False):
                    processed_file['resume_table_content'] = resume_table_result['resume_table_content']
                    processed_file['resume_table_variable_name'] = resume_table_result['resume_table_variable_name']
                    processed_file['resume_table_header_keyword'] = resume_table_result.get('header_keyword', '')
                    processed_file['resume_table_footer_keyword'] = resume_table_result.get('footer_keyword', '')
                    logger.info(f"✓ {ranking} 简历表内容截取成功，长度: {len(resume_table_result['resume_table_content'])} 字符")
                else:
                    processed_file['resume_table_content'] = ''
                    processed_file['resume_table_variable_name'] = f"{ranking}简历表源文件"
                    processed_file['resume_table_error'] = resume_table_result.get('error_message', '简历表内容截取失败')
                    logger.warning(f"✗ {ranking} 简历表内容截取失败: {resume_table_result.get('error_message', '未知错误')}")
                
                # 保存最终清理后的内容
                processed_file['filtered_content'] = resume_table_result.get('original_content', current_content)
                
                # 添加处理状态信息
                processed_file['content_filter_status'] = {
                    'performance_success': performance_result.get('extraction_success', False),
                    'qualification_success': qualification_result.get('extraction_success', False),
                    'resume_table_success': resume_table_result.get('extraction_success', False),
                    'total_extracted_sections': sum([
                        performance_result.get('extraction_success', False),
                        qualification_result.get('extraction_success', False),
                        resume_table_result.get('extraction_success', False)
                    ])
                }
                
                processed_files[ranking] = processed_file
                logger.info(f"✓ {ranking} 内容截取处理完成")
            
            # 第二步：批量并发提取所有排名的业绩表格
            if performance_texts:
                logger.info(f"开始批量并发提取 {len(performance_texts)} 个排名的业绩表格...")
                try:
                    performance_tables_results = await self.bid_file_processor.process_multiple_rankings(performance_texts)
                    
                    # 将提取结果更新到对应的文件中
                    for ranking, result in performance_tables_results.items():
                        if ranking in processed_files:
                            if result.get('success', False):
                                # 保存业绩汇总表
                                processed_files[ranking]['performance_summary_table'] = result['performance_summary_table']
                                # 保存单个业绩表
                                processed_files[ranking]['individual_performances'] = result['individual_performances']
                                logger.info(f"✓ {ranking} 业绩表格提取成功，汇总表1个，单个业绩{len(result['individual_performances'])}个")
                            else:
                                # 确保失败时也有默认值
                                if 'performance_summary_table' not in processed_files[ranking]:
                                    processed_files[ranking]['performance_summary_table'] = {'variable_name': f"{ranking}业绩汇总表", 'table_content': ''}
                                if 'individual_performances' not in processed_files[ranking]:
                                    processed_files[ranking]['individual_performances'] = []
                                logger.warning(f"✗ {ranking} 业绩表格提取失败: {result.get('error', '未知错误')}")
                except Exception as e:
                    logger.error(f"批量提取业绩表格异常: {e}")
                    # 为所有有业绩内容的文件设置默认值
                    for ranking in performance_texts.keys():
                        if ranking in processed_files:
                            if 'performance_summary_table' not in processed_files[ranking]:
                                processed_files[ranking]['performance_summary_table'] = {'variable_name': f"{ranking}业绩汇总表", 'table_content': ''}
                            if 'individual_performances' not in processed_files[ranking]:
                                processed_files[ranking]['individual_performances'] = []
            
            # 统计处理结果
            total_files = len(processed_files)
            successful_files = sum(1 for f in processed_files.values() 
                                 if f.get('content_filter_status', {}).get('total_extracted_sections', 0) > 0)
            
            logger.info(f"内容截取处理完成: 总文件数 {total_files}, 成功处理 {successful_files} 个文件")
            
            return processed_files
            
        except Exception as e:
            logger.error(f"内容截取处理失败: {e}")
            # 返回原始文件，避免中断主流程
            return ranked_files
    
    def validate_content_filter_results(self, processed_files: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        验证内容截取结果
        
        Args:
            processed_files: 处理后的文件字典
            
        Returns:
            Dict[str, Any]: 验证结果统计
        """
        try:
            validation_results = {
                'total_files': len(processed_files),
                'performance_success_count': 0,
                'qualification_success_count': 0,
                'resume_table_success_count': 0,
                'performance_tables_success_count': 0,
                'fully_successful_files': 0,
                'partially_successful_files': 0,
                'failed_files': 0,
                'details': {}
            }
            
            for ranking, file_info in processed_files.items():
                status = file_info.get('content_filter_status', {})
                
                performance_success = status.get('performance_success', False)
                qualification_success = status.get('qualification_success', False)
                resume_table_success = status.get('resume_table_success', False)
                total_sections = status.get('total_extracted_sections', 0)
                
                # 检查业绩表格提取是否成功
                performance_tables_success = False
                if performance_success and file_info.get('performance_summary_table', {}).get('table_content'):
                    performance_tables_success = True
                
                if performance_success:
                    validation_results['performance_success_count'] += 1
                if qualification_success:
                    validation_results['qualification_success_count'] += 1
                if resume_table_success:
                    validation_results['resume_table_success_count'] += 1
                if performance_tables_success:
                    validation_results['performance_tables_success_count'] += 1
                
                if total_sections == 3:
                    validation_results['fully_successful_files'] += 1
                elif total_sections > 0:
                    validation_results['partially_successful_files'] += 1
                else:
                    validation_results['failed_files'] += 1
                
                validation_results['details'][ranking] = {
                    'performance_success': performance_success,
                    'qualification_success': qualification_success,
                    'resume_table_success': resume_table_success,
                    'performance_tables_success': performance_tables_success,
                    'total_sections': total_sections
                }
            
            # logger.info(f"内容截取验证完成: {validation_results}")
            return validation_results
            
        except Exception as e:
            logger.error(f"内容截取验证失败: {e}")
            return {'error': str(e)}
    
    def get_content_summary(self, processed_files: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        获取内容截取摘要信息
        
        Args:
            processed_files: 处理后的文件字典
            
        Returns:
            Dict[str, Any]: 内容摘要
        """
        try:
            summary = {
                'total_files': len(processed_files),
                'content_types': {
                    'performance': {'count': 0, 'total_length': 0},
                    'qualification': {'count': 0, 'total_length': 0},
                    'resume_table': {'count': 0, 'total_length': 0},
                    'performance_tables': {'count': 0, 'summary_tables': 0, 'individual_tables': 0}
                },
                'file_details': {}
            }
            
            for ranking, file_info in processed_files.items():
                file_detail = {
                    'original_length': len(file_info.get('content', '')),
                    'filtered_length': len(file_info.get('filtered_content', '')),
                    'performance_length': len(file_info.get('performance_content', '')),
                    'qualification_length': len(file_info.get('qualification_content', '')),
                    'resume_table_length': len(file_info.get('resume_table_content', '')),
                    'performance_summary_table_length': len(file_info.get('performance_summary_table', {}).get('table_content', '')),
                    'individual_performances_count': len(file_info.get('individual_performances', []))
                }
                
                # 统计业绩内容
                if file_info.get('performance_content'):
                    summary['content_types']['performance']['count'] += 1
                    summary['content_types']['performance']['total_length'] += file_detail['performance_length']
                
                # 统计资质内容
                if file_info.get('qualification_content'):
                    summary['content_types']['qualification']['count'] += 1
                    summary['content_types']['qualification']['total_length'] += file_detail['qualification_length']
                
                # 统计简历表内容
                if file_info.get('resume_table_content'):
                    summary['content_types']['resume_table']['count'] += 1
                    summary['content_types']['resume_table']['total_length'] += file_detail['resume_table_length']
                
                # 统计业绩表格内容
                if file_info.get('performance_summary_table', {}).get('table_content'):
                    summary['content_types']['performance_tables']['count'] += 1
                    summary['content_types']['performance_tables']['summary_tables'] += 1
                    summary['content_types']['performance_tables']['individual_tables'] += file_detail['individual_performances_count']
                
                summary['file_details'][ranking] = file_detail
            
            # logger.info(f"内容截取摘要生成完成: {summary}")
            return summary
            
        except Exception as e:
            logger.error(f"内容截取摘要生成失败: {e}")
            return {'error': str(e)}
