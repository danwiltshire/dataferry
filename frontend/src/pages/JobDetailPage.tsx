import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getJob, jobLogDownloadUrl, jobLogStreamUrl, listAgents, listConnections } from "../api";
import type { Job } from "../types";
import { isActiveJob } from "../types";
import StatusBadge from "../components/StatusBadge";

function connectionLabel(agentName: string, connectionName: string, databaseName: string) {
  const suffix = connectionName.includes(databaseName) ? "" : ` (${databaseName})`;
  return `${agentName} / ${connectionName}${suffix}`;
}

interface Event {
  timestamp: Date;
  phase: string;
  status: string;
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [connectionLabels, setConnectionLabels] = useState<Record<number, string>>({});
  const [loadError, setLoadError] = useState("");
  const [events, setEvents] = useState<Event[]>([]);
  const [logLines, setLogLines] = useState<string[]>([]);

  useEffect(() => {
    if (!id) return;

    const source = new EventSource(jobLogStreamUrl(id));
    source.onmessage = (event) => {
      setLogLines((prev) => [...prev, event.data]);
    };
    source.addEventListener("end", () => source.close());
    source.onerror = () => source.close();

    return () => source.close();
  }, [id]);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    let lastSeen = "";

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
      if (!cancelled) setConnectionLabels(Object.fromEntries(entries.flat()));
    }

    async function poll() {
      try {
        const current = await getJob(id!);
        if (cancelled) return;
        setJob(current);
        setLoadError("");
        const key = `${current.phase}:${current.status}`;
        if (key !== lastSeen) {
          lastSeen = key;
          setEvents((prev) => [...prev, { timestamp: new Date(), phase: current.phase, status: current.status }]);
        }
      } catch (err) {
        if (!cancelled) setLoadError((err as Error).message);
      }
    }

    (async () => {
      await loadConnectionLabels();
      await poll();
    })();

    const handle = setInterval(() => {
      if (job && !isActiveJob(job)) return;
      poll();
    }, 3000);

    return () => {
      cancelled = true;
      clearInterval(handle);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  function label(connectionId: number) {
    return connectionLabels[connectionId] ?? `connection #${connectionId}`;
  }

  function formatTime(date: Date) {
    return date.toTimeString().slice(0, 8);
  }

  return (
    <>
      <Link
        to="/jobs"
        className="inline-flex items-center gap-2 text-[12px] font-bold text-white/60 hover:text-white transition-colors"
      >
        <svg className="w-3 h-3 -rotate-90" viewBox="0 0 15 9" fill="currentColor" aria-hidden="true">
          <path d="M1.7625 9L7.5 3.43725L13.2375 9L15 7.28745L7.5 0L0 7.28745L1.7625 9Z" />
        </svg>
        BACK TO JOBS
      </Link>

      <h1 className="font-bold text-2xl text-white mt-3">Job #{id}</h1>

      {loadError ? (
        <p className="mt-4 font-medium text-[13px] text-[#ff5f57]">{loadError}</p>
      ) : !job ? (
        <p className="mt-4 font-medium text-[13px] text-white/60">Loading…</p>
      ) : (
        <>
          <div className="bg-surface rounded-lg px-5 py-4 mt-5 max-w-[1127px] flex flex-wrap items-center gap-x-8 gap-y-3">
            <div className="flex flex-col gap-1">
              <span className="font-bold text-[11px] text-white/50 tracking-wide">SOURCE</span>
              <span className="font-bold text-[14px] text-white">{label(job.source_connection_id)}</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="font-bold text-[11px] text-white/50 tracking-wide">DESTINATION</span>
              <span className="font-bold text-[14px] text-white">{label(job.destination_connection_id)}</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="font-bold text-[11px] text-white/50 tracking-wide">PHASE</span>
              <span className="font-bold text-[14px] text-white uppercase">{job.phase}</span>
            </div>
            <div className="flex flex-col gap-1">
              <span className="font-bold text-[11px] text-white/50 tracking-wide">STATUS</span>
              <StatusBadge status={job.status} />
            </div>
          </div>

          {job.error && <p className="mt-4 font-medium text-[13px] text-[#ff5f57] max-w-[1127px]">{job.error}</p>}

          <div className="bg-black border border-surface-border rounded-lg mt-5 max-w-[1127px] overflow-hidden">
            <div className="flex items-center justify-between gap-4 px-4 py-3 border-b border-surface-border">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]"></span>
                <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]"></span>
                <span className="font-bold text-[11px] text-white/50 ml-2 tracking-wide">job logs</span>
              </div>
              <a
                href={jobLogDownloadUrl(job.id)}
                download
                className="text-[11px] font-bold tracking-wide text-white/60 hover:text-white transition-colors"
              >
                DOWNLOAD LOG
              </a>
            </div>
            <pre className="font-mono text-[12px] leading-relaxed text-white/80 p-4 h-[420px] overflow-y-auto whitespace-pre-wrap">
              {logLines.length > 0
                ? logLines.join("\n")
                : events.map((event, i) => (
                    <div key={i}>
                      [{formatTime(event.timestamp)}] phase={event.phase} status={event.status}
                    </div>
                  ))}
            </pre>
          </div>
        </>
      )}
    </>
  );
}
