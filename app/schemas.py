"""Pydantic 模型: 请求 / 响应 / 模型输出结构。"""

from pydantic import BaseModel, Field

# 合法的 RPA 动作枚举 (影刀端按这些值分支)
RPA_ACTIONS = {
    "reply_message",  # 只发送 answer, 不做额外动作
    "send_company_address",  # 发送公司地址
}

# 招聘沟通阶段状态机 (stage 由 Python 维护, 模型每轮输出它判断的 next_stage)
# 初步接触 -> 了解动机 -> 能力验证 -> 邀约 -> 已结束
STAGES = {
    "初步接触",  # 用硬实力吸引 + 筛选意向
    "了解动机",  # 判断稳定性与求职动机 (在职/离职原因)
    "能力验证",  # 验证核心能力匹配
    "邀约",  # 直接邀约面试
    "约面中",  # 已触发发送地址/确认面试, 兼容旧值
    "已结束",  # 已约面或已礼貌退出, 不再主动推进
}

DEFAULT_STAGE = "初步接触"


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
    next_stage: str = Field(
        "", description="模型判断的下一招聘阶段 (取值限 STAGES); 影刀可忽略"
    )


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


class ResumeEvaluationRequest(BaseModel):
    """单独评价图片简历的请求体。"""

    candidate_id: str = Field("", description="候选人唯一标识，可为空")
    resume_text: str = Field("", description="图片简历 OCR 后的文本内容")
    resume_image_url: str = Field("", description="图片简历 URL 或 data URL，可为空")
    resume_video_url: str = Field("", description="视频简历 URL 或 data URL，可为空")
    job_requirement: str = Field(..., description="岗位招聘需求")


class ResumeEvaluationResponse(BaseModel):
    """简历匹配评价结果。"""

    candidate_id: str = ""
    score: int = Field(..., description="简历与岗位匹配分，0-100")
    passed: bool = Field(..., description="是否达到当前通过阈值")
    threshold: int = Field(..., description="当前通过阈值")
    basis: str = Field("", description="评分依据")
    matched: list[str] = Field(default_factory=list, description="匹配点")
    risks: list[str] = Field(default_factory=list, description="风险点")


class ResetRequest(BaseModel):
    candidate_id: str
