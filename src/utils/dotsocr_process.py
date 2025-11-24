# -*- coding: utf-8 -*-
"""
DotsOCR PDF处理器
将DotsOCR API的PDF提取功能集成到现有项目架构中，替换MinerU
保持与原MinerU相同的接口和数据格式
"""

import os
import re
import logging
import requests
import time
from typing import List, Dict, Optional, Union

# 配置日志
logger = logging.getLogger(__name__)

class DotsOCRProcessor:
    """DotsOCR PDF处理器类，兼容MinerU接口"""
    
    def __init__(self, server_url: str = "http://192.168.1.94:8089", timeout: int = 600):
        """
        初始化DotsOCR处理器
        
        Args:
            server_url: DotsOCR服务器地址
            timeout: 请求超时时间（秒）
        """
        self.server_url = server_url
        self.timeout = timeout
        self.api_endpoint = f"{server_url}/parse-pdf-to-md"
    
    def call_dotsocr_api(self, pdf_file_path: str) -> Optional[str]:
        """
        调用DotsOCR API处理PDF文件
        
        Args:
            pdf_file_path: PDF文件路径
            
        Returns:
            str: 解析后的文本内容，失败时返回None
        """
        logger.info(f"使用DotsOCR API处理PDF文件: {pdf_file_path}")
        
        if not os.path.exists(pdf_file_path):
            logger.error(f"PDF文件不存在: {pdf_file_path}")
            return None

        headers = {
            'accept': 'text/plain',
        }

        try:
            with open(pdf_file_path, 'rb') as f:
                files = {
                    'pdf_file': (os.path.basename(pdf_file_path), f, 'application/pdf')
                }
                response = requests.post(
                    self.api_endpoint, 
                    headers=headers, 
                    files=files, 
                    timeout=self.timeout
                )
                response.raise_for_status()
                logger.info(f"DotsOCR API调用成功")
                return response.text
                
        except requests.exceptions.RequestException as e:
            logger.error(f"DotsOCR API调用失败: {e}")
            return None

    def clean_text_content(self, content: str) -> str:
        """
        清理文本内容，只移除[前面紧挨着的数字
        
        Args:
            content: 原始文本内容
            
        Returns:
            str: 清理后的文本内容
        """
        if not content:
            return content
            
        lines = content.splitlines()
        cleaned_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # 跳过空行
            if not line_stripped:
                continue
                
            # 只处理一种情况：移除[前面紧挨着的数字
            # 匹配模式如 "43|[页码：54]" -> "[页码：54]"
            cleaned_line = re.sub(r'^\d+\|', '', line_stripped)
            
            # 如果清理后还有内容，添加到结果中
            if cleaned_line.strip():
                cleaned_lines.append(cleaned_line.strip())
        
        return "\n".join(cleaned_lines)

    def parse_dotsocr_to_pages(self, parsed_data: str, filename: str) -> List[Dict]:
        """
        将DotsOCR返回的文本解析为页面列表格式（兼容MinerU格式）
        
        Args:
            parsed_data: DotsOCR返回的文本数据
            filename: 文件名
            
        Returns:
            List[Dict]: 页面内容列表，每个dict包含content、page、file_name字段
        """
        if not parsed_data:
            return []
        
        page_contents = {}
        current_page = 0
        current_content = []

        lines = parsed_data.splitlines()
        for line in lines:
            line_stripped = line.strip()
            # 匹配页码标记 "==第X页=="
            if line_stripped.startswith("==第") and line_stripped.endswith("页=="):
                # 保存前一页内容
                if current_page != 0:
                    page_contents[current_page] = "\n".join(current_content).strip()
                    current_content = []
                
                # 提取页码
                try:
                    page_match = re.search(r"==第(\d+)页==", line_stripped)
                    if page_match:
                        current_page = int(page_match.group(1))
                    else:
                        current_page = 0
                except (ValueError, AttributeError):
                    current_page = 0
                    
            elif current_page != 0 and line_stripped:  # 只添加非空行
                # 收集当前页内容
                current_content.append(line_stripped)
        
        # 添加最后一页内容
        if current_page != 0 and current_content:
            page_contents[current_page] = "\n".join(current_content).strip()

        # 转换为MinerU兼容格式
        result = []
        base_filename = os.path.basename(filename) if filename else "unknown.pdf"
        
        for page_num in sorted(page_contents.keys()):
            content = page_contents[page_num]
            if content.strip():  # 只添加非空内容
                # 清理页面内容
                cleaned_content = self.clean_text_content(content)
                if cleaned_content.strip():  # 确保清理后还有内容
                    result.append({
                        "content": cleaned_content,
                        "page": page_num,
                        "file_name": base_filename
                    })
        
        return result
    
    def format_to_text_with_pages(self, page_data: List[Dict]) -> str:
        """
        将页面数据格式化为带页码的文本格式
        
        Args:
            page_data: 页面数据列表
            
        Returns:
            str: 格式化后的文本，每页以"===== 第X页 ====="分隔
        """
        if not page_data:
            return ""
        
        merged = []
        for page_info in page_data:
            page_num = page_info.get("page", 1)
            content = page_info.get("content", "")
            if content.strip():
                merged.append(f"\n===== 第{page_num}页 =====")
                merged.append(content.strip())
        
        return "\n".join(merged)
    
    def extract_pdf_with_dotsocr(self, pdf_path: str, output_format: str = "page_content") -> Union[List[Dict], str, None]:
        """
        使用DotsOCR提取PDF内容的主要接口（兼容MinerU接口）
        
        Args:
            pdf_path: PDF文件路径
            output_format: 输出格式，可选值：
                         - "page_content": 返回页面内容字典列表（兼容现有系统）
                         - "text_with_pages": 返回带页码分隔的文本字符串
                         - "raw": 返回原始DotsOCR解析数据
                         
        Returns:
            根据output_format返回不同格式的数据，失败时返回None
        """
        try:
            # 直接使用DotsOCR API处理
            logger.info(f"使用DotsOCR处理PDF文件: {pdf_path}")
            parsed_text = self.call_dotsocr_api(pdf_path)
            if not parsed_text:
                logger.error("DotsOCR解析PDF失败")
                return None
            
            # 根据输出格式返回相应数据
            if output_format == "raw":
                return parsed_text
            elif output_format == "text_with_pages":
                # 直接返回DotsOCR的原始文本（已包含页码分隔）
                return parsed_text
            elif output_format == "page_content":
                # 解析为页面列表格式
                return self.parse_dotsocr_to_pages(parsed_text, pdf_path)
            else:
                logger.error(f"不支持的输出格式: {output_format}")
                return None
                
        except Exception as e:
            logger.error(f"PDF提取内容时发生异常: {str(e)}")
            return None
    
    def extract_scanned_pdf_with_dotsocr(self, pdf_path: str, output_format: str = "page_content") -> Union[List[Dict], str, None]:
        """
        使用DotsOCR处理扫描PDF（与普通PDF处理相同，DotsOCR本身就支持OCR）
        
        Args:
            pdf_path: PDF文件路径
            output_format: 输出格式
            
        Returns:
            根据output_format返回不同格式的数据，失败时返回None
        """
        logger.info(f"使用DotsOCR处理扫描PDF: {pdf_path}")
        # DotsOCR本身就支持OCR，所以直接调用主要接口
        return self.extract_pdf_with_dotsocr(pdf_path, output_format)
    
    def is_available(self) -> bool:
        """
        检查DotsOCR服务是否可用
        
        Returns:
            bool: 服务可用返回True，否则返回False
        """
        try:
            # 尝试访问服务器根路径或健康检查接口
            response = requests.post(f"{self.server_url}/", timeout=10)
            return response.status_code in [200, 404, 405]  # 服务器响应即认为可用
        except:
            try:
                # 尝试访问主要API端点
                response = requests.post(self.api_endpoint, timeout=10)
                return response.status_code in [200, 400, 405, 422]  # 各种响应都表示服务在运行
            except:
                return False

