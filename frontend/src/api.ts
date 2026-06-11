import type {
  ApprovalTicket,
  ArtifactResponse,
  CreateTaskRequest,
  CreateTaskResponse,
  EventRecord,
  Metrics,
  TaskStatus,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${path}: ${body}`);
  }
  return (await response.json()) as T;
}

export function listTasks(): Promise<TaskStatus[]> {
  return request<TaskStatus[]>("/v1/tasks");
}

export function getTask(taskId: string): Promise<TaskStatus> {
  return request<TaskStatus>(`/v1/tasks/${taskId}`);
}

export function getEvents(taskId: string): Promise<EventRecord[]> {
  return request<EventRecord[]>(`/v1/tasks/${taskId}/events`);
}

export function getArtifact(taskId: string): Promise<ArtifactResponse> {
  return request<ArtifactResponse>(`/v1/tasks/${taskId}/artifact`);
}

export function createTask(body: CreateTaskRequest): Promise<CreateTaskResponse> {
  return request<CreateTaskResponse>("/v1/tasks", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listApprovals(): Promise<ApprovalTicket[]> {
  return request<ApprovalTicket[]>("/v1/approvals");
}

export function resolveApproval(
  ticketId: string,
  granted: boolean,
  approver: string,
): Promise<{ resolved: boolean; granted: boolean }> {
  return request<{ resolved: boolean; granted: boolean }>(`/v1/approvals/${ticketId}`, {
    method: "POST",
    body: JSON.stringify({ granted, approver }),
  });
}

export function getMetrics(): Promise<Metrics> {
  return request<Metrics>("/v1/metrics");
}
