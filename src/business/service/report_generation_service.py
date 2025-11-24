# 报告生成服务
import json
import logging
import re
from typing import Dict, List, Any, Optional
from common.rich_text_templates import RichTextTemplateManager
from database.data_process import save_final_report_to_database, get_variables_values_by_id


class ReportGenerationService:
    """报告生成服务类"""
    
    def __init__(self):
        """初始化服务"""
        self.rich_text_manager = RichTextTemplateManager()
    
    async def generate_final_report(
        self, 
        project_id: str,
        template_id: str
    ) -> str:
        """
        生成最终报告（从数据库读取变量数据）
        
        【重要】此方法只从数据库读取变量数据，不直接使用内存中的变量。
        确保所有变量都已保存到数据库后再调用此方法。
        
        Args:
            project_id: 项目ID
            template_id: 模板ID
            
        Returns:
            str: 最终报告内容
        """
        # 从数据库获取所有变量的数据（不从内存读取）
        logging.info(f"开始从数据库读取变量数据，项目ID: {project_id}")
        logging.info("注意：此方法只从数据库读取变量，确保所有变量已保存到数据库")
        
        variables_dict = get_variables_values_by_id(project_id)
        
        if not variables_dict:
            logging.warning(f"从数据库获取变量数据为空，项目ID: {project_id}")
            raise Exception(f"从数据库获取变量数据失败，项目ID: {project_id}")
        
        logging.info(f"从数据库成功读取 {len(variables_dict)} 个变量")
        logging.info(f"变量列表（前10个）: {list(variables_dict.keys())[:10]}")
        
        # 获取富文本模板
        template = self.rich_text_manager.get_template(template_id)
        
        # 将数据库中的变量字典转换为列表格式（用于动态表格生成）
        results_list = []
        for variable_name, variable_value in variables_dict.items():
            # 处理null值
            if variable_value is None or variable_value == "null":
                variable_value = ""
            results_list.append({
                "variable_name": variable_name,
                "variable_value": variable_value
            })
        
        logging.info(f"准备渲染模板，变量数量: {len(variables_dict)}")
        
        # 【重要】生成动态表格（从数据库读取的数据）
        self._generate_dynamic_tables(results_list, variables_dict)
        
        # 将结果拼接到模板中
        final_report = await self.rich_text_manager.render_template(template, variables_dict)
        
        # 清理多余的换行符
        final_report = self._clean_newlines(final_report)
        
        return final_report
    
    def _generate_dynamic_tables(self, results: List[Dict[str, Any]], variables_dict: Dict[str, Any]) -> None:
        """
        生成动态表格并添加到变量字典中
        
        Args:
            results: 变量列表
            variables_dict: 变量字典（会被修改）
        """
        try:
            # 检查是否有推荐中标候选人数
            candidate_count_str = variables_dict.get("推荐中标候选人数", "")
            if not candidate_count_str:
                logging.warning("未找到推荐中标候选人数，跳过动态表格生成")
                return
            
            try:
                candidate_count = int(candidate_count_str)
            except (ValueError, TypeError):
                logging.warning(f"推荐中标候选人数无效: {candidate_count_str}")
                return
            
            if candidate_count <= 0:
                logging.warning(f"推荐中标候选人数无效: {candidate_count}")
                return
            
            logging.info(f"开始生成动态表格，候选人数量: {candidate_count}")
            
            # 导入动态表格生成器
            from src.utils.preliminary_review_table import create_qualification_review_table
            from src.utils.business_score_table import create_detailed_score_table
            
            # 1. 生成资质、资格业绩等评审情况表格
            try:
                qualification_table_html = create_qualification_review_table(
                    candidate_count=candidate_count,
                    extracted_variables=results
                )
                variables_dict["中标候选人资质资格业绩等评审情况表格"] = qualification_table_html
                logging.info(f"资质评审表格生成成功，长度: {len(qualification_table_html)}")
            except Exception as e:
                logging.error(f"资质评审表格生成失败: {e}")
                variables_dict["中标候选人资质资格业绩等评审情况表格"] = ""
            
            # 2. 生成详细评审客观分得分情况表格
            # 注意：这个表格需要评审项结构，这里需要根据实际情况配置
            # 暂时使用示例结构，实际应从招标文件或其他地方提取
            try:
                # TODO: 从招标文件或评标办法中提取评审项结构
                # 暂时使用通用结构
                evaluation_structure = self._get_default_evaluation_structure()
                
                detailed_score_table_html = create_detailed_score_table(
                    candidate_count=candidate_count,
                    extracted_variables=results,
                    evaluation_structure=evaluation_structure
                )
                variables_dict["中标候选人详细评审客观分得分情况表格"] = detailed_score_table_html
                logging.info(f"详细评审表格生成成功，长度: {len(detailed_score_table_html)}")
            except Exception as e:
                logging.error(f"详细评审表格生成失败: {e}")
                variables_dict["中标候选人详细评审客观分得分情况表格"] = ""
            
        except Exception as e:
            logging.error(f"动态表格生成过程失败: {e}")
    
    def _get_default_evaluation_structure(self) -> List[Dict[str, Any]]:
        """
        获取默认的评审项结构
        
        TODO: 应该从招标文件或评标办法中动态提取
        
        Returns:
            List[Dict[str, Any]]: 评审项结构
        """
        # 动态生成业绩子项，支持最多20个业绩
        # 实际显示时，空的业绩行会被自动过滤掉
        max_performance_count = 20
        performance_items = [f'业绩{i}' for i in range(1, max_performance_count + 1)]
        
        # 通用的评审项结构
        return [
            {'供应商近年类似项目业绩': performance_items},
            {'三体系认证': ['质量管理体系', '环境管理体系', '职业健康安全管理体系']},
            {'信用评价': []},
        ]
    
    def clean_newlines(self, content: str) -> str:
        """
        完全移除内容中的所有换行符
        
        Args:
            content: 原始内容
            
        Returns:
            str: 清理后的内容（无换行符）
        """
        if not content:
            return content
            
        # 完全移除所有换行符和回车符
        content = re.sub(r'[\n\r]+', '', content)
        
        return content
    
    def _clean_newlines(self, content: str) -> str:
        """
        完全移除内容中的所有换行符
        
        Args:
            content: 原始内容
            
        Returns:
            str: 清理后的内容（无换行符）
        """
        if not content:
            return content
            
        # 完全移除所有换行符和回车符
        content = re.sub(r'[\n\r]+', '', content)
        
        return content
    
    async def save_final_report(self, project_id: str, final_report: str, template_id: str = None) -> bool:
        """
        保存最终报告到数据库
        
        Args:
            project_id: 项目ID
            final_report: 最终报告内容
            template_id: 模板ID（可选）
            
        Returns:
            bool: 保存是否成功
        """
        try:
            save_success = save_final_report_to_database(project_id, final_report, template_id)
            if not save_success:
                logging.warning(f"最终报告保存到数据库失败，项目ID: {project_id}")
                return False
            else:
                logging.info(f"最终报告已保存到数据库，项目ID: {project_id}")
                return True
        except Exception as e:
            logging.error(f"保存最终报告时发生异常: {e}")
            return False
