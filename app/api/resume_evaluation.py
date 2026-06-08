"""单独评价图片简历 OCR 文本的接口。"""

from fastapi import APIRouter, HTTPException

from app.core.scoring import (
    SCORE_PASS_THRESHOLD,
    score_resume,
    score_resume_image,
    score_resume_video,
)
from app.schemas import ResumeEvaluationRequest, ResumeEvaluationResponse

router = APIRouter()


@router.post("/resume/evaluate", response_model=ResumeEvaluationResponse)
def evaluate_resume(req: ResumeEvaluationRequest) -> ResumeEvaluationResponse:
    """评价图片简历与岗位要求的匹配度。"""
    if req.resume_video_url.strip():
        try:
            score = score_resume_video(
                video_url=req.resume_video_url,
                job_requirement=req.job_requirement,
            )
        except NotImplementedError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif req.resume_image_url.strip():
        try:
            score = score_resume_image(
                image_url=req.resume_image_url,
                job_requirement=req.job_requirement,
            )
        except NotImplementedError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif req.resume_text.strip():
        score = score_resume(
            resume=req.resume_text,
            job_requirement=req.job_requirement,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="resume_text、resume_image_url、resume_video_url 至少传一个",
        )

    return ResumeEvaluationResponse(
        candidate_id=req.candidate_id,
        score=score.total,
        passed=score.passed,
        threshold=SCORE_PASS_THRESHOLD,
        basis=score.basis,
        matched=score.matched,
        risks=score.risks,
    )
