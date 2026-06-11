"""模型返回 JSON 的容错解析。"""

import json
import re
from dataclasses import dataclass

from app.schemas import MODEL_RPA_ACTIONS, RPA_ACTIONS, STAGES, ReplyReason, ReplyResponse

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

FALLBACK_REPLY = ReplyResponse(
    answer="您好，感谢您的消息，我稍后回复您。",
    need_resume_ocr=False,
    reason=ReplyReason(
        rpa_action="reply_message",
        basis="模型返回结构不符合要求，已使用兜底回复",
    ),
)

REPAIR_SYSTEM_PROMPT = """你是 JSON 修复器。请把输入中的模型原始输出修复为严格 JSON。
只能输出 JSON，不要输出 Markdown，不要添加解释。

标准结构：
{
  "score": 0,
  "answer": "reply_message/request_resume 时填写；send_company_address/skip 时必须为空字符串",
  "reason": {
    "rpa_action": "reply_message 或 send_company_address",
    "basis": "简要说明依据",
    "next_stage": "可选，取值：初步接触/了解动机/能力验证/邀约/已结束，拿不准就留空字符串"
  }
}

规则：
- rpa_action 只能是 "reply_message" 或 "send_company_address"（模型不输出 skip/request_resume）。
- reply_message 时 answer 必须有内容；send_company_address 时 answer 必须为空字符串。
- 若原文含 score 字段，保留 0-100 整数。"""


@dataclass(frozen=True)
class ParsedReply:
    response: ReplyResponse
    is_valid: bool
    score: int | None = None


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _JSON_BLOCK.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def _parse_score_value(data: dict) -> int | None:
    if "score" not in data:
        return None
    try:
        return max(0, min(100, int(data.get("score", 0))))
    except (TypeError, ValueError):
        return None


def _build_reason(reason_raw) -> tuple[ReplyReason, bool]:
    is_valid = True
    if isinstance(reason_raw, str):
        return ReplyReason(rpa_action="reply_message", basis=reason_raw), False
    if not isinstance(reason_raw, dict):
        return ReplyReason(), False

    action = str(reason_raw.get("rpa_action", "reply_message")).strip()
    if action not in MODEL_RPA_ACTIONS:
        is_valid = False
        action = "reply_message"
    basis = str(reason_raw.get("basis", "")).strip()
    next_stage = str(reason_raw.get("next_stage", "")).strip()
    if next_stage and next_stage not in STAGES:
        next_stage = ""
    return (
        ReplyReason(rpa_action=action, basis=basis, next_stage=next_stage),
        is_valid,
    )


def _validate_answer(action: str, answer: str) -> tuple[str, bool]:
    is_valid = True
    if action in {"send_company_address", "skip"}:
        if answer:
            is_valid = False
        return "", is_valid
    if action == "request_resume":
        return answer, True
    if action == "reply_message":
        if not answer:
            is_valid = False
        return answer, is_valid
    return answer, is_valid


def parse_reply(raw: str) -> ReplyResponse:
    return parse_reply_result(raw).response


def parse_reply_result(raw: str) -> ParsedReply:
    data = _extract_json(raw)
    if not data:
        return ParsedReply(response=FALLBACK_REPLY, is_valid=False)

    score = _parse_score_value(data)
    is_valid = True
    answer = str(data.get("answer", "")).strip()
    reason, reason_valid = _build_reason(data.get("reason", {}))
    is_valid = is_valid and reason_valid

    answer, answer_valid = _validate_answer(reason.rpa_action, answer)
    is_valid = is_valid and answer_valid

    if reason.rpa_action == "reply_message" and not answer:
        return ParsedReply(response=FALLBACK_REPLY, is_valid=False, score=score)

    response = ReplyResponse(answer=answer, reason=reason, need_resume_ocr=False)
    return ParsedReply(response=response, is_valid=is_valid, score=score)


def build_repair_messages(raw: str) -> tuple[str, str]:
    return REPAIR_SYSTEM_PROMPT, f"模型原始输出：\n{raw}"


def make_fast_response(
    *,
    rpa_action: str,
    answer: str = "",
    basis: str = "",
    next_stage: str = "",
    need_resume_ocr: bool = False,
) -> ReplyResponse:
    action = rpa_action if rpa_action in RPA_ACTIONS else "reply_message"
    answer, _ = _validate_answer(action, answer)
    return ReplyResponse(
        answer=answer,
        need_resume_ocr=need_resume_ocr,
        reason=ReplyReason(rpa_action=action, basis=basis, next_stage=next_stage),
    )
