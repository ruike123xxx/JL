"""简历匹配评分。"""

import json
import re
from dataclasses import dataclass, field

from app.config import settings
from app.llm.base import get_provider

SCORE_PASS_THRESHOLD = 60
LOW_SCORE_MESSAGE = (
    "您好，感谢您发送简历。我们看了下您目前的经历和本岗位核心要求还有一些差距，"
    "暂时先不进一步安排沟通。后续如果有更匹配的岗位，我们再和您联系，祝您求职顺利。"
)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

SCORING_SYSTEM_PROMPT = """你是一名招聘简历筛选助手，负责判断候选人简历与岗位要求的匹配度。
请只根据候选人简历和岗位要求打分，不要考虑年龄、婚育、民族、宗教、健康隐私等不合规因素。

评分规则：
- 总分 0-100。
- 重点看硬性要求、相关工作经验、关键技能、行业/岗位相似度、稳定性风险。
- 明显缺少核心经验时应低于 60 分。
- 只输出严格 JSON，不要输出 Markdown 或额外解释。

输出格式：
{
  "score": 0,
  "basis": "一句话说明评分依据",
  "matched": ["匹配点1", "匹配点2"],
  "risks": ["风险点1", "风险点2"]
}"""

SCORING_USER_TEMPLATE = """岗位要求：
{{job_requirement}}

候选人简历：
{{resume}}

请按评分规则输出严格 JSON。"""

MEDIA_SCORING_PROMPT_TEMPLATE = """请读取{{media_label}}中的简历内容，并评价它与岗位要求的匹配度。

岗位要求：
{{job_requirement}}

请按以下 JSON 格式输出，不要输出 Markdown 或额外解释：
{
  "score": 0,
  "basis": "一句话说明评分依据",
  "matched": ["匹配点1", "匹配点2"],
  "risks": ["风险点1", "风险点2"]
}"""


@dataclass(frozen=True)
class ResumeScore:
    total: int
    basis: str = ""
    matched: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.total >= SCORE_PASS_THRESHOLD


def score_resume(*, resume: str, job_requirement: str) -> ResumeScore:
    """返回简历匹配评分；解析失败时默认放行，避免误伤候选人。"""
    resume = resume.strip()
    job_requirement = job_requirement.strip()
    if not resume or not job_requirement:
        return ResumeScore(total=100, basis="缺少简历或岗位要求，跳过评分并默认放行")

    if settings.llm_provider.lower() == "mock":
        return _heuristic_score(resume=resume, job_requirement=job_requirement)

    system, user = _build_score_messages(resume=resume, job_requirement=job_requirement)
    raw = get_provider().generate(system, user)
    return _parse_score(raw)


def score_resume_image(*, image_url: str, job_requirement: str) -> ResumeScore:
    """读取图片简历并评分；需要当前 provider 支持图片输入。"""
    image_url = image_url.strip()
    job_requirement = job_requirement.strip()
    if not image_url or not job_requirement:
        return ResumeScore(total=100, basis="缺少图片或岗位要求，跳过评分并默认放行")

    if settings.llm_provider.lower() == "mock":
        return ResumeScore(total=100, basis="mock provider 不读取图片，默认放行")

    prompt = _build_media_score_prompt(
        media_label="图片", job_requirement=job_requirement
    )
    raw = get_provider().generate_with_image_url(prompt=prompt, image_url=image_url)
    return _parse_score(raw)


def score_resume_video(*, video_url: str, job_requirement: str) -> ResumeScore:
    """读取视频简历并评分；需要当前 provider 支持视频输入。"""
    video_url = video_url.strip()
    job_requirement = job_requirement.strip()
    if not video_url or not job_requirement:
        return ResumeScore(total=100, basis="缺少视频或岗位要求，跳过评分并默认放行")

    if settings.llm_provider.lower() == "mock":
        return ResumeScore(total=100, basis="mock provider 不读取视频，默认放行")

    prompt = _build_media_score_prompt(
        media_label="视频", job_requirement=job_requirement
    )
    raw = get_provider().generate_with_video_url(prompt=prompt, video_url=video_url)
    return _parse_score(raw)


def _build_media_score_prompt(*, media_label: str, job_requirement: str) -> str:
    return MEDIA_SCORING_PROMPT_TEMPLATE.replace(
        "{{media_label}}", media_label
    ).replace("{{job_requirement}}", job_requirement)


def _build_score_messages(*, resume: str, job_requirement: str) -> tuple[str, str]:
    user = SCORING_USER_TEMPLATE.replace(
        "{{job_requirement}}", job_requirement
    ).replace("{{resume}}", resume)
    return SCORING_SYSTEM_PROMPT, user


def _parse_score(raw: str) -> ResumeScore:
    data = _extract_json(raw)
    if not data:
        return ResumeScore(total=100, basis="评分结果无法解析，默认放行")

    try:
        total = int(data.get("score", data.get("total", 100)))
    except (TypeError, ValueError):
        total = 100

    total = max(0, min(100, total))
    return ResumeScore(
        total=total,
        basis=str(data.get("basis", "")).strip(),
        matched=_string_list(data.get("matched", [])),
        risks=_string_list(data.get("risks", [])),
    )


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if not match:
            return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _heuristic_score(*, resume: str, job_requirement: str) -> ResumeScore:
    resume_lower = resume.lower()
    job_lower = job_requirement.lower()
    keywords = _extract_keywords(job_lower)
    if not keywords:
        return ResumeScore(total=100, basis="岗位要求关键词不足，默认放行")

    matched = [keyword for keyword in keywords if keyword in resume_lower]
    ratio = len(matched) / len(keywords)
    total = int(35 + ratio * 65)
    risks = [] if total >= SCORE_PASS_THRESHOLD else ["简历中缺少岗位核心关键词"]
    return ResumeScore(
        total=max(0, min(100, total)),
        basis=f"mock 关键词匹配 {len(matched)}/{len(keywords)}",
        matched=matched,
        risks=risks,
    )


def _extract_keywords(text: str) -> list[str]:
    candidates = re.findall(r"[a-zA-Z][a-zA-Z+#.]*|[\u4e00-\u9fff]{2,}", text)
    stopwords = {
        "岗位职责",
        "任职要求",
        "相关",
        "以上",
        "以下",
        "熟悉",
        "熟练",
        "使用",
        "良好",
        "能力",
        "工作",
        "经验",
        "负责",
        "处理",
        "以及",
        "各种",
        "其它",
        "其他",
        "公司",
        "要求",
        "岗位",
        "优先",
        "具备",
        "独立",
    }
    keywords = []
    for candidate in candidates:
        keyword = candidate.lower()
        if keyword in stopwords or len(keyword) > 12:
            continue
        if keyword not in keywords:
            keywords.append(keyword)
    return keywords[:30]
