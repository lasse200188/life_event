from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import configure_engine, get_engine
from app.main import app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{tmp_path / 'test_plans.db'}"
    configure_engine(database_url)
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def test_plans_end_to_end_happy_path(client: TestClient) -> None:
    create_payload = {
        "template_key": "birth_de/v1",
        "facts": {
            "birth_date": "2026-04-01",
            "employment_type": "employed",
            "public_insurance": True,
            "private_insurance": False,
        },
    }

    create_response = client.post("/plans", json=create_payload)
    assert create_response.status_code == 201
    body = create_response.json()
    plan_id = body["id"]

    plan_response = client.get(f"/plans/{plan_id}")
    assert plan_response.status_code == 200
    plan_body = plan_response.json()
    assert plan_body["id"] == plan_id
    assert plan_body["status"] == "active"
    assert plan_body["facts"]["birth_date"] == "2026-04-01"
    assert plan_body["snapshot"] is None
    assert plan_body["snapshot_meta"]["task_count"] >= 1

    plan_with_snapshot = client.get(f"/plans/{plan_id}?include_snapshot=true")
    assert plan_with_snapshot.status_code == 200
    snapshot_body = plan_with_snapshot.json()
    assert snapshot_body["snapshot"]["template_meta"]["template_key"] == "birth_de/v1"
    assert "generated_at" in snapshot_body["snapshot"]

    tasks_response = client.get(f"/plans/{plan_id}/tasks")
    assert tasks_response.status_code == 200
    tasks = tasks_response.json()
    assert len(tasks) >= 1
    task_id = tasks[0]["id"]

    patch_response = client.patch(
        f"/plans/{plan_id}/tasks/{task_id}",
        json={"status": "done"},
    )
    assert patch_response.status_code == 200
    patch_body = patch_response.json()
    assert patch_body["status"] == "done"
    completed_at = patch_body["completed_at"]
    assert completed_at is not None

    patch_response_again = client.patch(
        f"/plans/{plan_id}/tasks/{task_id}",
        json={"status": "done"},
    )
    assert patch_response_again.status_code == 200
    assert patch_response_again.json()["completed_at"] == completed_at

    tasks_after_response = client.get(f"/plans/{plan_id}/tasks?status=done")
    assert tasks_after_response.status_code == 200
    tasks_after = tasks_after_response.json()
    assert any(
        item["id"] == task_id and item["status"] == "done" for item in tasks_after
    )


