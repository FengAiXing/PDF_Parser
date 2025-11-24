# -*- coding: utf-8 -*-
"""
AI模型处理器 - 可复用的AI模型调用工具类

这个模块提供了一个统一的接口来调用各种AI模型（文本模型、视觉模型），
可以在其他项目中轻松集成和使用。

主要功能：
1. 文本大模型调用 - 用于信息提取和分析
2. 视觉大模型调用 - 用于图片内容识别
3. 图片预处理 - 自动压缩和编码
4. 并发配置 - 提供并发参数配置（线程池大小、协程并发数等）

使用说明：
==========

基础使用：
---------
```python
from ai_model_processor import AIModelProcessor

# 初始化处理器（使用默认配置）
processor = AIModelProcessor()

# 或者使用自定义配置
processor = AIModelProcessor(
    text_model_url="https://api.example.com/v1/chat/completions",
    text_model_name="text_model",
    text_model_password="your-api-key",
    pic_model_url="https://api.example.com/v1/chat/completions",
    pic_model_name="vision-model",
    pic_model_password="your-api-key"
)

# 调用文本模型提取信息
result = processor.extract_text(prompt="提取以下文本的关键信息：...")
print(result)

# 调用视觉模型识别图片
text_content, image_path = processor.extract_text_from_image(
    image_path="path/to/image.jpg"
)
print(text_content)
```

配置说明：
---------
可以通过初始化参数或配置类来设置：

1. 模型配置：
   - text_model_url: 文本模型API地址
   - text_model_name: 文本模型名称
   - text_model_password: 文本模型API密钥
   - pic_model_url: 视觉模型API地址
   - pic_model_name: 视觉模型名称
   - pic_model_password: 视觉模型API密钥

2. 超时和重试配置：
   - text_read_timeout: 文本模型读取超时（秒）
   - text_connect_timeout: 文本模型连接超时（秒）
   - pic_read_timeout: 视觉模型读取超时（秒）
   - pic_connect_timeout: 视觉模型连接超时（秒）
   - max_retries: 最大重试次数
   - pic_max_retries: 视觉模型最大重试次数
   - retry_delay: 重试延迟（秒）
   - max_timeout_retries: 超时重试最大次数

3. API调用间隔配置：
   - api_call_min_intervals: 按API类型分别配置调用间隔

4. 并发配置：
   - text_max_workers: 文本模型线程池最大工作线程数，默认20（用于配置，实际使用时由调用方创建线程池）
   - pic_max_workers: 视觉模型线程池最大工作线程数，默认20（用于配置，实际使用时由调用方创建线程池）
   - max_concurrent_coroutines: 协程最大并发数，默认20（用于配置，实际使用时由调用方创建信号量）

5. 图片处理配置：
   - image_quality: 图片JPEG质量（1-100），默认95
   - detail: 图像理解精度模式，'high' 或 'low'，默认'high'
     * detail所对应的图片像素大小是根据doubao-seed-1-6-vision-250815所支持的传输大小来决定的，参考https://www.volcengine.com/docs/82379/1362931
     * 'high': 高精度理解，压缩至约401万像素（2048×1960）
     * 'low': 低精度理解，压缩至约104万像素（1024×1024）

图片处理说明：
-------------
图片会自动根据配置的detail模式进行压缩，压缩遵循API规范，避免不必要的传输浪费。

注意事项：
---------
1. 确保网络连接正常，能够访问API地址
2. API密钥需要正确配置，否则会调用失败
3. 图片路径需要存在且可读
4. 大量调用时注意API限流，模块已内置调用间隔控制
5. 建议根据实际业务需求调整超时和重试参数

更新日志：
---------
- v1.1.0: 添加并发配置参数（text_max_workers, pic_max_workers, max_concurrent_coroutines）
- v1.0.0: 初始版本，支持文本和视觉模型调用
"""

import json
import logging
import threading
import time
import base64
import requests
import os
import sys
from io import BytesIO
from PIL import Image, ImageFile

# 添加项目根目录到路径，以便导入config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# 防止PIL自动截断大图片，在with Image.open()时避免因文件问题导致程序崩溃
ImageFile.LOAD_TRUNCATED_IMAGES = True


