export type PlanCreateRequest = {
  template_key: string;
  facts: Record<string, unknown>;
};

export type PlanCreateResponse = {
  id: string;
  template_key: string;
  status: string;
  created_at: string;
  updated_at: string;
  links: {
    self: string;
    tasks: string;
  };
};

export type PlanResponse = {
  id: string;
  template_key: string;
  facts: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
  snapshot_meta: {
    generated_at: string | null;
    task_count: number | null;
    engine_version: string | null;
    template_key: string | null;
  };
  snapshot?: {
    planner_plan?: {
      tasks?: Array<{
        id: string;
        task_key?: string;
        depends_on?: string[];
      }>;
    };
  } | null;
};

export type TaskStatus = "todo" | "done" | "dismissed";

export type TaskResponse = {
  id: string;
  plan_id: string;
  task_key: string;
  title: string;
  description: string | null;
  task_kind: "normal" | "decision";
  status: TaskStatus;
  due_date: string | null;
  metadata?: {
    priority?: number;
    category?: string;
    blocked_by?: string[];
    tags?: string[];
  } | null;
  sort_key: number;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

type ApiError = {
  error?: {
    code?: string;
    message?: string;
  };
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function buildUrl(path: string): string {
  return new URL(path, API_BASE_URL).toString();
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as ApiError;
      if (body.error?.message) {
        message = body.error.message;
      }
    } catch {
      // keep fallback message
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export async function createPlan(payload: PlanCreateRequest): Promise<PlanCreateResponse> {
  return apiRequest<PlanCreateResponse>("/plans", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getPlan(planId: string): Promise<PlanResponse> {
  return apiRequest<PlanResponse>(`/plans/${planId}`, {
    method: "GET",
  });
}

export async function getPlanWithSnapshot(planId: string): Promise<PlanResponse> {
  return apiRequest<PlanResponse>(`/plans/${planId}?include_snapshot=true`, {
    method: "GET",
  });
}

export async function getPlanTasks(planId: string): Promise<TaskResponse[]> {
  return apiRequest<TaskResponse[]>(`/plans/${planId}/tasks?include_metadata=true`, {
    method: "GET",
  });
}

export async function patchTaskStatus(
  planId: string,
  taskId: string,
  status: TaskStatus,
  force = false,
): Promise<TaskResponse> {
  return apiRequest<TaskResponse>(`/plans/${planId}/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify({ status, force }),
  });
}

export async function patchPlanFacts(
  planId: string,
  facts: Record<string, unknown>,
  recompute = true,
): Promise<PlanResponse> {
  return apiRequest<PlanResponse>(`/plans/${planId}/facts`, {
    method: "PATCH",
    body: JSON.stringify({ facts, recompute }),
  });
}

export async function recomputePlan(planId: string): Promise<PlanResponse> {
  return apiRequest<PlanResponse>(`/plans/${planId}/recompute`, {
    method: "POST",
  });
}