def test_create_plan_unknown_template_returns_404(client: TestClient) -> None:
    response = client.post(
        "/plans",
        json={"template_key": "birth_de/v999", "facts": {"birth_date": "2026-04-01"}},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TEMPLATE_NOT_FOUND"


def test_create_plan_missing_event_fact_returns_400(client: TestClient) -> None:
    response = client.post("/plans", json={"template_key": "birth_de/v1", "facts": {}})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PLANNER_INPUT_INVALID"


def test_patch_task_not_in_plan_returns_404(client: TestClient) -> None:
    payload = {"template_key": "birth_de/v1", "facts": {"birth_date": "2026-04-01"}}
    first_plan = client.post("/plans", json=payload).json()["id"]
    second_plan = client.post("/plans", json=payload).json()["id"]
    task_id = client.get(f"/plans/{first_plan}/tasks").json()[0]["id"]

    response = client.patch(
        f"/plans/{second_plan}/tasks/{task_id}", json={"status": "done"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TASK_NOT_FOUND"


def test_cannot_complete_blocked_task_without_force(client: TestClient) -> None:
    create_payload = {
        "template_key": "birth_de/v1",
        "facts": {
            "birth_date": "2026-04-01",
            "employment_type": "employed",
            "public_insurance": True,
            "private_insurance": False,
        },
    }
    plan_id = client.post("/plans", json=create_payload).json()["id"]

    tasks_response = client.get(f"/plans/{plan_id}/tasks?include_metadata=true")
    assert tasks_response.status_code == 200
    blocked_task = next(
        item
        for item in tasks_response.json()
        if item.get("metadata", {}).get("blocked_by")
    )

    response = client.patch(
        f"/plans/{plan_id}/tasks/{blocked_task['id']}",
        json={"status": "done"},
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "TASK_BLOCKED"


def test_can_force_complete_blocked_task(client: TestClient) -> None:
    create_payload = {
        "template_key": "birth_de/v1",
        "facts": {
            "birth_date": "2026-04-01",
            "employment_type": "employed",
            "public_insurance": True,
            "private_insurance": False,
        },
    }
    plan_id = client.post("/plans", json=create_payload).json()["id"]

    tasks_response = client.get(f"/plans/{plan_id}/tasks?include_metadata=true")
    assert tasks_response.status_code == 200
    blocked_task = next(
        item
        for item in tasks_response.json()
        if item.get("metadata", {}).get("blocked_by")
    )

    response = client.patch(
        f"/plans/{plan_id}/tasks/{blocked_task['id']}",
        json={"status": "done", "force": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["completed_at"] is not None


def test_create_plan_v2_normalizes_child_insurance_unknown_when_ambiguous(
    client: TestClient,
) -> None:
    create_payload = {
        "template_key": "birth_de/v2",
        "facts": {
            "birth_date": "2026-04-01",
            "employment_type": "employed",
            "public_insurance": True,
            "private_insurance": True,
        },
    }

    create_response = client.post("/plans", json=create_payload)
    assert create_response.status_code == 201
    plan_id = create_response.json()["id"]

    plan_response = client.get(f"/plans/{plan_id}")
    assert plan_response.status_code == 200
    plan_body = plan_response.json()
    assert plan_body["facts"]["child_insurance_kind"] == "unknown"

    tasks_response = client.get(f"/plans/{plan_id}/tasks")
    assert tasks_response.status_code == 200
    task_keys = {item["task_key"] for item in tasks_response.json()}
    assert "t_decide_child_insurance" in task_keys
    assert "t_add_child_insurance_gkv" not in task_keys
    assert "t_add_child_insurance_pkv" not in task_keys


def test_patch_plan_facts_recompute_switches_child_insurance_and_keeps_done(
    client: TestClient,
) -> None:
    create_payload = {
        "template_key": "birth_de/v2",
        "facts": {
            "birth_date": "2026-04-01",
            "employment_type": "employed",
            "public_insurance": True,
            "private_insurance": True,
        },
    }
    plan_id = client.post("/plans", json=create_payload).json()["id"]

    tasks_before = client.get(f"/plans/{plan_id}/tasks").json()
    birth_task = next(
        item for item in tasks_before if item["task_key"] == "t_birth_certificate"
    )
    done_response = client.patch(
        f"/plans/{plan_id}/tasks/{birth_task['id']}",
        json={"status": "done"},
    )
    assert done_response.status_code == 200

    patch_response = client.patch(
        f"/plans/{plan_id}/facts",
        json={"facts": {"child_insurance_kind": "gkv"}, "recompute": True},
    )
    assert patch_response.status_code == 200
    patched_plan = patch_response.json()
    assert patched_plan["facts"]["child_insurance_kind"] == "gkv"

    tasks_after = client.get(f"/plans/{plan_id}/tasks").json()
    task_status_by_key = {item["task_key"]: item["status"] for item in tasks_after}
    assert "t_decide_child_insurance" not in task_status_by_key
    assert "t_add_child_insurance_gkv" in task_status_by_key
    assert "t_add_child_insurance_pkv" not in task_status_by_key
    assert task_status_by_key["t_birth_certificate"] == "done"


def test_cannot_manually_complete_decision_task_even_with_force(
    client: TestClient,
) -> None:
    create_payload = {
        "template_key": "birth_de/v2",
        "facts": {
            "birth_date": "2026-04-01",
            "employment_type": "employed",
            "public_insurance": True,
            "private_insurance": True,
        },
    }
    plan_id = client.post("/plans", json=create_payload).json()["id"]

    tasks_response = client.get(f"/plans/{plan_id}/tasks?include_metadata=true")
    assert tasks_response.status_code == 200
    assert any(item.get("task_kind") == "decision" for item in tasks_response.json())
    decision_task = next(
        item
        for item in tasks_response.json()
        if "decision" in item.get("metadata", {}).get("tags", [])
    )

    response = client.patch(
        f"/plans/{plan_id}/tasks/{decision_task['id']}",
        json={"status": "done", "force": True},
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "TASK_DECISION_MANUAL_COMPLETE_FORBIDDEN"
    assert "nicht manuell abgeschlossen" in body["error"]["message"]


def test_tasks_without_metadata_still_include_task_kind(client: TestClient) -> None:
    create_payload = {
        "template_key": "birth_de/v2",
        "facts": {
            "birth_date": "2026-04-01",
            "employment_type": "employed",
            "public_insurance": True,
            "private_insurance": True,
        },
    }
    plan_id = client.post("/plans", json=create_payload).json()["id"]

    tasks_response = client.get(f"/plans/{plan_id}/tasks?include_metadata=false")
    assert tasks_response.status_code == 200
    tasks = tasks_response.json()
    assert any(item["task_kind"] == "decision" for item in tasks)
    assert all(item.get("metadata") is None for item in tasks)
