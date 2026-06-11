"""HTTP 路由: RPA 调用入口。"""

from fastapi import APIRouter

from app.core.pipeline import handle_reply
from app.schemas import ReplyRequest, ReplyResponse, ResetRequest
from app.store import db

router = APIRouter()


@router.post("/reply", response_model=ReplyResponse)
def reply(req: ReplyRequest) -> ReplyResponse:
    """RPA 主接口: 传入抓取的对话上下文, 返回回复内容 + RPA 动作指令。

    RPA 拿到后: 先发送 answer, 再按 reason.rpa_action 决定是否执行后续动作。
    """
    return handle_reply(req)


@router.post("/reset")
def reset(req: ResetRequest) -> dict:
    """调试用: 清除某候选人的会话状态, 方便联调重来。"""
    deleted = db.reset_session(req.candidate_id)
    return {"candidate_id": req.candidate_id, "deleted": deleted}
