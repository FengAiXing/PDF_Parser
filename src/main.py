# 评标报告生成AI系统 - 应用入口
import uvicorn
import sys
import os
import logging
from fastapi import FastAPI

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
    force=True  # 强制重新配置日志
)

# 添加项目根目录到Python路径
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.business.api.api import router as api_router

# =============================================================================
# 🚀 服务启动配置 - 开发人员可根据需要调整以下参数
# =============================================================================
API_HOST = "0.0.0.0"        # 服务监听地址 (0.0.0.0 表示监听所有网络接口)
API_PORT = 8009             # 服务端口 (可根据需要修改，如 8080, 9000 等)
API_RELOAD = True          # 生产环境关闭自动重载 (开发环境可设为 True)
API_LOG_LEVEL = "INFO"      # 日志级别 (DEBUG, INFO, WARNING, ERROR)
NUM_WORKERS = 3          # 任务处理器数量 (建议设置为1，避免资源竞争)
# =============================================================================

# 创建FastAPI应用
app = FastAPI()

# 注册路由
app.include_router(api_router)

if __name__ == "__main__":
    # 测试数据库连接
    print("测试数据库连接...")
    from database.database import test_database_connection
    from database.redis_client import test_redis_connection
    
    if test_database_connection():
        print("MySQL数据库连接成功！")
    else:
        print("MySQL数据库连接失败！")
    
    if test_redis_connection():
        print("Redis连接成功！")
    else:
        print("Redis连接失败！")
    
    print("启动评标报告生成AI系统...")
    
    uvicorn.run(
        'main:app', 
        host=API_HOST, 
        port=API_PORT, 
        workers=NUM_WORKERS, 
        reload=API_RELOAD,
        log_level=API_LOG_LEVEL.lower()
    )
