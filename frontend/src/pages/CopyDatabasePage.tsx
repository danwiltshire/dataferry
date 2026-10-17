import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { cloneConnection, createJob, getJob, listAgents, listConnections } from "../api";
import type { Agent, DatabaseConnection, Job } from "../types";
import { isActiveJob } from "../types";
import Modal from "../components/Modal";
import Button from "../components/Button";
import StatusBadge from "../components/StatusBadge";

type ConnectionWithAgent = DatabaseConnection & { agentName: string };
type TrackedJob = { sourceConnectionId: number; targetLabel: string; job: Job };

export default function CopyDatabasePage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [connectionsByAgent, setConnectionsByAgent] = useState<Record<number, DatabaseConnection[]>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [trackedJobs, setTrackedJobs] = useState<Record<number, TrackedJob>>({});

  async function loadAll() {
    setLoading(true);
    setLoadError("");
    try {
      const agentList = await listAgents();
      setAgents(agentList);
      const entries = await Promise.all(
        agentList.map(async (agent) => [agent.id, await listConnections(agent.id)] as const)
      );
      setConnectionsByAgent(Object.fromEntries(entries));
    } catch (err) {
      setLoadError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    const handle = setInterval(async () => {
      const ids = Object.keys(trackedJobs);
      if (ids.length === 0) return;
      const updates = await Promise.all(
        ids.map(async (id) => {
          try {
            return [Number(id), await getJob(id)] as const;
          } catch {
            return null;
          }
        })
      );
      setTrackedJobs((current) => {
        const next = { ...current };
        for (const entry of updates) {
          if (entry) next[entry[0]] = { ...next[entry[0]], job: entry[1] };
        }
        return next;
      });
    }, 3000);
    return () => clearInterval(handle);
  }, [trackedJobs]);

  const allConnections: ConnectionWithAgent[] = useMemo(
    () =>
      agents.flatMap((agent) =>
        (connectionsByAgent[agent.id] ?? []).map((conn) => ({ ...conn, agentName: agent.name }))
      ),
    [agents, connectionsByAgent]
  );

  function jobForConnection(connectionId: number) {
    return Object.values(trackedJobs).find((entry) => entry.sourceConnectionId === connectionId);
  }

  // --- Copy modal ---
  const [modalSource, setModalSource] = useState<ConnectionWithAgent | null>(null);
  const [targetConnectionId, setTargetConnectionId] = useState("");
  const [newDatabaseName, setNewDatabaseName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState("");

  function openCopyModal(connection: DatabaseConnection, agentName: string) {
    setModalSource({ ...connection, agentName });
    setTargetConnectionId("");
    setNewDatabaseName("");
    setModalError("");
  }

  function closeCopyModal() {
    setModalSource(null);
  }

  // Includes the source connection itself, so copying to a new database name
  // on the same host (a point-in-time snapshot) is possible with just one
  // connection registered.
  const targetOptions = useMemo(() => (modalSource ? allConnections : []), [allConnections, modalSource]);
  const targetTemplate = targetOptions.find((conn) => conn.id === Number(targetConnectionId));

  async function confirmCopy() {
    if (!modalSource || !targetTemplate || !newDatabaseName.trim()) return;
    setSubmitting(true);
    setModalError("");
    try {
      const destination = await cloneConnection(targetTemplate.agent_id, targetTemplate.id, newDatabaseName.trim());
      const job = await createJob(modalSource.id, destination.id);
      setTrackedJobs((current) => ({
        ...current,
        [job.id]: { sourceConnectionId: modalSource.id, targetLabel: targetTemplate.agentName, job },
      }));
      closeCopyModal();
    } catch (err) {
      setModalError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  const confirmDisabled = !targetConnectionId || !newDatabaseName.trim() || submitting;

  return (
    <>
      <div className="flex items-start justify-between">
        <h1 className="font-bold text-2xl text-white">Copy Database</h1>
        <button
          type="button"
          className="font-bold text-[12px] text-white/60 hover:text-white transition-colors"
          onClick={loadAll}
        >
          REFRESH
        </button>
      </div>

      {loading ? (
        <p className="mt-6 font-medium text-[13px] text-white/60">Loading…</p>
      ) : loadError ? (
        <p className="mt-6 font-medium text-[13px] text-[#ff5f57]">{loadError}</p>
      ) : agents.length === 0 ? (
        <p className="mt-6 font-medium text-[13px] text-white/60">
          No agents registered yet. Add one under{" "}
          <Link to="/agents" className="text-brand hover:underline">
            Agents &amp; Connections
          </Link>
          .
        </p>
      ) : (
        agents.map((agent) => {
          const connections = connectionsByAgent[agent.id] ?? [];
          if (connections.length === 0) return null;
          return (
            <div key={agent.id}>
              <div className="flex items-center gap-[10px] mt-[42px]">
                <h2 className="font-bold text-lg text-white">{agent.name}</h2>
              </div>
              <div className="flex flex-col gap-[18px] mt-[20px] max-w-[1127px]">
                {connections.map((connection) => {
                  const tracked = jobForConnection(connection.id);
                  return (
                    <article key={connection.id} className="bg-surface rounded-lg px-5 py-4 flex flex-col gap-[14px]">
                      <p className="font-bold text-[14px] text-white">{connection.name}</p>
                      <p className="font-medium text-[14px] text-white">
                        {connection.engine} · {connection.host}:{connection.port}/{connection.database_name}
                      </p>

                      {tracked ? (
                        <div className="flex items-center gap-[10px] h-9">
                          <StatusBadge status={tracked.job.status} />
                          <span className="font-bold text-[12px] text-white">
                            {isActiveJob(tracked.job) ? (
                              <>
                                Copying to <span className="text-brand">{tracked.targetLabel}</span>…
                              </>
                            ) : tracked.job.status === "succeeded" ? (
                              <>
                                Copied to <span className="text-brand">{tracked.targetLabel}</span>
                              </>
                            ) : (
                              <>
                                Copy to <span className="text-brand">{tracked.targetLabel}</span> {tracked.job.status}
                              </>
                            )}
                          </span>
                          <Link
                            to={`/jobs/${tracked.job.id}`}
                            className="font-bold text-[11px] text-brand hover:underline tracking-wide"
                          >
                            VIEW JOB
                          </Link>
                        </div>
                      ) : (
                        <div className="flex items-center gap-[10px]">
                          <Button onClick={() => openCopyModal(connection, agent.name)}>
                            <img src="/icons/icon-copy.svg" alt="" className="w-[15px] h-[18px]" />
                            COPY TO...
                          </Button>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            </div>
          );
        })
      )}

      <Modal
        open={modalSource !== null}
        title="Copy Database"
        onClose={closeCopyModal}
        footer={
          <>
            <Button variant="secondary" onClick={closeCopyModal}>
              CANCEL
            </Button>
            <Button disabled={confirmDisabled} onClick={confirmCopy}>
              <img src="/icons/icon-copy.svg" alt="" className="w-[15px] h-[18px]" />
              {submitting ? "COPYING..." : "COPY DATABASE"}
            </Button>
          </>
        }
      >
        {modalSource && (
          <>
            <p className="text-[13px] font-medium text-white/70">
              Copying <span className="font-bold text-white">{modalSource.database_name}</span> from{" "}
              <span className="font-bold text-white">
                {modalSource.agentName} / {modalSource.name}
              </span>
              .
            </p>

            <div className="mt-5 flex flex-col gap-[6px]">
              <label htmlFor="target-connection" className="font-bold text-[12px] text-white/70 tracking-wide">
                TARGET CONNECTION (used for host/credentials)
              </label>
              <select
                id="target-connection"
                value={targetConnectionId}
                onChange={(event) => setTargetConnectionId(event.target.value)}
                className="bg-canvas border border-surface-border rounded-lg px-[13px] py-[10px] text-[12px] font-bold text-white focus:outline-none focus:border-brand"
              >
                <option value="" disabled>
                  Select connection...
                </option>
                {targetOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.agentName} / {option.name} ({option.host})
                    {modalSource && option.id === modalSource.id ? " (same connection)" : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="mt-4 flex flex-col gap-[6px]">
              <label htmlFor="new-db-name" className="font-bold text-[12px] text-white/70 tracking-wide">
                NEW DATABASE NAME
              </label>
              <input
                id="new-db-name"
                type="text"
                value={newDatabaseName}
                onChange={(event) => setNewDatabaseName(event.target.value)}
                placeholder="mydb_2026_10_27_14_28"
                autoComplete="off"
                className="bg-canvas border border-surface-border rounded-lg px-[13px] py-[10px] text-[12px] font-bold text-white placeholder:text-white/40 placeholder:font-medium focus:outline-none focus:border-brand"
              />
            </div>

            {modalError && <p className="mt-3 text-[12px] font-bold text-[#ff5f57]">{modalError}</p>}
          </>
        )}
      </Modal>
    </>
  );
}
