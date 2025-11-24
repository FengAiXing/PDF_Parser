# 应用配置管理
import os
import sys
import json
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# 从.env文件加载环境变量
load_dotenv()

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.ai_model_processor import AIModelProcessor

# 创建全局的AI模型处理器实例（懒加载）
_ai_processor = None

def _get_ai_processor():
    """获取AI模型处理器实例（单例模式）"""
    global _ai_processor
    if _ai_processor is None:
        _ai_processor = AIModelProcessor()
    return _ai_processor


def openai_chat(messages, model='gemini-2.5-pro', finish_try=2):
    """
    OpenAI聊天函数，支持Gemini模型（使用AIModelProcessor统一管理）
    
    Args:
        messages: 用户消息
        model: 模型名称，默认为gemini-2.5-pro
        finish_try: 重试次数（已由AIModelProcessor内部处理，此参数保留用于兼容性）
    
    Returns:
        str: 模型返回的内容
    """
    try:
        # 使用AIModelProcessor统一调用
        processor = _get_ai_processor()
        
        # 构建完整的提示词（包含system和user消息）
        full_prompt = f"you are a good assistant\n\n{messages}"
        
        # 调用文本模型提取信息
        result = processor.extract_text(prompt=full_prompt, temperature=0.3)
        
        return result
        
    except Exception as e:
        print(f"Error in openai_chat: {e}")
        return None


class DatabaseConfig:
    """
    数据库配置类
    
    处理所有与数据库相关的配置，包括连接参数、凭据和连接字符串生成。
    """
    
    def __init__(self) -> None:
        """
        从环境变量初始化数据库配置
        """
        # 测试环境配置
        self.host: str = os.getenv('DB_HOST', '192.168.1.111')
        self.database: str = os.getenv('DB_DATABASE', 'ai_bid_eval_report')
        self.user: str = os.getenv('DB_USER', 'root')
        self.password: str = os.getenv('DB_PASSWORD', 'Jccd&2023Bk')
        self.port: int = int(os.getenv('DB_PORT', '3306'))
        self.charset: str = os.getenv('DB_CHARSET', 'utf8mb4')
        self.use_unicode: bool = os.getenv('DB_USE_UNICODE', 'True').lower() == 'true'
        
        
        # 产品环境配置
        # self.host: str = os.getenv('DB_HOST', '172.25.73.21')
        # self.database: str = os.getenv('DB_DATABASE', 'ai_bid_eval_report')
        # self.user: str = os.getenv('DB_USER', 'root')
        # self.password: str = os.getenv('DB_PASSWORD', '!h3tT3Mm*UQvDxJ8')
        # self.port: int = int(os.getenv('DB_PORT', '3306'))
        # self.charset: str = os.getenv('DB_CHARSET', 'utf8mb4')
        # self.use_unicode: bool = os.getenv('DB_USE_UNICODE', 'True').lower() == 'true'
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将配置转换为字典格式
        
        Returns:
            Dict[str, Any]: 包含所有数据库配置参数的字典
        """
        return {
            'host': self.host,
            'database': self.database,
            'user': self.user,
            'password': self.password,
            'port': self.port,
            'charset': self.charset,
            'use_unicode': self.use_unicode
        }
    
    def get_connection_string(self) -> str:
        """
        生成SQLAlchemy连接字符串
        
        Returns:
            str: 适用于MySQL数据库的SQLAlchemy兼容连接字符串
        """
        return (
            f"mysql+mysqlconnector://{self.user}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}?charset={self.charset}"
        )


class AppConfig:
    """
    应用程序配置类
    
    集中管理所有应用程序配置，包括数据库、AI服务和一般应用程序设置。
    """
    
    def __init__(self) -> None:
        """
        从环境变量初始化应用程序配置
        """
        # Redis测试环境配置
        self.redis_host: str = os.getenv('REDIS_HOST', '192.168.1.202')
        self.redis_port: int = int(os.getenv('REDIS_PORT', '6379'))
        self.redis_password: str = os.getenv('REDIS_PASSWORD', '')
        self.redis_db: int = int(os.getenv('REDIS_DB', '11'))
        
         # Redis产品环境配置
        # self.redis_host: str = os.getenv('REDIS_HOST', '172.25.73.21')
        # self.redis_port: int = int(os.getenv('REDIS_PORT', '6379'))
        # self.redis_password: str = os.getenv('REDIS_PASSWORD', '')
        # self.redis_db: int = int(os.getenv('REDIS_DB', '11'))
        
        # 大模型配置
        
        # 默认模型配置（使用Gemini作为默认文本模型）
        self.model_config: Dict[str, str] = {
            "model": os.getenv('DEFAULT_MODEL_NAME', 'gemini-2.5-pro'),
            "api_url": os.getenv('DEFAULT_API_URL', 'http://209.146.116.208:10086/v1/chat/completions'),
            "api_key": os.getenv('DEFAULT_API_KEY', 'sk-5LkyYyoIeM14tBH8LdKKQlGbxH9lWmwPi5xjDYZG8OBjMXkN')
        }
        
        # OCR模型配置
        self.ocr_model_config: Dict[str, str] = {
            "model": os.getenv('OCR_MODEL_NAME', 'doubao-seed-1-6-vision-250815'),
            "api_url": os.getenv('OCR_API_URL', 'http://209.146.116.208:10086/v1/chat/completions'),
            "api_key": os.getenv('OCR_API_KEY', 'sk-WysHSMggLo44YInFqNL51htBLGOq26RaevPOF4sOkImsM8mp')
        }
        
        # Gemini模型配置
        self.gemini_model_config: Dict[str, str] = {
            "model": os.getenv('GEMINI_MODEL_NAME', 'gemini-2.5-pro'),
            # "api_url": os.getenv('GEMINI_API_URL', 'http://123.129.219.111:3000/v1/chat/completions'),
            # "api_key": os.getenv('GEMINI_API_KEY', 'sk-pQwiKDvVyrwqRZStdDItecnKAVsZitD55A6Cw4y0PTeGfCP1')
            "api_url": os.getenv('GEMINI_API_URL', 'http://209.146.116.208:10086/v1/chat/completions'),
            "api_key": os.getenv('GEMINI_API_KEY', 'sk-5LkyYyoIeM14tBH8LdKKQlGbxH9lWmwPi5xjDYZG8OBjMXkN')
        }

        # QWEN模型配置
        self.qwen_model_config: Dict[str, str] = {
            "model": os.getenv('QWEN_MODEL_NAME', 'qwen3-max'),
            "api_url": os.getenv('QWEN_API_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'),
            "api_key": os.getenv('QWEN_API_KEY', 'sk-9c6f156a83214b17b1279d1fc993060c')
        }
        
        
        # 复杂文件处理模型配置（用于OCR和图片识别）
        self.complex_file_model_config: Dict[str, str] = {
            "model": os.getenv('COMPLEX_FILE_MODEL_NAME', 'qwen3-vl-plus'),
            "api_url": os.getenv('COMPLEX_FILE_API_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'),
            "api_key": os.getenv('COMPLEX_FILE_API_KEY', 'sk-9c6f156a83214b17b1279d1fc993060c')
        }

        
        # 数据库配置
        self.database: DatabaseConfig = DatabaseConfig()


# 全局配置实例
config: AppConfig = AppConfig()

# 向后兼容的遗留配置
JN_DB_CONFIG: Dict[str, Any] = config.database.to_dict()
