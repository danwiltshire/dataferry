import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAgents, listConnections, listJobs } from "../api";
import type { Job } from "../types";
import StatusBadge from "../components/StatusBadge";

function connectionLabel(agentName: string, connectionName: string, databaseName: string) {
  const suffix = connectionName.includes(databaseName) ? "" : ` (${databaseName})`;
  return `${agentName} / ${connectionName}${suffix}`;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [connectionLabels, setConnectionLabels] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  async function loadConnectionLabels() {
    const agents = await listAgents();
    const entries = await Promise.all(
      agents.map(async (agent) => {
        const connections = await listConnections(agent.id);
        return connections.map(
          (conn) => [conn.id, connectionLabel(agent.name, conn.name, conn.database_name)] as const
        );
      })
    );
    setConnectionLabels(Object.fromEntries(entries.flat()));
  }

  async function loadJobs() {
    try {
      const list = await listJobs();
      setJobs([...list].sort((a, b) => b.id - a.id));
      setLoadError("");
    } catch (err) {
      setLoadError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        await loadConnectionLabels();
        await loadJobs();
      } catch (err) {
        setLoadError((err as Error).message);
        setLoading(false);
      }
    })();

    const handle = setInterval(loadJobs, 4000);
    return () => clearInterval(handle);
  }, []);

  function label(connectionId: number) {
    return connectionLabels[connectionId] ?? `connection #${connectionId}`;
  }

  return (
    <>
      <h1 className="font-bold text-2xl text-white">Jobs</h1>
      <p className="font-medium text-[13px] text-white/60 mt-1">All database copy jobs, newest first.</p>

      {loading ? (
        <p className="mt-6 font-medium text-[13px] text-white/60">Loading…</p>
      ) : loadError ? (
        <p className="mt-6 font-medium text-[13px] text-[#ff5f57]">{loadError}</p>
      ) : jobs.length === 0 ? (
        <p className="mt-6 font-medium text-[13px] text-white/60">No jobs yet.</p>
      ) : (
        <div className="flex flex-col gap-[14px] mt-6 max-w-[900px]">
          {jobs.map((job) => (
            <article key={job.id} className="bg-surface rounded-lg px-5 py-4 flex items-center justify-between gap-4 flex-wrap">
              <div className="flex flex-col gap-1 min-w-0">
                <p className="font-bold text-[14px] text-white truncate">
                  {label(job.source_connection_id)} &rarr; {label(job.destination_connection_id)}
                </p>
                <p className="font-medium text-[12px] text-white/50">
                  job #{job.id} · phase: {job.phase}
                  {job.error && <> · {job.error}</>}
                </p>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <StatusBadge status={job.status} />
                <Link to={`/jobs/${job.id}`} className="font-bold text-[12px] text-brand hover:underline tracking-wide">
                  VIEW LOGS
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}
