from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.db.base import Base
from app.db.models import TaskStatus
from app.db.session import configure_engine, get_engine, get_session_factory
from app.services.plan_service import PlanService, _next_status
from app.services.task_service import TaskService
from app.services.template_repository import TemplateRepository


@pytest.fixture()
def session(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'test_recompute_m7.db'}"
    configure_engine(database_url)
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    session_factory = get_session_factory()
    with session_factory() as session:
        yield session

    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def workflows_root(tmp_path: Path) -> Path:
    src = (
        Path(__file__).resolve().parents[3]
        / "workflows"
        / "birth_de"
        / "v2"
        / "compiled.json"
    )
    dst = tmp_path / "workflows" / "birth_de" / "v2" / "compiled.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path / "workflows"


@pytest.fixture()
def service(workflows_root: Path) -> PlanService:
    return PlanService(template_repository=TemplateRepository(workflows_root))


def _load_template(workflows_root: Path) -> dict:
    path = workflows_root / "birth_de" / "v2" / "compiled.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _save_template(workflows_root: Path, template: dict) -> None:
    path = workflows_root / "birth_de" / "v2" / "compiled.json"
    path.write_text(json.dumps(template, indent=2), encoding="utf-8")


def _tasks_by_key(session, plan_id):
    return {
        task.task_key: task
        for task in TaskService().list_tasks(session, plan_id=plan_id, status=None)
    }


@pytest.mark.parametrize(
    "old_status,eligible,expected",
    [
        (TaskStatus.todo.value, True, TaskStatus.todo.value),
        (TaskStatus.todo.value, False, TaskStatus.skipped.value),
        (TaskStatus.blocked.value, True, TaskStatus.blocked.value),
        (TaskStatus.blocked.value, False, TaskStatus.skipped.value),
        (TaskStatus.done.value, True, TaskStatus.done.value),
        (TaskStatus.done.value, False, TaskStatus.done.value),
        (TaskStatus.skipped.value, True, TaskStatus.todo.value),
        (TaskStatus.skipped.value, False, TaskStatus.skipped.value),
    ],
)
def test_status_matrix_complete(old_status: str, eligible: bool, expected: str) -> None:
    assert _next_status(old_status=old_status, eligible=eligible) == expected


def test_deadline_policy_hybrid_updates_only_open_tasks(
    session,
    workflows_root: Path,
    service: PlanService,
) -> None:
    plan = service.create_plan(
        session,
        template_key="birth_de/v2",
        facts={
            "birth_date": "2026-04-01",
            "employment_type": "employed",
            "public_insurance": True,
            "private_insurance": False,
            "child_insurance_kind": "gkv",
        },
    )
    plan_id = plan.id
    tasks = _tasks_by_key(session, plan_id)

    birth = tasks["t_birth_certificate"]
    allowance = tasks["t_parental_allowance"]
    leave = tasks["t_parental_leave_employer"]
    benefit = tasks["t_child_benefit"]

    TaskService().update_status(
        session, plan_id=plan_id, task_id=birth.id, status=TaskStatus.done
    )
    TaskService().update_status(
        session, plan_id=plan_id, task_id=allowance.id, status=TaskStatus.blocked
    )
    TaskService().update_status(
        session, plan_id=plan_id, task_id=leave.id, status=TaskStatus.skipped
    )

    original = {
        "birth": birth.due_date,
        "allowance": allowance.due_date,
        "leave": leave.due_date,
        "benefit": benefit.due_date,
    }

    template = _load_template(workflows_root)
    template["tasks"]["t_birth_certificate"]["deadline"]["offset_days"] = 30
    template["tasks"]["t_parental_allowance"]["deadline"]["offset_days"] = 150
    template["tasks"]["t_parental_leave_employer"]["deadline"]["offset_days"] = 45
    template["tasks"]["t_child_benefit"]["deadline"]["offset_days"] = 120
    _save_template(workflows_root, template)

    service.update_facts(
        session,
        plan_id=plan_id,
        facts_patch={"employment_type": "unemployed"},
        recompute=True,
    )

    recomputed = _tasks_by_key(session, plan_id)
    assert recomputed["t_birth_certificate"].status == TaskStatus.done.value
    assert recomputed["t_birth_certificate"].due_date == original["birth"]

    assert recomputed["t_parental_allowance"].status == TaskStatus.blocked.value
    assert recomputed["t_parental_allowance"].due_date != original["allowance"]

    assert recomputed["t_parental_leave_employer"].status == TaskStatus.skipped.value
    assert recomputed["t_parental_leave_employer"].due_date == original["leave"]

    assert recomputed["t_child_benefit"].status == TaskStatus.todo.value
    assert recomputed["t_child_benefit"].due_date != original["benefit"]