class AIModelProcessor:
    """
    AI模型处理器类
    
    提供统一的接口来调用各种AI模型，包括文本模型和视觉模型。
    支持自动重试、超时控制、API调用间隔控制等功能。
    
    所有模型相关的配置（包括并发配置参数）都集中在此类中管理，便于统一配置和复用。
    注意：并发配置参数（text_max_workers等）仅用于配置，实际使用时由调用方创建线程池或信号量。
    """
    
    def __init__(self, 
                 # 文本模型配置
                 text_model_url=None,
                 text_model_name=None,
                 text_model_password=None,
                 # 视觉模型配置
                 pic_model_url=None,
                 pic_model_name=None,
                 pic_model_password=None,
                 # 超时配置
                 text_read_timeout=300,
                 text_connect_timeout=10,
                 pic_read_timeout=60,
                 pic_connect_timeout=30,
                 # 重试配置
                 max_retries=3,
                 pic_max_retries=3,
                 retry_delay=5,
                 max_timeout_retries=5,
                # API调用间隔配置
                api_call_min_intervals={'text': 0.1, 'pic': 0.2},
                 # 并发配置
                 text_max_workers=20,
                 pic_max_workers=20,
                 max_concurrent_coroutines=20,
                 # 图片处理配置
                 image_quality=95,
                 detail='high'):
        """
        初始化AI模型处理器
        
        Args:
            text_model_url (str, optional): 文本模型API地址
            text_model_name (str, optional): 文本模型名称
            text_model_password (str, optional): 文本模型API密钥
            pic_model_url (str, optional): 视觉模型API地址
            pic_model_name (str, optional): 视觉模型名称
            pic_model_password (str, optional): 视觉模型API密钥
            text_read_timeout (int): 文本模型读取超时时间（秒），默认300（5分钟）
            text_connect_timeout (int): 文本模型连接超时时间（秒），默认10
            pic_read_timeout (int): 视觉模型读取超时时间（秒），默认60（1分钟）
            pic_connect_timeout (int): 视觉模型连接超时时间（秒），默认30
            max_retries (int): 最大重试次数，默认3
            pic_max_retries (int): 视觉模型最大重试次数，默认3
            retry_delay (float): 重试延迟时间（秒），默认5
            max_timeout_retries (int): 超时重试最大次数，默认5
            api_call_min_intervals (dict): 按API类型分别配置调用间隔，格式：
                {'text': 0.1, 'pic': 0.2}，默认值为 {'text': 0.1, 'pic': 0.2}
            text_max_workers (int): 文本模型线程池最大工作线程数，默认20
                用于配置ThreadPoolExecutor的max_workers参数，控制文本模型API调用的并发线程数
            pic_max_workers (int): 视觉模型线程池最大工作线程数，默认20
                用于配置ThreadPoolExecutor的max_workers参数，控制视觉模型API调用的并发线程数
            max_concurrent_coroutines (int): 协程最大并发数，默认20
                用于配置asyncio.Semaphore的参数，控制异步协程的最大并发数量
            image_quality (int): 图片JPEG质量（1-100），默认95
            detail (str): 图像理解精度模式，'high' 或 'low'，默认'high'
                - 'high': 高精度理解，压缩至约401万像素（2048×1960）
                - 'low': 低精度理解，压缩至约104万像素（1024×1024）
        """
        # 加载所有模型配置（用于重试时切换模型）
        try:
            from config.config import config
            # 文本模型配置
            self.gemini_config = config.gemini_model_config
            self.qwen_config = config.qwen_model_config
            # 视觉模型配置
            self.doubao_vision_config = config.ocr_model_config  # 豆包视觉模型
            self.qwen_vision_config = config.complex_file_model_config  # QWEN视觉模型
        except ImportError:
            # 如果无法导入config，使用默认值
            self.gemini_config = {
                "model": "gemini-2.5-pro",
                "api_url": "http://209.146.116.208:10086/v1/chat/completions",
                "api_key": ""
            }
            self.qwen_config = {
                "model": "qwen3-max",
                "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                "api_key": "sk-9c6f156a83214b17b1279d1fc993060c"
            }
            self.doubao_vision_config = {
                "model": "doubao-seed-1-6-vision-250815",
                "api_url": "http://209.146.116.208:10086/v1/chat/completions",
                "api_key": "sk-WysHSMggLo44YInFqNL51htBLGOq26RaevPOF4sOkImsM8mp"
            }
            self.qwen_vision_config = {
                "model": "qwen3-vl-plus",
                "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                "api_key": "sk-9c6f156a83214b17b1279d1fc993060c"
            }
        
        # 文本模型配置（默认使用Gemini）
        if text_model_url is None or text_model_name is None or text_model_password is None:
            self.text_model_url = text_model_url or self.gemini_config.get("api_url", "http://209.146.116.208:10086/v1/chat/completions")
            self.text_model_name = text_model_name or self.gemini_config.get("model", "gemini-2.5-pro")
            self.text_model_password = text_model_password or self.gemini_config.get("api_key", "")
        else:
            self.text_model_url = text_model_url
            self.text_model_name = text_model_name
            self.text_model_password = text_model_password
        
        # 视觉模型配置（默认使用豆包视觉模型）
        if pic_model_url is None or pic_model_name is None or pic_model_password is None:
            self.pic_model_url = pic_model_url or self.doubao_vision_config.get("api_url", "http://209.146.116.208:10086/v1/chat/completions")
            self.pic_model_name = pic_model_name or self.doubao_vision_config.get("model", "doubao-seed-1-6-vision-250815")
            self.pic_model_password = pic_model_password or self.doubao_vision_config.get("api_key", "")
        else:
            self.pic_model_url = pic_model_url
            self.pic_model_name = pic_model_name
            self.pic_model_password = pic_model_password
        
        # 超时配置
        self.text_read_timeout = text_read_timeout
        self.text_connect_timeout = text_connect_timeout
        self.pic_read_timeout = pic_read_timeout
        self.pic_connect_timeout = pic_connect_timeout
        
        # 重试配置
        self.max_retries = max_retries
        self.pic_max_retries = pic_max_retries
        self.retry_delay = retry_delay
        self.max_timeout_retries = max_timeout_retries
        
        # API调用间隔配置
        # 优化：支持按API类型分别配置调用间隔（仅文本和视觉模型）
        self.api_call_min_intervals = api_call_min_intervals.copy()
        
        # 并发配置（仅用于配置，实际使用时由调用方创建线程池）
        self.text_max_workers = text_max_workers
        self.pic_max_workers = pic_max_workers
        self.max_concurrent_coroutines = max_concurrent_coroutines
        
        # 图片质量配置（95效果与100效果差异不大，但文件大小更小）
        self.image_quality = image_quality
        
        # 图片理解精度模式配置
        self.detail = detail
        
        # 线程安全的API调用时间戳记录
        # 优化：为每种API类型创建独立的锁，允许文本模型和视觉模型真正并发调用
        self._last_api_call_time = {}
        self._api_call_locks = {
            'text': threading.Lock(),   # 文本模型API调用锁
            'pic': threading.Lock()      # 视觉模型API调用锁
        }
    
    def _wait_for_api_interval(self, api_type='text'):
        """
        等待API调用间隔，确保每次调用之间有足够的时间间隔
        
        优化说明：
        - 为每种API类型使用独立的锁，允许文本模型和视觉模型真正并发调用
        - 为每种API类型使用独立的间隔配置，允许灵活调整不同模型的调用频率
        - 文本模型和视觉模型是独立的API端点，不需要互相等待
        - 只需要保证同类型API之间的间隔即可
        - 这样可以显著提升并发性能，特别是文本和视觉模型混合调用的场景
        
        Args:
            api_type (str): API类型 ('text', 'pic')
        """
        # 获取对应API类型的锁（如果类型不存在，默认使用text锁）
        api_lock = self._api_call_locks.get(api_type, self._api_call_locks['text'])
        
        # 获取对应API类型的调用间隔（如果类型不存在，默认使用text的间隔）
        min_interval = self.api_call_min_intervals.get(api_type, self.api_call_min_intervals['text'])
        
        with api_lock:
            current_time = time.time()
            if api_type in self._last_api_call_time:
                elapsed = current_time - self._last_api_call_time[api_type]
                if elapsed < min_interval:
                    sleep_time = min_interval - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        current_time = time.time()
            
            # 在锁内更新时间戳，确保后续线程能正确计算间隔
            self._last_api_call_time[api_type] = current_time
    
    # 图片处理方法
    def _encode_image(self, image_path, quality=None, force_format='JPEG'):
        """
        将图片转换为指定格式并编码为Base64，根据detail模式动态压缩（内部方法）
        
        这个方法会根据方舟API规范自动校验和处理图片：
        1. 校验最小尺寸：宽>14px且高>14px
        2. 校验像素数范围：[196, 3600万]
        3. 如果图片过大（>3600万像素），会先压缩至3600万以内
        4. 然后根据实例配置的detail模式压缩至目标尺寸
        
        Args:
            image_path (str): 图片文件路径
            quality (int, optional): JPEG质量（1-100），如果为None则使用实例的image_quality
            force_format (str): 目标格式，'JPEG' 或 'PNG'，默认'JPEG'
        
        Returns:
            str: Base64编码的图片数据，失败时返回None
            
        Note:
            如果图片尺寸不符合要求（宽或高≤14px）或像素数过小（<196像素），
            会记录错误日志并返回None，不会发起API请求
        """
        if quality is None:
            quality = self.image_quality
        
        try:
            # 根据detail模式动态设置max_size（参考API规范）
            if self.detail == 'high':
                max_size_limit = (2048, 1960)  # 401万像素
            elif self.detail == 'low':
                max_size_limit = (1024, 1024)  # 104万像素
            else:
                logging.warning(f"未知的detail模式: {self.detail}，将使用high模式")
                max_size_limit = (2048, 1960)
            
            max_pixels = max_size_limit[0] * max_size_limit[1]
            
            # 方舟API图片限制常量
            MIN_WIDTH = 14  # 最小宽度（像素）
            MIN_HEIGHT = 14  # 最小高度（像素）
            MIN_PIXELS = 196  # 最小像素数（宽×高）
            MAX_PIXELS = 36000000  # 最大像素数（3600万）
            
            # 读取原始图像并记录基础信息
            with Image.open(image_path) as img:
                original_format = img.format or "UNKNOWN"
                original_mode = img.mode
                original_size = img.size
                width, height = original_size
                original_pixels = width * height
                # logging.info(f"原始图片: 路径={image_path}, 格式={original_format}, 尺寸={original_size}, 像素数={original_pixels}, 模式={original_mode}, detail={self.detail}")

                # 图片尺寸和像素数校验（根据方舟API规范）
                # 校验最小尺寸
                if width <= MIN_WIDTH or height <= MIN_HEIGHT:
                    logging.error(f"图片尺寸不符合要求: 宽={width}px, 高={height}px, 要求宽>{MIN_WIDTH}且高>{MIN_HEIGHT}px。图片路径: {image_path}")
                    return None
                
                # 校验像素数范围
                if original_pixels < MIN_PIXELS:
                    logging.error(f"图片像素数过小: {original_pixels}像素, 要求≥{MIN_PIXELS}像素。图片路径: {image_path}")
                    return None
                
                if original_pixels > MAX_PIXELS:
                    logging.warning(f"图片像素数过大: {original_pixels}像素（超过{MAX_PIXELS}像素上限），将进行压缩处理。图片路径: {image_path}")
                    # 如果原始图片超过3600万像素，先压缩到3600万以内，然后再按detail模式压缩
                    scale = (MAX_PIXELS / original_pixels) ** 0.5
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    img = img.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)
                    logging.info(f"图片过大，压缩至安全范围: {original_size} -> {img.size}, 像素数: {original_pixels} -> {img.size[0] * img.size[1]}")

                # 强制转换为目标色彩模式（RGB/RGBA）
                if force_format == 'JPEG':
                    target_mode = 'RGB'
                    if img.mode != target_mode:
                        img = img.convert(target_mode)
                        logging.info(f"转换模式: {original_mode} -> {target_mode}")
                else:  # PNG支持RGBA
                    target_mode = 'RGBA'
                    if img.mode != target_mode:
                        img = img.convert(target_mode)
                        logging.info(f"转换模式: {original_mode} -> {target_mode}")

                # 尺寸缩放（按detail模式限制的像素总数，保持比例）
                width, height = img.size
                current_pixels = width * height
                
                if current_pixels > max_pixels:
                    # 计算缩放比例，保持宽高比
                    scale = (max_pixels / current_pixels) ** 0.5  # 开平方根，保持宽高比
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    new_size = (new_width, new_height)
                    img = img.resize(new_size, resample=Image.Resampling.LANCZOS)
                    logging.info(f"图片按detail模式压缩: {width}×{height} -> {new_size}, 像素数: {current_pixels} -> {new_width * new_height}")

                # 强制转换为目标格式并保存到缓冲区
                buffer = BytesIO()
                img.save(buffer, format=force_format, quality=quality)
                buffer.seek(0)

                # 生成Base64并验证
                base64_data = base64.b64encode(buffer.read()).decode('utf-8')
                
                if current_pixels > max_pixels:
                    final_size = img.size
                    final_pixels = img.size[0] * img.size[1]
                    logging.info(f"图片过大: detail={self.detail}, 目标格式={force_format}, 最终尺寸={final_size}, 最终像素数={final_pixels}, Base64长度={len(base64_data)}字符")

                return base64_data

        except FileNotFoundError:
            logging.error(f"文件不存在: {image_path}")
        except Image.UnidentifiedImageError:
            logging.error(f"无法识别的图像格式: {image_path}")
        except Exception as e:
            logging.error(f"图像处理异常: {image_path}, 错误={str(e)}")
        return None
    
    # 文本模型调用方法
    def extract_text(self, prompt, temperature=0.3):
        """
        调用文本大模型进行信息提取和分析
        
        这是最常用的方法，用于调用文本大模型处理各种文本分析任务。
        重试逻辑：首次gemini，重试第一次qwen，重试第二次gemini
        
        Args:
            prompt (str): 发送给AI模型的提示词内容
            temperature (float): 温度参数，控制输出的随机性，默认0.3
            
        Returns:
            str: AI模型生成的内容，失败时返回None
            
        Example:
            >>> processor = AIModelProcessor()
            >>> result = processor.extract_text("提取以下文本的关键信息：...")
            >>> print(result)
        """
        # 定义文本模型重试顺序：首次gemini，重试第一次qwen，重试第二次gemini
        text_model_sequence = [
            ('gemini', self.gemini_config),
            ('qwen', self.qwen_config),
            ('gemini', self.gemini_config)
        ]
        
        attempt = 0
        timeout_attempts = 0
        json_parse_retries = 0  # JSON解析失败时，同一模型的重试次数
        max_json_parse_retries = 2  # JSON解析失败时，同一模型最多重试2次
        
        while attempt < len(text_model_sequence):
            # 根据重试次数选择模型
            model_name, model_config = text_model_sequence[attempt]
            current_model_name = model_config.get("model", "")
            current_model_url = model_config.get("api_url", "")
            current_model_key = model_config.get("api_key", "")
            
            # logging.info(f"调用文本大模型（尝试 {attempt + 1}/{len(text_model_sequence)}）: {model_name} ({current_model_name})")
            self._wait_for_api_interval(api_type='text')
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {current_model_key}"
            }
            data = {
                "model": current_model_name,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "提取信息"}
                ],
                "temperature": temperature
            }

            try:
                response = requests.post(
                    current_model_url,
                    headers=headers,
                    data=json.dumps(data),
                    timeout=(self.text_connect_timeout, self.text_read_timeout)
                )
                response.raise_for_status()
                logging.info(f"模型响应码: {response.status_code}")
                llm_output = response.json()
                
                # 打印token使用情况
                if "usage" in llm_output:
                    usage = llm_output["usage"]
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    total_tokens = usage.get("total_tokens", 0)
                    # logging.info(f"Token使用情况 - 输入: {prompt_tokens}, 输出: {completion_tokens}, 总计: {total_tokens}")
                
                answer = llm_output["choices"][0]["message"]["content"]
                # JSON解析成功，重置JSON解析重试计数器
                json_parse_retries = 0
                return answer
                
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                timeout_attempts += 1
                error_response = None
                try:
                    if hasattr(e, 'response') and e.response is not None:
                        error_response = e.response.json()
                        logging.error(f"文本模型api调用超时（{model_name}），超时第{timeout_attempts}次，报错信息为{error_response}")
                    else:
                        logging.error(f"文本模型api调用超时（{model_name}），超时第{timeout_attempts}次，报错信息为{e}")
                except:
                    logging.error(f"文本模型api调用超时（{model_name}），超时第{timeout_attempts}次，报错信息为{e}")
                
                if timeout_attempts >= self.max_timeout_retries:
                    logging.error(f"达到最大超时重试次数 ({self.max_timeout_retries})")
                    # 超时也尝试切换模型
                    attempt += 1
                    json_parse_retries = 0  # 切换到下一个模型时，重置JSON解析重试计数器
                    if attempt < len(text_model_sequence):
                        logging.info(f"超时后切换到下一个模型，准备重试...")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        return None
                
                logging.info("文本模型api调用准备重试...")
                time.sleep(self.retry_delay)
                self._wait_for_api_interval(api_type='text')
                continue

            except requests.exceptions.RequestException as e:
                attempt += 1
                json_parse_retries = 0  # 切换到下一个模型时，重置JSON解析重试计数器
                error_response = None
                try:
                    if hasattr(e, 'response') and e.response is not None:
                        error_response = e.response.json()
                        logging.error(f"文本api请求出错（{model_name}，尝试 {attempt}/{len(text_model_sequence)}），报错信息为{error_response}")
                    else:
                        logging.error(f"文本api请求出错（{model_name}，尝试 {attempt}/{len(text_model_sequence)}），报错信息为{e}")
                except:
                    logging.error(f"文本api请求出错（{model_name}，尝试 {attempt}/{len(text_model_sequence)}），报错信息为{e}")
                
                if attempt < len(text_model_sequence):
                    logging.info(f"准备切换到下一个模型重试...")
                    time.sleep(self.retry_delay)
                    self._wait_for_api_interval(api_type='text')
                    continue
                else:
                    logging.error(f"达到最大重试次数 ({len(text_model_sequence)})，放弃重试")
                    return None

            except (KeyError, json.JSONDecodeError) as e:
                json_parse_retries += 1
                logging.error(f"文本api响应结果解析出错（{model_name}，JSON解析重试 {json_parse_retries}/{max_json_parse_retries}）：{e}")
                
                # 如果JSON解析失败，先用同一个模型重试（最多重试max_json_parse_retries次）
                if json_parse_retries < max_json_parse_retries:
                    logging.info(f"JSON解析失败，使用同一模型（{model_name}）重试，第 {json_parse_retries + 1} 次...")
                    time.sleep(self.retry_delay)
                    self._wait_for_api_interval(api_type='text')
                    continue  # 继续使用当前模型重试
                else:
                    # 同一模型重试多次都失败，切换到下一个模型
                    attempt += 1
                    json_parse_retries = 0  # 重置JSON解析重试计数器
                    logging.warning(f"同一模型（{model_name}）JSON解析重试 {max_json_parse_retries} 次都失败，切换到下一个模型")
                    if attempt < len(text_model_sequence):
                        logging.info(f"准备切换到下一个模型重试...")
                        time.sleep(self.retry_delay)
                        self._wait_for_api_interval(api_type='text')
                        continue
                    else:
                        logging.error(f"达到最大重试次数 ({len(text_model_sequence)})，放弃重试")
                        return None
        
        logging.error(f"文本api调用失败，已尝试 {len(text_model_sequence)} 次")
        return None
    
    # 视觉模型调用方法
    def extract_text_from_image(self, image_path, prompt=None):
        """
        从图片中提取文本信息（调用视觉大模型）
        
        这是最常用的视觉模型调用方法，用于识别图片中的文字内容。
        使用实例配置的detail模式进行图片处理。
        重试逻辑：第一次豆包，第二次qwen
        
        Args:
            image_path (str): 图片文件路径
            prompt (str, optional): 视觉模型的提示词，如果为None则使用默认提示词
        
        Returns:
            tuple: (提取的文本内容, 图片路径)，失败时返回 (None, image_path)
            
        Example:
            >>> processor = AIModelProcessor(detail='high')
            >>> result, path = processor.extract_text_from_image("path/to/image.jpg")
            >>> if result:
            ...     print(result)
        """
        # 使用默认提示词（通用的图片文本提取提示词）
        # 用户可以根据自己的业务需求自定义提示词
        if prompt is None:
            prompt = ("你是一个可以从图片中提取文本信息的大师。当用户要求你提取图片中的文本信息时，"
                     "你首先需要判断图片的核心内容是什么，例如设计图、食物之类的。"
                     "其次，你需要判断图片中是否存在一个红色或者黑白色的圆章，例如图片中存在盖章。"
                     "最后，你需要提取图片中完整的文本信息，并且输出一个合适的排版，从而提升用户的阅读体验，"
                     "因为有的图片可能是非正常角度或者内容存在错位。"
                     "此外，提取图片内容时，请仔细辨认文本信息，避免出现文字识别错误。"
                     "输出范例为:当前图片核心内容为:XXX。（换行）"
                     "当前图片是否存在圆型盖章:存在/不存在。（换行）"
                     "当前图片文字信息为:XXX。"
                     "除了输出范例中要求输出的内容，其他任何解释性的文字都不要出现。"
                     "注意，你需要对从图片中获取的文本进行进行一定的加工组合。"
                     "例如你发现识别到的文字信息全是重复新的文字，我需要你进行简略优化，将重复新的内容删除。"
                     "或者一些明显是表格格式的信息，我需要尽量组装回一个按照表格样式的排版。")
        
        # 使用内部方法编码图片
        base64_image = self._encode_image(image_path=image_path)

        if not base64_image:
            logging.error(f"图片编码失败: {image_path}")
            return None, image_path
        
        # 记录图片信息用于调试
        image_size = len(base64_image)
        
        # 检查图片大小，如果过大则记录警告
        if image_size > 1000000:  # 1MB
            logging.warning(f"图片Base64编码较大: {image_size} 字符，可能导致API调用超时")
        
        # 定义视觉模型重试顺序：第一次豆包，第二次qwen，第三次豆包
        vision_model_sequence = [
            ('doubao', self.doubao_vision_config),
            ('qwen', self.qwen_vision_config),
            ('doubao', self.doubao_vision_config)
        ]
        
        attempt = 0
        while attempt < len(vision_model_sequence):
            # 根据重试次数选择模型
            model_name, model_config = vision_model_sequence[attempt]
            current_model_name = model_config.get("model", "")
            current_model_url = model_config.get("api_url", "")
            current_model_key = model_config.get("api_key", "")
            
            # logging.info(f"调用视觉大模型（尝试 {attempt + 1}/{len(vision_model_sequence)}）: {model_name} ({current_model_name})")
            self._wait_for_api_interval(api_type='pic')
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {current_model_key}"
            }
            data = {
                "model": current_model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": self.detail
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                "temperature": 0.1,
                "thinking": {
                    "type": "disabled"
                }
            }
            
            try:
                response = requests.post(
                    current_model_url,
                    headers=headers,
                    data=json.dumps(data),
                    timeout=(self.pic_connect_timeout, self.pic_read_timeout)
                )
                response.raise_for_status()
                logging.info(f"模型响应码: {response.status_code}")
                llm_output = response.json()
                
                # 打印token使用情况
                if "usage" in llm_output:
                    usage = llm_output["usage"]
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    completion_tokens = usage.get("completion_tokens", 0)
                    total_tokens = usage.get("total_tokens", 0)
                    # logging.info(f"视觉模型Token使用情况 - 输入: {prompt_tokens}, 输出: {completion_tokens}, 总计: {total_tokens}")
                
                answer = llm_output["choices"][0]["message"]["content"]
                return answer, image_path
                
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                attempt += 1
                error_details = f"超时时间: {self.pic_read_timeout}秒"
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_response = e.response.json()
                        error_details += f", API响应: {error_response}"
                    except:
                        error_details += f", HTTP状态码: {e.response.status_code}"
                
                if attempt < len(vision_model_sequence):
                    logging.warning(
                        f"视觉大模型调用超时（{model_name}，尝试 {attempt}/{len(vision_model_sequence)}）: {image_path}, {error_details}，等待 {self.retry_delay} 秒后切换到下一个模型重试...")
                    time.sleep(self.retry_delay)
                    self._wait_for_api_interval(api_type='pic')
                    continue
                else:
                    logging.error(f"视觉大模型调用超时: {image_path}, {error_details}，已达最大重试次数 ({len(vision_model_sequence)})")
                    return None, image_path
                    
            except Exception as e:
                attempt += 1
                error_details = f"错误类型: {type(e).__name__}, 错误信息: {str(e)}"
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_response = e.response.json()
                        error_details += f", API响应: {error_response}"
                    except:
                        error_details += f", HTTP状态码: {e.response.status_code}"
                
                if attempt < len(vision_model_sequence):
                    logging.warning(
                        f"视觉大模型调用失败（{model_name}，尝试 {attempt}/{len(vision_model_sequence)}）: {image_path}, {error_details}，等待 {self.retry_delay} 秒后切换到下一个模型重试...")
                    time.sleep(self.retry_delay)
                    self._wait_for_api_interval(api_type='pic')
                    continue
                else:
                    logging.error(f"视觉大模型调用失败: {image_path}, {error_details}，已达最大重试次数 ({len(vision_model_sequence)})")
                    return None, image_path
        
        logging.error(f"视觉大模型调用失败，已尝试 {len(vision_model_sequence)} 次")
        return None, image_path


