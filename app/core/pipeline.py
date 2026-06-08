"""主编排: 读状态 -> 合并简历 -> 评分 -> 调模型 -> 修复解析 -> 更新状态 -> 返回。

稳定性约定: 模型相关异常 (LLMUnavailableError 等) 一律在本层吞掉并降级为
FALLBACK_REPLY, /reply 接口永远返回 200, 不把模型故障透传成 500。
"""

import logging

from app.config import settings
from app.core.json_repair import (
    FALLBACK_REPLY,
    build_repair_messages,
    parse_reply_result,
)
from app.core.prompt import build_messages
from app.core.scoring import LOW_SCORE_MESSAGE, SCORE_PASS_THRESHOLD, score_resume
from app.llm.base import LLMError, get_provider
from app.schemas import DEFAULT_STAGE, STAGES, ReplyReason, ReplyRequest, ReplyResponse
from app.store import db

logger = logging.getLogger(__name__)

# rpa_action -> 推进后的招聘阶段 (模型未给出合法 next_stage 时的保底映射)
_STAGE_BY_ACTION = {
    "send_company_address": "约面中",
}


def _normalize_stage(stage: str) -> str:
    """把库里可能存在的旧 stage 值归一到当前状态机, 防止未知值让阶段查表落空。"""
    return stage if stage in STAGES else DEFAULT_STAGE


def handle_reply(req: ReplyRequest) -> ReplyResponse:
    # 1. 读会话状态 (stage / turns 由 Python 维护, 不由 RPA 传)
    session = db.get_or_default(req.candidate_id)
    stage = _normalize_stage(session["stage"])
    turns = session.get("turns", 0)
    next_turns = turns + 1  # 本轮计入轮次

    # 2. 合并简历: 本轮有则用本轮并更新; 本轮空则复用库里的
    resume = req.resume.strip() or session["resume"]

    if resume:
        # 评分失败不应阻断整轮回复: 出错时默认放行, 继续走正常回复链路。
        try:
            score = score_resume(resume=resume, job_requirement=req.job_requirement)
        except LLMError as exc:
            logger.warning("简历评分调用失败, 默认放行: %s", exc)
            score = None
        if score is not None and not score.passed:
            db.upsert_session(req.candidate_id, stage, resume, next_turns)
            return ReplyResponse(
                answer=LOW_SCORE_MESSAGE,
                reason=ReplyReason(
                    rpa_action="reply_message",
                    basis=f"简历评分{score.total}分低于{SCORE_PASS_THRESHOLD}分，暂不推进",
                ),
            )

    # 3. 拼 prompt (注入当前阶段 + 轮次)
    system, user = build_messages(
        conversation=req.conversation,
        job_requirement=req.job_requirement,
        resume=resume,
        company_info=req.company_info,
        stage=stage,
        turns=turns,
    )

    # 4. 调模型 + 5. 校验解析 + 一次修复; 模型不可用时整体降级为兜底, 不抛 500
    result = _generate_reply(system, user)

    # 6. 推进 stage: 模型给的合法 next_stage 优先, 否则按动作映射, 再否则不动
    new_stage = _advance_stage(stage, result)
    db.upsert_session(req.candidate_id, new_stage, resume, next_turns)

    return result


def _advance_stage(current_stage: str, result: ReplyResponse) -> str:
    """决定推进后的 stage。

    优先级: 模型给的合法 next_stage > rpa_action 动作映射 > 维持当前阶段。
    """
    next_stage = result.reason.next_stage
    if next_stage in STAGES:
        return next_stage
    return _STAGE_BY_ACTION.get(result.reason.rpa_action, current_stage)


def _generate_reply(system: str, user: str) -> ReplyResponse:
    """调模型并校验; 结构不合规时修复一次; 模型不可用或仍不合规时返回兜底。"""
    provider = get_provider()
    try:
        raw = provider.generate(system, user)
    except LLMError as exc:
        logger.warning("主回复模型调用失败, 返回兜底: %s", exc)
        return FALLBACK_REPLY

    parsed = parse_reply_result(raw)
    if parsed.is_valid:
        return parsed.response

    # 结构不合规: 用低温度做一次性 JSON 修复
    repair_system, repair_user = build_repair_messages(raw)
    try:
        repaired_raw = provider.generate(
            repair_system, repair_user, temperature=settings.llm_temperature_structured
        )
    except LLMError as exc:
        logger.warning("修复调用失败, 返回兜底: %s", exc)
        return FALLBACK_REPLY

    repaired = parse_reply_result(repaired_raw)
    return repaired.response if repaired.is_valid else FALLBACK_REPLY
