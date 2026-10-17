import { useState } from "react";
import Modal from "./Modal";
import Button from "./Button";
import { createConnection } from "../api";
import type { CredentialSource, DatabaseConnection, DatabaseEngine } from "../types";

interface CreateConnectionModalProps {
  open: boolean;
  agentId: number | null;
  onClose: () => void;
  onCreated: (connection: DatabaseConnection) => void;
}

const EMPTY_FORM = {
  name: "",
  engine: "postgres" as DatabaseEngine,
  host: "",
  port: "5432",
  database_name: "",
  credential_source: "static" as CredentialSource,
  username: "",
  password: "",
  aws_secret_arn: "",
};

export default function CreateConnectionModal({ open, agentId, onClose, onCreated }: CreateConnectionModalProps) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function update<K extends keyof typeof EMPTY_FORM>(key: K, value: (typeof EMPTY_FORM)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function handleClose() {
    setForm(EMPTY_FORM);
    setError("");
    onClose();
  }

  async function handleSubmit() {
    if (!agentId) return;
    setSubmitting(true);
    setError("");
    try {
      const connection = await createConnection(agentId, {
        name: form.name,
        engine: form.engine,
        host: form.host,
        port: Number(form.port),
        database_name: form.database_name,
        credential_source: form.credential_source,
        ...(form.credential_source === "static"
          ? { username: form.username, password: form.password }
          : { aws_secret_arn: form.aws_secret_arn }),
      });
      onCreated(connection);
      handleClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  const inputClass =
    "bg-canvas border border-surface-border rounded-lg px-[13px] py-[10px] text-[12px] font-bold text-white placeholder:text-white/40 placeholder:font-medium focus:outline-none focus:border-brand";

  return (
    <Modal
      open={open}
      title="New Database Connection"
      onClose={handleClose}
      footer={
        <>
          <Button variant="secondary" onClick={handleClose}>
            CANCEL
          </Button>
          <Button disabled={!form.name || !form.host || !form.database_name || submitting} onClick={handleSubmit}>
            {submitting ? "ADDING..." : "ADD CONNECTION"}
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-[10px]">
        <input
          type="text"
          placeholder="name"
          value={form.name}
          onChange={(event) => update("name", event.target.value)}
          className={inputClass}
        />
        <select value={form.engine} onChange={(event) => update("engine", event.target.value as DatabaseEngine)} className={inputClass}>
          <option value="postgres">postgres</option>
          <option value="mysql">mysql</option>
        </select>
        <input
          type="text"
          placeholder="host"
          value={form.host}
          onChange={(event) => update("host", event.target.value)}
          className={inputClass}
        />
        <input
          type="number"
          placeholder="port"
          value={form.port}
          onChange={(event) => update("port", event.target.value)}
          className={inputClass}
        />
        <input
          type="text"
          placeholder="database name"
          value={form.database_name}
          onChange={(event) => update("database_name", event.target.value)}
          className={inputClass}
        />
        <select
          value={form.credential_source}
          onChange={(event) => update("credential_source", event.target.value as CredentialSource)}
          className={inputClass}
        >
          <option value="static">static</option>
          <option value="aws_secrets_manager">aws_secrets_manager</option>
        </select>
        {form.credential_source === "static" ? (
          <>
            <input
              type="text"
              placeholder="username"
              value={form.username}
              onChange={(event) => update("username", event.target.value)}
              className={inputClass}
            />
            <input
              type="password"
              placeholder="password"
              value={form.password}
              onChange={(event) => update("password", event.target.value)}
              className={inputClass}
            />
          </>
        ) : (
          <input
            type="text"
            placeholder="AWS secret ARN"
            value={form.aws_secret_arn}
            onChange={(event) => update("aws_secret_arn", event.target.value)}
            className={`${inputClass} col-span-2`}
          />
        )}
      </div>
      {error && <p className="mt-3 text-[12px] font-bold text-[#ff5f57]">{error}</p>}
    </Modal>
  );
}
