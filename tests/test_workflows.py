import uuid
import time
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from backend.database import SessionLocal, Reading, ExternalOrder


def key():
    return {"Idempotency-Key": str(uuid.uuid4())}


def assets(client):
    return client.get("/api/assets").json()


def investigation(client, asset_id):
    r = client.post("/api/investigations", json={"asset_id": asset_id}, headers=key())
    assert r.status_code == 201, r.text
    return r.json()


def approve(client, sign_in, inv):
    sign_in("approver")
    r = client.post(
        f'/api/investigations/{inv["id"]}/decision',
        json={
            "expected_version": inv["version"],
            "decision": "approve",
            "reason": "Reviewed applicable evidence and observed measurements.",
        },
        headers=key(),
    )
    assert r.status_code == 200, r.text
    return r.json()


def planned_order(client, sign_in):
    sign_in("engineer")
    a = assets(client)[0]
    inv = investigation(client, a["id"])
    approved = approve(client, sign_in, inv)
    sign_in("planner")
    body = {
        "investigation_id": inv["id"],
        "expected_version": approved["version"],
        "due_date": (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat(),
        "assignee": "Test technician",
    }
    r = client.post("/api/work-orders", json=body, headers=key())
    assert r.status_code == 201, r.text
    return r.json()


def test_anonymous_data_is_not_exposed(client):
    assert client.get("/api/assets").status_code == 401
    assert client.get("/api/documents").status_code == 401


def test_login_and_logout_revoke_session(client, sign_in):
    sign_in()
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout", json={}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_bad_password_rejected(client):
    assert (
        client.post(
            "/api/auth/login", json={"email": "engineer@sentinel.local", "password": "wrong"}
        ).status_code
        == 401
    )


def test_csrf_token_required_for_mutation(client, sign_in):
    sign_in()
    client.headers.pop("X-CSRF-Token")
    assert (
        client.post("/api/simulation/tick", json={"scenario": "normal"}, headers=key()).status_code
        == 403
    )


def test_foreign_origin_rejected(client, sign_in):
    sign_in()
    assert (
        client.post(
            "/api/simulation/tick",
            json={"scenario": "normal"},
            headers={**key(), "Origin": "https://untrusted.example"},
        ).status_code
        == 403
    )


def test_site_isolation_applies_to_assets_and_documents(client, sign_in):
    sign_in()
    all_assets = assets(client)
    blocked = next(a for a in all_assets if a["site"] == "Ruwais Energy Complex")
    doc = next(
        d for d in client.get("/api/documents").json() if d["site"] == "Ruwais Energy Complex"
    )
    sign_in("restricted")
    assert client.get("/api/assets/" + blocked["id"]).status_code == 404
    assert client.get("/api/documents/" + doc["id"]).status_code == 404
    assert all(a["site"] == "Habshan Processing Hub" for a in assets(client))


def test_asset_create_unknown_health_and_unique_tag(client, sign_in):
    sign_in()
    body = {
        "tag": "TEST-" + uuid.uuid4().hex[:7],
        "name": "Test reference pump",
        "site": "Ruwais Energy Complex",
        "location": "Test loop",
    }
    r = client.post("/api/assets", json=body, headers=key())
    assert r.status_code == 201, r.text
    assert r.json()["health"] is None and r.json()["status"] == "unknown"
    assert client.post("/api/assets", json=body, headers=key()).status_code == 409
    assert (
        client.post(
            "/api/investigations", json={"asset_id": r.json()["id"]}, headers=key()
        ).status_code
        == 409
    )


def test_wrong_role_cannot_register_asset(client, sign_in):
    sign_in("technician")
    assert (
        client.post(
            "/api/assets",
            json={
                "tag": "P-TEST",
                "name": "Test pump",
                "site": "Ruwais Energy Complex",
                "location": "Test loop",
            },
            headers=key(),
        ).status_code
        == 403
    )


def test_telemetry_identity_and_retry_body_are_enforced(client, sign_in):
    sign_in()
    a = next(a for a in assets(client) if a["reading"])
    rec = {
        "asset_id": a["id"],
        "timestamp": time.time(),
        "vibration": 2.2,
        "temperature": 65,
        "pressure": 5.2,
        "flow": 120,
        "message_id": "test-" + uuid.uuid4().hex,
    }
    body = {"records": [rec]}
    header = key()
    r = client.post("/api/telemetry/batches", json=body, headers=header)
    assert r.status_code == 200, r.text
    assert client.post("/api/telemetry/batches", json=body, headers=header).json() == r.json()
    assert client.post("/api/telemetry/batches", json=body, headers=key()).json()["duplicates"] == 1
    changed = {"records": [{**rec, "vibration": 9}]}
    assert client.post("/api/telemetry/batches", json=changed, headers=header).status_code == 409
    assert client.post("/api/telemetry/batches", json=changed, headers=key()).status_code == 409


def test_invalid_and_future_readings_are_rejected(client, sign_in):
    sign_in()
    a = next(a for a in assets(client) if a["reading"])
    row = {
        "asset_id": a["id"],
        "timestamp": time.time() + 10000,
        "vibration": 2,
        "temperature": 65,
        "pressure": 5,
        "flow": 100,
        "message_id": "future-" + uuid.uuid4().hex,
    }
    assert (
        client.post("/api/telemetry/batches", json={"records": [row]}, headers=key()).status_code
        == 422
    )
    row["timestamp"] = time.time()
    row["vibration"] = "NaN"
    assert (
        client.post("/api/telemetry/batches", json={"records": [row]}, headers=key()).status_code
        == 422
    )


def test_approval_requires_independent_person(client, sign_in):
    sign_in("admin")
    a = next(a for a in assets(client) if a["reading"])
    inv = investigation(client, a["id"])
    r = client.post(
        f'/api/investigations/{inv["id"]}/decision',
        json={"expected_version": 1, "decision": "approve", "reason": "Self approval attempt"},
        headers=key(),
    )
    assert r.status_code == 403


def test_engineer_cannot_approve(client, sign_in):
    sign_in()
    a = next(a for a in assets(client) if a["reading"])
    inv = investigation(client, a["id"])
    assert (
        client.post(
            f'/api/investigations/{inv["id"]}/decision',
            json={"expected_version": 1, "decision": "approve", "reason": "Role violation"},
            headers=key(),
        ).status_code
        == 403
    )


def test_edit_invalidates_approval_and_stale_versions(client, sign_in):
    sign_in()
    a = next(a for a in assets(client) if a["reading"])
    inv = investigation(client, a["id"])
    approved = approve(client, sign_in, inv)
    sign_in()
    body = {
        "expected_version": approved["version"],
        "recommendation": "Revised inspection proposal with reviewed scope.",
        "checklist": ["Review the applicable equipment procedure."],
    }
    r = client.patch(f'/api/investigations/{inv["id"]}', json=body, headers=key())
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "awaiting_review" and r.json()["approver"] is None
    assert (
        client.patch(f'/api/investigations/{inv["id"]}', json=body, headers=key()).status_code
        == 409
    )


def test_unapproved_work_order_is_blocked(client, sign_in):
    sign_in()
    a = next(a for a in assets(client) if a["reading"])
    inv = investigation(client, a["id"])
    sign_in("planner")
    r = client.post(
        "/api/work-orders",
        json={"investigation_id": inv["id"], "expected_version": 1, "due_date": "2026-12-01"},
        headers=key(),
    )
    assert r.status_code == 409


def test_unknown_cmms_result_reconciles_without_duplicate(client, sign_in):
    order = planned_order(client, sign_in)
    r = client.post(
        f'/api/work-orders/{order["id"]}/dispatch',
        json={"expected_version": order["version"], "simulate_timeout": True},
        headers=key(),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "reconciling" and r.json()["external_ref"] is None
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(ExternalOrder)
                .where(ExternalOrder.command_id == order["id"])
            )
            == 1
        )
    header = key()
    body = {"expected_version": r.json()["version"]}
    r = client.post(f'/api/work-orders/{order["id"]}/reconcile', json=body, headers=header)
    assert r.json()["status"] == "in_progress" and r.json()["external_ref"].startswith("SIM-")
    assert (
        client.post(f'/api/work-orders/{order["id"]}/reconcile', json=body, headers=header).json()
        == r.json()
    )
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(ExternalOrder)
                .where(ExternalOrder.command_id == order["id"])
            )
            == 1
        )


