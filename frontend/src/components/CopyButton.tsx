import { useState } from "react";

type CopyButtonSize = "sm" | "md";

interface CopyButtonProps {
  value: string;
  label?: string;
  size?: CopyButtonSize;
}

const SIZE_CLASSES: Record<CopyButtonSize, string> = {
  sm: "px-2 py-0.5 text-[10px] gap-1",
  md: "px-3 py-1.5 text-[11px] gap-1.5",
};

const ICON_SIZE_CLASSES: Record<CopyButtonSize, string> = {
  sm: "w-3 h-3",
  md: "w-3.5 h-3.5",
};

/** Green "copy to clipboard" button, reused wherever a secret/id is shown. */
export default function CopyButton({ value, label = "COPY", size = "sm" }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={`inline-flex items-center shrink-0 bg-brand rounded font-bold text-ink tracking-wide hover:brightness-110 transition-all ${SIZE_CLASSES[size]}`}
    >
      {copied ? (
        <svg className={ICON_SIZE_CLASSES[size]} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path d="M16.7 5.3a1 1 0 0 1 0 1.4l-8 8a1 1 0 0 1-1.4 0l-4-4a1 1 0 1 1 1.4-1.4L8 12.6l7.3-7.3a1 1 0 0 1 1.4 0Z" />
        </svg>
      ) : (
        <svg className={ICON_SIZE_CLASSES[size]} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path d="M13 0H4a2 2 0 0 0-2 2v11h2V2h9V0Zm3 4H8a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2Zm0 14H8V6h8v12Z" />
        </svg>
      )}
      {copied ? "COPIED" : label}
    </button>
  );
}

