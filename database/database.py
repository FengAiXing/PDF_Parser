# MySQL数据库连接管理
import logging
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入配置
from config.config import config

# 配置日志
logger = logging.getLogger(__name__)

# 创建数据库基类
Base = declarative_base()


class DatabaseManager:
    """MySQL数据库连接管理器"""

    def __init__(self):
        """初始化数据库管理器"""
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None

        # 使用统一的配置
        self._connection_string = config.database.get_connection_string()

    def create_engine(self) -> Engine:
        """
        创建数据库引擎

        Returns:
            Engine: SQLAlchemy数据库引擎
        """
        try:
            if self.engine is None:
                self.engine = create_engine(
                    self._connection_string,
                    pool_pre_ping=True,  # 连接前测试连接
                    pool_recycle=3600,  # 连接回收时间（秒）
                    pool_size=10,  # 连接池大小
                    max_overflow=20,  # 最大溢出连接数
                    echo=False  # 是否打印SQL语句
                )
                logger.info(f"数据库引擎创建成功: {config.database.host}:{config.database.port}")
            return self.engine
        except Exception as e:
            logger.error(f"创建数据库引擎失败: {e}")
            raise

    def get_session_local(self) -> sessionmaker:
        """
        获取会话工厂

        Returns:
            sessionmaker: SQLAlchemy会话工厂
        """
        if self.SessionLocal is None:
            engine = self.create_engine()
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return self.SessionLocal

    @contextmanager
    def get_db_session(self):
        """
        获取数据库会话的上下文管理器

        Yields:
            Session: 数据库会话
        """
        session_local = self.get_session_local()
        session = session_local()
        try:
            yield session
        except Exception as e:
            logger.error(f"数据库操作异常: {e}")
            session.rollback()
            raise
        finally:
            session.close()

    def test_connection(self) -> bool:
        """
        测试数据库连接

        Returns:
            bool: 连接是否成功
        """
        try:
            engine = self.create_engine()
            with engine.connect() as connection:
                from sqlalchemy import text
                result = connection.execute(text("SELECT 1"))
                logger.info("数据库连接测试成功")
                return True
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            return False

    def create_tables(self):
        """
        创建所有表（如果不存在）
        """
        try:
            engine = self.create_engine()
            Base.metadata.create_all(bind=engine)
            logger.info("数据库表创建成功")
        except Exception as e:
            logger.error(f"创建数据库表失败: {e}")
            raise


# 创建全局数据库管理器实例
db_manager = DatabaseManager()


# 便捷函数
def get_db():
    """获取数据库会话的依赖注入函数"""
    with db_manager.get_db_session() as session:
        yield session


def test_database_connection() -> bool:
    """测试数据库连接"""
    return db_manager.test_connection()


def init_database():
    """初始化数据库"""
    if test_database_connection():
        db_manager.create_tables()
        return True
    return False