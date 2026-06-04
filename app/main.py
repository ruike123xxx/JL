"""FastAPI 应用入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.store import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()  # 启动时建表
    yield


app = FastAPI(
    title="Boss直聘自动招聘沟通机器人",
    description="RPA 做手脚, Python 做大脑: 拼 prompt / 调模型 / 解析决策 / 维护会话状态",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