# ============================================================================
# 便捷函数 - 保持向后兼容
# ============================================================================

# 默认处理器实例（懒加载）
# 
# 作用说明：
# 1. 支持便捷函数调用方式：允许用户直接调用 extract_text() 等函数而不需要先创建实例
# 2. 单例模式：确保多个便捷函数调用共享同一个处理器实例，避免重复创建
# 3. 懒加载：只有在第一次调用便捷函数时才创建实例，节省资源
#
# 调试说明：
# 如果需要使用不同的参数进行调试，有两种方式：
# 
# 方式1：使用类的方式（推荐）
#   processor = AIModelProcessor(
#       text_model_url="https://your-api.com/v1/chat/completions",
#       text_model_name="your-model",
#       text_model_password="your-api-key",
#       pic_model_url="https://your-api.com/v1/chat/completions",
#       pic_model_name="your-vision-model",
#       pic_model_password="your-api-key"
#   )
#   result = processor.extract_text("测试提示词")
#
# 方式2：临时替换默认处理器（用于调试）
#   from ai_model_processor import AIModelProcessor, _default_processor
#   import ai_model_processor
#   # 使用自定义配置创建新实例并替换默认实例
#   ai_model_processor._default_processor = AIModelProcessor(
#       text_model_password="debug-api-key",
#       max_retries=5,  # 调试时可以增加重试次数
#       image_quality=100  # 调试时可以使用最高质量
#   )
#   # 然后就可以直接使用便捷函数了
#   from ai_model_processor import extract_text
#   result = extract_text("测试提示词")
_default_processor = None


