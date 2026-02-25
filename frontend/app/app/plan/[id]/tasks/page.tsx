"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getPlanTasks,
  getPlanWithSnapshot,
  patchPlanFacts,
  patchTaskStatus,
  type TaskStatus,
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
    const mapped: Record<string, TaskStatus> = {};
    for (const task of tasks) {
      mapped[task.task_key] = task.status;
    }
    return mapped;
  }, [tasks]);

  const sortedTasks = useMemo(() => sortTasksByDeadlinePriority(tasks), [tasks]);

  function isDecisionTask(task: TaskResponse): boolean {
    return task.task_kind === "decision";
  }

  function getUnresolvedDependencies(task: TaskResponse): string[] {
    const blockedBy = dependencies[task.task_key] ?? task.metadata?.blocked_by ?? [];
    return blockedBy.filter((dependency) => taskStatusByKey[dependency] !== "done");
  }

  async function toggleDone(task: TaskResponse) {
    const nextStatus = task.status === "done" ? "todo" : "done";
    const previousTasks = tasks;

    setTasks((current) =>
      current.map((item) => (item.id === task.id ? { ...item, status: nextStatus } : item)),
    );
    setInFlight((current) => ({ ...current, [task.id]: true }));

    try {
      const updated = await patchTaskStatus(params.id, task.id, nextStatus, false);
      setTasks((current) => current.map((item) => (item.id === task.id ? updated : item)));
    } catch {
      setTasks(previousTasks);
      setError("Task-Update fehlgeschlagen. Bitte erneut versuchen.");
    } finally {
      setInFlight((current) => ({ ...current, [task.id]: false }));
    }
  }

  async function forceComplete(task: TaskResponse) {
    const confirmed = window.confirm(
      "Diese Aufgabe ist noch blockiert. Trotzdem als erledigt markieren?",
    );
    if (!confirmed) {
      return;
    }

    const previousTasks = tasks;
    setTasks((current) =>
      current.map((item) => (item.id === task.id ? { ...item, status: "done" } : item)),
    );
    setInFlight((current) => ({ ...current, [task.id]: true }));

    try {
      const updated = await patchTaskStatus(params.id, task.id, "done", true);
      setTasks((current) => current.map((item) => (item.id === task.id ? updated : item)));
    } catch (updateError) {
      setTasks(previousTasks);
      setError(
        updateError instanceof Error
          ? updateError.message
          : "Task-Update fehlgeschlagen. Bitte erneut versuchen.",
      );
    } finally {
      setInFlight((current) => ({ ...current, [task.id]: false }));
    }
  }

  async function setChildInsuranceKind(task: TaskResponse, insuranceKind: "gkv" | "pkv") {
    const label = insuranceKind === "gkv" ? "GKV" : "PKV";
    const confirmed = window.confirm(
      `Versicherung wirklich auf ${label} festlegen? Danach wird dein Plan neu berechnet.`,
    );
    if (!confirmed) {
      return;
    }

    setInFlight((current) => ({ ...current, [task.id]: true }));
    setError(null);
    try {
      await patchPlanFacts(params.id, { child_insurance_kind: insuranceKind }, true);
      await load();
    } catch (updateError) {
      setError(
        updateError instanceof Error
          ? updateError.message
          : "Entscheidung konnte nicht gespeichert werden.",
      );
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
          const isDecision = isDecisionTask(task);
          const unresolved = getUnresolvedDependencies(task);
          const isBlocked = task.status !== "done" && unresolved.length > 0;

          return (
            <article key={task.id} className="card" style={{ display: "grid", gap: "0.45rem" }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: "0.65rem" }}>
                {isDecision ? null : (
                  <input
                    checked={task.status === "done"}
                    disabled={Boolean(inFlight[task.id]) || isBlocked}
                    onChange={() => void toggleDone(task)}
                    type="checkbox"
                    style={{ marginTop: "0.35rem" }}
                  />
                )}
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
              {isBlocked ? (
                <div>
                  <button
                    className="button button-ghost"
                    disabled={Boolean(inFlight[task.id])}
                    onClick={() => void forceComplete(task)}
                    type="button"
                  >
                    Trotzdem als erledigt markieren
                  </button>
                </div>
              ) : null}
              {isDecision ? (
                <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
                  <button
                    className="button button-primary"
                    disabled={Boolean(inFlight[task.id])}
                    onClick={() => void setChildInsuranceKind(task, "gkv")}
                    type="button"
                  >
                    GKV waehlen
                  </button>
                  <button
                    className="button button-ghost"
                    disabled={Boolean(inFlight[task.id])}
                    onClick={() => void setChildInsuranceKind(task, "pkv")}
                    type="button"
                  >
                    PKV waehlen
                  </button>
                </div>
              ) : null}
            </article>
          );
        })}
      </section>
    </main>
  );
}
