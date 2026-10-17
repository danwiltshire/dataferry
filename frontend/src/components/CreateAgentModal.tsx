import { useState } from "react";
import Modal from "./Modal";
import Button from "./Button";
import CopyableField from "./CopyableField";
import { createAgent } from "../api";
import type { AgentCreated } from "../types";

interface CreateAgentModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (agent: AgentCreated) => void;
}

export default function CreateAgentModal({ open, onClose, onCreated }: CreateAgentModalProps) {
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [createdAgent, setCreatedAgent] = useState<AgentCreated | null>(null);

  function handleClose() {
    setName("");
    setError("");
    setCreatedAgent(null);
    onClose();
  }

  async function handleSubmit() {
    if (!name.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      const agent = await createAgent(name.trim());
      setCreatedAgent(agent);
      onCreated(agent);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      title={createdAgent ? "Agent Created" : "New Agent"}
      onClose={handleClose}
      footer={
        createdAgent ? (
          <Button variant="secondary" onClick={handleClose}>
            CLOSE
          </Button>
        ) : (
          <>
            <Button variant="secondary" onClick={handleClose}>
              CANCEL
            </Button>
            <Button disabled={!name.trim() || submitting} onClick={handleSubmit}>
              {submitting ? "CREATING..." : "CREATE AGENT"}
            </Button>
          </>
        )
      }
    >
      {createdAgent ? (
        <>
          <p className="text-[13px] font-bold text-brand">
            Agent "{createdAgent.name}" created. Save these now, the secret is never shown again:
          </p>
          <div className="flex flex-col gap-3 mt-3">
            <CopyableField label="Client ID" value={createdAgent.client_id} />
            <CopyableField label="Client Secret" value={createdAgent.client_secret} />
          </div>
        </>
      ) : (
        <>
          <div className="flex flex-col gap-[6px]">
            <label htmlFor="new-agent-name" className="font-bold text-[12px] text-white/70 tracking-wide">
              NAME
            </label>
            <input
              id="new-agent-name"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="agent name"
              className="bg-canvas border border-surface-border rounded-lg px-[13px] py-[10px] text-[12px] font-bold text-white placeholder:text-white/40 placeholder:font-medium focus:outline-none focus:border-brand"
            />
          </div>
          {error && <p className="mt-3 text-[12px] font-bold text-[#ff5f57]">{error}</p>}
        </>
      )}
    </Modal>
  );
}

