import type { ReactNode } from "react";

interface ModalProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  maxWidthClassName?: string;
}

export default function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  maxWidthClassName = "max-w-md",
}: ModalProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className={`bg-surface border border-surface-border rounded-lg w-full ${maxWidthClassName} p-6`}>
        <div className="flex items-start justify-between">
          <h2 className="font-bold text-lg text-white">{title}</h2>
          <button
            type="button"
            className="text-white/60 hover:text-white transition-colors"
            onClick={onClose}
            aria-label="Close"
          >
            <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M4.34 3.05 10 8.71l5.66-5.66 1.41 1.41L11.41 10.12l5.66 5.66-1.41 1.41-5.66-5.66-5.66 5.66-1.41-1.41 5.66-5.66-5.66-5.66z" />
            </svg>
          </button>
        </div>

        <div className="mt-2">{children}</div>

        {footer && <div className="mt-6 flex items-center justify-end gap-[10px]">{footer}</div>}
      </div>
    </div>
  );
}
