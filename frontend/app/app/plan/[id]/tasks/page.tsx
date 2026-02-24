"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getPlanTasks,
  getPlanWithSnapshot,
  patchTaskStatus,
  type TaskResponse,
} from "@/lib/api";
import {
  mapDependenciesByTask,
  isOverdue,
  sortTasksByDeadlinePriority,
  toDateLabel,
} from "@/lib/plan";

type TaskListPageProps = {
  params: {
    id: string;
  };
};

export default function PlanTasksPage({ params }: TaskListPageProps) {
  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [dependencies, setDependencies] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [inFlight, setInFlight] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [plan, fetchedTasks] = await Promise.all([
        getPlanWithSnapshot(params.id),
        getPlanTasks(params.id),
      ]);

      setDependencies(mapDependenciesByTask(plan));
      setTasks(fetchedTasks);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Tasks konnten nicht geladen werden");
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const taskStatusByKey = useMemo(() => {
    const mapped: Record<string, string> = {};
    for (const task of tasks) {
      mapped[task.task_key] = task.status;
    }
    return mapped;
  }, [tasks]);

  const sortedTasks = useMemo(() => sortTasksByDeadlinePriority(tasks), [tasks]);

  async function toggleDone(task: TaskResponse) {
    const nextStatus = task.status === "done" ? "todo" : "done";
    const previousTasks = tasks;

    setTasks((current) =>
      current.map((item) => (item.id === task.id ? { ...item, status: nextStatus } : item)),
    );
    setInFlight((current) => ({ ...current, [task.id]: true }));

    try {
      const updated = await patchTaskStatus(params.id, task.id, nextStatus);
      setTasks((current) => current.map((item) => (item.id === task.id ? updated : item)));
    } catch {
      setTasks(previousTasks);
      setError("Task-Update fehlgeschlagen. Bitte erneut versuchen.");
    } finally {
      setInFlight((current) => ({ ...current, [task.id]: false }));
    }
  }

  if (loading) {
    return (
      <main>
        <p>Lade Tasks ...</p>
      </main>
    );
  }

  if (error && tasks.length === 0) {
    return (
      <main>
        <p style={{ color: "#b01b2e" }}>{error}</p>
        <button className="button button-ghost" onClick={() => void load()} type="button">
          Erneut laden
        </button>
      </main>
    );
  }

  return (
    <main>
      <h1>Taskliste</h1>
      <p style={{ marginTop: 0 }}>
        <Link href={`/app/plan/${params.id}`}>Zurueck zum Dashboard</Link>
      </p>
      {error ? <p style={{ color: "#b01b2e" }}>{error}</p> : null}

      <section style={{ display: "grid", gap: "0.65rem" }}>
        {sortedTasks.map((task) => {
          const blockedBy = dependencies[task.task_key] ?? task.metadata?.blocked_by ?? [];
          const unresolved = blockedBy.filter((dependency) => taskStatusByKey[dependency] !== "done");
          const isBlocked = task.status !== "done" && unresolved.length > 0;

          return (
            <article key={task.id} className="card" style={{ display: "grid", gap: "0.45rem" }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: "0.65rem" }}>
                <input
                  checked={task.status === "done"}
                  disabled={Boolean(inFlight[task.id])}
                  onChange={() => void toggleDone(task)}
                  type="checkbox"
                  style={{ marginTop: "0.35rem" }}
                />
                <div style={{ flex: 1 }}>
                  <strong>{task.title}</strong>
                  <div style={{ marginTop: "0.3rem", color: "#5b665f", fontSize: "0.9rem" }}>
                    Kategorie: {task.metadata?.category ?? "n/a"} | Prioritaet: {task.metadata?.priority ?? "n/a"}
                  </div>
                  <div style={{ marginTop: "0.2rem", fontSize: "0.9rem" }}>
                    Deadline: {toDateLabel(task.due_date)} | Status: {task.status}
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
                {isOverdue(task) ? <span className="badge badge-danger">Ueberfaellig</span> : null}
                {isBlocked ? <span className="badge badge-warning">Blockiert</span> : null}
                {isBlocked ? <span className="badge">blocked_by: {unresolved.join(", ")}</span> : null}
              </div>
            </article>
          );
        })}
      </section>
    </main>
  );
}
