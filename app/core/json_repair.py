"""模型返回 JSON 的容错解析。

模型偶尔会:
- 用 ```json ... ``` 包裹
- 在 JSON 前后加解释文字
- 字段缺失 / rpa_action 给了非法值

策略: 先直接 json.loads; 失败则抠出第一个 {...} 块再解析;
最后用 Pydantic 校验并补默认值, 非法的 rpa_action 归一为 reply_message。
"""

import json
import re

from app.schemas import RPA_ACTIONS, ReplyReason, ReplyResponse

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


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
    data = _extract_json(raw)

    answer = str(data.get("answer", "")).strip()

    reason_raw = data.get("reason", {})
    if isinstance(reason_raw, str):
        # 兼容最简版: reason 是一段文字
        reason = ReplyReason(rpa_action="reply_message", basis=reason_raw)
    elif isinstance(reason_raw, dict):
        action = str(reason_raw.get("rpa_action", "reply_message")).strip()
        if action not in RPA_ACTIONS:
            action = "reply_message"
        reason = ReplyReason(
            rpa_action=action,
            basis=str(reason_raw.get("basis", "")).strip(),
        )
    else:
        reason = ReplyReason()

    if reason.rpa_action != "reply_message":
        answer = ""
    elif not answer:
        # 兜底: 解析彻底失败或 reply_message 缺少 answer 时, 给一个安全提示
        answer = "您好，感谢您的消息，我稍后回复您。"
        reason = ReplyReason(
            rpa_action="reply_message",
            basis="模型返回无法解析为有效JSON",
        )

    return ReplyResponse(answer=answer, reason=reason)
