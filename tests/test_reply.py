"""端到端测试: 用 mock provider 跑通 /reply, 断言返回结构与分支。"""

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# 测试用独立 db, 避免污染开发库
os.environ["DB_PATH"] = os.path.join(tempfile.gettempdir(), "test_sessions.db")
os.environ["LLM_PROVIDER"] = "mock"

from app.main import app  # noqa: E402
from app.store import db  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_db():
    db.init_db()
    yield
    if os.path.exists(os.environ["DB_PATH"]):
        os.remove(os.environ["DB_PATH"])


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _post(client, **overrides):
    body = {
        "candidate_id": "t1",
        "conversation": "你好，我想了解下这个岗位",
        "resume": "",
        "job_requirement": "Java后端开发",
        "company_info": "某科技公司，单双休",
    }
    body.update(overrides)
    return client.post("/reply", json=body)


def test_response_shape(client):
    r = _post(client)
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "reason" in data
    assert set(data["reason"]) == {"rpa_action", "basis", "next_stage"}


def test_reply_missing_candidate_id_returns_hint(client):
    r = client.post("/reply", json={"conversation": "你好"})
    assert r.status_code == 422
    data = r.json()
    assert data["error"] == "请求体不符合接口要求"
    assert data["expected_body"]["candidate_id"] == "boss_user_12345"


def test_no_resume_still_replies_message(client):
    r = _post(client, resume="")
    data = r.json()
    assert data["answer"]
    assert data["reason"]["rpa_action"] == "reply_message"


def test_ask_address_triggers_send_address(client):
    r = _post(
        client,
        resume="5年Java经验，做过电商后台",
        conversation="公司面试地点在哪里？怎么去？",
    )
    data = r.json()
    assert data["answer"] == ""
    assert data["reason"]["rpa_action"] == "send_company_address"


def test_reply_message_has_answer(client):
    r = _post(client, resume="5年Java经验", conversation="我想了解岗位技术栈")
    data = r.json()
    assert data["answer"]
    assert data["reason"]["rpa_action"] == "reply_message"


def test_invalid_model_output_is_repaired_once(monkeypatch, client):
    class FakeProvider:
        def __init__(self):
            self.outputs = [
                "不是 JSON 的模型输出",
                json.dumps(
                    {
                        "answer": "您好，感谢关注，可以进一步沟通岗位细节。",
                        "reason": {
                            "rpa_action": "reply_message",
                            "basis": "修复为标准结构",
                        },
                    },
                    ensure_ascii=False,
                ),
            ]

        def generate(self, system, user, *, temperature=None):
            return self.outputs.pop(0)

    provider = FakeProvider()
    monkeypatch.setattr("app.core.pipeline.get_provider", lambda: provider)

    r = _post(client, resume="", conversation="您好，我想了解岗位")
    data = r.json()
    assert data == {
        "answer": "您好，感谢关注，可以进一步沟通岗位细节。",
        "reason": {
            "rpa_action": "reply_message",
            "basis": "修复为标准结构",
            "next_stage": "",
        },
    }
    assert provider.outputs == []


def test_invalid_model_output_falls_back_after_repair_failure(monkeypatch, client):
    class FakeProvider:
        def __init__(self):
            self.outputs = ["不是 JSON 的模型输出", "依然不是 JSON"]

        def generate(self, system, user, *, temperature=None):
            return self.outputs.pop(0)

    provider = FakeProvider()
    monkeypatch.setattr("app.core.pipeline.get_provider", lambda: provider)

    r = _post(client, resume="", conversation="您好，我想了解岗位")
    data = r.json()
    assert data["answer"] == "您好，感谢您的消息，我稍后回复您。"
    assert data["reason"] == {
        "rpa_action": "reply_message",
        "basis": "模型返回结构不符合要求，已使用兜底回复",
        "next_stage": "",
    }
    assert provider.outputs == []


def test_model_unavailable_returns_fallback_not_500(monkeypatch, client):
    """模型重试耗尽 (LLMUnavailableError) 时, /reply 应返回 200 兜底而非 500。"""
    from app.llm.base import LLMUnavailableError

    class FailingProvider:
        def generate(self, system, user, *, temperature=None):
            raise LLMUnavailableError("模型限流, 重试耗尽")

    monkeypatch.setattr("app.core.pipeline.get_provider", lambda: FailingProvider())

    r = _post(client, resume="", conversation="您好，我想了解岗位")
    assert r.status_code == 200
    data = r.json()
    assert data["answer"] == "您好，感谢您的消息，我稍后回复您。"
    assert data["reason"]["rpa_action"] == "reply_message"

    r = _post(
        client,
        resume="英语老师，主要负责一对一英语教学和课程规划",
        conversation="您好，我对岗位感兴趣",
        job_requirement="Java后端开发，熟悉Spring Boot和MySQL",
    )
    data = r.json()
    assert set(data) == {"answer", "reason"}
    assert data["reason"]["rpa_action"] == "reply_message"
    assert "暂时先不进一步安排沟通" in data["answer"]
    assert "低于60分" in data["reason"]["basis"]


def test_rpa_action_always_valid(client):
    valid = {"reply_message", "send_company_address"}
    r = _post(client, resume="有经验", conversation="随便聊聊")
    assert r.json()["reason"]["rpa_action"] in valid


def test_stage_advances_and_turns_increment(client):
    """首轮: 默认 初步接触, mock 输出 next_stage=了解动机 -> 库里 stage 推进, turns=1。"""
    _post(client, candidate_id="adv1", conversation="你好，我想了解下这个岗位")
    session = db.get_session("adv1")
    assert session["stage"] == "了解动机"
    assert session["turns"] == 1


