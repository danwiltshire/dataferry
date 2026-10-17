export type DatabaseEngine = "postgres" | "mysql";
export type CredentialSource = "static" | "aws_secrets_manager";
export type JobPhase = "dump" | "restore";
export type JobStatus = "pending" | "leased" | "running" | "succeeded" | "failed" | "killed";

export interface Agent {
  id: number;
  name: string;
  client_id: string;
  created_at: string;
}

export interface AgentCreated extends Agent {
  client_secret: string;
}

export interface DatabaseConnection {
  id: number;
  agent_id: number;
  name: string;
  engine: DatabaseEngine;
  host: string;
  port: number;
  database_name: string;
  credential_source: CredentialSource;
  username: string | null;
  aws_secret_arn: string | null;
  created_at: string;
}

export interface DatabaseConnectionCreate {
  name: string;
  engine: DatabaseEngine;
  host: string;
  port: number;
  database_name: string;
  credential_source: CredentialSource;
  username?: string;
  password?: string;
  aws_secret_arn?: string;
}

export interface Job {
  id: number;
  source_connection_id: number;
  destination_connection_id: number;
  phase: JobPhase;
  status: JobStatus;
  leased_by_agent_id: number | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

// A job is still in flight until it reaches a terminal status.
const ACTIVE_JOB_STATUSES = new Set<JobStatus>(["pending", "leased", "running"]);

export function isActiveJob(job: Job): boolean {
  return ACTIVE_JOB_STATUSES.has(job.status);
}
