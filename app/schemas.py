"""Pydantic 模型: 请求 / 响应 / 模型输出结构。"""

from typing import Literal

from pydantic import BaseModel, Field

# 合法的 RPA 动作枚举 (影刀端按这些值分支)
RPA_ACTIONS = {
    "reply_message",  # 发送 answer
    "send_company_address",  # 执行发地址预设
    "request_resume",  # 发送 answer（可选）+ 点击求简历
    "skip",  # 不操作，继续下一个候选人
}

# 招聘沟通阶段状态机 (stage 由 Python 维护, 模型每轮输出它判断的 next_stage)
STAGES = {
    "初步接触",
    "了解动机",
    "能力验证",
    "邀约",
    "约面中",
    "已结束",
}

DEFAULT_STAGE = "初步接触"

# skip/request_resume 由服务端前置规则产生；模型只应输出以下子集
MODEL_RPA_ACTIONS = {
    "reply_message",
    "send_company_address",
}


class ReplyRequest(BaseModel):
    """RPA 每轮抓取后发来的请求体。"""

    candidate_id: str = Field(..., description="候选人唯一标识")
    conversation: str = Field("", description="RPA 抓取的当前窗口全部可见对话文本")
    resume: str = Field("", description="候选人简历文本, 没有则空字符串")
    job_requirement: str = Field("", description="岗位招聘需求；可留空，配合 job_id 使用")
    company_info: str = Field("", description="公司信息；可留空，配合 job_id 使用")
    job_id: str = Field("", description="岗位编码，从 jobs.yaml 加载 JD/公司信息")
    trigger: Literal["auto", "after_resume_ocr"] = Field(
        default="auto",
        description="auto=常规轮次；after_resume_ocr=影刀 OCR 完成后二次调用",
    )
    last_message_from: Literal["", "candidate", "hr", "system", "unknown"] = Field(
        default="",
        description="JS 抓取的最后发言方，用于 skip 判断",
    )


class ReplyReason(BaseModel):
    """动作与依据 (结构化, 供影刀读取)。"""

    rpa_action: str = Field("reply_message", description="需要触发的影刀动作")
    basis: str = Field("", description="依据说明")
    next_stage: str = Field(
        "", description="模型判断的下一招聘阶段 (取值限 STAGES); 影刀可忽略"
    )


class ReplyResponse(BaseModel):
    """返回给 RPA 的响应体。"""

    answer: str = Field("", description="reply_message/request_resume 时可发送的文本")
    reason: ReplyReason
    need_resume_ocr: bool = Field(
        default=False,
        description="true 时影刀应点附件简历 OCR 后带 resume 再调 /reply",
    )


class ResetRequest(BaseModel):
    candidate_id: str