def test_completion_requires_actual_findings_and_state(client, sign_in):
    order = planned_order(client, sign_in)
    assert (
        client.post(
            f'/api/work-orders/{order["id"]}/transition',
            json={
                "expected_version": order["version"],
                "status": "completed",
                "outcome": "This cannot complete planned work.",
            },
            headers=key(),
        ).status_code
        == 409
    )
    r = client.post(
        f'/api/work-orders/{order["id"]}/dispatch',
        json={"expected_version": order["version"]},
        headers=key(),
    )
    assert r.status_code == 200
    sign_in("technician")
    assert (
        client.post(
            f'/api/work-orders/{order["id"]}/transition',
            json={"expected_version": r.json()["version"], "status": "completed", "outcome": "ok"},
            headers=key(),
        ).status_code
        == 409
    )
    done = client.post(
        f'/api/work-orders/{order["id"]}/transition',
        json={
            "expected_version": r.json()["version"],
            "status": "completed",
            "outcome": "Inspected the mounting and recorded actual technician observations.",
        },
        headers=key(),
    )
    assert done.status_code == 200 and done.json()["status"] == "completed"


def test_document_upload_and_authorized_retrieval(client, sign_in):
    sign_in()
    phrase = "Unique spindle review protocol checks the amber coupling fixture."
    r = client.post(
        "/api/documents/upload",
        data={"site": "Ruwais Energy Complex", "kind": "Pump", "title": "Test spindle protocol"},
        files={"file": ("test.txt", phrase.encode(), "text/plain")},
        headers=key(),
    )
    assert r.status_code == 201, r.text
    answer = client.post(
        "/api/knowledge/ask",
        json={"question": "Unique spindle amber coupling", "site": "Ruwais Energy Complex"},
    ).json()
    assert any(x["document_id"] == r.json()["id"] for x in answer["evidence"])
    sign_in("restricted")
    answer = client.post(
        "/api/knowledge/ask", json={"question": "Unique spindle amber coupling"}
    ).json()
    assert not any(x["document_id"] == r.json()["id"] for x in answer["evidence"])


