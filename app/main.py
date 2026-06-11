"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    hint = "POST /reply 必须使用 application/json，并至少包含 candidate_id。其它字段可传空字符串。"
    expected_body = {
        "candidate_id": "boss_user_12345",
        "conversation": "影刀抓取的当前窗口全部可见对话文本",
        "resume": "",
        "job_id": "ecommerce_ops_suzhou",
        "job_requirement": "",
        "company_info": "",
        "trigger": "auto",
        "last_message_from": "",
    }

    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            {
                "error": "请求体不符合接口要求",
                "hint": hint,
                "expected_body": expected_body,
                "detail": exc.errors(),
            }
        ),
    )


@app.get("/health")
def health():
    return {"status": "ok"}
