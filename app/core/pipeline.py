"""主编排: 读状态 -> 前置规则 -> 合并评分回复 -> 调模型 -> 更新状态 -> 返回。"""

import logging

from app.config import settings
from app.core.fast_path import (
    conversation_fingerprint,
    resume_fingerprint,
    try_fast_path,
)
from app.core.jobs import resolve_job_context
from app.core.json_repair import (
    FALLBACK_REPLY,
    ParsedReply,
    build_repair_messages,
    make_fast_response,
    parse_reply_result,
)
from app.core.prompt import build_messages, build_messages_with_scoring
from app.core.scoring import LOW_SCORE_MESSAGE, SCORE_PASS_THRESHOLD
from app.llm.base import LLMError, get_provider
from app.schemas import DEFAULT_STAGE, STAGES, ReplyRequest, ReplyResponse
from app.store import db

logger = logging.getLogger(__name__)

_STAGE_BY_ACTION = {
    "send_company_address": "约面中",
}


def _normalize_stage(stage: str) -> str:
    return stage if stage in STAGES else DEFAULT_STAGE


def handle_reply(req: ReplyRequest) -> ReplyResponse:
    session = db.get_or_default(req.candidate_id)
    stage = _normalize_stage(session["stage"])
    turns = session.get("turns", 0)

    job_requirement, company_info = resolve_job_context(
        job_id=req.job_id,
        job_requirement=req.job_requirement,
        company_info=req.company_info,
    )

    resume = req.resume.strip() or session.get("resume", "")
    conv_hash = conversation_fingerprint(req.conversation)
    res_hash = resume_fingerprint(resume)

    fast = try_fast_path(
        req,
        stage=stage,
        conversation_hash=conv_hash,
        stored_hash=session.get("conversation_hash", ""),
        resume=resume,
    )
    if fast is not None:
        if fast.reason.rpa_action == "skip":
            db.upsert_session(
                req.candidate_id,
                stage,
                resume,
                turns,
                conversation_hash=conv_hash,
                resume_hash=res_hash,
                resume_score=session.get("resume_score"),
            )
            return fast
        new_stage = _advance_stage(stage, fast)
        db.upsert_session(
            req.candidate_id,
            new_stage,
            resume,
            turns + 1,
            conversation_hash=conv_hash,
            resume_hash=res_hash,
            resume_score=session.get("resume_score"),
        )
        return fast

    cached_score = session.get("resume_score")
    use_combined = bool(resume) and not (
        res_hash and res_hash == session.get("resume_hash", "") and cached_score is not None
    )

    if resume and cached_score is not None and res_hash == session.get("resume_hash", ""):
        if cached_score < SCORE_PASS_THRESHOLD:
            db.upsert_session(
                req.candidate_id,
                stage,
                resume,
                turns + 1,
                conversation_hash=conv_hash,
                resume_hash=res_hash,
                resume_score=cached_score,
            )
            return make_fast_response(
                rpa_action="reply_message",
                answer=LOW_SCORE_MESSAGE,
                basis=f"简历评分{cached_score}分低于{SCORE_PASS_THRESHOLD}分，暂不推进",
            )

    if use_combined:
        system, user = build_messages_with_scoring(
            conversation=req.conversation,
            job_requirement=job_requirement,
            resume=resume,
            company_info=company_info,
            stage=stage,
            turns=turns,
        )
    else:
        system, user = build_messages(
            conversation=req.conversation,
            job_requirement=job_requirement,
            resume=resume,
            company_info=company_info,
            stage=stage,
            turns=turns,
        )

    parsed = _generate_reply(system, user)
    result = parsed.response
    resume_score = parsed.score if parsed.score is not None else cached_score

    if parsed.score is not None and parsed.score < SCORE_PASS_THRESHOLD:
        result = make_fast_response(
            rpa_action="reply_message",
            answer=LOW_SCORE_MESSAGE,
            basis=f"简历评分{parsed.score}分低于{SCORE_PASS_THRESHOLD}分，暂不推进",
            next_stage="已结束",
        )
        resume_score = parsed.score

    new_stage = _advance_stage(stage, result)
    db.upsert_session(
        req.candidate_id,
        new_stage,
        resume,
        turns + 1,
        conversation_hash=conv_hash,
        resume_hash=res_hash,
        resume_score=resume_score,
    )
    return result


def _advance_stage(current_stage: str, result: ReplyResponse) -> str:
    if result.reason.rpa_action == "skip":
        return current_stage
    next_stage = result.reason.next_stage
    if next_stage in STAGES:
        return next_stage
    return _STAGE_BY_ACTION.get(result.reason.rpa_action, current_stage)


def _generate_reply(system: str, user: str):
    provider = get_provider()
    try:
        raw = provider.generate(system, user)
    except LLMError as exc:
        logger.warning("主回复模型调用失败, 返回兜底: %s", exc)
        return ParsedReply(response=FALLBACK_REPLY, is_valid=True)

    parsed = parse_reply_result(raw)
    if parsed.is_valid:
        return parsed

    repair_system, repair_user = build_repair_messages(raw)
    try:
        repaired_raw = provider.generate(
            repair_system, repair_user, temperature=settings.llm_temperature_structured
        )
    except LLMError as exc:
        logger.warning("修复调用失败, 返回兜底: %s", exc)
        return ParsedReply(response=FALLBACK_REPLY, is_valid=True)

    repaired = parse_reply_result(repaired_raw)
    return repaired if repaired.is_valid else ParsedReply(response=FALLBACK_REPLY, is_valid=True)
