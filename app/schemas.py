"""Pydantic 模型: 请求 / 响应 / 模型输出结构。"""
from pydantic import BaseModel, Field

# 合法的 RPA 动作枚举 (RPA 端按这些值分支)
RPA_ACTIONS = {
    "none",
    "request_resume",          # 索要简历
    "send_company_address",    # 发送公司地址
    "confirm_interview_time",  # 确认面试时间
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
    """模型输出的决策依据 (结构化, 供 RPA 读取)。"""
    reply_intent: str = Field("", description="本次回复目的")
    rpa_action: str = Field("none", description="需要触发的 RPA 动作")
    basis: str = Field("", description="依据说明")


class ReplyResponse(BaseModel):
    """返回给 RPA 的响应体。"""
    answer: str = Field(..., description="给候选人的正式回复内容")
    reason: ReplyReason


class ResetRequest(BaseModel):
    candidate_id: str
