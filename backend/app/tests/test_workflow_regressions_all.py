from __future__ import annotations

from pathlib import Path

import pytest

from domain.workflow_test_runner import load_template, load_testcase, run_template

pytestmark = pytest.mark.workflow

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
def test_workflow_regressions(compiled_path: Path, testcase_path: Path) -> None:
    template = load_template(compiled_path)
    testcase = load_testcase(testcase_path)

    assert testcase.get("template_id") == template.get("template_id")
    assert testcase.get("template_version") == template.get("version")

    facts = testcase.get("facts", {})
    assert isinstance(facts, dict), f"facts must be object in {testcase_path}"

    result = run_template(template, facts)
    assert isinstance(result.active_tasks, set)
    assert isinstance(result.blocked_by, dict)
    assert isinstance(result.deadlines, dict)
    assert isinstance(result.active_recommendations, set)
    assert all(isinstance(task_id, str) for task_id in result.active_tasks)
    assert all(
        isinstance(task_id, str) and isinstance(blockers, list)
        for task_id, blockers in result.blocked_by.items()
    )
    assert all(
        isinstance(task_id, str) and isinstance(due, str)
        for task_id, due in result.deadlines.items()
    )
    assert all(isinstance(rec_id, str) for rec_id in result.active_recommendations)

    expect = testcase.get("expect", {})
    assert isinstance(expect, dict), f"expect must be object in {testcase_path}"

    for task_id in expect.get("tasks_present", []):
        assert task_id in result.active_tasks

    for task_id in expect.get("tasks_absent", []):
        assert task_id not in result.active_tasks

    blocked_expect = expect.get("blocked_initially", {})
    if blocked_expect:
        for task_id, required_ids in blocked_expect.items():
            assert task_id in result.active_tasks
            assert sorted(required_ids) == sorted(result.blocked_by.get(task_id, []))

    deadlines_expect = expect.get("deadlines", {})
    if deadlines_expect:
        for task_id, due_date in deadlines_expect.items():
            expected = str(due_date)
            got = result.deadlines.get(task_id)
            assert got == expected

    for rec_id in expect.get("recommendations_present", []):
        assert rec_id in result.active_recommendations

    for rec_id in expect.get("recommendations_absent", []):
        assert rec_id not in result.active_recommendations
