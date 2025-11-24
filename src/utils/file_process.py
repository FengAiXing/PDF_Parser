# 文件处理工具类
import os
import shutil
import logging
import warnings
from datetime import datetime
import uuid
import requests
from urllib.parse import urlparse
from tqdm import tqdm
from typing import Union, List, Dict, Optional, Any, Tuple
import fitz  # PyMuPDF

# 抑制 openpyxl 的样式警告（不影响功能）
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')


class FileProcessor:
    """文件处理器 - 统一管理所有文件处理相关功能"""
    
    def __init__(self):
        """初始化文件处理器"""
        self.supported_formats = {
            'pdf': self._extract_pdf_content,
            'xlsx': self._extract_excel_content,
            'xls': self._extract_excel_content
        }
    
    # ==================== 临时目录管理 ====================
    
    def create_temp_directory(self) -> str:
        """
        在当前目录下创建一个临时目录，并返回其路径
        
        Returns:
            str: 创建的临时目录路径
        """
        # 获取当前工作目录
        current_dir = os.getcwd()
        
        # 创建临时目录名称：时间戳 + 随机字符串
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = str(uuid.uuid4())[:8]
        temp_dir_name = f"temp_bid_report_{timestamp}_{random_suffix}"
        
        # 在当前目录下创建临时目录
        data_save_directory = os.path.join(current_dir, temp_dir_name)
        
        # 创建目录
        os.makedirs(data_save_directory, exist_ok=True)
        
        logging.info(f"创建临时目录: {data_save_directory}")
        return data_save_directory
    
    def cleanup_temp_directory(self, temp_directory: str) -> bool:
        """
        安全地清理临时目录
        
        Args:
            temp_directory (str): 要清理的临时目录路径
            
        Returns:
            bool: 清理是否成功
        """
        if not temp_directory:
            return True
            
        try:
            if os.path.exists(temp_directory):
                # 检查是否是临时目录（防止误删其他目录）
                if "temp_bid_report_" in temp_directory:
                    # 尝试清理，如果失败则重试
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            shutil.rmtree(temp_directory)
                            logging.info(f"成功清理临时目录: {temp_directory}")
                            return True
                        except PermissionError as pe:
                            if attempt < max_retries - 1:
                                logging.warning(f"清理临时目录失败（尝试 {attempt + 1}/{max_retries}）: {temp_directory}, 错误: {str(pe)}，等待后重试...")
                                import time
                                time.sleep(0.5)  # 等待500ms后重试
                            else:
                                logging.error(f"清理临时目录失败，已重试 {max_retries} 次: {temp_directory}, 错误: {str(pe)}")
                                return False
                        except Exception as e:
                            logging.error(f"清理临时目录时发生意外错误: {temp_directory}, 错误: {str(e)}")
                            return False
                    return False
                else:
                    logging.warning(f"拒绝清理非临时目录: {temp_directory}")
                    return False
            else:
                # logging.info(f"临时目录不存在，无需清理: {temp_directory}")
                return True
        except Exception as e:
            logging.error(f"清理临时目录失败: {temp_directory}, 错误: {str(e)}")
            return False
    
    # ==================== 文件下载 ====================
    
    def download_file(self, urls: str, save_path: str) -> Tuple[bool, str]:
        """
        下载一个或多个URL的文件
        
        Args:
            urls: 字符串(英文逗号分隔)，包含要下载的URL
            save_path: 保存目录路径
            
        Returns:
            tuple: (success, result) 
                - success (bool): 是否成功
                - result (str): 成功时的文件路径字符串或失败时的错误信息
        """
        # 将urls字符串按逗号分割为列表
        urls = [url.strip() for url in urls.split(',') if url.strip()]
        
        if not urls:
            raise ValueError("没有提供有效的URL")
            
        # 确保save_path目录存在
        os.makedirs(save_path, exist_ok=True)
        
        successful_paths = []
        
        for url in urls:
            try:
                # 为每个URL生成唯一的保存路径
                file_name = os.path.basename(urlparse(url).path)
                if not file_name:
                    file_name = "downloaded_file"
                current_save_path = os.path.join(save_path, file_name)
                
                # 直接发起GET请求，从响应头获取文件大小
                response = requests.get(url, stream=True, timeout=180)
                response.raise_for_status()
                
                # 从GET响应头中获取文件大小
                content_length = int(response.headers.get('Content-Length', 0))

                with open(current_save_path, "wb") as f, tqdm(
                        total=content_length,
                        unit='B',
                        unit_scale=True,
                        desc=f'下载进度 - {file_name}'
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
                            
                logging.info(f"文件 {url} 下载完成，保存至：{current_save_path}")
                successful_paths.append(current_save_path)
                
            except Exception as e:
                logging.error(f"文件下载失败: {url}, 错误: {str(e)}")
                raise Exception(f"文件下载失败: {str(e)}")
        
        # 返回成功路径
        logging.info(f"下载成功: {successful_paths}")
        return True, ",".join(successful_paths)
    
    # ==================== 文件内容提取 ====================
    
    def extract_file_content(self, file_path: str, file_format: str = None) -> Optional[str]:
        """
        智能提取文件内容 - 自动检测文件类型并选择相应的处理方法

        Args:
            file_path: 文件路径
            file_format: 文件格式（可选，如果不提供则自动检测）

        Returns:
            str: 提取的文件内容，失败时返回None
            
        Raises:
            ValueError: 不支持的文件格式
        """
        try:
            # 如果没有提供文件格式，则自动检测
            if file_format is None:
                file_format = self._detect_file_format_from_path(file_path)
                logging.info(f"自动检测文件格式: {file_path} -> {file_format}")
            
            # 验证文件格式是否支持
            if file_format not in self.supported_formats:
                error_msg = f"不支持的文件格式: {file_format}。支持的格式: {list(self.supported_formats.keys())}"
                logging.error(error_msg)
                raise ValueError(error_msg)

            # 使用对应的提取方法
            extractor_func = self.supported_formats[file_format]
            content = extractor_func(file_path)

            if content:
                logging.info(f"成功提取文件内容: {file_path} ({file_format})") 
                return content
            else:
                logging.error(f"文件内容提取失败: {file_path}")
                return None
                
        except ValueError:
            # 重新抛出ValueError，让上层处理
            raise
        except Exception as e:
            logging.error(f"提取文件内容时发生错误: {file_path}, 错误: {e}")
            return None
    
    def _detect_file_format_from_path(self, file_path: str) -> str:
        """
        从文件路径检测文件格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 检测到的文件格式
            
        Raises:
            ValueError: 不支持的文件格式
        """
        try:
            # 获取文件扩展名
            file_extension = os.path.splitext(file_path)[1].lower()
            logging.info(f"检测文件扩展名: {file_extension}")
            
            # 扩展名映射
            extension_map = {
                '.pdf': 'pdf',
                '.xlsx': 'xlsx',
                '.xls': 'xls'
            }
            
            if file_extension in extension_map:
                return extension_map[file_extension]
            else:
                # 不支持的文件格式，抛出异常
                error_msg = f"不支持的文件格式: {file_extension}。支持的格式: {list(extension_map.keys())}"
                logging.error(error_msg)
                raise ValueError(error_msg)
                
        except Exception as e:
            if isinstance(e, ValueError):
                raise e  # 重新抛出ValueError
            else:
                logging.error(f"文件格式检测失败: {file_path}, 错误: {e}")
                raise ValueError(f"文件格式检测失败: {str(e)}")
    
    def _extract_pdf_content(self, file_path: str) -> Optional[str]:
        """
        智能提取PDF文件内容
        优先使用PyMuPDF处理文本PDF，扫描件使用DotsOCR
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            str: PDF文件内容
        """
        try:
            # 首先检测PDF类型
            pdf_type = self._detect_pdf_type(file_path)
            
            if pdf_type == "text":
                # 文本PDF，使用PyMuPDF快速处理
                logging.info(f"检测到文本PDF，使用PyMuPDF处理: {file_path}")
                content = self._extract_pdf_with_pymupdf(file_path)
            elif pdf_type == "scanned":
                # 扫描件，使用DotsOCR处理
                logging.info(f"检测到扫描件，使用DotsOCR处理: {file_path}")
                content = self._extract_pdf_with_dotsocr(file_path)
            else:
                # 混合类型，先尝试PyMuPDF，失败则使用DotsOCR
                logging.info(f"检测到混合PDF，先尝试PyMuPDF: {file_path}")
                content = self._extract_pdf_with_pymupdf(file_path)
                
                if not content or len(content.strip()) < 50:
                    logging.info(f"PyMuPDF提取内容不足，切换到DotsOCR: {file_path}")
                    content = self._extract_pdf_with_dotsocr(file_path)
            
            return content
                
        except Exception as e:
            logging.error(f"PDF内容提取失败: {file_path}, 错误: {e}")
            return None
    
    def _detect_pdf_type(self, file_path: str) -> str:
        """
        检测PDF类型：文本PDF、扫描件或混合类型
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            str: PDF类型 ("text", "scanned", "mixed")
        """
        try:
            doc = fitz.open(file_path)
            
            # 检查前几页来确定PDF类型
            text_pages = 0
            image_pages = 0
            total_pages = min(len(doc), 3)  # 只检查前3页
            
            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                
                # 获取文本内容
                text = page.get_text()
                
                # 获取图片数量
                image_list = page.get_images()
                
                if len(text.strip()) > 100:
                    # 有足够的文本内容
                    text_pages += 1
                elif len(image_list) > 0:
                    # 有图片但文本很少，可能是扫描件
                    image_pages += 1
            
            doc.close()
            
            # 根据统计结果判断PDF类型
            if text_pages > image_pages:
                return "text"
            elif image_pages > text_pages:
                return "scanned"
            else:
                return "mixed"
                
        except Exception as e:
            logging.error(f"PDF类型检测失败: {file_path}, 错误: {e}")
            # 检测失败时，默认按混合类型处理
            return "mixed"
    
    def _extract_pdf_with_pymupdf(self, file_path: str) -> Optional[str]:
        """
        使用PyMuPDF提取PDF内容
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            str: 提取的文本内容
        """
        try:
            doc = fitz.open(file_path)
            text_content = []
            
            for page_num in range(len(doc)):
                try:
                    page = doc.load_page(page_num)
                    page_text = page.get_text()
                    
                    if page_text.strip():
                        text_content.append(f"==第{page_num + 1}页==")
                        text_content.append(page_text.strip())
                        text_content.append("")
                        
                except Exception as e:
                    logging.warning(f"处理第{page_num + 1}页时出错: {e}")
                    continue
            
            doc.close()
            
            if text_content:
                return "\n".join(text_content)
            else:
                logging.warning("PyMuPDF未提取到任何内容")
                return None
                
        except Exception as e:
            logging.error(f"PyMuPDF处理失败: {file_path}, 错误: {e}")
            return None
    
    def _extract_pdf_with_dotsocr(self, file_path: str) -> Optional[str]:
        """
        使用DotsOCR提取PDF内容
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            str: 提取的文本内容
        """
        try:
            from src.utils.dotsocr_process import DotsOCRProcessor
            processor = DotsOCRProcessor()
            return processor.call_dotsocr_api(file_path)
        except Exception as e:
            logging.error(f"DotsOCR处理失败: {file_path}, 错误: {e}")
            return None
    
    def _extract_excel_content(self, file_path: str) -> Optional[str]:
        """
        提取Excel文件内容
        
        Args:
            file_path: Excel文件路径
            
        Returns:
            str: 提取的文本内容
        """
        try:
            import pandas as pd
            
            # 使用上下文管理器确保ExcelFile正确关闭
            with pd.ExcelFile(file_path) as excel_file:
                content_parts = []
                
                for sheet_name in excel_file.sheet_names:
                    # 根据文件扩展名确定引擎
                    file_ext = os.path.splitext(file_path)[1].lower()
                    
                    if file_ext == '.xlsx':
                        df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
                    elif file_ext == '.xls':
                        df = pd.read_excel(file_path, sheet_name=sheet_name, engine='xlrd')
                    else:
                        # 尝试自动检测
                        df = pd.read_excel(file_path, sheet_name=sheet_name)
                    
                    # 添加工作表标题
                    content_parts.append(f"=== 工作表: {sheet_name} ===")
                    
                    # 将DataFrame转换为文本
                    if not df.empty:
                        text_content = df.to_string(index=True, header=True, na_rep='')
                        content_parts.append(text_content)
                    else:
                        content_parts.append("(空工作表)")
                    
                    content_parts.append("")  # 添加空行分隔
                
                return "\n".join(content_parts)
                
        except Exception as e:
            logging.error(f"Excel内容提取失败: {file_path}, 错误: {e}")
            return None