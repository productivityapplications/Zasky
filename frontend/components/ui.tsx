"use client";

import { X } from "lucide-react";
import {
  type AnchorHTMLAttributes,
  type ButtonHTMLAttributes,
  type ReactNode,
  useEffect,
} from "react";

import { cn } from "@/lib/utils";

export function Modal({
  title,
  subtitle,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/35 p-4 backdrop-blur-md"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        className={cn(
          "max-h-[calc(100vh-32px)] w-full overflow-y-auto rounded-shell border border-white/70 bg-surface p-5 shadow-shell sm:p-6",
          wide ? "max-w-3xl" : "max-w-xl",
        )}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="flex items-start justify-between gap-4 pb-5">
          <div>
            <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-muted">
              {subtitle ?? "Owner action"}
            </p>
            <h2 className="mt-1 font-display text-2xl font-semibold tracking-[-0.04em]">
              {title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-black/10 bg-white/70 text-ink/60 transition hover:bg-white hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/30"
          >
            <X size={15} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "calendar";
  size?: "sm" | "md";
};

export function Button({
  variant = "secondary",
  size = "md",
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/30 disabled:cursor-wait disabled:opacity-50",
        size === "sm" ? "h-8 px-3 text-[10px]" : "h-10 px-4 text-xs",
        variant === "primary" &&
          "bg-ink text-white shadow-[0_10px_22px_-12px_rgba(0,0,0,0.8)] hover:-translate-y-0.5 hover:bg-ink-soft",
        variant === "secondary" &&
          "border border-black/10 bg-white/80 text-ink shadow-sm hover:-translate-y-0.5 hover:bg-white",
        variant === "calendar" &&
          "border border-black/10 bg-zest text-ink shadow-sm hover:-translate-y-0.5 hover:bg-[#f8ed82]",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function LinkButton({
  variant = "secondary",
  size = "md",
  className,
  children,
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement> & {
  variant?: "primary" | "secondary" | "calendar";
  size?: "sm" | "md";
}) {
  return (
    <a
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/30",
        size === "sm" ? "h-8 px-3 text-[10px]" : "h-10 px-4 text-xs",
        variant === "primary" &&
          "bg-ink text-white shadow-[0_10px_22px_-12px_rgba(0,0,0,0.8)] hover:-translate-y-0.5 hover:bg-ink-soft",
        variant === "secondary" &&
          "border border-black/10 bg-white/80 text-ink shadow-sm hover:-translate-y-0.5 hover:bg-white",
        variant === "calendar" &&
          "border border-black/10 bg-zest text-ink shadow-sm hover:-translate-y-0.5 hover:bg-[#f8ed82]",
        className,
      )}
      {...props}
    >
      {children}
    </a>
  );
}

export function StatusPill({
  status,
  className,
}: {
  status: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.12em]",
        status === "active" && "bg-ink/10 text-ink/70",
        status === "parked" && "bg-amber-200/60 text-amber-900",
        status === "completed" && "bg-black/10 text-black/45",
        status === "cancelled" && "bg-red-200/60 text-red-900",
        className,
      )}
    >
      {status}
    </span>
  );
}

export function Spinner({ large = false }: { large?: boolean }) {
  return (
    <span
      className={cn(
        "inline-block animate-spin rounded-full border-2 border-ink/15 border-t-ink",
        large ? "h-7 w-7" : "h-3.5 w-3.5",
      )}
      aria-hidden="true"
    />
  );
}

export function EmptyState({
  title,
  body,
  icon,
}: {
  title: string;
  body: string;
  icon?: ReactNode;
}) {
  return (
    <div className="grid min-h-64 place-items-center rounded-panel border border-dashed border-black/10 bg-white/45 p-8 text-center">
      <div>
        <div className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-2xl bg-zest text-2xl shadow-card">
          {icon ?? "✦"}
        </div>
        <h3 className="font-display text-xl font-semibold tracking-[-0.03em]">
          {title}
        </h3>
        <p className="mx-auto mt-2 max-w-sm text-xs leading-relaxed text-muted">
          {body}
        </p>
      </div>
    </div>
  );
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="text-[9px] font-bold uppercase tracking-[0.18em] text-muted">
      {children}
    </p>
  );
}
