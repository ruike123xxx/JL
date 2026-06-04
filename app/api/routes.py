"""HTTP 路由: RPA 调用入口。"""

from fastapi import APIRouter

from app.core.pipeline import handle_reply
from app.schemas import (
    ConversationIngestRequest,
    ConversationIngestResponse,
    ReplyRequest,
    ReplyResponse,
    ResetRequest,
)
from app.store import db

router = APIRouter()


@router.post("/reply", response_model=ReplyResponse)
def reply(req: ReplyRequest) -> ReplyResponse:
    """RPA 主接口: 传入抓取的对话上下文, 返回回复内容 + RPA 动作指令。

    RPA 拿到后: 先发送 answer, 再按 reason.rpa_action 决定是否执行后续动作。
    """
    return handle_reply(req)


@router.post("/rpa/conversation", response_model=ConversationIngestResponse)
def ingest_conversation(req: ConversationIngestRequest) -> ConversationIngestResponse:
    """影刀第一步联调接口: 上传抓取到的对话文本, 返回接收回执。"""
    session = db.get_or_default(req.candidate_id)
    return ConversationIngestResponse(
        candidate_id=req.candidate_id,
        received=True,
        conversation_chars=len(req.conversation),
        stage=session["stage"],
        next_endpoint="/reply",
    )


@router.post("/reset")
def reset(req: ResetRequest) -> dict:
    """调试用: 清除某候选人的会话状态, 方便联调重来。"""
    deleted = db.reset_session(req.candidate_id)
    return {"candidate_id": req.candidate_id, "deleted": deleted}