def _get_default_processor():
    """
    获取默认处理器实例（单例模式）
    
    用于便捷函数的内部实现，确保所有便捷函数共享同一个处理器实例。
    """
    global _default_processor
    if _default_processor is None:
        _default_processor = AIModelProcessor()
    return _default_processor


def extract_text(prompt, temperature=0.3):
    """
    便捷函数：调用文本大模型提取信息（使用默认配置）
    
    Args:
        prompt (str): 提示词
        temperature (float): 温度参数，默认0.3
        
    Returns:
        str: AI生成的内容，失败时返回None
    """
    return _get_default_processor().extract_text(prompt, temperature)


def extract_text_from_image(image_path, prompt=None):
    """
    便捷函数：从图片中提取文本（使用默认配置）
    
    Args:
        image_path (str): 图片路径
        prompt (str, optional): 提示词
        
    Returns:
        tuple: (文本内容, 图片路径)，失败时返回 (None, image_path)
    """
    return _get_default_processor().extract_text_from_image(image_path, prompt)


if __name__ == "__main__":
    """测试代码"""
    # 示例1：使用类的方式
    print("=" * 60)
    print("示例1：使用类的方式")
    print("=" * 60)
    
    processor = AIModelProcessor(
        text_model_url="http://209.146.116.208:10086/v1/chat/completions",
        text_model_name="gemini-2.5-pro",
        text_model_password="your-api-key-here"
    )
    
    # result = processor.extract_text("你好，请介绍一下你自己")
    # print(f"结果: {result}")
    
    # 示例2：使用便捷函数
    print("\n" + "=" * 60)
    print("示例2：使用便捷函数")
    print("=" * 60)
    
    # result2 = extract_text("你好，请介绍一下你自己")
    # print(f"结果: {result2}")

