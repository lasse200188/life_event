"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { getPlan, getPlanTasks, type TaskResponse } from "@/lib/api";
import {
  computeProgress,
  hasCriticalTag,
  isOverdue,
  sortTasksByDeadlinePriority,
  toDateLabel,
} from "@/lib/plan";

type PlanPageProps = {
  params: {
    id: string;
  };
};

export default function PlanDashboardPage({ params }: PlanPageProps) {
  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [planStatus, setPlanStatus] = useState<string>("active");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [plan, fetchedTasks] = await Promise.all([getPlan(params.id), getPlanTasks(params.id)]);
        if (!mounted) {
          return;
        }
        setPlanStatus(plan.status);
        setTasks(fetchedTasks);
      } catch (loadError) {
        if (!mounted) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Plan konnte nicht geladen werden");
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      mounted = false;
    };
  }, [params.id]);

  const sortedTasks = useMemo(() => sortTasksByDeadlinePriority(tasks), [tasks]);
  const progress = useMemo(() => computeProgress(tasks), [tasks]);
  const nextDeadlines = useMemo(
    () => sortedTasks.filter((task) => task.status !== "done").slice(0, 3),
    [sortedTasks],
  );
  const criticalTasks = useMemo(
    () => sortedTasks.filter((task) => isOverdue(task) || hasCriticalTag(task)),
    [sortedTasks],
  );

  if (loading) {
    return (
      <main>
        <p>Lade Plan ...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main>
        <p style={{ color: "#b01b2e" }}>{error}</p>
        <Link className="button button-ghost" href="/app/onboarding">
          Zurueck zum Onboarding
        </Link>
      </main>
    );
  }

  return (
    <main>
      <h1>Plan Dashboard</h1>
      <p style={{ marginTop: 0, color: "#5b665f" }}>
        Plan-ID: <code>{params.id}</code> | Status: <strong>{planStatus}</strong>
      </p>

      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>Fortschritt: {progress}%</h2>
        <div className="progress-wrap">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <p style={{ marginBottom: 0 }}>{tasks.filter((task) => task.status === "done").length} von {tasks.length} Tasks erledigt</p>
      </section>

      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>Naechste 3 Fristen</h2>
        {nextDeadlines.length === 0 ? (
          <p>Keine offenen Fristen.</p>
        ) : (
          <ul>
            {nextDeadlines.map((task) => (
              <li key={task.id}>
                {task.title} ({toDateLabel(task.due_date)})
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card" style={{ marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>Kritische Tasks</h2>
        {criticalTasks.length === 0 ? (
          <p>Keine kritischen Tasks.</p>
        ) : (
          <ul>
            {criticalTasks.slice(0, 5).map((task) => (
              <li key={task.id}>
                {task.title}
                {isOverdue(task) ? <span className="badge badge-danger" style={{ marginLeft: "0.4rem" }}>Ueberfaellig</span> : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <Link className="button button-primary" href={`/app/plan/${params.id}/tasks`}>
        Alle Tasks anzeigen
      </Link>
    </main>
  );
}