def test_polite_exit_sets_ended_stage(client):
    """候选人表达无意向 -> reply_message 礼貌收尾 + stage=已结束。"""
    r = _post(client, candidate_id="exit1", conversation="谢谢，我暂时不考虑了，已找到工作")
    data = r.json()
    assert data["reason"]["rpa_action"] == "reply_message"
    assert data["answer"]  # 礼貌收尾话术非空
    assert data["reason"]["next_stage"] == "已结束"
    assert db.get_session("exit1")["stage"] == "已结束"


def test_invalid_next_stage_falls_back_to_action_map(monkeypatch, client):
    """模型给非法 next_stage 时不崩, 退回动作映射 (这里维持当前阶段)。"""
    class FakeProvider:
        def generate(self, system, user, *, temperature=None):
            return json.dumps(
                {
                    "answer": "好的，了解～",
                    "reason": {
                        "rpa_action": "reply_message",
                        "basis": "测试非法阶段",
                        "next_stage": "火星阶段",
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr("app.core.pipeline.get_provider", lambda: FakeProvider())
    r = _post(client, candidate_id="bad1", conversation="你好")
    # 非法 next_stage 被 json_repair 置空, pipeline 退回动作映射 -> reply_message 不改阶段
    assert r.json()["reason"]["next_stage"] == ""
    assert db.get_session("bad1")["stage"] == "初步接触"


def test_turn_hint_injected_into_prompt():
    """轮次提示随 turns 注入 user prompt: 第5轮起应出现催促邀约/收尾的提示。"""
    from app.core.prompt import build_messages

    _, early = build_messages(
        conversation="c", job_requirement="j", resume="", company_info="", stage="能力验证", turns=1
    )
    _, late = build_messages(
        conversation="c", job_requirement="j", resume="", company_info="", stage="能力验证", turns=5
    )
    assert "轮次提示" in late
    assert "邀约" in late and "收尾" in late
    assert late != early



def test_ingest_conversation_ack(client):
    conversation = "候选人：你好，我想了解下这个岗位\nHR：您好"
    r = client.post(
        "/rpa/conversation",
        json={"candidate_id": "yingdao_1", "conversation": conversation},
    )
    assert r.status_code == 200
    assert r.json() == {
        "candidate_id": "yingdao_1",
        "received": True,
        "conversation_chars": len(conversation),
        "stage": "初步接触",
        "next_endpoint": "/reply",
    }


def test_resume_evaluate_low_match(client):
    r = client.post(
        "/resume/evaluate",
        json={
            "candidate_id": "resume_low",
            "resume_text": "英语老师，主要负责一对一英语教学和课程规划",
            "job_requirement": "Java后端开发，熟悉Spring Boot和MySQL",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["candidate_id"] == "resume_low"
    assert data["score"] < data["threshold"]
    assert data["passed"] is False
    assert "risks" in data


def test_resume_evaluate_missing_fields_returns_hint(client):
    r = client.post("/resume/evaluate", json={"resume_text": "简历文本"})
    assert r.status_code == 422
    data = r.json()
    assert data["error"] == "请求体不符合接口要求"
    assert data["expected_body"]["resume_text"] == "图片简历 OCR 后的文本内容"
    assert data["expected_body"]["job_requirement"] == "岗位招聘需求"


def test_resume_evaluate_requires_text_or_image(client):
    r = client.post(
        "/resume/evaluate",
        json={"candidate_id": "empty", "job_requirement": "Java后端"},
    )
    assert r.status_code == 400
    assert (
        r.json()["detail"]
        == "resume_text、resume_image_url、resume_video_url 至少传一个"
    )


def test_resume_evaluate_image_url_with_mock(client):
    r = client.post(
        "/resume/evaluate",
        json={
            "candidate_id": "image_mock",
            "resume_image_url": "https://example.com/resume.png",
            "job_requirement": "Java后端开发，熟悉Spring Boot和MySQL",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["candidate_id"] == "image_mock"
    assert data["passed"] is True
    assert data["basis"] == "mock provider 不读取图片，默认放行"


def test_resume_evaluate_video_url_with_mock(client):
    r = client.post(
        "/resume/evaluate",
        json={
            "candidate_id": "video_mock",
            "resume_video_url": "https://example.com/resume.mp4",
            "job_requirement": "Java后端开发，熟悉Spring Boot和MySQL",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["candidate_id"] == "video_mock"
    assert data["passed"] is True
    assert data["basis"] == "mock provider 不读取视频，默认放行"


def test_resume_evaluate_high_match(client):
    r = client.post(
        "/resume/evaluate",
        json={
            "candidate_id": "resume_high",
            "resume_text": "5年Java后端开发经验，熟悉Spring Boot、MySQL和微服务",
            "job_requirement": "Java后端开发，熟悉Spring Boot和MySQL",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["candidate_id"] == "resume_high"
    assert data["score"] >= data["threshold"]
    assert data["passed"] is True


def test_aliyun_provider_registered(monkeypatch):
    from app.config import settings
    from app.llm.base import get_provider

    monkeypatch.setattr(settings, "llm_provider", "aliyun")
    provider = get_provider()
    assert provider.__class__.__name__ == "AliyunProvider"


def test_reset(client):
    _post(client)
    r = client.post("/reset", json={"candidate_id": "t1"})
    assert r.status_code == 200
    assert r.json()["deleted"] is True