# 全局处理器实例
_dotsocr_processor = DotsOCRProcessor()

# 兼容函数（保持与MinerU相同的函数名和接口）
def extract_pdf_with_dotsocr(pdf_path: str, output_format: str = "page_content") -> Union[List[Dict], str, None]:
    """
    全局函数：使用DotsOCR提取PDF内容（兼容extract_pdf_with_mineru）
    """
    return _dotsocr_processor.extract_pdf_with_dotsocr(pdf_path, output_format)

def extract_scanned_pdf_with_dotsocr(pdf_path: str, output_format: str = "page_content") -> Union[List[Dict], str, None]:
    """
    全局函数：使用DotsOCR处理扫描PDF（兼容extract_scanned_pdf_with_mineru）
    """
    return _dotsocr_processor.extract_scanned_pdf_with_dotsocr(pdf_path, output_format)

def is_dotsocr_available() -> bool:
    """
    全局函数：检查DotsOCR服务是否可用（兼容is_mineru_available）
    """
    return _dotsocr_processor.is_available()

# 为了完全兼容，提供MinerU函数名的别名
extract_pdf_with_mineru = extract_pdf_with_dotsocr
extract_scanned_pdf_with_mineru = extract_scanned_pdf_with_dotsocr
is_mineru_available = is_dotsocr_available

