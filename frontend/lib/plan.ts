import type { PlanResponse, TaskResponse } from "./api";

export function toDateLabel(isoDate: string | null): string {
  if (!isoDate) {
    return "Kein Datum";
  }

  const date = new Date(isoDate);
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

export function isOverdue(task: TaskResponse): boolean {
  if (!task.due_date || task.status === "done") {
    return false;
  }

  const due = new Date(task.due_date);
  const now = new Date();

  due.setHours(0, 0, 0, 0);
  now.setHours(0, 0, 0, 0);

  return due.getTime() < now.getTime();
}

export function mapDependenciesByTask(plan: PlanResponse): Record<string, string[]> {
  const items = plan.snapshot?.planner_plan?.tasks ?? [];
  const mapped: Record<string, string[]> = {};

  for (const item of items) {
    mapped[item.id] = item.depends_on ?? [];
  }

  return mapped;
}

export function computeProgress(tasks: TaskResponse[]): number {
  if (tasks.length === 0) {
    return 0;
  }
  const done = tasks.filter((task) => task.status === "done").length;
  return Math.round((done / tasks.length) * 100);
}

export function sortTasksByDeadlinePriority(tasks: TaskResponse[]): TaskResponse[] {
  return [...tasks].sort((left, right) => {
    const leftDue = left.due_date ? new Date(left.due_date).getTime() : Number.POSITIVE_INFINITY;
    const rightDue = right.due_date ? new Date(right.due_date).getTime() : Number.POSITIVE_INFINITY;

    if (leftDue !== rightDue) {
      return leftDue - rightDue;
    }

    const leftPriority = left.metadata?.priority ?? 0;
    const rightPriority = right.metadata?.priority ?? 0;
    if (leftPriority !== rightPriority) {
      return rightPriority - leftPriority;
    }

    return left.sort_key - right.sort_key;
  });
}
