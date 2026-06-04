"""端到端测试: 用 mock provider 跑通 /reply, 断言返回结构与分支。"""

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
    assert set(data["reason"]) == {"rpa_action", "basis"}


def test_no_resume_triggers_request_resume(client):
    r = _post(client, resume="")
    data = r.json()
    assert data["answer"] == ""
    assert data["reason"]["rpa_action"] == "request_resume"


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


def test_rpa_action_always_valid(client):
    valid = {"reply_message", "request_resume", "send_company_address"}
    r = _post(client, resume="有经验", conversation="随便聊聊")
    assert r.json()["reason"]["rpa_action"] in valid


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
        "stage": "初次接触",
        "next_endpoint": "/reply",
    }


def test_reset(client):
    _post(client)
    r = client.post("/reset", json={"candidate_id": "t1"})
    assert r.status_code == 200
    assert r.json()["deleted"] is True
