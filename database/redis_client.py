# Redis连接管理
import logging
import json
from typing import Any, Optional, Union
import redis
from redis import Redis
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import os

# 配置日志
logger = logging.getLogger(__name__)

class RedisManager:
    """Redis连接管理器"""
    
    def __init__(self):
        """初始化Redis管理器"""
        self.redis_client: Optional[Redis] = None
        self._connect()
    
    def _connect(self):
        """建立Redis连接"""
        try:
            # 直接从环境变量获取配置
            redis_host = os.getenv('REDIS_HOST', '192.168.1.6')
            redis_port = int(os.getenv('REDIS_PORT', '6379'))
            redis_password = os.getenv('REDIS_PASSWORD', '')
            redis_db = int(os.getenv('REDIS_DB', '11'))
            
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password if redis_password else None,
                db=redis_db,
                decode_responses=True,  # 自动解码响应
                socket_connect_timeout=5,  # 连接超时
                socket_timeout=5,  # 操作超时
                retry_on_timeout=True,  # 超时重试
                health_check_interval=30  # 健康检查间隔
            )
            logger.info(f"Redis连接成功: {redis_host}:{redis_port}")
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            self.redis_client = None
    
    def test_connection(self) -> bool:
        """
        测试Redis连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            if self.redis_client is None:
                self._connect()
            
            if self.redis_client is None:
                return False
                
            # 执行ping命令测试连接
            result = self.redis_client.ping()
            if result:
                logger.info("Redis连接测试成功")
            return result
        except Exception as e:
            logger.error(f"Redis连接测试失败: {e}")
            return False
    
    def get_client(self) -> Optional[Redis]:
        """
        获取Redis客户端
        
        Returns:
            Optional[Redis]: Redis客户端实例
        """
        if self.redis_client is None:
            self._connect()
        return self.redis_client
    
    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """
        设置键值对
        
        Args:
            key: 键名
            value: 值
            ex: 过期时间（秒）
            
        Returns:
            bool: 是否设置成功
        """
        try:
            client = self.get_client()
            if client is None:
                return False
            
            # 如果值是字典或列表，转换为JSON字符串
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            
            result = client.set(key, value, ex=ex)
            logger.debug(f"Redis SET: {key} = {value}")
            return result
        except Exception as e:
            logger.error(f"Redis SET操作失败: {e}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取键值
        
        Args:
            key: 键名
            
        Returns:
            Optional[Any]: 键值，如果不存在返回None
        """
        try:
            client = self.get_client()
            if client is None:
                return None
            
            value = client.get(key)
            if value is None:
                return None
            
            # 尝试解析JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Redis GET操作失败: {e}")
            return None
    
    def delete(self, key: str) -> bool:
        """
        删除键
        
        Args:
            key: 键名
            
        Returns:
            bool: 是否删除成功
        """
        try:
            client = self.get_client()
            if client is None:
                return False
            
            result = client.delete(key)
            logger.debug(f"Redis DELETE: {key}")
            return bool(result)
        except Exception as e:
            logger.error(f"Redis DELETE操作失败: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """
        检查键是否存在
        
        Args:
            key: 键名
            
        Returns:
            bool: 键是否存在
        """
        try:
            client = self.get_client()
            if client is None:
                return False
            
            result = client.exists(key)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis EXISTS操作失败: {e}")
            return False
    
    def expire(self, key: str, seconds: int) -> bool:
        """
        设置键的过期时间
        
        Args:
            key: 键名
            seconds: 过期时间（秒）
            
        Returns:
            bool: 是否设置成功
        """
        try:
            client = self.get_client()
            if client is None:
                return False
            
            result = client.expire(key, seconds)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis EXPIRE操作失败: {e}")
            return False
    
    def get_info(self) -> Optional[dict]:
        """
        获取Redis服务器信息
        
        Returns:
            Optional[dict]: 服务器信息字典
        """
        try:
            client = self.get_client()
            if client is None:
                return None
            
            info = client.info()
            return info
        except Exception as e:
            logger.error(f"获取Redis信息失败: {e}")
            return None

# 创建全局Redis管理器实例
redis_manager = RedisManager()

# 便捷函数
def get_redis() -> Optional[Redis]:
    """获取Redis客户端"""
    return redis_manager.get_client()

def test_redis_connection() -> bool:
    """测试Redis连接"""
    return redis_manager.test_connection()

def cache_set(key: str, value: Any, ex: Optional[int] = None) -> bool:
    """设置缓存"""
    return redis_manager.set(key, value, ex)

def cache_get(key: str) -> Optional[Any]:
    """获取缓存"""
    return redis_manager.get(key)

def cache_delete(key: str) -> bool:
    """删除缓存"""
    return redis_manager.delete(key)