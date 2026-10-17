import type { JobStatus } from "../types";

const CONFIG: Record<JobStatus, { bg: string; text: string; label: string; spinner?: boolean; check?: boolean }> = {
  pending: { bg: "bg-surface-muted", text: "text-white", label: "QUEUED" },
  leased: { bg: "bg-surface-muted", text: "text-white", label: "QUEUED" },
  running: { bg: "bg-[#66BCFA]", text: "text-black", label: "IN PROGRESS", spinner: true },
  succeeded: { bg: "bg-[#6AEE6F]", text: "text-black", label: "COMPLETE", check: true },
  failed: { bg: "bg-[#ff5f57]", text: "text-black", label: "FAILED" },
  killed: { bg: "bg-[#febc2e]", text: "text-black", label: "KILLED" },
};

export default function StatusBadge({ status }: { status: JobStatus }) {
  const config = CONFIG[status] ?? CONFIG.pending;

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full ${config.bg} px-2.5 py-1 w-fit`}>
      {config.spinner && (
        <svg className={`animate-spin w-3 h-3 ${config.text}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {config.check && (
        <svg className={`w-3 h-3 ${config.text}`} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path d="M16.7 5.3a1 1 0 0 1 0 1.4l-8 8a1 1 0 0 1-1.4 0l-4-4a1 1 0 1 1 1.4-1.4L8 12.6l7.3-7.3a1 1 0 0 1 1.4 0Z" />
        </svg>
      )}
      <span className={`font-bold text-[10px] ${config.text} tracking-wide`}>{config.label}</span>
    </span>
  );
}
