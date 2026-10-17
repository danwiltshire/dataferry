import { useEffect, useState } from "react";
import { listAgents, listConnections, revokeAgent, deleteConnection } from "../api";
import type { Agent, DatabaseConnection } from "../types";
import CreateAgentModal from "../components/CreateAgentModal";
import CreateConnectionModal from "../components/CreateConnectionModal";
import CopyableField from "../components/CopyableField";
import Button from "../components/Button";
import TrashIcon from "../components/TrashIcon";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [connectionsByAgent, setConnectionsByAgent] = useState<Record<number, DatabaseConnection[]>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [agentModalOpen, setAgentModalOpen] = useState(false);
  const [connectionModalAgentId, setConnectionModalAgentId] = useState<number | null>(null);

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

  async function handleRevokeAgent(agentId: number) {
    if (!confirm("Revoke this agent? This permanently deletes it and its database connections.")) return;
    await revokeAgent(agentId);
    await loadAll();
  }

  async function handleDeleteConnection(agentId: number, connectionId: number) {
    if (!confirm("Delete this database connection?")) return;
    await deleteConnection(agentId, connectionId);
    await loadAll();
  }

  return (
    <>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-bold text-2xl text-white">Agents &amp; Connections</h1>
          <p className="font-medium text-[13px] text-white/60 mt-1">
            Agents are pull-only workers that run pg_dump/pg_restore for the database connections they own.
          </p>
        </div>
        <Button size="md" onClick={() => setAgentModalOpen(true)}>
          + NEW AGENT
        </Button>
      </div>

      {loading ? (
        <p className="mt-6 font-medium text-[13px] text-white/60">Loading…</p>
      ) : loadError ? (
        <p className="mt-6 font-medium text-[13px] text-[#ff5f57]">{loadError}</p>
      ) : (
        <div className="flex flex-col gap-[18px] mt-8 max-w-[900px]">
          {agents.map((agent) => (
            <article key={agent.id} className="bg-surface rounded-lg px-5 py-4 flex flex-col gap-[14px]">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-bold text-[14px] text-white">{agent.name}</p>
                  <div className="mt-1 max-w-sm">
                    <CopyableField label="Client ID" value={agent.client_id} />
                  </div>
                </div>
                <Button size="sm" variant="danger" onClick={() => handleRevokeAgent(agent.id)}>
                  <TrashIcon />
                  REVOKE
                </Button>
              </div>

              <div className="flex flex-col gap-2">
                {(connectionsByAgent[agent.id] ?? []).map((connection) => (
                  <div key={connection.id} className="flex items-center justify-between bg-canvas rounded-lg px-4 py-3">
                    <div>
                      <p className="font-bold text-[12px] text-white">{connection.name}</p>
                      <p className="font-medium text-[11px] text-white/50">
                        {connection.engine} · {connection.host}:{connection.port}/{connection.database_name} ·{" "}
                        {connection.credential_source}
                      </p>
                    </div>
                    <Button size="sm" variant="danger" onClick={() => handleDeleteConnection(agent.id, connection.id)}>
                      <TrashIcon />
                      DELETE
                    </Button>
                  </div>
                ))}
              </div>

              <Button size="sm" variant="secondary" className="self-start" onClick={() => setConnectionModalAgentId(agent.id)}>
                + ADD CONNECTION
              </Button>
            </article>
          ))}
        </div>
      )}

      <CreateAgentModal
        open={agentModalOpen}
        onClose={() => setAgentModalOpen(false)}
        onCreated={() => loadAll()}
      />

      <CreateConnectionModal
        open={connectionModalAgentId !== null}
        agentId={connectionModalAgentId}
        onClose={() => setConnectionModalAgentId(null)}
        onCreated={() => loadAll()}
      />
    </>
  );
}
