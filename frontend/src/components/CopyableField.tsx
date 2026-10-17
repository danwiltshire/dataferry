import CopyButton from "./CopyButton";

interface CopyableFieldProps {
  label: string;
  value: string;
}

/** "Label | boxed value | copy button" row, used wherever an id/secret is shown. */
export default function CopyableField({ label, value }: CopyableFieldProps) {
  return (
    <div className="flex items-center gap-3">
      <span className="font-bold text-[12px] text-white/70 tracking-wide w-24 shrink-0">{label}</span>
      <span className="flex-1 min-w-0 bg-canvas border border-surface-border rounded-lg px-3 py-2 font-mono text-[12px] text-white break-all">
        {value}
      </span>
      <CopyButton value={value} size="md" />
    </div>
  );
}
