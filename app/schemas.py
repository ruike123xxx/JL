"""Pydantic 模型: 请求 / 响应 / 模型输出结构。"""

from pydantic import BaseModel, Field

# 合法的 RPA 动作枚举 (影刀端按这些值分支)
RPA_ACTIONS = {
    "reply_message",  # 只发送 answer, 不做额外动作
    "request_resume",  # 索要简历
    "send_company_address",  # 发送公司地址
}

DEFAULT_STAGE = "初次接触"


class ReplyRequest(BaseModel):
    """RPA 每轮抓取后发来的请求体。"""

    candidate_id: str = Field(..., description="候选人唯一标识")
    conversation: str = Field("", description="RPA 抓取的当前窗口全部可见对话文本")
    resume: str = Field("", description="候选人简历文本, 没有则空字符串")
    job_requirement: str = Field("", description="岗位招聘需求")
    company_info: str = Field("", description="公司信息")


class ReplyReason(BaseModel):
    """模型输出的动作与依据 (结构化, 供影刀读取)。"""

    rpa_action: str = Field("reply_message", description="需要触发的影刀动作")
    basis: str = Field("", description="依据说明")


class ReplyResponse(BaseModel):
    """返回给 RPA 的响应体。"""

    answer: str = Field("", description="rpa_action=reply_message 时给候选人的回复内容")
    reason: ReplyReason


class ConversationIngestRequest(BaseModel):
    """影刀第一步上传的对话文本。"""

    candidate_id: str = Field(..., description="候选人唯一标识")
    conversation: str = Field("", description="影刀抓取的当前窗口全部可见对话文本")


class ConversationIngestResponse(BaseModel):
    """对话文本上传回执。"""

    candidate_id: str
    received: bool
    conversation_chars: int = Field(..., description="收到的对话文本字符数")
    stage: str = Field(..., description="当前候选人招聘阶段")
    next_endpoint: str = Field(..., description="下一步生成回复可调用的接口")


class ResetRequest(BaseModel):
    candidate_id: str