def test_text_cleaning():
    """测试文本清理功能"""
    processor = DotsOCRProcessor()
    
    # 测试文本（模拟你遇到的问题）
    test_text = """42|48
    43|[页码：54] 山西省阳泉荫营煤业有限责任公司黄土采购招标文件
    2024年6月10日
    供应商需按照采购方指定的送货时间和送货地点完成送货；采购方对供应的黄土在收货时发现如有不符合质量要求的一律做退货处理（退货所发生的费用均由供应方承担）。
    ## 六、检验要求
    黄土按采购方要求运至采购方指定地点过磅，运达采购方指定地点卸车后，由双方组织相关部门（采购方安全环保部、救护消防中队保卫、车队、供应部、运销部及供应方负责人）现场确认后签字为准。
    黄土运输量预估为30.86万吨，超出部分采购方概不负责。
    ## 七、合同价款及支付方式
    1. 付款条件：完成服务期内的黄土采购工作，出卖方提供黄土的实际采购数量，黄土的实际采购数量需经采购方运销部、供应部、车队及供应方负责人签字盖章确认。采购方运销部提供所采购黄土过磅数据的情况说明或记录依据。
    2. 付款方式：完成服务期内的黄土采购工作，出卖方提供黄土的实际采购数量乘以合同规定的单价所计算出的费用签字盖章后，报送荫营煤业安全环保部，并开具增值税专用发票进行挂账，12个月分次付清。
    结算货款=合同单价（元/吨）×实际采购量（吨）
    ## 八、报价范围与要求
    1. 固定单价合同，费用组成包括但不限于：含挖土、装车、篷布苫盖、运土、卸土、清理机下余土等，空回、场内道路洒水等所有费用。
    2. 报价不得超过控制价。
    3. 以投标总价计算报价得分。
    ## 九、其他要求
    1. 双方在本项目合同订立、履行中知悉对方的技术信息和经营信息均负有保密义务，不得泄露或不正当使用，泄露或不正当使用该信息给对方造成损失的，应当承担赔偿责任。
    2. 合同签订后任何一方不得单独终止、修改本项目合同，如需修改或终止本项目合同，需经双方协商一致达成共识后进行。
    3. 供应方要确保按期按质完成工作，采购方除按合同规定支付的费用外，不再支付其它任何费用。
    4. 双方因履行本项目合同而发生的争议，依法向阳泉市郊区人民法院起诉。
    晋能控股集团山西工程咨询有限公司
    49
    [页码：55] 山西省阳泉荫营煤业有限责任公司黄土采购招标文件
    """
    
    print("原始文本:")
    print("=" * 50)
    print(test_text)
    print("\n" + "=" * 50)
    
    cleaned_text = processor.clean_text_content(test_text)
    print("清理后文本:")
    print("=" * 50)
    print(cleaned_text)
    print("=" * 50)

if __name__ == "__main__":
    # 测试文本清理功能
    test_text_cleaning()
    
    # 测试DotsOCR处理器
    processor = DotsOCRProcessor()
    
    # 测试PDF文件路径
    test_pdf = "/Users/aurora/Documents/work/hzb_code_jn/catalog/黃土采购项目招标资料要求.pdf"
    
    if os.path.exists(test_pdf):
        print(f"测试DotsOCR处理器: {test_pdf}")
        
        # 测试服务可用性
        if processor.is_available():
            print("DotsOCR服务可用")
            
            # 测试PDF解析
            result = processor.extract_pdf_with_dotsocr(test_pdf, "page_content")
            if result:
                # 保存为txt
                with open(os.path.join(os.getcwd(), 'result.txt'), 'w', encoding='utf-8') as f:
                    if isinstance(result, list):
                        # 如果是页面内容列表，格式化为文本
                        formatted_text = processor.format_to_text_with_pages(result)
                        f.write(formatted_text)
                    else:
                        # 如果是字符串，直接写入
                        f.write(str(result))
            else:
                print("PDF解析失败")
        else:
            print("DotsOCR服务不可用")
    else:
        print(f"测试文件不存在: {test_pdf}")
