# 异步文件处理工具类
import os
import shutil
import logging
import asyncio
import aiohttp
import warnings
from datetime import datetime
import uuid
from urllib.parse import urlparse
from typing import Union, List, Dict, Optional, Any, Tuple
import fitz  # PyMuPDF

# 抑制 openpyxl 的样式警告（不影响功能）
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')


class AsyncFileProcessor:
    """异步文件处理器 - 支持真正的异步文件下载和处理"""
    
    def __init__(self):
        """初始化异步文件处理器"""
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
    
    # ==================== 异步文件下载 ====================
    
    def _is_local_file_path(self, path: str) -> bool:
        """
        判断路径是否为本地文件路径
        
        Args:
            path: 文件路径或URL
            
        Returns:
            bool: 如果是本地文件路径返回True，否则返回False
        """
        # 检查是否为HTTP/HTTPS URL
        if path.startswith(('http://', 'https://')):
            return False
        
        # 检查是否为本地文件路径（存在且为文件）
        if os.path.exists(path) and os.path.isfile(path):
            return True
        
        # 对于Windows路径，检查是否以盘符开头（如 C:\）
        if len(path) >= 2 and path[1] == ':' and path[0].isalpha():
            return True
        
        # 对于Unix路径，检查是否以/开头
        if path.startswith('/'):
            return True
        
        return False
    
    async def download_file(self, urls: str, save_path: str) -> Tuple[bool, str]:
        """
        异步下载一个或多个URL的文件，或复制本地文件
        
        Args:
            urls: 字符串(英文逗号分隔)，包含要下载的URL或本地文件路径
            save_path: 保存目录路径
            
        Returns:
            tuple: (success, result) 
                - success (bool): 是否成功
                - result (str): 成功时的文件路径字符串或失败时的错误信息
        """
        # 将urls字符串按逗号分割为列表
        urls = [url.strip() for url in urls.split(',') if url.strip()]
        
        if not urls:
            raise ValueError("没有提供有效的URL或文件路径")
            
        # 确保save_path目录存在
        os.makedirs(save_path, exist_ok=True)
        
        successful_paths = []
        
        for url in urls:
            # 判断是否为本地文件路径
            if self._is_local_file_path(url):
                # 处理本地文件：直接复制
                try:
                    if not os.path.exists(url):
                        raise FileNotFoundError(f"本地文件不存在: {url}")
                    
                    # 获取文件名
                    file_name = os.path.basename(url)
                    if not file_name:
                        file_name = "local_file"
                    
                    current_save_path = os.path.join(save_path, file_name)
                    
                    logging.info(f"复制本地文件: {url} -> {current_save_path}")
                    
                    # 使用异步方式复制文件
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, shutil.copy2, url, current_save_path)
                    
                    logging.info(f"本地文件复制完成: {current_save_path}")
                    successful_paths.append(current_save_path)
                    
                except Exception as e:
                    logging.error(f"复制本地文件失败: {url}, 错误: {str(e)}")
                    raise Exception(f"复制本地文件失败: {str(e)}")
            else:
                # 处理HTTP/HTTPS URL：使用aiohttp下载
                # 创建连接器，增加连接池大小和超时设置
                connector = aiohttp.TCPConnector(
                    limit=100,
                    limit_per_host=30,
                    ttl_dns_cache=300,
                    use_dns_cache=True,
                    keepalive_timeout=30,
                    enable_cleanup_closed=True
                )
                
                # 设置更长的超时时间，针对大文件下载优化
                # 根据文件大小动态调整超时时间
                timeout = aiohttp.ClientTimeout(
                    total=3600,  # 总超时1小时 - 大文件下载需要更长时间
                    connect=60,  # 连接超时1分钟
                    sock_read=1800  # 读取超时30分钟 - 适应慢速网络和不稳定连接
                )
                
                async with aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                ) as session:
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            # 为每个URL生成唯一的保存路径
                            file_name = os.path.basename(urlparse(url).path)
                            if not file_name:
                                file_name = "downloaded_file"
                            current_save_path = os.path.join(save_path, file_name)
                            
                            logging.info(f"开始下载文件 (尝试 {attempt + 1}/{max_retries}): {url}")
                            
                            # 异步下载文件
                            async with session.get(url) as response:
                                response.raise_for_status()
                                
                                # 检查内容长度
                                content_length = response.headers.get('Content-Length')
                                if content_length:
                                    logging.info(f"文件大小: {content_length} bytes")
                                
                                # 使用异步文件写入，避免阻塞事件循环
                                loop = asyncio.get_event_loop()
                                downloaded_size = 0
                                
                                with open(current_save_path, 'wb') as f:
                                    async for chunk in response.content.iter_chunked(8192):
                                        if chunk:  # 确保chunk不为空
                                            # 在线程池中执行文件写入，避免阻塞事件循环
                                            await loop.run_in_executor(None, f.write, chunk)
                                            downloaded_size += len(chunk)
                                            
                                            # 每下载1MB打印一次进度
                                            if downloaded_size % (1024 * 1024) == 0:
                                                logging.info(f"已下载: {downloaded_size} bytes")
                                
                                # 验证文件大小
                                if content_length and downloaded_size != int(content_length):
                                    logging.warning(f"文件大小不匹配: 期望 {content_length}, 实际 {downloaded_size}")
                                    if attempt < max_retries - 1:
                                        logging.info(f"重试下载...")
                                        continue
                                
                                logging.info(f"文件 {url} 异步下载完成，保存至：{current_save_path}")
                                successful_paths.append(current_save_path)
                                break  # 成功下载，跳出重试循环
                                
                        except aiohttp.ClientPayloadError as e:
                            logging.error(f"内容长度错误 (尝试 {attempt + 1}/{max_retries}): {url}, 错误: {str(e)}")
                            if attempt < max_retries - 1:
                                logging.info(f"等待 {2 ** attempt} 秒后重试...")
                                await asyncio.sleep(2 ** attempt)  # 指数退避
                                continue
                            else:
                                raise Exception(f"文件异步下载失败: 内容长度错误 - {str(e)}")
                                
                        except aiohttp.ClientConnectorError as e:
                            logging.error(f"连接错误 (尝试 {attempt + 1}/{max_retries}): {url}, 错误: {str(e)}")
                            if attempt < max_retries - 1:
                                logging.info(f"等待 {2 ** attempt} 秒后重试...")
                                await asyncio.sleep(2 ** attempt)  # 指数退避
                                continue
                            else:
                                raise Exception(f"文件异步下载失败: 连接错误 - {str(e)}")
                                
                        except asyncio.TimeoutError as e:
                            logging.error(f"下载超时 (尝试 {attempt + 1}/{max_retries}): {url}, 错误: {str(e)}")
                            if attempt < max_retries - 1:
                                logging.info(f"等待 {2 ** attempt} 秒后重试...")
                                await asyncio.sleep(2 ** attempt)  # 指数退避
                                continue
                            else:
                                raise Exception(f"文件异步下载失败: 下载超时 - {str(e)}")
                                
                        except Exception as e:
                            logging.error(f"文件异步下载失败 (尝试 {attempt + 1}/{max_retries}): {url}, 错误: {str(e)}")
                            if attempt < max_retries - 1:
                                logging.info(f"等待 {2 ** attempt} 秒后重试...")
                                await asyncio.sleep(2 ** attempt)  # 指数退避
                                continue
                            else:
                                raise Exception(f"文件异步下载失败: {str(e)}")
        
        # 返回成功路径
        logging.info(f"异步下载成功: {successful_paths}")
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
        """
        # 获取文件扩展名
        _, ext = os.path.splitext(file_path)
        ext = ext.lower().lstrip('.')
        
        # 映射常见扩展名
        format_mapping = {
            'pdf': 'pdf',
            'xlsx': 'xlsx',
            'xls': 'xls'
        }
        
        return format_mapping.get(ext, ext)
    
    # ==================== 文件内容提取方法 ====================
    
    def _extract_pdf_content(self, file_path: str) -> Optional[str]:
        """
        提取PDF文件内容
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            str: 提取的文本内容
        """
        try:
            content = []
            doc = fitz.open(file_path)
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    content.append(f"=== 第{page_num + 1}页 ===\n{text}")
            
            doc.close()
            return "\n\n".join(content)
            
        except Exception as e:
            logging.error(f"PDF内容提取失败: {file_path}, 错误: {e}")
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
            
            # 根据文件扩展名确定引擎
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # 根据文件扩展名选择合适的engine
            if file_ext == '.xlsx':
                engine = 'openpyxl'
            elif file_ext == '.xls':
                engine = 'xlrd'
            else:
                engine = None  # 让pandas自动检测
            
            # 使用上下文管理器确保ExcelFile正确关闭
            with pd.ExcelFile(file_path, engine=engine) as excel_file:
                content_parts = []
                
                for sheet_name in excel_file.sheet_names:
                    # 根据文件扩展名确定引擎
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
                        # 使用to_string()方法，设置合适的参数
                        text_content = df.to_string(index=True, header=True, na_rep='')
                        content_parts.append(text_content)
                    else:
                        content_parts.append("(空工作表)")
                    
                    content_parts.append("")  # 添加空行分隔
                
                return "\n".join(content_parts)
            
        except Exception as e:
            logging.error(f"Excel内容提取失败: {file_path}, 错误: {e}")
            return None

