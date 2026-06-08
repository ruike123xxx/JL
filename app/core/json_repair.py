"""模型返回 JSON 的容错解析。

模型偶尔会:
- 用 ```json ... ``` 包裹
- 在 JSON 前后加解释文字
- 字段缺失 / rpa_action 给了非法值

策略: 先直接 json.loads; 失败则抠出第一个 {...} 块再解析;
最后用 Pydantic 校验并补默认值。结构不合规时由 pipeline 触发一次模型修复。
"""

import json
import re
from dataclasses import dataclass

from app.schemas import RPA_ACTIONS, STAGES, ReplyReason, ReplyResponse

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

FALLBACK_REPLY = ReplyResponse(
    answer="您好，感谢您的消息，我稍后回复您。",
    reason=ReplyReason(
        rpa_action="reply_message",
        basis="模型返回结构不符合要求，已使用兜底回复",
    ),
)

REPAIR_SYSTEM_PROMPT = """你是 JSON 修复器。请把输入中的模型原始输出修复为严格 JSON。
只能输出 JSON，不要输出 Markdown，不要添加解释。

标准结构：
{
  "answer": "只有 rpa_action 为 reply_message 时填写；send_company_address 时必须为空字符串",
  "reason": {
    "rpa_action": "reply_message 或 send_company_address",
    "basis": "简要说明依据",
    "next_stage": "可选，取值：初步接触/了解动机/能力验证/邀约/已结束，拿不准就留空字符串"
  }
}

规则：
- rpa_action 只能是 "reply_message" 或 "send_company_address"。
- 如果是普通回复，rpa_action 用 "reply_message"，answer 必须有内容。
- 如果候选人询问地址、面试地点、怎么去、到场方式，rpa_action 用 "send_company_address"，answer 必须是空字符串。
- next_stage 只能取上述五个阶段之一或空字符串，不要臆造其它值。
- 不要新增其它字段。"""


@dataclass(frozen=True)
class ParsedReply:
    response: ReplyResponse
    is_valid: bool


def _extract_json(text: str) -> dict:
    text = text.strip()
    # 去掉 markdown 代码围栏
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 抠出第一个 {...} 块
    m = _JSON_BLOCK.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def parse_reply(raw: str) -> ReplyResponse:
    """把模型原始文本解析为校验后的 ReplyResponse, 永不抛错。"""
    return parse_reply_result(raw).response


def parse_reply_result(raw: str) -> ParsedReply:
    """解析模型输出，并标记原始结构是否已经符合标准。"""
    data = _extract_json(raw)
    if not data:
        return ParsedReply(response=FALLBACK_REPLY, is_valid=False)

    is_valid = True
    answer_raw = data.get("answer", "")
    if not isinstance(answer_raw, str):
        is_valid = False
    answer = str(answer_raw).strip()

    reason_raw = data.get("reason", {})
    if isinstance(reason_raw, str):
        is_valid = False
        reason = ReplyReason(rpa_action="reply_message", basis=reason_raw)
    elif isinstance(reason_raw, dict):
        action_raw = reason_raw.get("rpa_action", "reply_message")
        action = str(action_raw).strip()
        if action not in RPA_ACTIONS:
            is_valid = False
            action = "reply_message"
        basis_raw = reason_raw.get("basis", "")
        if not isinstance(basis_raw, str):
            is_valid = False
        # next_stage 容错: 非法值置空, 由 pipeline 兜底为不推进 (不算致命错误)
        next_stage = str(reason_raw.get("next_stage", "")).strip()
        if next_stage and next_stage not in STAGES:
            next_stage = ""
        reason = ReplyReason(
            rpa_action=action,
            basis=str(basis_raw).strip(),
            next_stage=next_stage,
        )
    else:
        is_valid = False
        reason = ReplyReason()

    if reason.rpa_action != "reply_message":
        if answer:
            is_valid = False
        answer = ""
    elif not answer:
        is_valid = False
        return ParsedReply(response=FALLBACK_REPLY, is_valid=False)

    return ParsedReply(
        response=ReplyResponse(answer=answer, reason=reason), is_valid=is_valid
    )


def build_repair_messages(raw: str) -> tuple[str, str]:
    """构造一次性模型修复 Prompt。"""
    return REPAIR_SYSTEM_PROMPT, f"模型原始输出：\n{raw}"
