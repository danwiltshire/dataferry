import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonSize = "sm" | "md";
type ButtonVariant = "primary" | "danger" | "secondary";

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "type"> {
  size?: ButtonSize;
  variant?: ButtonVariant;
  children: ReactNode;
}

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "px-[10px] py-[6px] text-[11px]",
  md: "px-[13px] py-[10px] text-[12px]",
};

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-brand text-ink hover:brightness-110",
  danger: "bg-[#ff5f57] text-ink hover:brightness-110",
  secondary: "bg-transparent border border-surface-border text-white hover:bg-[#454545]",
};

/** Standard button: pick a size (sm/md) and variant (primary/danger/secondary). */
export default function Button({
  size = "md",
  variant = "primary",
  className = "",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-bold tracking-wide transition-colors disabled:bg-surface-muted disabled:text-white/50 disabled:cursor-not-allowed ${SIZE_CLASSES[size]} ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
