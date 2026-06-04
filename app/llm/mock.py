"""Mock provider: 返回结构合法的假 JSON, 用于和 RPA 联调。

根据 user 提示词里的内容做简单规则判断, 让联调时能看到不同的 rpa_action 分支:
- 简历为空            -> request_resume
- 提到地址/面试地点   -> send_company_address
- 其它                -> reply_message

注意: 这是假数据, 不调用任何真实模型。返回的是 JSON 字符串
(故意保留外层可能的 markdown 包裹场景由 json_repair 处理, 此处返回纯净 JSON)。
"""

import json

from app.llm.base import LLMProvider


def _has(text: str, *keywords: str) -> bool:
    return any(k in text for k in keywords)


class MockProvider(LLMProvider):
    def generate(self, system: str, user: str) -> str:
        text = user

        # 简历是否缺失: prompt 里简历段落为空时的简单探测
        resume_missing = (
            "候选人简历内容：\n\n" in user or "候选人简历内容：\n（无）" in user
        )

        if resume_missing:
            result = {
                "answer": "",
                "reason": {
                    "rpa_action": "request_resume",
                    "basis": "候选人尚未提供简历，无法判断匹配度",
                },
            }
        elif _has(text, "地址", "面试地点", "怎么去", "在哪", "到场"):
            result = {
                "answer": "",
                "reason": {
                    "rpa_action": "send_company_address",
                    "basis": "候选人询问公司地址/面试地点",
                },
            }
        elif _has(text, "面试", "约个时间", "什么时候", "时间"):
            result = {
                "answer": "您的经历和岗位比较匹配，想邀请您进一步沟通。您看本周哪天方便？我这边帮您安排面试时间。",
                "reason": {
                    "rpa_action": "reply_message",
                    "basis": "候选人表达面试意向，先通过回复确认可面试时间",
                },
            }
        else:
            result = {
                "answer": "您好，感谢关注本岗位！这边补充几点信息供您参考：公司实行单双休，岗位偶有加班，工作地点在市区。结合您的经历，想请教一下您过往项目中负责的核心模块是哪些？",
                "reason": {
                    "rpa_action": "reply_message",
                    "basis": "候选人处于初步了解阶段，同步关键信息并提出针对性问题",
                },
            }

        return json.dumps(result, ensure_ascii=False)
