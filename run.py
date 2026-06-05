"""启动入口: python run.py"""
import uvicorn

from app.config import settings
#你好啊，亲爱的小伙伴
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