def test_metadata_merge_updates_open_tasks_only(
    session,
    workflows_root: Path,
    service: PlanService,
) -> None:
    plan = service.create_plan(
        session,
        template_key="birth_de/v2",
        facts={
            "birth_date": "2026-04-01",
            "employment_type": "employed",
            "public_insurance": True,
            "private_insurance": False,
            "child_insurance_kind": "gkv",
        },
    )
    plan_id = plan.id
    tasks = _tasks_by_key(session, plan_id)

    birth = tasks["t_birth_certificate"]
    TaskService().update_status(
        session, plan_id=plan_id, task_id=birth.id, status=TaskStatus.done
    )
    before = _tasks_by_key(session, plan_id)
    birth_meta_before = dict(before["t_birth_certificate"].metadata_json)

    template = _load_template(workflows_root)
    template["tasks"]["t_child_benefit"]["priority"] = 777
    template["tasks"]["t_child_benefit"]["effort"] = {"minutes_estimate": 999}
    template["tasks"]["t_child_benefit"]["links"] = [
        {"label": "Neu", "url": "https://example.org/neu", "kind": "info"}
    ]
    template["tasks"]["t_child_benefit"]["docs_required"] = [
        {"doc_type": "new_doc", "optional": False}
    ]
    template["tasks"]["t_birth_certificate"]["priority"] = 5
    template["graph"]["edges"].append(
        {"from": "t_parental_allowance", "to": "t_child_benefit"}
    )
    _save_template(workflows_root, template)

    service.recompute_plan(session, plan_id=plan_id, reason="TEMPLATE_UPDATE")
    after = _tasks_by_key(session, plan_id)

    child_meta = after["t_child_benefit"].metadata_json
    assert child_meta["priority"] == 777
    assert child_meta["effort"] == {"minutes_estimate": 999}
    assert child_meta["links"] == [
        {"label": "Neu", "url": "https://example.org/neu", "kind": "info"}
    ]
    assert child_meta["docs_required"] == [{"doc_type": "new_doc", "optional": False}]
    assert child_meta["blocked_by"] == [
        "t_birth_certificate",
        "t_parental_allowance",
    ]

    assert after["t_birth_certificate"].metadata_json == birth_meta_before


def test_graph_blocked_by_recompute_updates_dependencies(
    session,
    workflows_root: Path,
    service: PlanService,
) -> None:
    plan = service.create_plan(
        session,
        template_key="birth_de/v2",
        facts={
            "birth_date": "2026-04-01",
            "employment_type": "employed",
            "public_insurance": True,
            "private_insurance": False,
            "child_insurance_kind": "gkv",
        },
    )
    plan_id = plan.id

    before = _tasks_by_key(session, plan_id)
    assert before["t_add_child_insurance_gkv"].metadata_json["blocked_by"] == [
        "t_birth_certificate"
    ]

    template = _load_template(workflows_root)
    template["graph"]["edges"].append(
        {"from": "t_parental_allowance", "to": "t_add_child_insurance_gkv"}
    )
    _save_template(workflows_root, template)

    service.recompute_plan(session, plan_id=plan_id, reason="TEMPLATE_UPDATE")
    after = _tasks_by_key(session, plan_id)
    assert after["t_add_child_insurance_gkv"].metadata_json["blocked_by"] == [
        "t_birth_certificate",
        "t_parental_allowance",
    ]
