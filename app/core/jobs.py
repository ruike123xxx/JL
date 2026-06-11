"""岗位配置 lookup：影刀只传 job_id，JD/公司信息从此加载。"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.config import settings


@dataclass(frozen=True)
class JobContext:
    job_id: str
    job_title: str
    job_requirement: str
    company_info: str


@lru_cache(maxsize=1)
def _load_jobs_file() -> dict[str, JobContext]:
    path = Path(settings.jobs_path)
    if not path.is_absolute():
        path = Path(settings.project_root) / path
    if not path.exists():
        return {}

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    jobs: dict[str, JobContext] = {}
    for item in raw.get("jobs", []):
        job_id = str(item.get("job_id", "")).strip()
        if not job_id:
            continue
        jobs[job_id] = JobContext(
            job_id=job_id,
            job_title=str(item.get("job_title", "")).strip(),
            job_requirement=str(item.get("job_requirement", "")).strip(),
            company_info=str(item.get("company_info", "")).strip(),
        )
    return jobs


def resolve_job_context(
    *,
    job_id: str,
    job_requirement: str,
    company_info: str,
) -> tuple[str, str]:
    """按 job_id 补全 JD/公司信息；请求体显式传入的值优先。"""
    job_requirement = job_requirement.strip()
    company_info = company_info.strip()
    job_id = job_id.strip()

    if job_id:
        job = _load_jobs_file().get(job_id)
        if job:
            if not job_requirement:
                job_requirement = job.job_requirement
            if not company_info:
                company_info = job.company_info

    return job_requirement, company_info


def clear_jobs_cache() -> None:
    _load_jobs_file.cache_clear()
