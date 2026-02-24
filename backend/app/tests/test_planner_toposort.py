from __future__ import annotations

import pytest

from app.planner.errors import PlannerCycleError, PlannerDependencyError
from app.planner.toposort import toposort_task_ids


def test_toposort_linear_chain() -> None:
    order = toposort_task_ids({"t_a", "t_b", "t_c"}, [("t_a", "t_b"), ("t_b", "t_c")])
    assert order == ["t_a", "t_b", "t_c"]


def test_toposort_branching_is_stable_by_id() -> None:
    order = toposort_task_ids(
        {"t_a", "t_b", "t_c", "t_d"},
        [("t_a", "t_c"), ("t_b", "t_c")],
    )
    assert order == ["t_a", "t_b", "t_c", "t_d"]


def test_toposort_unknown_dependency_raises() -> None:
    with pytest.raises(PlannerDependencyError, match="unknown active task"):
        toposort_task_ids({"t_a", "t_b"}, [("t_x", "t_b")])


def test_toposort_cycle_raises_stable_message() -> None:
    with pytest.raises(PlannerCycleError, match="Cycle detected in active task graph"):
        toposort_task_ids({"t_a", "t_b"}, [("t_a", "t_b"), ("t_b", "t_a")])
