from __future__ import annotations


class PlannerError(ValueError):
    """Base class for planner failures."""


class PlannerInputError(PlannerError):
    """Raised for invalid workflow/user input payloads."""


class PlannerDependencyError(PlannerError):
    """Raised when dependency data is inconsistent."""


class PlannerRuleError(PlannerError):
    """Raised when rule definitions are invalid."""


class PlannerCycleError(PlannerError):
    """Raised when active task graph contains a cycle."""
