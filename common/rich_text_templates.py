# 富文本模板管理器
# 这个文件用于管理评标报告的富文本模板
# 根据template_id获取对应的模板内容，并渲染生成最终报告
# 具体实现由相关同事完成

import sys
import os
# 添加项目根目录到Python路径（必须在导入其他模块之前）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import re
import html
from typing import Dict, Any, Optional
from jinja2 import Template

from templates.engineering_report import ENGINEERING_EVALUATION_REPORT_TEMPLATES
from templates.goods_report import GOODS_EVALUATION_REPORT_TEMPLATES
from templates.service_report import SERVICE_EVALUATION_REPORT_TEMPLATES
# 导入数据库函数
from database.data_process import get_template_type_by_id,get_variables_values_by_id

# 配置日志
logger = logging.getLogger(__name__)

class RichTextTemplateManager:
    """富文本模板管理器类 - 负责获取和渲染评标报告模板"""
    
    def __init__(self):
        """初始化富文本模板管理器"""
        self.engineer_templates = ENGINEERING_EVALUATION_REPORT_TEMPLATES
        self.goods_templates = GOODS_EVALUATION_REPORT_TEMPLATES
        self.service_templates = SERVICE_EVALUATION_REPORT_TEMPLATES

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定模板ID的富文本模板
        1.根据模版id，从数据库中获取对应模版的类型
        2.再根据类型去获取templates下的对应模版内容
        
        Args:
            template_id: 模板ID
                - "1": 工程项目评标报告模板
                - "2": 货物项目评标报告模板  
                - "3": 服务项目评标报告模板
            
        Returns:
            Optional[Dict[str, Any]]: 模板信息，如果不存在返回None
        """
        try:
            # 根据模版id，从数据库中获取对应模版的类型 (已注释用于测试)
            template_type = get_template_type_by_id(template_id)
            if not template_type:
                logger.warning(f"未找到模板ID为 {template_id} 的模板")
                return None
            
            # 根据类型去获取templates下的对应模版内容
            if template_type == "工程":
                template_content = self.engineer_templates
            elif template_type == "货物":
                template_content = self.goods_templates
            elif template_type == "服务":
                template_content = self.service_templates
            else:
                logger.warning(f"未找到类型为 {template_type} 的模板内容")
                return None
            
            # 直接提取模板字符串内容
            actual_template = ""
            if isinstance(template_content, dict) and "评标报告" in template_content:
                report_template = template_content["评标报告"]
                if isinstance(report_template, dict) and "template" in report_template:
                    actual_template = report_template["template"]
            
            return {
                "template_id": template_id,
                "type": template_type,
                "content": actual_template
            }
            
        except Exception as e:
            logger.error(f"获取模板失败: {e}")
            return None
    
    async def render_template(self, template_info: Dict[str, Any], data: Dict[str, Any]) -> str:
        """
        渲染富文本模板
        
        Args:
            template_info: 模板信息，包含template_id和content
            data: 已处理好的变量数据字典
            
        Returns:
            str: 渲染后的富文本内容
        """
        try:
            # 获取模板内容
            template_content = template_info.get("content", {})
            if not template_content:
                logger.error("模板内容为空")
                return ""
            
            # 获取模板字符串（现在content直接就是模板字符串）
            template_string = str(template_content) if template_content else ""
            
            if not template_string:
                logger.error("模板字符串为空")
                return ""
            
            # 使用传入的已处理好的变量数据（已经过预处理）
            variables_data = data if data is not None else {}
            
            # 渲染模板（变量已在保存到数据库前进行了预处理）
            rendered_content = self.render_template_string(template_string, variables_data)
            
            logger.info(f"模板渲染完成，内容长度: {len(rendered_content)}")
            return rendered_content
            
        except Exception as e:
            logger.error(f"渲染模板失败: {e}")
            return f"模板渲染失败: {str(e)}"
    
    def render_template_string(self, template_string: str, variables_data: Dict[str, Any]) -> str:
        """
        渲染模板字符串，将变量占位符替换为实际值
        
        Args:
            template_string: 模板字符串
            variables_data: 变量数据字典
            
        Returns:
            str: 渲染后的内容
        """
        
        # 添加生成日期变量
        from datetime import datetime
        current_date = datetime.now()
        formatted_date = current_date.strftime("%Y年%m月%d日")
        variables_data["生成日期"] = formatted_date
        
        try:
            # 第一步：将简单的 {变量名} 格式转换为Jinja2语法 {{变量名}}
            # 但需要小心处理，避免与现有的Jinja2语法冲突
            
            # 先保护现有的Jinja2语法
            jinja_placeholders = {}
            placeholder_counter = 0
            
            def protect_jinja(match):
                nonlocal placeholder_counter
                placeholder = f"__JINJA_PLACEHOLDER_{placeholder_counter}__"
                jinja_placeholders[placeholder] = match.group(0)
                placeholder_counter += 1
                return placeholder
            
            # 保护现有的Jinja2变量和标签
            template = re.sub(r'\{\{[^}]*\}\}', protect_jinja, template_string)
            template = re.sub(r'\{%[^%]*%\}', protect_jinja, template)
            
            # 现在转换简单的 {变量名} 格式
            def convert_variable(match):
                var_name = match.group(1).strip()
                # 直接使用变量名，Jinja2会自动查找对应的变量
                return f'{{{{ {var_name} }}}}'
            
            template = re.sub(r'\{([^{}%]+)\}', convert_variable, template)
            
            # 恢复被保护的Jinja2语法
            for placeholder, original in jinja_placeholders.items():
                template = template.replace(placeholder, original)
            
            # 第二步：准备渲染变量，添加高亮样式
            variables_for_render = {}
            highlight_color_recognized = "rgb(192,192,192)"  # 灰色背景
            highlight_color_missing = "rgb(255,255,0)"       # 黄色背景
            
            # 需要保持原始值进行条件判断的变量列表
            conditional_variables = {
                "开标记录表格", "否决投标情况说明", "评审结果", 
                "中标候选人得分汇总情况", "中标候选人资质和资格业绩等评审情况", 
                "中标候选人详细评审客观分得分情况", "招标内容及范围", "推荐中标候选人数", "推荐中标候选人名称",
                "项目名称", "招标编号", "标段号", "招标人", "招标代理", "生成日期",
                "中标候选人资质资格业绩等评审情况表格", "中标候选人详细评审客观分得分情况表格"
            }
            
            # 表格类型变量列表（需要特殊处理表格标灰）
            table_variables = {
                "开标记录表格", "评审结果", "中标候选人得分汇总情况", 
                "中标候选人详细评审客观分得分情况", "否决投标情况说明"
            }
            
            # 混合内容变量列表（既有文本也有表格，需要特殊处理换行和边框）
            mixed_content_variables = {
                "招标内容及范围"
            }
            
            for var_name, var_value in variables_data.items():
                # 对于需要条件判断的变量，保持原始值不做任何处理
                if var_name in conditional_variables:
                    # 为表格变量添加边框样式和标灰效果
                    if var_value and isinstance(var_value, str) and var_value.strip():
                        # 检查是否为混合内容变量（既有文本也有表格）
                        if var_name in mixed_content_variables:
                            # 混合内容变量：文本部分处理换行，表格部分添加边框
                            variables_for_render[var_name] = self._add_table_highlight_and_border(var_value, var_name, variables_data)
                        # 检查是否为表格类型变量
                        elif var_name in table_variables:
                            # 为表格类型变量只添加边框样式，不添加div包装
                            variables_for_render[var_name] = self._add_table_border_style(var_value, var_name, variables_data)
                        else:
                            # 非表格类型变量，只添加边框样式
                            variables_for_render[var_name] = self._add_table_border_style(var_value, var_name, variables_data)
                    else:
                        variables_for_render[var_name] = var_value
                else:
                    # 其他变量进行正常的高亮处理
                    if var_value is None or var_value == "":
                        # 空值显示为黄色背景
                        variables_for_render[var_name] = f'<span id="{var_name}" style="background-color: {highlight_color_missing}; font-family: 宋体;">______</span>'
                    else:
                        # 非空值添加灰色背景高亮
                        value_str = str(var_value)
                        
                        # 检查是否包含HTML表格标签，如果包含则不进行HTML转义
                        if '<table' in value_str.lower() or '<tr' in value_str.lower() or '<td' in value_str.lower():
                            # 包含HTML表格，不进行转义，只处理换行符
                            safe_value = value_str.replace('\n', '<br>')
                        else:
                            # 普通文本，进行HTML转义
                            safe_value = html.escape(value_str)
                            safe_value = safe_value.replace('\n', '<br>')
                        
                        variables_for_render[var_name] = f'<span id="{var_name}" style="background-color: {highlight_color_recognized}; font-family: 宋体;">{safe_value}</span>'
            
            # 第三步：使用Jinja2渲染模板
            jinja_template = Template(template)
            rendered_content = jinja_template.render(variables_for_render)
            
            return rendered_content
            
        except Exception as e:
            logger.error(f"Jinja2模板渲染失败: {e}")
            # 如果Jinja2渲染失败，回退到简单的字符串替换
            try:
                # 添加生成日期变量
                from datetime import datetime
                current_date = datetime.now()
                formatted_date = current_date.strftime("%Y年%m月%d日")
                variables_data["生成日期"] = formatted_date
                
                # 先处理Jinja2语法标签，移除注释和条件判断
                template = template_string
                
                # 移除Jinja2注释 {% comment %}...{% endcomment %}
                template = re.sub(r'\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}', '', template, flags=re.DOTALL)
                
                # 处理条件判断 {% if condition %}...{% else %}...{% endif %}
                def process_conditional(match):
                    full_match = match.group(0)
                    condition = match.group(1).strip()
                    
                    # 提取if和else部分的内容
                    if_content = match.group(2) if match.group(2) else ""
                    else_content = match.group(3) if match.group(3) else ""
                    
                    # 解析条件：检查变量是否为空
                    # 例如：开标记录表格 is none or 开标记录表格 == "" or 开标记录表格 == "______"
                    var_name = ""
                    if " is none or " in condition and " == \"\"" in condition and " == \"______\"" in condition:
                        var_name = condition.split(" is none")[0].strip()
                    elif " is none or " in condition:
                        var_name = condition.split(" is none")[0].strip()
                    elif " == \"\"" in condition:
                        var_name = condition.split(" == \"\"")[0].strip()
                    elif " == \"______\"" in condition:
                        var_name = condition.split(" == \"______\"")[0].strip()
                    
                    # 检查变量值
                    if var_name in variables_data:
                        var_value = variables_data[var_name]
                        # 判断是否为空
                        if var_value is None or var_value == "" or var_value == "______":
                            return if_content  # 使用if部分（通常是默认表格）
                        else:
                            return else_content  # 使用else部分（通常是实际数据）
                    else:
                        return if_content  # 变量不存在，使用默认表格
                
                # 匹配条件判断块
                conditional_pattern = r'\{%\s*if\s+([^%]+)\s*%\}\s*(.*?)\s*\{%\s*else\s*%\}\s*(.*?)\s*\{%\s*endif\s*%\}'
                template = re.sub(conditional_pattern, process_conditional, template, flags=re.DOTALL)
                
                # 处理简单的变量替换 {变量名}
                pattern = r'(?<!\{)\{([^{}%]+)\}(?!\})'
                
                # 需要保持原始值进行条件判断的变量列表
                conditional_variables = {
                    "开标记录表格", "否决投标情况说明", "评审结果", 
                    "中标候选人得分汇总情况", "中标候选人资质和资格业绩等评审情况", 
                    "中标候选人详细评审客观分得分情况", "招标内容及范围", "推荐中标候选人数", "推荐中标候选人名称",
                    "项目名称", "招标编号", "标段号", "招标人", "招标代理", "生成日期"
                }
                
                # 表格类型变量列表（需要特殊处理表格标灰）
                table_variables = {
                    "开标记录表格", "评审结果", "中标候选人得分汇总情况", 
                    "中标候选人详细评审客观分得分情况", "否决投标情况说明"
                }
                
                # 混合内容变量列表（既有文本也有表格，需要特殊处理换行和边框）
                mixed_content_variables = {
                    "招标内容及范围"
                }
                
                def replace_variable(match):
                    variable_name = match.group(1).strip()
                    variable_value = variables_data.get(variable_name, "")
                    
                    # 对于需要条件判断的变量，为表格添加边框样式和标灰效果
                    if variable_name in conditional_variables:
                        if variable_value and isinstance(variable_value, str) and variable_value.strip():
                            # 检查是否为混合内容变量（既有文本也有表格）
                            if variable_name in mixed_content_variables:
                                # 混合内容变量：文本部分处理换行，表格部分添加边框
                                return self._add_table_highlight_and_border(variable_value, variable_name, variables_data)
                            # 检查是否为表格类型变量
                            elif variable_name in table_variables:
                                # 为表格类型变量只添加边框样式，不添加div包装
                                return self._add_table_border_style(variable_value, variable_name, variables_data)
                            else:
                                # 非表格类型变量，只添加边框样式
                                return self._add_table_border_style(variable_value, variable_name, variables_data)
                        else:
                            return str(variable_value) if variable_value is not None else ""
                    
                    if variable_value is None or variable_value == "":
                        return f'<span id="{variable_name}" style="background-color: rgb(255,255,0); font-family: 宋体;">______</span>'
                    
                    value_str = str(variable_value)
                    safe_value = html.escape(value_str)
                    safe_value = safe_value.replace('\n', '<br>')
                    return f'<span id="{variable_name}" style="background-color: rgb(192,192,192); font-family: 宋体;">{safe_value}</span>'
                
                rendered_content = re.sub(pattern, replace_variable, template)
                return rendered_content
                
            except Exception as fallback_error:
                logger.error(f"回退渲染也失败: {fallback_error}")
                return template_string
    
    def _add_table_highlight_and_border(self, content: str, content_type: str = None, variables_data: dict = None) -> str:
        """
        为表格内容添加标灰效果和边框样式，支持混合内容（文本+表格）
        
        Args:
            content: 原始内容（可能包含文本和表格）
            content_type: 内容类型，用于特殊处理（同时也是变量名称）
            variables_data: 变量数据，用于渲染特殊内容
            
        Returns:
            str: 添加了标灰效果和边框样式的内容
        """
        try:
            # 检查内容是否包含表格
            if '<table' in content.lower():
                # 处理混合内容：分离文本和表格部分
                import re
                
                # 分割内容为文本和表格部分
                parts = re.split(r'(<table[^>]*>.*?</table>)', content, flags=re.DOTALL | re.IGNORECASE)
                
                processed_parts = []
                is_first_part = True
                
                for i, part in enumerate(parts):
                    if part.strip():
                        if part.strip().startswith('<table'):
                            # 这是表格部分
                            # 特殊处理：如果是【招标内容及范围】变量，需要处理p标签
                            if content_type == "招标内容及范围":
                                # 表格前：关闭p标签
                                processed_parts.append('</p>')
                            
                            # 添加边框样式
                            processed_table = self._add_table_border_style(part, content_type, variables_data)
                            processed_parts.append(processed_table)
                            
                            # 特殊处理：如果是【招标内容及范围】变量，表格后需要重新开启p标签
                            # 无论后面是否有内容，都要开启p标签，以便与模板中的</p>配对
                            if content_type == "招标内容及范围":
                                processed_parts.append('<p style="text-indent:2em;">')
                            
                            is_first_part = False
                        else:
                            # 这是文本部分，添加标灰背景和宋体字体，并添加id
                            safe_text = html.escape(part)
                            safe_text = safe_text.replace('\n', '<br>')
                            id_attr = f'id="{content_type}"' if content_type else ''
                            processed_text = f'<span {id_attr} style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{safe_text}</span>'
                            processed_parts.append(processed_text)
                            is_first_part = False
                
                return ''.join(processed_parts)
            else:
                # 纯文本内容，添加标灰背景和宋体字体，并添加id
                safe_content = html.escape(content)
                safe_content = safe_content.replace('\n', '<br>')
                id_attr = f'id="{content_type}"' if content_type else ''
                return f'<span {id_attr} style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{safe_content}</span>'
                
        except Exception as e:
            logger.error(f"添加表格标灰效果失败: {e}")
            return content

    def _add_table_border_style(self, table_content: str, table_type: str = None, variables_data: dict = None) -> str:
        """
        为表格内容添加边框样式，严格按照模板样式
        只添加模板中存在的样式，不添加任何额外样式
        并为td单元格内的文本内容添加灰色背景标记和id属性
        
        Args:
            table_content: 原始表格HTML内容
            table_type: 表格类型，用于特殊处理（同时也是变量名称，用于生成id）
            variables_data: 变量数据，用于渲染特殊内容
            
        Returns:
            str: 添加了边框样式和文本标灰的表格HTML
        """
        try:
            # 检查是否已经是带样式的表格
            if 'style=' in table_content and 'border:' in table_content:
                return table_content
            
            # 严格按照模板样式：为table标签添加样式（不包括背景色）
            table_style = 'style="width: 100%; table-layout: fixed; border-collapse: collapse; margin: 0;"'
            if '<table>' in table_content:
                table_content = table_content.replace('<table>', f'<table {table_style}>')
            elif '<table ' in table_content and 'style=' not in table_content:
                # 如果table标签已有其他属性但没有style
                table_content = table_content.replace('<table ', f'<table {table_style} ')
            
            # 严格按照模板样式：为td标签添加边框样式，并为td内的文本内容添加灰色背景和id
            import re
            
            # 处理td标签及其内容
            def replace_td_with_content(match):
                full_td = match.group(0)  # 完整的<td>...</td>
                td_opening = match.group(1)  # <td ...>
                td_content = match.group(2)  # td内的内容
                
                # 为td标签添加边框样式
                if 'style=' in td_opening:
                    # 如果已有style属性，只添加模板中存在的边框样式
                    if 'border:' not in td_opening:
                        td_opening = td_opening.replace('style="', 'style="border: 1px solid #000; padding: 8px; text-align: center; ')
                else:
                    # 如果没有style属性，添加完整的模板样式
                    td_opening = td_opening.replace('<td', '<td style="border: 1px solid #000; padding: 8px; text-align: center;"')
                
                # 为td内的文本内容添加灰色背景（如果内容不为空且不是已经包含span标签）
                if td_content and td_content.strip():
                    # 检查是否已经包含背景色span标签
                    if 'background-color:' not in td_content:
                        # 为文本内容添加灰色背景、宋体字体和id属性
                        id_attr = f'id="{table_type}"' if table_type else ''
                        td_content = f'<span {id_attr} style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">{td_content}</span>'
                
                return f'{td_opening}{td_content}</td>'
            
            # 匹配<td...>内容</td>模式
            table_content = re.sub(r'(<td[^>]*>)(.*?)</td>', replace_td_with_content, table_content, flags=re.DOTALL)

            # 额外需求：将第一行<tr>内的单元格内容加粗（<strong>）
            try:
                def _bold_first_row(match):
                    tr_open = match.group(1)
                    tr_inner = match.group(2)
                    tr_close = match.group(3)

                    def _wrap_td(m):
                        td_open = m.group(1)
                        td_inner = m.group(2)
                        td_close = m.group(3)
                        # strong 必须位于 span 内部
                        # 如果已有 span，优先在 span 内部包裹 strong
                        span_match = re.search(r'(<span[^>]*>)(.*?)(</span>)', td_inner, flags=re.IGNORECASE | re.DOTALL)
                        if span_match:
                            span_open = span_match.group(1)
                            span_content = span_match.group(2)
                            span_close = span_match.group(3)
                            # 如果 span 内容内已经有 strong，则不重复包裹
                            if re.search(r'<strong>.*?</strong>', span_content, flags=re.IGNORECASE | re.DOTALL):
                                new_span = f'{span_open}{span_content}{span_close}'
                            else:
                                new_span = f'{span_open}<strong>{span_content}</strong>{span_close}'
                            # 用处理后的 span 替换原 td_inner 中的该 span 片段
                            new_inner = td_inner[:span_match.start()] + new_span + td_inner[span_match.end():]
                        else:
                            # 没有 span，则创建包含样式的 span 并将 strong 放入其中
                            new_inner = f'<span style="font-family: 宋体; font-size: 14px; background-color: rgb(192,192,192);"><strong>{td_inner}</strong></span>'
                        return f'{td_open}{new_inner}{td_close}'

                    # 仅处理第一行中的<td>
                    tr_inner_bold = re.sub(r'(<td[^>]*>)(.*?)(</td>)', _wrap_td, tr_inner, flags=re.DOTALL)
                    return f'{tr_open}{tr_inner_bold}{tr_close}'

                # 只对第一个<tr>应用一次
                table_content = re.sub(r'(<tr[^>]*>)(.*?)(</tr>)', _bold_first_row, table_content, count=1, flags=re.DOTALL)
            except Exception:
                pass
            
            # 特殊处理：开标记录表格需要添加最高投标限价行
            if table_type == "开标记录表格":
                table_content = self._add_highest_bid_limit_row(table_content, variables_data, table_type)
            
            return table_content
            
        except Exception as e:
            logger.error(f"添加表格边框样式失败: {e}")
            return table_content
    
    def _add_highest_bid_limit_row(self, table_content: str, variables_data: dict = None, table_type: str = None) -> str:
        """
        为开标记录表格添加最高投标限价行
        
        Args:
            table_content: 表格HTML内容
            variables_data: 变量数据
            table_type: 表格类型（不使用，保留参数兼容性）
            
        Returns:
            str: 添加了最高投标限价行的表格HTML
        """
        try:
            # 获取最高投标限价值
            highest_bid_limit = ""
            if variables_data and "最高投标限价" in variables_data:
                highest_bid_limit = variables_data["最高投标限价"]
                if not highest_bid_limit or highest_bid_limit.strip() == "":
                    highest_bid_limit = "______"
            else:
                highest_bid_limit = "______"
            
            # 动态计算表格列数
            import re
            # 查找第一个tr标签中的td数量来确定列数
            first_tr_match = re.search(r'<tr[^>]*>(.*?)</tr>', table_content, re.DOTALL)
            if first_tr_match:
                first_tr_content = first_tr_match.group(1)
                # 计算td标签数量（包括有colspan的td）
                td_matches = re.findall(r'<td[^>]*>', first_tr_content)
                total_columns = 0
                for td_match in td_matches:
                    # 检查是否有colspan属性
                    colspan_match = re.search(r'colspan="(\d+)"', td_match)
                    if colspan_match:
                        total_columns += int(colspan_match.group(1))
                    else:
                        total_columns += 1
            else:
                # 如果找不到tr，默认使用5列
                total_columns = 5
            
            # 计算剩余列数
            remaining_columns = total_columns - 2
            
            # 判断是否需要添加黄色背景（未识别的值）
            if highest_bid_limit == "______":
                highlight_style = 'background-color: rgb(255,255,0); font-family: 宋体;'
            else:
                highlight_style = 'background-color: rgb(192,192,192); font-family: 宋体;'
            
            # 最高投标限价是独立变量，使用自己的变量名作为id
            id_attr = 'id="最高投标限价"'
            
            # 构建最高投标限价行，严格按照模板样式（在td内容外包裹span标签，并添加id）
            highest_bid_row = f'''
    <tr>
        <td style="border: 1px solid #000; padding: 8px; text-align: center;" colspan="2"><span id="最高投标限价" style="background-color: rgb(192,192,192); font-family: 宋体; font-size: 14px;">最高投标限价</span></td>
        <td style="border: 1px solid #000; padding: 8px; text-align: center;" colspan="{remaining_columns}"><span {id_attr} style="{highlight_style} font-size: 14px;">{highest_bid_limit}</span></td>
    </tr>'''
            
            # 在</table>标签前插入最高投标限价行
            table_content = table_content.replace('</table>', f'{highest_bid_row}\n</table>')
            
            return table_content
            
        except Exception as e:
            logger.error(f"添加最高投标限价行失败: {e}")
            return table_content


if __name__ == "__main__":
    rich_text_template_manager = RichTextTemplateManager()
    template_info = rich_text_template_manager.get_template("2")
    # print(template_info)
    data = get_variables_values_by_id("451111111111333105")
    final_result = rich_text_template_manager.render_template(template_info, data)
    #保存为html文件
    with open("final_result.html", "w", encoding="utf-8") as f:
        f.write(final_result)
