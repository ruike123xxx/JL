"""不调 LLM 的前置规则：skip / request_resume / need_resume_ocr。"""

import hashlib
import re

from app.schemas import ReplyReason, ReplyRequest, ReplyResponse

ONLINE_ONLY_HINT = "备注：无附件简历，仅在线简历"
REQUEST_RESUME_MARKERS = ("方便看下你的简历", "发一下简历", "求简历", "简历吗", "先看下简历")


def conversation_fingerprint(conversation: str) -> str:
    return hashlib.sha256(conversation.strip().encode("utf-8")).hexdigest()


def resume_fingerprint(resume: str) -> str:
    text = resume.strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _already_requested_resume(conversation: str) -> bool:
    return any(marker in conversation for marker in REQUEST_RESUME_MARKERS)


def compute_need_resume_ocr(*, conversation: str, resume: str, trigger: str) -> bool:
    if resume.strip():
        return False
    if trigger == "after_resume_ocr":
        return False
    if ONLINE_ONLY_HINT in conversation:
        return False
    if "附件简历" in conversation:
        return True
    return False


def infer_last_message_from(conversation: str) -> str:
    """从对话文本推断最后发言方（影刀未传 last_message_from 时的兜底）。"""
    text = conversation.strip()
    if not text:
        return "unknown"

    patterns = [
        (r"(?:^|\n)\s*(?:候选人|对方|求职者)\s*[:：]", "candidate"),
        (r"(?:^|\n)\s*(?:HR|我|招聘方)\s*[:：]", "hr"),
    ]
    last_idx = -1
    last_speaker = "unknown"
    for pattern, speaker in patterns:
        for match in re.finditer(pattern, text):
            if match.start() >= last_idx:
                last_idx = match.start()
                last_speaker = speaker
    return last_speaker


def try_fast_path(
    req: ReplyRequest,
    *,
    stage: str,
    conversation_hash: str,
    stored_hash: str,
    resume: str,
) -> ReplyResponse | None:
    conv = req.conversation or ""
    last_from = (req.last_message_from or "").strip().lower() or infer_last_message_from(conv)

    if stage == "已结束":
        return ReplyResponse(
            answer="",
            need_resume_ocr=False,
            reason=ReplyReason(
                rpa_action="skip",
                basis="会话阶段已结束，不再主动推进",
            ),
        )

    if conversation_hash and conversation_hash == stored_hash:
        return ReplyResponse(
            answer="",
            need_resume_ocr=False,
            reason=ReplyReason(
                rpa_action="skip",
                basis="对话内容与上次相同，无需重复处理",
            ),
        )

    if last_from == "hr" and req.trigger == "auto":
        return ReplyResponse(
            answer="",
            need_resume_ocr=False,
            reason=ReplyReason(
                rpa_action="skip",
                basis="最后一条为 HR 发送，等待候选人回复",
            ),
        )

    if (
        ONLINE_ONLY_HINT in conv
        and not resume.strip()
        and not _already_requested_resume(conv)
        and req.trigger != "after_resume_ocr"
    ):
        return ReplyResponse(
            answer="你好，方便看下你的简历吗？",
            need_resume_ocr=False,
            reason=ReplyReason(
                rpa_action="request_resume",
                basis="仅在线简历，引导候选人发送附件简历",
                next_stage="初步接触",
            ),
        )

    need_ocr = compute_need_resume_ocr(
        conversation=conv,
        resume=resume,
        trigger=req.trigger,
    )
    if need_ocr and not resume.strip():
        return ReplyResponse(
            answer="",
            need_resume_ocr=True,
            reason=ReplyReason(
                rpa_action="skip",
                basis="检测到附件简历，需影刀 OCR 后再次调用",
            ),
        )

    return None
