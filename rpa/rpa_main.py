"""
影刀「插入代码段(Python)」参考 — 统一单循环 /reply 调用。

影刀变量（由前置步骤注入）:
- api_url          例如 http://127.0.0.1:8000/reply
- current_job_id   例如 ecommerce_ops_suzhou
- chat_data        extract_chat.js 返回并 json.loads 后的 dict
- resume_person    OCR 后的简历，无则 ""

输出变量:
- rpa_action       skip / request_resume / reply_message / send_company_address
- content          要发送的文本（无则空字符串）
- need_resume_ocr  true 时影刀执行 OCR 后调 rpa_after_ocr.py
- rpa_log          单行 JSON 日志，直接接「打印日志」节点

接口异常时不抛错: 降级为 rpa_action="skip"，影刀流程继续跑下一候选人。
"""

import json
import time

import requests

# --- 影刀注入变量（本地调试时可取消注释） ---
# api_url = "http://127.0.0.1:8000/reply"
# current_job_id = "ecommerce_ops_suzhou"
# chat_data = {"candidate_id": "test", "conversation": "你好", "last_message_from": "candidate"}
# resume_person = ""

start = time.time()
chat_data = chat_data if isinstance(chat_data, dict) else json.loads(chat_data)
resume_person = (resume_person or "").strip()

payload = {
    "candidate_id": chat_data.get("candidate_id") or "unknown",
    "conversation": chat_data.get("conversation") or "",
    "resume": resume_person,
    "job_id": current_job_id,
    "trigger": "auto",
    "last_message_from": chat_data.get("last_message_from") or "",
}


def _elapsed_ms():
    return int((time.time() - start) * 1000)


try:
    resp = requests.post(api_url, json=payload, timeout=30)
    resp.raise_for_status()
    result = resp.json()
except Exception as exc:  # 后端不可用 / 超时 / 非 200: 降级 skip，不中断影刀流程
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

    if need_resume_ocr and not resume_person:
        # 影刀后续: 点「附件简历」→ 等元素 → OCR → resume_person → rpa_after_ocr.py
        phase = "need_ocr"
    else:
        phase = "done"
        if rpa_action == "send_company_address":
            content = ""

    rpa_log = json.dumps(
        {
            "phase": phase,
            "candidate_id": payload["candidate_id"],
            "rpa_action": rpa_action,
            "need_resume_ocr": need_resume_ocr,
            "basis": result["reason"].get("basis", ""),
            "elapsed_ms": _elapsed_ms(),
        },
        ensure_ascii=False,
    )

answer = json.dumps(result, ensure_ascii=False) if result is not None else ""
