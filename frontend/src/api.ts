import type {
  Agent,
  AgentCreated,
  DatabaseConnection,
  DatabaseConnectionCreate,
  Job,
} from "./types";

declare global {
  interface Window {
    __ENV__?: { API_BASE_URL?: string };
  }
}

const BASE_URL = window.__ENV__?.API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${options.method ?? "GET"} ${path} failed (${response.status}): ${detail}`);
  }
  if (response.status === 204) return null as T;
  return response.json() as Promise<T>;
}

// Agents

export function listAgents(): Promise<Agent[]> {
  return request("/admin/agents");
}

export function createAgent(name: string): Promise<AgentCreated> {
  return request("/admin/agents", { method: "POST", body: JSON.stringify({ name }) });
}

export function revokeAgent(agentId: number): Promise<null> {
  return request(`/admin/agents/${agentId}`, { method: "DELETE" });
}

// Database connections

export function listConnections(agentId: number): Promise<DatabaseConnection[]> {
  return request(`/admin/agents/${agentId}/databases`);
}

export function createConnection(
  agentId: number,
  body: DatabaseConnectionCreate,
): Promise<DatabaseConnection> {
  return request(`/admin/agents/${agentId}/databases`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function deleteConnection(agentId: number, connectionId: number): Promise<null> {
  return request(`/admin/agents/${agentId}/databases/${connectionId}`, { method: "DELETE" });
}

// Creates a new connection re-using an existing one's host/credentials (the
// password is copied server-side, never sent to the client).
export function cloneConnection(
  agentId: number,
  connectionId: number,
  databaseName: string,
): Promise<DatabaseConnection> {
  return request(`/admin/agents/${agentId}/databases/${connectionId}/clone`, {
    method: "POST",
    body: JSON.stringify({ database_name: databaseName }),
  });
}

// Jobs

export function listJobs(): Promise<Job[]> {
  return request("/admin/jobs");
}

export function getJob(jobId: number | string): Promise<Job> {
  return request(`/admin/jobs/${jobId}`);
}

export function createJob(
  sourceConnectionId: number,
  destinationConnectionId: number,
): Promise<Job> {
  return request("/admin/jobs", {
    method: "POST",
    body: JSON.stringify({
      source_connection_id: sourceConnectionId,
      destination_connection_id: destinationConnectionId,
    }),
  });
}

export function jobLogDownloadUrl(jobId: number | string): string {
  return `${BASE_URL}/admin/jobs/${jobId}/log`;
}

export function jobLogStreamUrl(jobId: number | string): string {
  return `${BASE_URL}/admin/jobs/${jobId}/log/stream`;
}
