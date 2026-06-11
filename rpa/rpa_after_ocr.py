"""OCR 完成后二次调用 /reply 的影刀 Python 片段。

影刀变量（由前置步骤注入）:
- api_url / current_job_id / chat_data
- resume_person   OCR 识别出的简历文本

输出变量: rpa_action / content / need_resume_ocr / rpa_log
接口异常时降级为 rpa_action="skip"，不中断影刀流程。
"""

import json
import time

import requests

start = time.time()
chat_data = chat_data if isinstance(chat_data, dict) else json.loads(chat_data)

payload = {
    "candidate_id": chat_data.get("candidate_id") or "unknown",
    "conversation": chat_data.get("conversation") or "",
    "resume": (resume_person or "").strip(),
    "job_id": current_job_id,
    "trigger": "after_resume_ocr",
    "last_message_from": chat_data.get("last_message_from") or "",
}


def _elapsed_ms():
    return int((time.time() - start) * 1000)


try:
    resp = requests.post(api_url, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
except Exception as exc:
    result = None
    rpa_action = "skip"
    content = ""
    need_resume_ocr = False
    rpa_log = json.dumps(
        {
            "phase": "error",
            "candidate_id": payload["candidate_id"],
            "rpa_action": rpa_action,
            "error": f"{type(exc).__name__}: {exc}",
            "elapsed_ms": _elapsed_ms(),
        },
        ensure_ascii=False,
    )

if result is not None:
    rpa_action = result["reason"]["rpa_action"]
    content = result.get("answer") or ""
    need_resume_ocr = bool(result.get("need_resume_ocr"))
    if rpa_action == "send_company_address":
        content = ""

    rpa_log = json.dumps(
        {
            "phase": "after_ocr",
            "candidate_id": payload["candidate_id"],
            "rpa_action": rpa_action,
            "need_resume_ocr": need_resume_ocr,
            "basis": result["reason"].get("basis", ""),
            "elapsed_ms": _elapsed_ms(),
        },
        ensure_ascii=False,
    )

answer = json.dumps(result, ensure_ascii=False) if result is not None else ""
