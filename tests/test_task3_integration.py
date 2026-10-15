"""任务3主链路集成测试：鉴权 + 审核流水 + 幂等 + 非法迁移 + 越权。"""

from __future__ import annotations

import io
import uuid
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import select

from intern_platform.models.application import Application
from intern_platform.models.audit_log import AuditLog
from intern_platform.models.review_record import ReviewRecord
from intern_platform.services.ledger import verify_audit_chain


def _login(client: TestClient, email: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Demo@123456"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _idem() -> str:
    return str(uuid.uuid4())


def test_full_path_draft_to_completed_writes_ledger(client_and_db) -> None:
    client, SessionLocal, ids = client_and_db
    app_id = ids["application_id"]

    student = _login(client, "student@test.local")
    mentor = _login(client, "mentor@test.local")
    admin = _login(client, "admin@test.local")
    committee = _login(client, "committee@test.local")

    # submit draft → mentor_review
    r = client.post(
        f"/api/v1/applications/{app_id}/submit",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "mentor_review"

    def review(token: str, decision: str = "approve") -> dict:
        resp = client.post(
            f"/api/v1/applications/{app_id}/reviews",
            headers={**_auth(token), "X-Idempotency-Key": _idem()},
            json={"decision": decision, "comment": "ok"},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    review(mentor)
    # 社区通过后组委会自动接收中选，不必再审一次
    selected = review(admin)
    assert selected["to_status"] == "selected"

    r = client.post(
        f"/api/v1/applications/{app_id}/start-progress",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
    )
    assert r.status_code == 200
    assert r.json()["to_status"] == "in_progress"

    r = client.put(
        f"/api/v1/applications/{app_id}/final",
        headers=_auth(student),
        json={"pr_mr_url": "https://git.example/mr/1", "report_text": "done"},
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"/api/v1/applications/{app_id}/final/submit",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "mentor_final_review"

    r = client.post(
        f"/api/v1/applications/{app_id}/final/reviews",
        headers={**_auth(mentor), "X-Idempotency-Key": _idem()},
        json={"decision": "approve"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["to_status"] == "community_final_review"

    # 学生申请奖励 → 社区通过 → 组委会自动计入结项
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "reward proof")
    up = client.post(
        "/api/v1/uploads/zip",
        headers=_auth(student),
        files={"file": ("reward.zip", buf.getvalue(), "application/zip")},
    )
    assert up.status_code == 200, up.text
    r = client.post(
        f"/api/v1/applications/{app_id}/messages",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
        json={
            "body": "说明：集成测试奖励\n手机：13800000000",
            "kind": "reward",
            "attachment_url": up.json()["url"],
            "attachment_name": "reward.zip",
        },
    )
    assert r.status_code in (200, 201), r.text
    r = client.post(
        f"/api/v1/applications/{app_id}/reward-decision",
        headers={**_auth(admin), "X-Idempotency-Key": _idem()},
        json={"decision": "approved"},
    )
    assert r.status_code == 200, r.text
    r = client.get(f"/api/v1/applications/{app_id}", headers=_auth(student))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"

    db = SessionLocal()
    try:
        app_row = db.get(Application, app_id)
        assert app_row is not None
        assert app_row.status == "completed"
        assert app_row.version > 0
        reviews = list(db.scalars(select(ReviewRecord)).all())
        assert len(reviews) >= 10
        audits = list(db.scalars(select(AuditLog)).all())
        assert any(a.outcome == "SUCCESS" for a in audits)
        ok, err = verify_audit_chain(db)
        assert ok, err
    finally:
        db.close()


def test_idempotent_replay_no_double_review(client_and_db) -> None:
    client, SessionLocal, ids = client_and_db
    app_id = ids["application_id"]
    student = _login(client, "student@test.local")
    mentor = _login(client, "mentor@test.local")

    client.post(
        f"/api/v1/applications/{app_id}/submit",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
    )
    key = _idem()
    r1 = client.post(
        f"/api/v1/applications/{app_id}/reviews",
        headers={**_auth(mentor), "X-Idempotency-Key": key},
        json={"decision": "approve"},
    )
    r2 = client.post(
        f"/api/v1/applications/{app_id}/reviews",
        headers={**_auth(mentor), "X-Idempotency-Key": key},
        json={"decision": "approve"},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["idempotent_replay"] is True

    db = SessionLocal()
    try:
        # submit+start (2) + approve_mentor/community/committee (3)；回放不加
        count = len(list(db.scalars(select(ReviewRecord)).all()))
        assert count == 5
        assert r1.json()["to_status"] == "selected"
        # 幂等回放只命中首条 action 的记录
        assert r2.json()["to_status"] == "community_review"
    finally:
        db.close()


def test_illegal_transition_writes_fail_audit(client_and_db) -> None:
    client, SessionLocal, ids = client_and_db
    app_id = ids["application_id"]
    student = _login(client, "student@test.local")

    r = client.post(
        f"/api/v1/applications/{app_id}/transitions",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
        json={"action": "approve_committee"},
    )
    # 学生不得执行审核类 action（角色校验优先于状态机）
    assert r.status_code == 403

    db = SessionLocal()
    try:
        assert db.get(Application, app_id).status == "draft"
    finally:
        db.close()


def test_unauthorized_review_403(client_and_db) -> None:
    client, _, ids = client_and_db
    app_id = ids["application_id"]
    student = _login(client, "student@test.local")
    outsider = _login(client, "outsider@test.local")

    client.post(
        f"/api/v1/applications/{app_id}/submit",
        headers={**_auth(student), "X-Idempotency-Key": _idem()},
    )
    r = client.post(
        f"/api/v1/applications/{app_id}/reviews",
        headers={**_auth(outsider), "X-Idempotency-Key": _idem()},
        json={"decision": "approve"},
    )
    assert r.status_code == 403


def test_missing_idempotency_key_400(client_and_db) -> None:
    client, _, ids = client_and_db
    app_id = ids["application_id"]
    student = _login(client, "student@test.local")
    r = client.post(
        f"/api/v1/applications/{app_id}/transitions",
        headers=_auth(student),
        json={"action": "submit"},
    )
    assert r.status_code == 400