def test_unsupported_upload_and_no_evidence_abstention(client, sign_in):
    sign_in()
    r = client.post(
        "/api/documents/upload",
        data={"site": "Ruwais Energy Complex", "kind": "Pump", "title": "Executable disguised"},
        files={"file": ("bad.exe", b"not a document", "application/octet-stream")},
        headers=key(),
    )
    assert r.status_code == 422
    answer = client.post("/api/knowledge/ask", json={"question": "zyxquantumunfindable"}).json()
    assert answer["status"] == "insufficient_evidence" and not answer["evidence"]


def test_preferences_are_per_account(client, sign_in):
    sign_in()
    assert (
        client.put(
            "/api/preferences",
            json={"compact": True, "email_digest": False, "display_timezone": "Asia/Dubai"},
        ).status_code
        == 200
    )
    sign_in("restricted")
    assert client.get("/api/preferences").json()["compact"] is False


def test_health_model_and_csv_are_real_responses(client, sign_in):
    assert client.get("/api/health").json()["status"] == "ok"
    sign_in()
    model = client.get("/api/model").json()
    assert 0 <= model["f1"] <= 1 and model["data_type"].startswith("Synthetic")
    csv = client.get("/api/export/assets.csv")
    assert csv.status_code == 200 and "Vibration mm/s" in csv.text


def test_revision_preserves_history_and_updates_creator(client, sign_in):
    sign_in()
    a = next(a for a in assets(client) if a["reading"])
    inv = investigation(client, a["id"])
    admin = sign_in("admin")
    r = client.patch(
        f'/api/investigations/{inv["id"]}',
        json={
            "expected_version": 1,
            "recommendation": "A revised proposal authored by the admin for independent review.",
            "checklist": ["Review source applicability."],
        },
        headers=key(),
    )
    assert r.status_code == 200 and r.json()["creator_id"] == admin["id"]
    history = client.get(f'/api/investigations/{inv["id"]}/history').json()
    assert len(history) == 2 and history[0]["payload_hash"] != history[1]["payload_hash"]
    assert (
        client.post(
            f'/api/investigations/{inv["id"]}/decision',
            json={
                "expected_version": 2,
                "decision": "approve",
                "reason": "Attempt to approve my revision.",
            },
            headers=key(),
        ).status_code
        == 403
    )


def test_bad_quality_reading_does_not_appear_healthy(client, sign_in):
    sign_in()
    a = next(a for a in assets(client) if a["reading"])
    tag = "QA-" + uuid.uuid4().hex[:6]
    created = client.post(
        "/api/assets",
        json={"tag": tag, "name": "Quality test pump", "site": a["site"], "location": "Test loop"},
        headers=key(),
    ).json()
    rec = {
        "asset_id": created["id"],
        "timestamp": time.time(),
        "vibration": 1.8,
        "temperature": 65,
        "pressure": 5.2,
        "flow": 120,
        "quality": "bad",
        "message_id": "quality-" + uuid.uuid4().hex,
    }
    assert (
        client.post("/api/telemetry/batches", json={"records": [rec]}, headers=key()).status_code
        == 200
    )
    detail = client.get("/api/assets/" + created["id"]).json()
    assert detail["asset"]["status"] == "unknown" and detail["asset"]["health"] is None


def test_built_interface_and_api_docs_are_served(client):
    import re

    page = client.get("/")
    assert page.status_code == 200 and '<div id="root"></div>' in page.text
    resources = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', page.text)
    assert resources
    for resource in resources:
        assert client.get(resource).status_code == 200
    assert client.get("/sentinel.svg").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/api/investigations/{id}/decision" in schema["paths"]


def test_demo_step_initializes_a_new_asset(client, sign_in):
    sign_in()
    a = client.post(
        "/api/assets",
        json={
            "tag": "NEW-" + uuid.uuid4().hex[:7],
            "name": "New demonstration pump",
            "site": "Ruwais Energy Complex",
            "location": "Demo loop",
        },
        headers=key(),
    ).json()
    assert a["reading"] is None
    assert (
        client.post("/api/simulation/tick", json={"scenario": "normal"}, headers=key()).status_code
        == 200
    )
    detail = client.get("/api/assets/" + a["id"]).json()
    assert detail["asset"]["reading"] is not None and detail["asset"]["status"] == "healthy"
