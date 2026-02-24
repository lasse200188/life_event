from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.domain.workflow_test_runner import load_template, load_testcase
from app.planner.engine import generate_plan

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_ROOT = ROOT / "workflows"


def _compiled_and_testcases() -> list[tuple[Path, Path]]:
    items: list[tuple[Path, Path]] = []
    for compiled_path in sorted(WORKFLOWS_ROOT.rglob("compiled.json")):
        tests_dir = compiled_path.parent / "tests"
        for testcase_path in sorted(tests_dir.glob("tc_*.yaml")):
            items.append((compiled_path, testcase_path))
    return items


def _case_id(value: tuple[Path, Path]) -> str:
    compiled_path, testcase_path = value
    template_id = compiled_path.parent.parent.name
    version = compiled_path.parent.name
    return f"{template_id}/{version}/{testcase_path.name}"


def _assert_expected_plan_schema(expected_plan: Any, testcase_path: Path) -> None:
    assert isinstance(
        expected_plan, dict
    ), f"expected_plan must be object in {testcase_path}"
    for key in ("workflow_id", "event_date", "tasks"):
        assert key in expected_plan, f"expected_plan.{key} missing in {testcase_path}"

    tasks = expected_plan["tasks"]
    assert isinstance(
        tasks, list
    ), f"expected_plan.tasks must be list in {testcase_path}"

    required_task_keys = {
        "id",
        "title",
        "relative_days",
        "deadline",
        "depends_on",
        "meta",
    }
    for idx, task in enumerate(tasks):
        assert isinstance(task, dict), f"expected_plan.tasks[{idx}] must be object"
        missing = sorted(required_task_keys - set(task.keys()))
        assert (
            not missing
        ), f"expected_plan.tasks[{idx}] missing keys {missing} in {testcase_path}"


CASES = _compiled_and_testcases()
if not CASES:
    pytest.fail(
        f"No workflow regression testcases found under {WORKFLOWS_ROOT}",
        pytrace=False,
    )


@pytest.mark.parametrize(
    "compiled_path,testcase_path",
    CASES,
    ids=[_case_id(case) for case in CASES],
)
def test_planner_regressions(compiled_path: Path, testcase_path: Path) -> None:
    workflow = load_template(compiled_path)
    testcase = load_testcase(testcase_path)

    facts = testcase.get("facts", {})
    assert isinstance(facts, dict), f"facts must be object in {testcase_path}"

    expected_plan = testcase.get("expected_plan")
    _assert_expected_plan_schema(expected_plan, testcase_path)

    plan = generate_plan(workflow, facts)
    assert plan == expected_plan
