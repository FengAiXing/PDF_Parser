# 提示词模板管理器 - 支持来源追踪
# 这个文件用于管理不同文件类型的AI提示词模板
# 根据文件类型和变量定义生成支持来源追踪的AI分析提示词
# 所有生成的提示词都默认包含完整的来源信息追踪功能

from typing import Dict, List, Any, Optional
import json
from common.variable_templates import VariableDefinition

class PromptTemplateManager:
    """提示词模板管理器类 - 负责生成支持来源追踪的AI分析提示词"""
    
    def __init__(self):
        """初始化提示词模板管理器 - 专注于来源追踪功能"""
        # 基础提示词模板 - 为每种文件类型定义专业的分析指导
        self._base_templates = self._initialize_base_templates()
        
        # 通用指令模板
        self._common_instructions = {
            "role": "你是一位经验丰富的评标专家，具有丰富的招投标文件分析经验。",
            "task": "请仔细分析以下招投标文件内容，准确提取所需的信息。",
            "requirements": [
                "严格按照提取规则进行信息提取",
                "保持数据的准确性和完整性", 
                "对于无法确定的信息，请留空而不是编造",
                "所有数值保持原文精度",
                "企业名称保持完整，包含公司类型后缀"
            ],
            "output_format": "请以JSON格式输出结果，字段名使用英文，严格按照下面的模板格式",
            "extraction_principles": [
                "针对性提取：每个变量都要单独、具体地提取对应的详细内容，不要提取概括性的列表或分类名称",
                "内容完整性：当找到相关章节或段落时，必须提取完整的具体内容，而不是章节标题或分类名称",
                "严格按照提取规则：当变量有明确提取规则时，严格按照其description、rules和examples进行提取",
                "空值处理：如果文档中确实没有找到对应的具体内容，则设置为空字符串或null，不要编造",
                "NaN值处理：提取的内容中如果出现'NaN'字符串，应该将其设置为空字符串，而不是保留'NaN'",
                "避免重复和混淆：不要将一个字段的内容错误地分配给多个不同的变量",
                "表格内容处理：当提取的变量涉及表格数据时，variable_value和evidence_text都使用简洁的HTML表格标签（<table><tr><td>），不添加任何边框样式，避免JSON解析错误"
            ],
            "extraction_examples": {
                "correct": "包装及运输要求: '1. 包装方式：检验合格产品采用木箱包装，阀类配件须采取防锈处理并用防尘帽、塑料袋密封；2. 标识要求：在阀体表面激光打印煤安标志、厂名、厂址、生产日期及阀类示意图；3. 运输要求：运输途中须覆盖篷布，防止雨淋、抛洒，不得超载；4. 交付地点：山西省大同市大同力泰机械有限公司厂区指定库房'",
                "incorrect": "包装及运输要求: '包装及运输要求、检验要求、其他要求'"
            },
            "professional_terms": [
                "严格保护招标专业术语，不得判定为错误",
                "招标专业术语包括但不限于：",
                "  - '招标项目编号'、'项目编号'均为正确用语",
                "  - '投标人须知前附表'为标准术语",
                "  - '招标'、'投标'、'评标'、'废标'等专业术语",
                "  - 法规名称、规范标准名称",
                "  - 标准的项目编号（各种字母+数字组合）",
                "  - 评标办法中的专业术语",
                "  - 技术规范中的专业术语",
                "  - 采购相关术语（如'采购结构'、'采购结果'均为合法用语）",
                "  - 审批表相关术语（根据实际内容可用'结构'或'结果'）",
                "语病检查：重点检查影响理解的严重语病，不应判定为语病的情况包括招标行业通用表达方式、法规引用原文、技术规范中的专业表达",
                "标点符号规范：允许多种合法的时间范围表示方式，在遵循国标的同时考虑行业特点"
            ]
        }
    
    def generate_prompt(self, file_type: str, variables: List[VariableDefinition], file_url: str = None) -> str:
        """
        生成支持来源追踪的提示词

        Args:
            file_type: 文件类型
            variables: 变量定义列表

        Returns:
            str: 生成的提示词
        """
        # 1. 获取基础模板
        base_template = self._base_templates.get(file_type, self._base_templates["default"])

        # 2. 生成变量描述文本
        variables_description = self._generate_variables_description(variables)

        # 3. 生成JSON输出模板
        json_template = self._generate_json_template(variables, file_type)

        # 4. 拼接成完整的提示词
        prompt = f"""## 一、角色定义
{self._common_instructions['role']}

## 二、任务说明
{self._common_instructions['task']}
所有信息必须严格依据文件内容，不得自行编造或补充未提及内容。

## 三、文件类型特定指导
{base_template}

## 四、关键提取原则
{chr(10).join([f"- {principle}" for principle in self._common_instructions['extraction_principles']])}

### 提取示例对比：
✅ **正确示例**：
{self._common_instructions['extraction_examples']['correct']}

❌ **错误示例**：
{self._common_instructions['extraction_examples']['incorrect']}

## 五、专业术语处理说明
{chr(10).join([f"- {term}" for term in self._common_instructions['professional_terms']])}

## 六、提取要求
{chr(10).join([f"- {req}" for req in self._common_instructions['requirements']])}

## 七、需要提取的变量信息
{variables_description}

## 八、输出格式要求
请按照以下格式输出一个JSON数组，每个元素包含变量名、变量值和引用来源：

### JSON输出模板：
```json
{json_template}
```

## 九、格式与内容规范
1. 输出必须是JSON数组格式，以 [ 开始，以 ] 结束。
2. 每个变量一个对象，包含 "variable_name"、"variable_value" 和 "reference_source" 字段。
3. variable_name 使用变量的中文名称。
4. reference_source 对象包含 "source_url"、"evidence_text"、"pages"、"file_type" 字段。
5. 如果某个变量无法提取，跳过该变量或设置为空字符串。
6. 页码格式：多个页码用英文逗号分隔，如 "1, 2, 3" 或 "1, 2"。

## 十、重要注意事项
⚠️ **JSON格式要求**：
- 输出有效的JSON数组格式，以 [ 开始，以 ] 结束
- 字段名和字符串值使用英文双引号包围
- 确保JSON语法正确，括号和逗号匹配
- 优先保证数据准确性，格式可以适当调整

⚠️ **内容提取要求**：
- variable_value必须是准确提取的信息，不要编造
- source_url使用实际的文件URL地址
- evidence_text包含实际提取到的文本内容
- pages字段使用字符串格式记录页码，多个页码用英文逗号分隔，如 "1, 2, 3"
- 如果某个字段无法提取，跳过该变量
- 保持原文的专业术语和精确表述

⚠️ **来源信息追踪（重要）**：
- 为每个提取的变量记录完整的来源信息
- **source_url字段：直接使用文件头部标注的"文件URL"值**
- **evidence_text字段：记录实际提取到的原始文本内容**
- pages记录具体的页码信息，多个页码用英文逗号分隔
- 确保来源信息的准确性和完整性

**多文件处理说明：**
当文件内容包含多个文件时，每个文件都会有如下格式的标注：
```
=== 文件 1 ===
文件名: example.pdf
文件格式: pdf
文件URL: http://example.com/file.pdf
文件标识符: FILE_1_example_pdf
=== 文件内容开始 ===
...文件内容...
=== 文件内容结束 ===
```

**提取规则：**
1. 从哪个文件提取的变量，就使用该文件头部标注的"文件URL"值
2. 不要混淆不同文件的URL
3. evidence_text只包含纯粹的内容文本，不要包含文件元数据标注

⚠️ **表格内容处理要求**：
- 当提取的变量涉及表格数据时，variable_value和evidence_text都使用简洁的HTML表格格式：
  
  **统一格式（简洁无边框）：**
  ```html
  <table><tr><td>表头1</td><td>表头2</td><td>表头3</td></tr><tr><td>数据1</td><td>数据2</td><td>数据3</td></tr></table>
  ```
- 不要添加任何边框样式，避免JSON解析错误，确保整个表格内容在一行中展示，不要换行，返回的变量格式也要保持在一行中展示，不要换行，不要使用\n换行
- 表格内容必须保持原文的完整性和准确性
- 所有表格数据都要包含在HTML标签中，不要混合使用纯文本和HTML标签
- **重要：对于表格类型变量，evidence_text字段也必须使用HTML表格格式，不能使用纯文本**

## 当前文件信息
- 文件类型：{file_type}
- 文件URL：{file_url}

请开始分析文件内容：

## 文件内容：
$content

请严格按照上述文件内容进行信息提取，不得编造或使用其他文档的信息。"""

        return prompt
    
    # 来源追踪功能已默认集成到 generate_prompt 方法中
    # 所有生成的提示词都包含完整的来源信息追踪功能
    
    def _generate_variables_description(self, variables: List[VariableDefinition]) -> str:
        """
        生成变量描述文本
        
        Args:
            variables: 变量定义列表
            
        Returns:
            str: 变量描述文本
        """
        if not variables:
            return "无需提取变量。"
        
        descriptions = []
        for i, var in enumerate(variables, 1):
            # 基本信息
            desc = f"{i}. **{var.name}** ({var.english_name})\n"
            desc += f"   - 数据类型: {var.data_type}\n"
            desc += f"   - 变量描述: {var.description}\n"
            
            # 提取规则 - 更详细的格式
            if var.extraction_rule:
                desc += f"   - 提取规则:\n"
                for j, rule in enumerate(var.extraction_rule):
                    if rule.strip():  # 跳过空规则
                        desc += f"     {j+1}. {rule}\n"
            
            # 关键字定位
            if var.keywords:
                keywords_str = "、".join(var.keywords)
                desc += f"   - 关键字定位: 在文档中查找包含「{keywords_str}」等关键词的章节或段落\n"
            
            # 提取示例
            if var.examples:
                desc += f"   - 提取示例:\n"
                for j, example in enumerate(var.examples):
                    if example.strip():
                        desc += f"     示例{j+1}: {example}\n"
            
            # 特别注意事项（基于数据类型）
            if var.data_type == "int" or var.data_type == "float":
                desc += f"   - ⚠️ 注意: 提取数值时保持原文精度，如需要可包含单位\n"
            elif var.data_type == "str":
                # 检查是否为表格类型变量
                is_table_variable = (
                    any("表格" in rule for rule in var.extraction_rule) or
                    any("开标记录" in rule for rule in var.extraction_rule) or
                    any("评审结果" in rule for rule in var.extraction_rule) or
                    any("得分汇总" in rule for rule in var.extraction_rule) or
                    any("候选人" in rule for rule in var.extraction_rule) or
                    any("下载记录" in rule for rule in var.extraction_rule) or
                    "表格" in var.name or "记录" in var.name or "汇总" in var.name or "潜在投标人数" in var.name
                )
                if is_table_variable:
                    desc += f"   - ⚠️ 注意: 这是表格类字段，variable_value和evidence_text都使用简洁的HTML表格标签格式化\n"
                    desc += f"   - 表格格式: <table><tr><td>表头</td></tr><tr><td>数据</td></tr></table>\n"
                    desc += f"   - 不要添加任何边框样式，避免JSON解析错误\n"
                    desc += f"   - **重要：evidence_text字段必须使用HTML表格格式，不能使用纯文本描述**\n"
                else:
                    desc += f"   - ⚠️ 注意: 提取时保持原文完整性和准确性，避免遗漏重要信息\n"
            elif var.data_type == "list":
                desc += f"   - ⚠️ 注意: 如果是列表格式，请提取完整的列表内容\n"
            elif var.data_type == "bool":
                desc += f"   - ⚠️ 注意: 布尔值支持多种表示形式，如'是/否'、'有/无'、'1/0'等\n"
            else:
                desc += f"   - ⚠️ 注意: 严格按照提取规则进行提取，确保数据格式正确\n"
            
            descriptions.append(desc)
        
        return "\n".join(descriptions)
    
    def _generate_json_template(self, variables: List[VariableDefinition], file_type: str = "tender_file") -> str:
        """
        生成JSON模板

        Args:
            variables: 变量定义列表
            file_type: 文件类型

        Returns:
            str: JSON模板字符串
        """
        if not variables:
            return "[]"

        # 生成新的数组格式模板
        template = []
        for var in variables:
            # 根据数据类型设置示例值
            if var.data_type == "str":
                if var.examples:
                    example_value = var.examples[0]
                else:
                    example_value = "字符串值"
            elif var.data_type == "int":
                if var.examples:
                    try:
                        example_value = int(var.examples[0])
                    except (ValueError, IndexError):
                        example_value = 0
                else:
                    example_value = 0
            elif var.data_type == "float":
                if var.examples:
                    try:
                        example_value = float(var.examples[0])
                    except (ValueError, IndexError):
                        example_value = 0.0
                else:
                    example_value = 0.0
            elif var.data_type == "bool":
                example_value = False
            elif var.data_type == "list":
                if var.examples:
                    example_value = var.examples
                else:
                    example_value = []
            elif var.data_type == "dict":
                example_value = {}
            else:
                example_value = ""

            # 检查是否为表格类型变量，为evidence_text设置合适的示例
            is_table_variable = (
                any("表格" in rule for rule in var.extraction_rule) or
                any("开标记录" in rule for rule in var.extraction_rule) or
                any("评审结果" in rule for rule in var.extraction_rule) or
                any("得分汇总" in rule for rule in var.extraction_rule) or
                any("候选人" in rule for rule in var.extraction_rule) or
                any("下载记录" in rule for rule in var.extraction_rule) or
                "表格" in var.name or "记录" in var.name or "汇总" in var.name
            )
            
            if is_table_variable:
                evidence_text_example = "<table><tr><td>表头1</td><td>表头2</td></tr><tr><td>数据1</td><td>数据2</td></tr></table>"
            else:
                evidence_text_example = "提取到的具体文本内容"
            
            template.append({
                "variable_name": var.name,
                "variable_value": example_value,
                "reference_source": {
                    "source_url": "https://example.com/document.pdf",
                    "evidence_text": evidence_text_example,
                    "pages": "1, 2, 3",
                    "file_type": file_type
                }
            })

        # 格式化JSON，使其更易读
        return json.dumps(template, ensure_ascii=False, indent=2)
    
    def _initialize_base_templates(self) -> Dict[str, str]:
        """初始化基础提示词模板"""
        return {
            "tender_file": """
你正在分析**招标文件**，这是整个招投标流程的核心文档。招标文件包含了项目的基本信息、招标要求、评标标准等关键内容。

**分析要点：**
- 重点关注项目基本信息（项目名称、编号、招标单位等）
- 仔细提取招标要求和条件
- 注意评标办法和评分标准
- 关注时间节点和截止时间
- 准确识别投标限价和资金信息
- 提取评标委员会相关信息

**特别注意事项：**
- 项目编号注意不是计划文号，项目唯一的标识编码，含字母/数字，不要提取标包号
- 常见格式：ZB2025-XXX、JN2024-001、GC-2025-002等字母+数字组合
- ⚠️ 特别注意：**不要提取**类似"晋煤化企管字[2025]73号"等**企业内部发文编号**
- 优先查找"招标编号"、"项目编码"、"采购编号"、"Tender No."等字段
- 投标截止时间严格按照"响应文件递交截止时间"填写，格式为：YYYY年MM月DD日 HH时MM分
- 项目名称中不要出现标包号，只写项目名称
""",
            # candidate_bid_files 在第四次模型调用时单独处理，不在这里定义
            "opening_record_file": """
你正在分析**开标记录文件**，这记录了开标过程的详细信息和所有投标人的开标情况。

**分析要点：**
- 准确统计有效投标人数量
- 仔细提取开标记录表格的完整信息
- 注意投标人名称、报价、工期等关键信息
- 关注最高投标限价的设置
- 记录开标过程中的异常情况

**特别注意事项：**
- 开标记录表格必须输出为HTML格式的<table>标签结构
- 使用简洁格式：<table><tr><td>表头</td></tr><tr><td>数据</td></tr></table>
- 不要添加任何边框样式，避免JSON解析错误
- 投标人名称保持完整，包含公司类型后缀
- 投标报价保持原文精度，包含小数点
- 表格最后一行通常为'最高投标限价'及其对应数值
- 如果表格跨多列，注意使用colspan属性
""",
            "review_experts_file": """
你正在分析**评审专家信息文件**，这包含了评标委员会的组成和专家信息。

**分析要点：**
- 准确识别评标委员会主任
- 完整提取其他评标委员会成员信息
- 注意专家的专业背景和资质
- 关注评标委员会的组成规则
- 记录专家的职责分工
""",
            "evaluation_summary_file": """
你正在分析**评标汇总文件**，这是评标过程的核心结果文档，包含了最终的评审结果和排名。

**分析要点：**
- 准确提取各投标人的最终得分和排名
- 仔细分析推荐中标候选人信息
- 提取详细的得分汇总表格
- 关注评标结果的完整性和准确性
- 注意候选人的各项分值明细

**表格输出特别要求：**
- 中标候选人得分汇总情况使用简洁格式：<table><tr><td>表头</td></tr><tr><td>数据</td></tr></table>
- 不要添加任何边框样式，避免JSON解析错误
- 表格必须只使用<td>标签，不使用<th>、<thead>、<tbody>等标签
- 第一行为表头，包含：序号、候选人名称、投标报价、修正后报价、资信商务得分、技术服务得分、投标报价得分、其他部分得分、总分、排名
- 后续行按排名顺序列出前三名候选人的完整信息
- 所有分值保持原文精度，包含小数点（如85.5分）
""",
            "other_files": """
你正在分析**其他相关文件**，这些文件可能包含补充信息、澄清说明、公告信息等。

**分析要点：**
- 提取公告发布相关的时间和信息
- 关注潜在投标人的数量统计
- 仔细阅读澄清、说明、补正事项
- 注意文件中的重要补充信息
- 关注对主要文件的修正或澄清
""",
            "default": """
你正在分析招投标相关文件，请仔细阅读文档内容，准确提取所需信息。

**通用分析要点：**
- 保持信息提取的准确性和完整性
- 遵循提取规则的具体要求
- 对于不确定的信息，保持谨慎态度
- 注意文档的结构和重点内容
"""
        }
