"""主编排: 读状态 -> 合并简历 -> 拼 prompt -> 调模型 -> 解析 -> 更新状态 -> 返回。"""

from app.core.json_repair import parse_reply
from app.core.prompt import build_messages
from app.core.scoring import LOW_SCORE_MESSAGE, SCORE_PASS_THRESHOLD, score_resume
from app.llm.base import get_provider
from app.schemas import ReplyReason, ReplyRequest, ReplyResponse
from app.store import db

# rpa_action -> 推进后的招聘阶段 (简单映射, 后续可细化为状态机)
_STAGE_BY_ACTION = {
    "send_company_address": "约面中",
}


def handle_reply(req: ReplyRequest) -> ReplyResponse:
    # 1. 读会话状态 (stage 由 Python 维护, 不由 RPA 传)
    session = db.get_or_default(req.candidate_id)
    stage = session["stage"]

    # 2. 合并简历: 本轮有则用本轮并更新; 本轮空则复用库里的
    resume = req.resume.strip() or session["resume"]

    # if resume:
    #     score = score_resume(resume=resume, job_requirement=req.job_requirement)
    #     if not score.passed:
    #         db.upsert_session(req.candidate_id, stage, resume)
    #         return ReplyResponse(
    #             answer=LOW_SCORE_MESSAGE,
    #             reason=ReplyReason(
    #                 rpa_action="reply_message",
    #                 basis=f"简历评分{score.total}分低于{SCORE_PASS_THRESHOLD}分，暂不推进",
    #             ),
    #         )

    # 3. 拼 prompt
    system, user = build_messages(
        conversation=req.conversation,
        job_requirement=req.job_requirement,
        resume=resume,
        company_info=req.company_info,
        stage=stage,
    )

    # 4. 调模型 (provider 可插拔) -> 5. 容错解析
    raw = get_provider().generate(system, user)
    result = parse_reply(raw)

    # 6. 更新状态: 简历快照 + 按动作推进 stage
    new_stage = _STAGE_BY_ACTION.get(result.reason.rpa_action, stage)
    db.upsert_session(req.candidate_id, new_stage, resume)

    return result
