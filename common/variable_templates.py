# 变量模板管理器
# 基于Excel文件中的变量定义，管理不同文件类型需要提取的变量
# 包括变量名称、数据类型、是否必需、提取规则、关键字等信息

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import re

@dataclass
class VariableDefinition:
    """变量定义数据类"""
    name: str                    # 变量名称（中文）
    english_name: str           # 英文字段名
    description: str             # 变量描述
    data_type: str              # 数据类型 (str, int, float, bool, list, dict)
    extraction_rule: List[str]  # 提取规则描述（数组）
    keywords: List[str]         # 关键字（数组）
    examples: List[str]         # 示例值（数组）

class VariableTemplateManager:
    """变量模板管理器类 - 负责管理不同文件类型的变量定义"""
    
    def __init__(self):
        """初始化变量模板管理器"""
        # 基于Excel数据定义的文件类型与变量映射关系
        self._file_type_variables = self._initialize_variables()
    
    def _initialize_variables(self) -> Dict[str, List[VariableDefinition]]:
        """初始化所有文件类型的变量定义"""
        return {
            "tender_file": self._get_tender_file_variables(),
            # candidate_bid_files 在第四次模型调用时单独处理，不在此处定义
            "opening_record_file": self._get_opening_record_file_variables(),
            "review_experts_file": self._get_review_experts_file_variables(),
            "evaluation_summary_file": self._get_evaluation_summary_file_variables(),
            "other_files": self._get_other_files_variables()
        }
    
    def get_variables_for_file_type(self, file_type: str) -> List[VariableDefinition]:
        """
        获取指定文件类型需要提取的变量列表
        
        Args:
            file_type: 文件类型
            
        Returns:
            List[VariableDefinition]: 变量定义列表
        """
        return self._file_type_variables.get(file_type, [])
    
    def validate_extracted_data(self, file_type: str, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证提取的数据是否符合变量定义要求
        
        Args:
            file_type: 文件类型
            extracted_data: 提取的数据字典
            
        Returns:
            Dict[str, Any]: 验证结果，包含验证状态和错误信息
        """
        variables = self.get_variables_for_file_type(file_type)
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "validated_data": {}
        }
        
        # 验证所有变量
        for var in variables:
            if var.english_name in extracted_data:
                validated_value = self._validate_data_type(
                    extracted_data[var.english_name], 
                    var.data_type, 
                    var.name
                )
                if validated_value is not None:
                    validation_result["validated_data"][var.english_name] = validated_value
                else:
                    validation_result["warnings"].append(f"变量 {var.name} 数据类型不匹配，已忽略")
        
        return validation_result
    
    def _validate_data_type(self, value: Any, expected_type: str, var_name: str) -> Any:
        """验证数据类型"""
        if value is None or value == "":
            return None
            
        try:
            if expected_type == "str":
                return str(value)
            elif expected_type == "int":
                # 尝试提取数字
                if isinstance(value, str):
                    numbers = re.findall(r'\d+', value)
                    return int(numbers[0]) if numbers else None
                return int(value)
            elif expected_type == "float":
                if isinstance(value, str):
                    numbers = re.findall(r'\d+\.?\d*', value)
                    return float(numbers[0]) if numbers else None
                return float(value)
            elif expected_type == "bool":
                if isinstance(value, str):
                    return value.lower() in ['true', '是', '有', '1', 'yes']
                return bool(value)
            elif expected_type == "list":
                if isinstance(value, list):
                    return value
                elif isinstance(value, str):
                    return [item.strip() for item in value.split(',') if item.strip()]
                return [value]
            elif expected_type == "dict":
                if isinstance(value, dict):
                    return value
                return {"value": value}
            else:
                return str(value)
        except (ValueError, TypeError):
            return None
    
    def get_keywords_for_file_type(self, file_type: str) -> List[str]:
        """获取指定文件类型的所有关键字"""
        variables = self.get_variables_for_file_type(file_type)
        keywords = []
        for var in variables:
            if var.keywords:
                keywords.extend(var.keywords)  # keywords已经是数组，直接扩展
        return list(set(keywords))  # 去重
    
    def find_variable_by_keyword(self, file_type: str, keyword: str) -> Optional[VariableDefinition]:
        """通过关键字查找变量定义"""
        variables = self.get_variables_for_file_type(file_type)
        for var in variables:
            if var.keywords and keyword in var.keywords:  # keywords已经是数组，直接使用in操作符
                return var
        return None
    
    def _get_tender_file_variables(self) -> List[VariableDefinition]:
        """获取招标文件的变量定义"""
        return [
            VariableDefinition(
                name="项目名称",
                english_name="project_name",
                description="项目名称，整个招标项目的正式全称",
                data_type="str",
                extraction_rule=[
                    "提取项目的完整正式名称，不要包含标包号、标段号、招标单位等",
                    "如果文档中有多个项目名称，选择最完整、最正式的",
                    "若没有明确项目名称，则留空"
                ],
                keywords=["项目名称"],
                examples=["晋能控股装备制造集团大同机电装备有限公司中央机厂各类产品运输框架入围招标"]
            ),
            VariableDefinition(
                name="招标编号",
                english_name="tender_number",
                description="项目唯一的标识编码，含字母/数字组合",
                data_type="str",
                extraction_rule=[
                    "特别注意：不要提取企业内部发文编号，如'晋煤化企管字[2025]73号'，也不要提取计划文号或标包号",
                    "如果没有明确项目编号，不允许自动生成，且留空"
                ],
                keywords=["招标编号"],
                examples=["JNC246-ZB-250312"]
            ),
            VariableDefinition(
                name="招标人",
                english_name="tenderer",
                description="招标单位的具体名称",
                data_type="str",
                extraction_rule=[
                    "提取招标单位的完整名称，可能会用不同词汇表示，如'项目单位'、'招标人名称'等",
                    "若没有明确招标单位，则留空"
                ],
                keywords=["招标单位", "招标人"],
                examples=["晋能控股装备制造集团大同机电装备有限公司"]
            ),
            VariableDefinition(
                name="招标代理",
                english_name="tender_agent",
                description="代理机构名称",
                data_type="str",
                extraction_rule=[
                    "提取代理机构的具体名称",
                    "若没有明确代理机构名称，则留空"
                ],
                keywords=["招标代理", "代理机构"],
                examples=["晋能控股集团山西工程咨询有限公司"]
            ),
            VariableDefinition(
                name="招标方式",
                english_name="tender_method",
                description="招标方式",
                data_type="str",
                extraction_rule=[
                    "提取文档中明确标注的招标方式，保持原文用词，不要改写或扩展（如：公开招标、邀请招标等）",
                    "若文档未明确标注招标方式，则留空"
                ],
                keywords=["招标方式"],
                examples=["公开招标"]
            ),
            VariableDefinition(
                name="招标内容及范围",
                english_name="tender_scope",
                description="招标内容与范围",
                data_type="str",
                extraction_rule=[
                    "【定位范围】只提取第一章招标公告中'招标内容及范围'或'招标内容与范围'或'招标内容'这个小节下的内容",
                    "【严格边界控制】严格在本小节范围内提取，不要提取到其他小节的内容：",
                    "  - 不要提取'项目概况'的内容",
                    "  - 不要提取'交货地点'、'交货期'的内容",
                    "  - 不要提取'服务地点'、'服务周期'、'服务期限'的内容",
                    "  - 不要提取'质量标准'、'服务标准'的内容",
                    "  - 不要提取'标段（包）内容'的内容",
                    "  - 遇到下一个小节标题（如上述这些）立即停止提取",
                    "【章节处理】如果写有'详见其他章节'或'详见招标文件第X章'，只提取当前章节已有的内容，不要去其他章节提取",
                    "【格式判断-关键】判断内容本身的格式，而不是它所在的容器：",
                    "  - 【表格判断】只有同时满足以下所有条件，才提取为HTML表格格式：",
                    "    * 内容有多列结构（如：名称列、规格列、数量列、单价列等至少2列）",
                    "    * 有多行数据（表头+至少2行数据）",
                    "    * 有明确的表头行",
                    "    * 内容确实需要表格来展示结构关系",
                    "  - 【文本判断】以下情况必须提取为纯文本，绝对不使用HTML表格标签：",
                    "    * 单列内容（即使原文在表格的一个单元格中）",
                    "    * 带序号的列表（如：1. 2. 3. 或 2.1、2.2、2.3 等）",
                    "    * 段落描述",
                    "    * 标题+列表的组合（如'本招标项目划分为1个标段。1. ... 2. ... 3. ...'）",
                    "    * 即使有冒号分隔，但本质是列表或段落的内容",
                    "  - 【关键原则】不要因为原文在表格单元格中就添加<table>标签，要看内容本身的结构",
                    "  - 混合内容：既有文本描述又有真正的多列表格，则分别保留两种格式",
                    "【文本格式处理-重要】：",
                    "  - 如果内容是纯文本（包括带序号的列表、段落描述等），直接提取为纯文本内容，不添加任何HTML标签",
                    "  - 保留原文的序号格式（如'2.2'、'001'、'1、'、'1.'、'（1）'等）",
                    "  - 【关键】如果文本中有序号，必须在序号之间添加换行符\n，确保每个序号独立成行",
                    "  - 【示例1】原文：'本招标项目划分为1个标段。1.除锅炉... 2.对现有... 3.对新增... 4.除锅炉...'",
                    "    提取为：'本招标项目划分为1个标段。\n1.除锅炉...\n2.对现有...\n3.对新增...\n4.除锅炉...'",
                    "  - 【示例2】原文：'2.2.1 内容A 2.2.2 内容B'",
                    "    提取为：'2.2.1 内容A\n2.2.2 内容B'",
                    "  - 【示例3】原文：'001 标段内容A 002 标段内容B'",
                    "    提取为：'001 标段内容A\n002 标段内容B'",
                    "  - 即使原文在一个表格单元格中，如果内容本身是单列列表，也要提取为纯文本，不要添加<table>、<tr>、<td>标签",
                    "  - 保持文本的换行结构清晰，便于阅读",
                    "  - 【绝对禁止】不要把带序号的列表或段落描述转换成HTML表格格式",
                    "【表格格式处理】：",
                    "  - 只有当原文明确是多列多行的表格结构时，才使用HTML表格格式",
                    "  - 表格必须包含<table>、<tr>、<td>等标签",
                    "  - 准确识别表格的表头、行列、跨行跨列等结构",
                    "  - 保持表格的完整性和准确性",
                    "【混合格式处理】：",
                    "  - 如果既有文本描述又有表格，先输出文本部分（纯文本格式），然后输出表格部分（HTML格式）",
                    "  - 文本和表格之间用换行符分隔",
                    "  - 文本部分不要添加HTML标签，表格部分才使用HTML标签",
                    "若没有明确的招标内容和范围，则留空"
                ],
                keywords=["招标内容与范围", "招标内容及范围", "招标内容"],
                examples=[]
            ),
            VariableDefinition(
                name="交货期或计划工期或服务期限",
                english_name="delivery_or_service_period",
                description="交货期或计划工期或服务期限",
                data_type="str",
                extraction_rule=[
                    "格式基于原文内容上可以是时间段、具体时间或者其他描述，可能用不同词汇表示，如'供货期'、'实施周期'、'交货期'",
                    "如果数字和文本之间有空格，应该去掉空格",
                    "若没有明确工期或服务期或交货期，则留空",
                    "不要提取信息前缀，如'交货期：'、'服务期限：'等"
                ],
                keywords=["交货期", "计划工期", "服务期限"],
                examples=[]
            ),
            VariableDefinition(
                name="建设地点或交货地点或项目地点",
                english_name="project_location",
                description="建设地点或交货地点或项目地点",
                data_type="str",
                extraction_rule=[
                    "提取完整的建设地点或交货地点或项目地点",
                    "若没有明确字段，则留空"
                ],
                keywords=["建设地点", "交货地点", "项目地点"],
                examples=["山西转型综合改革示范区科技创新城园区"]
            ),
            VariableDefinition(
                name="质量要求",
                english_name="quality_requirements",
                description="质量要求",
                data_type="str",
                extraction_rule=[
                    "提取完整的质量要求，若没有明确字段，则留空"
                ],
                keywords=[],
                examples=[]
            ),
            VariableDefinition(
                name="公告发布网站",
                english_name="announcement_website",
                description="公告发布网站",
                data_type="str",
                extraction_rule=[
                    "按原文提取发布网站，与招标公告中所列网站保持一致（不改写、不增删）",
                    "允许是网站名称或URL，一般是平台名称，可能带'《》'之类的符号，需要原样输出",
                    "若同时给出名称与URL，按原文顺序保留",
                    "若出现多个网站，按原文顺序以'、'分隔",
                    "文档未明确发布网站时，则留空"
                ],
                keywords=[],
                examples=[]
            ),
            VariableDefinition(
                name="获取招标文件时间",
                english_name="document_obtain_period",
                description="获取招标文件时间",
                data_type="str",
                extraction_rule=[
                    "在句式'可于[开始时间]至[结束时间]（北京时间）……获取招标文件'中，提取第一个时间点",
                    "保持原文精度：原文到'日/时/分'就保留到相同粒度，不要自行补全或改写格式，只输出时间文本",
                    "不带引导词与括号内容（如'（北京时间）''可于/至/登录/获取'等不进入字段）",
                    "若文本只给出其中一个时间，另一个留空",
                    "若同一文件多处给出时间段（如补遗/更正），以最终有效版本为准",
                    "无法判断时取出现位置在'招标文件获取'段的首次时间段",
                    "类似'法定节假日除外/工作日/每日9:00-17:00'等说明不并入时间字段（仅保留开始/结束两项）"
                ],
                keywords=["获取时间"],
                examples=[]
            ),
            VariableDefinition(
                name="投标人要求",
                english_name="bidder_requirements",
                description="投标人要求",
                data_type="str",
                extraction_rule=[
                    "提取完整的投标人要求内容，有多少提多少，即使描述不完整也要提取所有能找到的相关内容",
                    "仅在'投标人资格要求'或'三、投标人资格要求'章节中提取，不要在其他位置提取",
                    "从'三、投标人资格要求'开始，到下一个大章节（如'四、'、'五、'等）之前的所有内容",
                    "包含所有子条款内容，如3.1、3.2、3.3、3.4、3.5等所有编号条款",
                    "包含投标人业绩要求（如'投标人近年承担过1项类似项目业绩'、'投标人近年具备1项类似业绩'等）",
                    "包含投标人资质要求（如'须具备合法有效的《道路运输经营许可证》'、'设计甲级资质'等）",
                    "包含投标人基本要求（如'应为中华人民共和国境内注册的独立法人'等）",
                    "包含项目经理要求（如'项目经理须具备'等）",
                    "包含其他所有投标人资格相关要求",
                    "包含业绩数量要求、时间范围定义、业绩类型定义、证明材料要求等",
                    "包含资质证书名称、资质等级要求、资质有效期要求、资质颁发部门要求等",
                    "包含所有子项和详细说明，如合同要求、发票要求、证明文件要求等",
                    "确保提取到该章节下的所有文字内容，包括括号内的补充说明",
                    "即使描述不完整，也要提取所有能找到的投标人要求相关内容",
                    "若没有明确的投标人资格要求章节，则留空",
                    "确保提取整个'三、投标人资格要求'章节的所有内容，不要遗漏任何子条款"
                ],
                keywords=["投标人要求", "投标人资格要求", "三、投标人资格要求"],
                examples=[]
            ),
            VariableDefinition(
                name="资格评审标准",
                english_name="qualification_review_standards",
                description="第三章评标办法中的评标办法前附表-资格评审标准",
                data_type="str",
                extraction_rule=[
                    "在'第三章评标办法'或'评标办法前附表'中查找'资格评审标准'相关内容",
                    "必须严格限定在'2.1.2 资格评审标准'或'资格评审标准'这一部分，不要提取其他部分的评审因素",
                    "严禁提取以下部分的评审因素：",
                    "  - '2.1.1 形式评审标准'或'形式评审标准'部分的所有条款（如：投标人名称、投标函及投标函附录、签字盖章、法定代表人身份证明、报价唯一等）",
                    "  - '2.1.3 响应性评审'或'响应性评审'部分的所有条款（如：投标报价等）",
                    "  - '商务评分标准'或'技术评分标准'部分的所有条款",
                    "在资格评审标准部分中，只提取评审因素（条款名称），不需要提取评审标准的具体描述内容",
                    "提取时去除括号及括号内的解释性文本，例如'资质要求(事业单位法人证书)'应提取为'资质要求'",
                    "出现以下条款时不提取：营业执照、信誉要求、其他要求、其他否决投标情形，即使出现在资格评审标准部分也要忽略，严禁提取这些条款",
                    "提取的条款名称之间用'|'（竖线）分隔",
                    "例如：业绩要求|资质要求",
                    "如果表格跨页，需要提取完整的评审因素列表，但必须确保所有提取的条款都来自资格评审标准部分",
                    "确保提取所有符合条件的评审因素，不要遗漏，但不要提取资格评审标准以外的任何条款"
                ],
                keywords=["资格评审标准", "业绩要求", "资质要求", "评标办法前附表", "评审因素", "2.1.2"],
                examples=[]
            ),
            VariableDefinition(
                name="商务评分标准",
                english_name="business_scoring_standards",
                description="第三章评标办法中的评标办法前附表-商务评分标准",
                data_type="str",
                extraction_rule=[
                    "在'第三章评标办法'或'评标办法前附表'中查找'商务评分标准'相关内容",
                    "只提取评分因素（条款名称），不需要提取评分标准的具体描述内容、分值或评分规则",
                    "提取时去除括号及括号内的解释性文本或分数，例如'近年投标人类似项目业绩(近3年)'应提取为'近年投标人类似项目业绩'",
                    "**重要：不要提取'标书质量'条款，即使该条款出现在商务评分标准中也要排除**",
                    "提取的条款名称之间用'|'（竖线）分隔",
                    "例如：近年投标人类似项目业绩|综合实力|业主反馈",
                    "如果表格跨页，需要提取完整的评分因素列表",
                    "确保提取所有评分因素（除标书质量外），不要遗漏"
                ],
                keywords=["商务评分标准", "近年投标人类似项目业绩", "综合实力", "评分标准", "评标办法前附表", "评分因素"],
                examples=[]
            ),
            VariableDefinition(
                name="公告发布时间",
                english_name="announcement_date",
                description="获取招标文件时间",
                data_type="str",
                extraction_rule=[
                    "在句式'可于[开始时间]至[结束时间]（北京时间）……获取招标文件'中，提取第一个时间点",
                    "保持原文精度：原文到'日/时/分'就保留到相同粒度，不要自行补全或改写格式，只输出时间文本",
                    "不带引导词与括号内容（如'（北京时间）''可于/至/登录/获取'等不进入字段）",
                    "若同一文件多处给出时间段（如补遗/更正），以最终有效版本为准",
                    "无法判断时取出现位置在'招标文件获取'段的首次时间段",
                    "类似'法定节假日除外/工作日/每日9:00-17:00'等说明不并入时间字段（仅保留开始/结束两项）"
                    "提取其对应的完整时间点,例如'2025-03-12',你需要对提取到的时间做格式转换,以YYYY年MM月DD日格式返回,只提取年月日这三个字段",
                ],
                keywords=["获取招标文件时间"],
                examples=["2024-11-18", "2025-10-1"]
            ),
            VariableDefinition(
                name="获取文件截止时间",
                english_name="document_deadline",
                description="获取文件截止时间",
                data_type="str",
                extraction_rule=[
                    "在句式'可于[开始时间]至[结束时间]（北京时间）……获取招标文件'中，提取第二个时间点",
                    "保持原文精度：原文到'日/时/分'就保留到相同粒度，不要自行补全或改写格式，只输出时间文本",
                    "不带引导词与括号内容（如'（北京时间）''可于/至/登录/获取'等不进入字段）",
                    "若文本只给出其中一个时间，另一个留空",
                    "若同一文件多处给出时间段（如补遗/更正），以最终有效版本为准",
                    "无法判断时取出现位置在'招标文件获取'段的首次时间段",
                    "类似'法定节假日除外/工作日/每日9:00-17:00'等说明不并入时间字段（仅保留开始/结束两项）"
                ],
                keywords=[],
                examples=[]
            ),
            VariableDefinition(
                name="评标委员会人数",
                english_name="evaluation_committee_count",
                description="评标委员会人数",
                data_type="int",
                extraction_rule=[
                    "仅输出阿拉伯数字（不带'家'等单位），一般在'评标委员会构成：'之后",
                    "若全文多处出现，以该段（获取文件情况）中的首次明确数字为准",
                    "未明确给出人数时留空"
                ],
                keywords=["评标委员会"],
                examples=["10", "5", "20"]
            ),
            VariableDefinition(
                name="抽取专家库名称",
                english_name="expert_database_name",
                description="抽取专家库名称",
                data_type="str",
                extraction_rule=[
                    "仅提取专家库的完整名称，去掉引导词与括号本身（不保留'从/在/（）/随机抽取'等）",
                    "若出现多个专家库名称，按原文顺序保留",
                    "用原文分隔符（如'、''及'）连接，不自行合并或改写",
                    "若只出现泛称'专家库'而未指明具体名称，则留空",
                    "只做轻度清洗：去首尾空格与多余标点，专有名词原样输出（不做标准化）"
                ],
                keywords=["评标委员会"],
                examples=["山西省评标专家库"]
            ),
            VariableDefinition(
                name="专家人数",
                english_name="experts_count",
                description="专家人数",
                data_type="int",
                extraction_rule=[
                    "仅输出阿拉伯数字（不带'家'等单位）",
                    "若全文多处出现，以该段（获取文件情况）中的首次明确数字为准",
                    "未明确给出人数时留空"
                ],
                keywords=["评标委员会"],
                examples=["10", "5", "20"]
            ),
            VariableDefinition(
                name="招标人代表人数",
                english_name="tenderer_representatives_count",
                description="招标人代表人数",
                data_type="int",
                extraction_rule=[
                    "仅输出阿拉伯数字（不带'家'等单位）",
                    "若全文多处出现，以该段（获取文件情况）中的首次明确数字为准",
                    "未明确给出人数时留空"
                ],
                keywords=["评标委员会"],
                examples=["10", "5", "20"]
            ),
            VariableDefinition(
                name="投标截止时间",
                english_name="bid_deadline",
                description="投标截止时间",
                data_type="str",
                extraction_rule=[
                    "在文档中定位'投标截止时间：'、'投标文件递交截止时间：'、'截止时间：'、'投标文件提交截止时间：'等字段后的内容",
                    "仅提取时间点，若出现多个截止时间（如修改公告中更新），仅保留最新一次出现的时间",
                    "只做轻度清洗：去首尾空格、去多余标点，时间内容原样输出",
                    "若文档未明确投标截止时间字段，则留空"
                ],
                keywords=["投标截止时间"],
                examples=[]
            ),
            VariableDefinition(
                name="最高投标限价",
                english_name="max_bid_price",
                description="最高投标限价",
                data_type="str",
                extraction_rule=[
                    "【定位目标】必须找到明确标注为'最高投标限价'或'最高投标限价或其计算方法'的字段位置",
                    "【严格范围限制-关键】只提取'最高投标限价'这个字段位置直接对应的内容：",
                    "  - 只提取该字段右侧单元格或该小节标题下方的内容",
                    "  - 绝对不要提取'分项限价表'、'分项单价限价表'等详细表格内容",
                    "  - 如果提到'详见分项限价表'，只提取这句话本身，不要去找那个表格",
                    "  - 不要提取标题为'分项限价表'的整个表格数据",
                    "【选项识别与提取-关键】根据勾选的选项提取对应内容：",
                    "  - 如果勾选'☑有'或'☑最高投标限价'：提取该选项后面的完整限价内容（金额、条件、说明等）",
                    "  - 如果勾选'☑无'或'☑不设最高投标限价'：提取该选项后面的完整说明内容（如'最低投标报价不得授予合同的保证'等）",
                    "  - 无论勾选哪个选项，都要提取该选项对应的后续内容，不留空",
                    "  - 勾选哪个就提取哪个选项后面的内容，不要混淆",
                    "【内容类型识别】最高投标限价字段的内容通常是以下几种形式之一：",
                    "  - 直接金额：'8059.071524 万元（含税价）'、'900 万元（含税价）'",
                    "  - 简要描述：'分项单价限价详见此表后附分项限价表（不含税价）投标分项报价高于分项投标限价的投标将被否决'",
                    "  - 分项说明：'块炭分拣加工费 14 元/吨（含 13%税价）、装车费 12 元/吨（含 6%税）...'",
                    "  - 带条件的完整描述（包含金额、税率、否决条款等）",
                    "  - 不设限价的说明：'最低投标报价不得授予合同的保证'等",
                    "【内容过滤-关键】只提取最相关的核心内容，排除解释性文本：",
                    "  - 保留：具体金额、限价数值、价格说明",
                    "  - 排除：税务规定解释、税率适用说明、政策解释性文字、否决条款、税率说明",
                    "  - 排除：'如供应商属于小规模纳税人或者满足税务上的其他规定，供应商可以根据自身情况适用税率'等解释性内容",
                    "  - 排除：括号内的详细解释性说明，除非是金额或限价相关的核心信息",
                    "  - 只保留与投标限价直接相关的核心信息",
                    "【完整性要求】对于该字段位置的内容，必须完整提取，不截断：",
                    "  - 包括金额、单位、含税说明、分项说明、条件、否决条款等",
                    "  - 如果一个单元格或段落内有多句话，全部提取",
                    "  - 但不要超出该字段的边界去提取其他内容",
                    "【边界识别】严格区分并排除以下内容：",
                    "  - 不要提取'项目规模'、'计划资金'、'计划金额'等其他字段",
                    "  - 不要提取独立的'分项限价表'表格（这是另外的详细表格，不是最高投标限价字段本身）",
                    "  - 遇到表格标题'分项限价表'时，不要提取该表格",
                    "【表格处理】如果最高投标限价在表格中：",
                    "  - 只提取该字段右侧单元格内的文本内容",
                    "  - 去除左侧的字段名'最高投标限价'",
                    "  - 将单元格内容转换为纯文本，不保留表格结构",
                    "  - 绝对不能返回HTML表格格式",
                    "【格式要求】：",
                    "  - 只返回纯文本格式",
                    "  - 不添加任何HTML标签或表格标签",
                    "  - 保留原文的换行、标点、括号",
                    "若该字段完全没有任何内容（既没有勾选项也没有说明），则留空"
                ],
                keywords=["最高投标限价"],
                examples=["分项单价限价详见此表后附分项限价表(不含税价),投标分项报价高于分项投标限价的投标将被否决。", "¥802.36万元", "26元/吨", "120.0万元", "100万元（含税）"]
            ),
            VariableDefinition(
                name="评标办法",
                english_name="evaluation_method",
                description="评标办法",
                data_type="str",
                extraction_rule=[
                    "在'评标办法'所在句或段中，按原文提取评标方法名称，不改写、不扩展（如：综合评估法、经评审的最低投标价法）",
                    "去掉提示前缀与标点（如'评标办法：'），只保留方法名称",
                    "若文档有勾选/删除线/加粗/说明文字等显式选择标识，只提取被选择的方法，无法判定选择时，按原文顺序保留并列文本整体（例如输出：综合评估法/经评审的最低投标价法）",
                    "若文档未明确评标办法，则留空"
                ],
                keywords=["评标办法", "评标办法前附表"],
                examples=["综合评估法"]
            ),
            VariableDefinition(
                name="评标因素标准",
                english_name="evaluation_factors",
                description="评标因素标准",
                data_type="int",
                extraction_rule=[
                    "仅提取阿拉伯数字（如'20'代表20分），不包含'分''%'等单位",
                    "需与'技术服务分值''投标报价分值'等其他维度分值区分，避免混淆",
                    "该值的位置一般在分值构成处，总分就是评标因素标准的值",
                    "若未明确该维度总分，留空，不得编造"
                ],
                keywords=[],
                examples=["10", "5", "20"]
            ),
            # 跨文件类型的变量 - 在招标文件和评标汇总表中都需要
            VariableDefinition(
                name="推荐中标候选人数规则",
                english_name="recommended_candidates_count_rule",
                description="推荐中标候选人数及工作量分配规则",
                data_type="str",
                extraction_rule=[
                    "提取完整的推荐中标候选人规则，包括人数和工作量分配原则",
                    "查找'推荐中标候选人'、'中标候选人'、'推荐排序'、'工作量分配原则'等相关表述",
                    "必须包含完整的规则内容，如：通过初步评审的投标人数量大于5名时推荐3名中标候选人等",
                    "如果存在工作量分配原则，需要完整提取分配比例，如：第一名60%，第二名40%等",
                    "提取内容包括：入围供应商数量限制、排序要求、工作量分配的具体百分比",
                    "保持原文的完整性和准确性，不得遗漏任何规则细节",
                    "如果规则分为多个条件，需要全部提取（如不同人数情况下的不同分配比例）"
                ],
                keywords=["推荐中标候选人", "工作量分配原则", "入围供应商", "排序"],
                examples=[
                    "通过初步评审的投标人数量大于5名时,推荐3名中标候选人;3名至5名时,推荐2名中标候选人;不足3名时,判定其报价是否具有竞争性,具备竞争性的全部推荐为中标候选人。",
                    "入围供应商最多六家,通过初步评审不足六家时,全部推荐为入围供应商。工作量分配原则:中标人数为一家时:100%;中标人数为两家时:第一名60%;第二名40%;中标人数为三家时:第一名45%;第二名35%;第三名20%;中标人数为四家时:第一名35%;第二名30%;第三名20%、第四名15%;中标人数为五家时:第一名35%;第二名25%;第三名20%、第四名15%;第五名5%;中标人数为六家时:第一名35%;第二名20%;第三名15%、第四名15%;第五名10%;第六名5%"
                ]
            ),
            # 缺失的变量
            VariableDefinition(
                name="分值部分",
                english_name="bid_score",
                description="商务、技术、报价、其他因素、方案",
                data_type="str",
                extraction_rule=[
                    "将这部分的内容完整提取出来，包含文本和分值",
                    "一般在编列内容这一列下面，你要将其中的内容完整提取出来，不要遗漏",
                    "对于提取到的内容你需要按照正确的格式来返回，按照提取到的内容顺序，分别列出每一项的名称加分值，没有的就留空",
                    "你要按照提取到的每项分值的文本描述来返回，不要添加其他内容也不要遗漏任何文本，分值之间不要添加额外的\n",
                    "若未明确，则留空，不得编造或估算"
                ],
                keywords=["编列内容"],
                examples=["商务部分:70分，投标报价部分：10分，技术服务部分：20分，其他因素评分：0分"]
            ),
        ]
    
    def _get_opening_record_file_variables(self) -> List[VariableDefinition]:
        """获取开标过程记录文件的变量定义"""
        return [
            VariableDefinition(
                name="有效投标人数",
                english_name="valid_bidders_count",
                description="有效投标人数",
                data_type="int",
                extraction_rule=[
                    "在开标记录或评标报告中，统计有效投标人的数量",
                    "查找'有效投标'、'符合要求的投标'、'参与评标'等相关表述",
                    "仅提取阿拉伯数字（如'8'代表8家），不包含'家'、'个'等单位",
                    "需排除被否决或无效的投标人，只统计通过初步评审的投标人数量",
                    "若文档中同时给出总投标人数和有效投标人数，提取有效投标人数",
                    "若未明确标注有效投标人数，可通过评标表格中的参评投标人数量进行统计",
                    "若无法确定有效投标人数，则留空"
                ],
                keywords=["有效投标"],
                examples=["10", "5", "20"]
            ),
            VariableDefinition(
                name="开标记录表格",
                english_name="bid_opening_records",
                description="开标记录表格",
                data_type="str",
                extraction_rule=[
                    "在开标记录文件中，提取开标记录表的完整信息，输出为HTML表格格式",
                    "表格必须使用<table>标签包裹，所有单元格都使用<td>标签",
                    "第一行为表头，包含：序号、投标人名称、投标报价(万元)、...（其他栏目）、备注",
                    "根据实际表格结构提取所有列，常见列包括：工期、质量承诺、项目经理、保证金等",
                    "按序号顺序列出所有参与开标的投标人信息",
                    "投标人名称保持完整，包含公司类型后缀",
                    "投标报价保持原文精度，包含小数点",
                    "表格最后一行为'最高投标限价(万元)'及其对应数值，最高投标限价应该是简单的文本描述，不要生成嵌套表格",
                    "单元格内容原样保留，仅去首尾空格",
                    "表格格式示例：<table><tr><td>序号</td><td>投标人名称</td><td>投标报价(万元)</td><td>备注</td></tr><tr><td>1</td><td>投标人A</td><td>100.0</td><td></td></tr><tr><td colspan='2'>最高投标限价(万元)</td><td>120.0</td><td></td></tr></table>",
                    "若无法获取完整的表格信息，则留空"
                ],
                keywords=["开标记录表"],
                examples=["<table><tr><td>序号</td><td>投标人名称</td><td>投标报价(万元)</td><td>备注</td></tr><tr><td>1</td><td>投标人A</td><td>100.0</td><td></td></tr><tr><td>2</td><td>投标人B</td><td>95.0</td><td></td></tr><tr><td>3</td><td>投标人C</td><td>105.0</td><td></td></tr><tr><td colspan='2'>最高投标限价</td><td>120.0</td><td></td></tr></table>"]
            )
        ]
    
    def _get_review_experts_file_variables(self) -> List[VariableDefinition]:
        """获取评审专家信息表的变量定义"""
        return [
            VariableDefinition(
                name="评标委员会主任",
                english_name="evaluation_committee_chair",
                description="评标委员会主任",
                data_type="str",
                extraction_rule=[
                    "在'评标委员会组成'段定位'评标委员会主任：'或'主任委员：'或'组长：'后的内容",
                    "仅提取人名，若出现多名主任（并列/共同主任）",
                    "按原文顺序提取，多人用'、'分隔",
                    "若在成员名单中以括注方式标识（如'张三（主任）'），仅取'张三'，去掉'（主任）/主任委员/主任/组长'等角色标注",
                    "只做轻度清洗：去首尾空格、去多余标点，姓名原样输出（不加先生/女士/职称）",
                    "若文件未明确姓名，则留空"
                ],
                keywords=[],
                examples=["张三"]
            ),
            VariableDefinition(
                name="其他评标委员会成员",
                english_name="evaluation_committee_members",
                description="其他评标委员会成员",
                data_type="str",
                extraction_rule=[
                    "在'评标委员会组成'段定位'其他评标委员会成员：'后的内容",
                    "若成员与主任混写（如'评标委员会成员：张三（主任）、李四、王五'），剔除主任，仅保留其余成员（示例输出：李四、王五）",
                    "若以角色分组（如'主任：张三，成员：李四、王五、赵六'），取'成员：'后的姓名列表",
                    "多人之间常见分隔符：'、/，/,/，/空格'，按原文顺序输出，统一用'、'连接",
                    "保留角色标注与括注（如'（专家）/（成员）/（主任）/（外聘）'等）",
                    "做轻度清洗（去首尾空格、重复标点）",
                    "若文中仅给出人数而无姓名，或仅出现'专家库/成员若干'等笼统表述，则留空"
                ],
                keywords=[],
                examples=["李四", "王五(业主评委)"]
            )
        ]
    
    def _get_evaluation_summary_file_variables(self) -> List[VariableDefinition]:
        """获取评标汇总表的变量定义"""
        return [
            VariableDefinition(
                name="评审结果",
                english_name="evaluation_result",
                description="评标表格最后合计得分",
                data_type="str",
                extraction_rule=[
                    "在评标汇总表或评分汇总表中，提取各投标人的最终得分情况，输出为完整的HTML表格格式",
                    "表格必须使用<table>标签包裹，所有单元格都使用<td>标签",
                    "第一行为表头，包含：序号、投标人名称、合计得分、排名、备注",
                    "后续行按排名顺序列出所有参评投标人的信息，不要提取到不符合的投标人",
                    "投标人名称保持完整，包含公司类型后缀",
                    "合计得分保持原文精度，包含小数点（如：85.5分）",
                    "排名按实际评标结果填写（1、2、3等）",
                    "备注栏可包含特殊说明或留空",
                    "表格格式示例：<table><tr><td>序号</td><td>投标人名称</td><td>合计得分</td><td>排名</td><td>备注</td></tr><tr><td>1</td><td>投标人A</td><td>85.5</td><td>1</td><td></td></tr></table>",
                    "若无法获取完整的评审结果，则留空"
                ],
                keywords=["评分汇总"],
                examples=["<table><tr><td>序号</td><td>投标人名称</td><td>合计得分</td><td>排名</td><td>备注</td></tr><tr><td>1</td><td>投标人A</td><td>85.5</td><td>1</td><td></td></tr><tr><td>2</td><td>投标人B</td><td>82.3</td><td>2</td><td></td></tr><tr><td>3</td><td>投标人C</td><td>78.9</td><td>3</td><td></td></tr></table>"]
            ),
            VariableDefinition(
                name="标段号",
                english_name="bid_section_number",
                description="标段号",
                data_type="str",
                extraction_rule=[
                    "提取评标表格首页的编号的最后三位，例如'JNA140-ZB-250613520/002',你只需要提取其中的'002'这后三位",
                    "特别注意：不要提取企业内部发文编号，如'晋煤化企管字[2025]73号'",
                    "如果没有明确标段号，不允许自动生成，且留空"
                ],
                keywords=["标段号"],
                examples=["002"]
            ),
            VariableDefinition(
                name="中标候选人得分汇总情况",
                english_name="candidate_score_summary",
                description="从评分汇总表格中提取前几名投标人名称以及各项的分值，然后按照排名顺序填写对应分值",
                data_type="str",
                extraction_rule=[
                    "在评分汇总表中，提取中标候选人的详细得分信息，输出为完整的HTML表格格式",
                    "投标报价和修正后报价需要分别在投标报价评分标准中提取对应的价格，如果有单位需要完整提取",
                    "投标报价在投标报价这一栏中提取",
                    "如果投标报价和修正后报价如果提取到的值没有单位需要根据文件中的内容判断并添加上正确的单位",
                    "修正后报价可能在算术修正价或评标价一栏中，以评标价优先，确保正确提取",
                    "表格必须使用<table>标签包裹，所有单元格都使用<td>标签",
                    "第一行为表头，包含：序号、候选人名称、投标报价、修正后报价、资信商务得分、技术服务得分、投标报价得分、其他部分得分、总分、排名",
                    "**重要：必须完整提取所有中标候选人的信息。** 后续行按排名顺序列出所有候选人的完整信息：第1名、第2名、第3名...第N名，确保提取表格中显示的所有候选人，不要遗漏任何候选人",
                    "如果文档中提到有多个候选人（如'第五中标候选人'、'第六中标候选人'等），请仔细检查评分汇总表或相关表格，确保提取了所有候选人的信息",
                    "如果表格中只显示了部分候选人（如前3名），但文档中明确提到还有其他候选人，请尽可能从文档的其他位置查找并补充完整信息",
                    "候选人名称保持完整，包含公司类型后缀",
                    "所有分值保持原文精度，包含小数点（如85.5分）",
                    "投标报价填写具体金额，保留小数位",
                    "若某项分值缺失，在对应单元格填写'-'或保留空白",
                    "表格格式示例：<table><tr><td>序号</td><td>候选人名称</td>...</tr><tr><td>1</td><td>候选人A</td>...</tr></table>",
                    "若无法获取完整的表格信息，则留空"
                ],
                keywords=["评分汇总"],
                examples=["<table><tr><td>序号</td><td>候选人名称</td><td>投标报价(万元)</td><td>修正后报价(万元)</td><td>资信商务得分</td><td>技术服务得分</td><td>投标报价得分</td><td>其他部分得分</td><td>总分</td><td>排名</td></tr><tr><td>1</td><td>候选人A</td><td>100.0</td><td>100.0</td><td>25.0</td><td>28.0</td><td>30.0</td><td>5.0</td><td>88.0</td><td>1</td></tr><tr><td>2</td><td>候选人B</td><td>95.0</td><td>95.0</td><td>23.0</td><td>26.0</td><td>32.0</td><td>4.0</td><td>85.0</td><td>2</td></tr></table>"]
            ),
            VariableDefinition(
                name="商务部分评分表",
                english_name="business_section_scoring_table",
                description="商务部分评分表",
                data_type="str",
                extraction_rule=[
                    "提取完整的商务部分评分表内容，包括所有投标人名称、评分条款、具体分数等",
                    "从'商务部分评分标准个人评分表'或'资信商务评分标准个人评分表'或'资信业绩评分标准个人评分表'开始，到表格结束的所有内容",
                    "重要：只提取个人评分表，不要提取包含专家姓名的评分表",
                    "排除规则：如果表格中包含专家姓名，则不要提取该表格",
                    "排除规则：如果表格的列标题是'专家/投标人'，则不要提取该表格",
                    "只提取评标条款和投标人对应的评分表，格式应该是：序号、评标条款/投标人、投标人1、投标人2等",
                    "包含所有投标人名称（如'保定市恒发发电设备有限公司'、'江苏中奕和创智能科技有限公司'等）",
                    "包含所有评分条款（如'投标人近年类似业绩'、'业主反馈'、'银行资信'、'综合实力'、'三体系认证','管理体系认证'等）",
                    "包含每个投标人在每个条款下的具体分数（包括整数和小数）",
                    "重要排除规则：不要提取以下条款：",
                    "- 总分、总分行",
                    "- 评议说明、评议说明行",
                    "- 标书质量",
                    "- 汇总、汇总行",
                    "- 其他非具体评分条款的汇总性内容",
                    "只提取具体的评分条款，如业绩、三体系认证、资信等具体评审项目",
                    "保持表格的完整结构，包括序号、评标条款/投标人列、各投标人列",
                    "确保所有投标人名称都要提取到，不要遗漏任何投标人",
                    "确保条款、分数都要正确，不要遗漏或错误",
                    "如果表格中有'/'符号，表示该投标人未参与或不符合条件，也要保留",
                    "提取时保持原有的表格格式和结构",
                    "由于表格可能跨页，需要确保完整提取所有内容",
                    "如果有多个人进行评分，但分数一致，只提取一份表格即可，避免重复提取相同的公司",
                    "去重规则：如果发现多个评分表包含相同的投标人公司，且分数相同，只保留一份",
                    "返回的内容必须用<table><tr><td>标签包裹，确保HTML表格格式正确",
                    "表格格式示例：<table><tr><td>序号</td><td>评标条款/投标人</td><td>投标人1</td><td>投标人2</td>...</tr><tr><td>1</td><td>投标人近年类似业绩</td><td>0</td><td>10</td>...</tr></table>",
                    "若没有找到商务部分评分表，则留空"
                ],
                keywords=["商务部分评分表", "商务部分评分标准", "个人评分表", "投标人", "评分条款","三体系认证"],
                examples=["商务部分评分标准个人评分表 武兴华"]
            ),
            
            VariableDefinition(
                name="商务部分评分表条款",
                english_name="business_section_scoring_clauses",
                description="商务部分评分表中的评标条款名称列表",
                data_type="str",
                extraction_rule=[
                    "从商务部分评分表中提取所有评标条款的名称",
                    "只提取条款名称，不包括分数、投标人名称等其他内容",
                    "需要排除的条款：",
                    "- 总分",
                    "- 评议说明",
                    "- 标书质量",
                    "- 三体系认证（或任何包含'三体系'的条款）",
                    "- 汇总",
                    "提取的条款名称要求：",
                    "- 去除条款名称中的分值范围（如【0~6】、（0-10分）、（4分）等括号内容）",
                    "- 只保留纯粹的条款名称",
                    "- 例如：'投标人近年类似业绩【0~6】' → 只提取 '投标人近年类似业绩'",
                    "- 例如：'业主反馈（0-2分）' → 只提取 '业主反馈'",
                    "- 例如：'银行资信[0~2]' → 只提取 '银行资信'",
                    "格式要求：",
                    "- 多个条款之间用顿号（、）分隔",
                    "- 不要使用逗号、分号或其他分隔符",
                    "- 不要在最后添加顿号",
                    "- 保持条款在表格中出现的顺序",
                    "示例输出格式：",
                    "- '投标人近年类似业绩、业主反馈、银行资信、综合实力'",
                    "- '类似项目业绩、企业获奖情况、资信证明'",
                    "注意事项：",
                    "- 确保提取的条款名称准确无误",
                    "- 不要遗漏任何有效的评标条款",
                    "- 如果条款名称有多种表述（如'投标人业绩'和'投标人近年类似业绩'），按表格中实际出现的名称提取",
                    "- 若没有找到有效的评标条款，则留空"
                ],
                keywords=["商务部分评分表", "评标条款", "评分标准", "条款名称"],
                examples=["投标人近年类似业绩、业主反馈、银行资信、综合实力"]
            ),
            VariableDefinition(
                name="资格评审标准表格",
                english_name="qualification_review_criteria_table",
                description="从资格评审标准表格中提取评审条款名称（排除指定条款）",
                data_type="str",
                extraction_rule=[
                    "【明确目标】在评标汇总文件中找到'资格评审标准'表格",
                    "【表格定位】查找标题为'资格评审标准'、'资格评审标准表'或类似标题的表格",
                    "【提取内容-关键】只提取评审条款的名称，不提取具体要求描述",
                    "【排除条款-必须遵守】必须排除以下条款，绝对不要提取：",
                    "  - 营业执照",
                    "  - 信誉要求",
                    "  - 其他要求",
                    "  - 其他否决投标情形",
                    "  - 汇总",
                    "  - 汇总行或总结行",
                    "  - 任何包含上述关键词的条款",
                    "【条款识别方法】：",
                    "  - 在表格中找到'评审因素'、'评审项'、'评审内容'、'条款名称'、'标准'等列",
                    "  - 提取该列中每一行的条款名称",
                    "  - 只提取条款名称本身，不提取具体要求或描述",
                    "  - 如果条款名称后面有冒号或其他符号，去掉符号只保留条款名称",
                    "【排除判断规则】：",
                    "  - 检查条款名称是否包含'营业执照'、'信誉要求'、'其他要求'、'其他否决投标情形'、'汇总'等关键词",
                    "  - 如果包含这些关键词（完全匹配或部分匹配），跳过该条款",
                    "  - 对于其他所有条款名称，都要提取并按规则简化",
                    "【输出格式-重要】：",
                    "  - 只返回纯文本格式，不要使用HTML表格标签",
                    "  - 多个条款名称之间用中文顿号'、'分隔",
                    "  - 不要添加序号、不要换行、不要添加其他标点符号",
                    "  - 格式示例：业绩、业绩要求、资质、资质要求、项目经理、项目经理要求、财务状况、财务要求",
                    "【完整性要求】：",
                    "  - 提取所有符合条件的条款名称，不要遗漏",
                    "  - 按照表格中的顺序提取（从上到下）",
                    "【边界控制】：",
                    "  - 只从'资格评审标准'这一个表格中提取",
                    "  - 不要从其他表格（如评分标准表、商务评分表等）提取",
                    "  - 遇到下一个表格标题时停止提取",
                    "【特殊情况处理】：",
                    "  - 如果某个条款有子项编号（如'1.业绩要求'），去掉编号，简化后输出'业绩要求'",
                    "  - 如果表格跨页，确保提取所有页的条款",
                    "若未找到资格评审标准表格，则留空"
                ],
                keywords=["资格评审标准", "评审因素", "评审标准", "业绩", "资质"],
                examples=[ ]
            )
            # "中标候选人详细评审客观分得分情况" 已移除
            # 原因：候选人的资质、业绩等详细信息在 candidate_bid_files 中
            # 在第四次模型调用时会从 candidate_bid_files 动态提取
        ]
    
    def _get_other_files_variables(self) -> List[VariableDefinition]:
        """获取其他相关文件的变量定义"""
        return [
            VariableDefinition(
                name="潜在投标人数",
                english_name="potential_bidders_count",
                description="潜在投标人数统计",
                data_type="int",
                extraction_rule=[
                    "统计表格中所有投标人的总数量，仅输出阿拉伯数字（不带'家'、'人'等单位）",
                    "查找包含'购标单位名称'、'供应商'、'投标人'等关键词的表格",
                    "统计表格中序号列的最大数值，或者统计有效投标人名称的行数",
                    "如果表格有序号列，以序号的最大值作为投标人总数",
                    "如果表格没有序号列，则统计包含投标人名称的有效行数",
                    "排除表头行，只统计数据行",
                    "若表格中有'是否下载'列，统计该列中为'是'的行数",
                    "确保统计的是实际参与投标的潜在投标人数量",
                    "若未找到相关表格或无法统计，留空"
                ],
                keywords=["购标单位名称", "供应商", "投标人", "序号", "是否下载", "下载记录"],
                examples=["32", "15", "8", "25"]
            ),
            VariableDefinition(
                name="否决投标情况说明",
                english_name="bid_rejection_notes",
                description="从评标报告、评标复核卡或评审记录中提取被否决投标人及其否决原因说明",
                data_type="str",
                extraction_rule=[
                    "从文档中提取所有被否决的投标人信息，用于生成标准化的否决情况说明表。",
                    "识别包含关键词的段落：‘被否决投标人’、‘否决原因’、‘招标文件要求’、‘投标人提供的证明材料’、‘评标委员会认为’等。",
                    "每个被否决投标人生成一行表格记录，表格包含四列：投标人名称、招标文件要求、投标人在投标文件中所附材料、评标委员会评审结论。",
                    "【投标人名称】：提取‘被否决投标人’后出现的公司名称；若多名投标人以顿号或逗号分隔，则为每个投标人分别提取并生成单独记录。",
                    "【招标文件要求】：从‘招标文件要求’或‘依据招标文件要求’开始提取，直到‘投标人提供的证明材料’或类似语句出现为止；保留完整章节号和要求原文。",
                    "【投标人在投标文件中所附材料】：从‘投标人提供的证明材料’、‘投标人递交的投标文件中提供了’等句式开始提取，直到出现‘评标委员会认为’前为止，保留业绩数量、项目内容、技术要点等信息。",
                    "【评标委员会评审结论】：从‘评标委员会认为’或‘评标委员会一致认为’开始提取，直至‘否决其投标’或该段结束；若存在‘视为串通投标’等其他情形，也应完整提取。",
                    "所有文本保持原文措辞和语序，不得改写或总结。",
                    "若同一公司在多个条款下被否决，可合并为同一行，条款间用换行或分号分隔。",
                    "输出格式为HTML表格，列名依次为：投标人名称、招标文件要求、投标人在投标文件中所附材料、评标委员会评审结论。",
                    "示例输出：<table><tr><td>投标人名称</td><td>招标文件要求</td><td>投标人在投标文件中所附材料</td><td>评标委员会评审结论</td></tr><tr><td>长治市山水智源地质勘察有限责任公司</td><td>第一章招标公告：三、投标人资格要求：3.3 投标人业绩要求：投标人近年具有1项类似项目业绩；类似业绩指：地面井抽采或钻孔技术研究业绩。</td><td>长治市山水智源地质勘察有限责任公司递交的投标文件中提供了1项业绩，该业绩内容为普通钻探井、地面煤层气抽采井施工，未包含技术研究，业绩类型不符合招标文件要求。</td><td>评标委员会一致认为上述证明材料不通过资格评审中业绩要求，否决其投标。</td></tr></table>",
                    "如果文档中未出现任何被否决投标人，则输出空表格或留空。"
                ],
                keywords=[
                    "被否决投标人", "否决原因", "招标文件要求", "资格评审", 
                    "评标委员会认为", "递交的投标文件", "提供的证明材料", "视为串通投标"
                ],
                examples=[
                    "<table><tr><td>投标人名称</td><td>招标文件要求</td><td>投标人在投标文件中所附材料</td><td>评标委员会评审结论</td></tr><tr><td>长治市山水智源地质勘察有限责任公司</td><td>第一章招标公告：三、投标人资格要求：3.3 投标人业绩要求：投标人近年具有1项类似项目业绩；类似业绩指：地面井抽采或钻孔技术研究业绩。</td><td>长治市山水智源地质勘察有限责任公司递交的投标文件中提供了1项业绩，该业绩内容为普通钻探井、地面煤层气抽采井施工，未包含技术研究，业绩类型不符合招标文件要求。</td><td>评标委员会一致认为上述证明材料不通过资格评审中业绩要求，否决其投标。</td></tr></table>"
                ]
            ),
            VariableDefinition(
                name="复核卡得分",
                english_name="review_card_score",
                description="从评审复核卡中提取对中标候选人详细评审中客观分项复核或中标候选人详细评审中客观得分情况的完整内容",
                data_type="str",
                extraction_rule=[
                    "【明确目标】只在评审复核卡文件中提取'对中标候选人详细评审中客观分项复核'或'中标候选人详细评审中客观得分情况'章节的全部内容",
                    "【章节定位】查找以下标题的章节：",
                    "  - '对中标候选人详细评审中客观分项复核'",
                    "  - '中标候选人详细评审中客观得分情况'",
                    "  - 或类似表述的章节标题（如'三、对中标候选人详细评审中客观分项复核'）",
                    "【完整提取】提取该章节下的全部内容，包括：",
                    "  - 章节标题",
                    "  - 所有子标题和说明文字",
                    "  - 所有表格内容（完整的行列结构）",
                    "  - 所有评审项目的详细信息",
                    "  - 各候选人的得分情况",
                    "  - 分值汇总和合计信息",
                    "【表格提取要求】对于表格内容：",
                    "  - 提取所有表头列（包括评审项、各中标候选人列等）",
                    "  - 提取所有数据行（包括各评审项的详细内容）",
                    "  - 保持原表格的完整结构和层次关系",
                    "  - 保留单元格合并信息（rowspan、colspan）",
                    "  - 包含所有得分项、描述、分值等完整信息",
                    "【边界控制】提取范围：",
                    "  - 从章节标题开始提取",
                    "  - 提取该章节下的全部内容",
                    "  - 直到遇到下一个主要章节标题（如'四、'、'五、'等）时停止",
                    "  - 不要遗漏中间的任何内容（文字、表格、说明等）",
                    "【格式要求】输出格式：",
                    "  - 使用标准HTML格式",
                    "  - 章节标题使用<h3>或<h4>标签",
                    "  - 表格使用<table><tr><td>标签，保持完整的表格结构",
                    "  - 文本段落使用<p>标签",
                    "  - 保持内容的原始排版和层次结构",
                    "  - 确保所有候选人的信息都完整呈现",
                    "【详细程度要求】：",
                    "  - 必须包含所有评审项目的详细描述",
                    "  - 必须包含每个项目各候选人的得分和评价",
                    "  - 必须包含所有备注和说明信息",
                    "  - 不要省略或简化任何内容",
                    "  - 如果有多个表格，全部提取",
                    "【特殊情况处理】：",
                    "  - 如果章节内容跨页，确保完整提取",
                    "  - 如果有嵌套表格，保持嵌套结构",
                    "  - 如果有附注或说明，一并提取",
                    "  - 空单元格保留为空，不要填充",
                    "【验证规则】提取后检查：",
                    "  - 必须包含评审项目的详细表格",
                    "  - 必须包含所有中标候选人的信息",
                    "  - 必须包含得分或评价信息",
                    "若评审复核卡中未找到该章节，则留空"
                ],
                keywords=["对中标候选人详细评审中客观分项复核", "中标候选人详细评审中客观得分情况", "客观分项复核", "客观得分"],
                examples=[]
            ),
            VariableDefinition(
                name="澄清说明补正事项纪要",
                english_name="clarification_summary",
                description="澄清、说明、补正事项纪要",
                data_type="str",
                extraction_rule=[
                    "暂不获取"
                ],
                keywords=[],
                examples=[]
            )
        ]
