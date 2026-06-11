"""Mock provider: 仅用于 pytest / 本地无 key 测试。"""

import json
import re

from app.core.scoring import SCORE_PASS_THRESHOLD, heuristic_score
from app.llm.base import LLMProvider


def _has(text: str, *keywords: str) -> bool:
    return any(k in text for k in keywords)


def _extract_scoring_inputs(user: str) -> tuple[str, str] | None:
    job_match = re.search(
        r"- 岗位招聘需求：\n(.+?)\n\n- 候选人简历内容：", user, flags=re.DOTALL
    )
    resume_match = re.search(
        r"- 候选人简历内容：\n(.+?)\n\n- 公司信息", user, flags=re.DOTALL
    )
    if job_match and resume_match:
        return job_match.group(1).strip(), resume_match.group(1).strip()
    return None


class MockProvider(LLMProvider):
    def generate(self, system: str, user: str, *, temperature: float | None = None) -> str:
        if "【简历匹配评估】" in system:
            inputs = _extract_scoring_inputs(user)
            if inputs:
                job_requirement, resume = inputs
                score = heuristic_score(resume=resume, job_requirement=job_requirement)
                if score.total < SCORE_PASS_THRESHOLD:
                    return json.dumps(
                        {
                            "score": score.total,
                            "answer": "您好，感谢您发送简历。我们看了下您目前的经历和本岗位核心要求还有一些差距，暂时先不进一步安排沟通。",
                            "reason": {
                                "rpa_action": "reply_message",
                                "basis": f"mock 评分{score.total}分低于阈值",
                                "next_stage": "已结束",
                            },
                        },
                        ensure_ascii=False,
                    )
                return json.dumps(
                    {
                        "score": score.total,
                        "answer": "您好，简历收到了，背景和岗位比较匹配，想进一步了解下您的项目经验。",
                        "reason": {
                            "rpa_action": "reply_message",
                            "basis": "mock 合并评分通过",
                            "next_stage": "能力验证",
                        },
                    },
                    ensure_ascii=False,
                )

        if "简历筛选助手" in system:
            from app.core.scoring import heuristic_score_json

            inputs = _extract_scoring_inputs_legacy(user)
            if inputs:
                job_requirement, resume = inputs
                return heuristic_score_json(resume=resume, job_requirement=job_requirement)

        text = user

        if _has(text, "地址", "面试地点", "怎么去", "在哪", "到场"):
            result = {
                "answer": "",
                "reason": {
                    "rpa_action": "send_company_address",
                    "basis": "候选人询问公司地址/面试地点",
                    "next_stage": "已结束",
                },
            }
        elif _has(text, "不感兴趣", "已入职", "已找到", "不考虑", "暂时不"):
            result = {
                "answer": "好的，理解～那就先不打扰您了。后续若有更合适的机会我再联系您，祝您工作顺利！",
                "reason": {
                    "rpa_action": "reply_message",
                    "basis": "候选人表达无意向/已入职，礼貌收尾",
                    "next_stage": "已结束",
                },
            }
        elif _has(text, "面试", "约个时间", "什么时候", "时间"):
            result = {
                "answer": "您的经历和岗位比较匹配，想邀请您进一步沟通。您看本周哪天方便？我这边帮您安排面试时间。",
                "reason": {
                    "rpa_action": "reply_message",
                    "basis": "候选人表达面试意向",
                    "next_stage": "邀约",
                },
            }
        else:
            result = {
                "answer": "您好，感谢关注本岗位！想请教一下您过往项目中负责的核心模块是哪些？",
                "reason": {
                    "rpa_action": "reply_message",
                    "basis": "初步了解阶段",
                    "next_stage": "了解动机",
                },
            }

        return json.dumps(result, ensure_ascii=False)


def _extract_scoring_inputs_legacy(user: str) -> tuple[str, str] | None:
    job_match = re.search(r"岗位要求：\n(.+?)\n\n候选人简历：", user, flags=re.DOTALL)
    resume_match = re.search(r"候选人简历：\n(.+?)\n\n请按评分规则", user, flags=re.DOTALL)
    if job_match and resume_match:
        return job_match.group(1).strip(), resume_match.group(1).strip()
    return None
