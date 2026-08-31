import React from "react";
import { cn } from "../../lib/utils";

export type BadgeVariant =
  | "default"
  | "success"
  | "warning"
  | "error"
  | "info"
  | "purple"
  | "brand"
  | "outline";

export interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: "xs" | "sm" | "md" | "lg";
  dot?: boolean;
  dotColor?: string;
  className?: string;
  title?: string;
}

export function Badge({
  children,
  variant = "default",
  size = "sm",
  dot = false,
  dotColor,
  className,
  title,
}: BadgeProps) {
  const variantStyles: Record<BadgeVariant, string> = {
    default: "bg-surface-800/90 text-surface-300 border-surface-700/60",
    success: "bg-emerald-950/70 text-emerald-300 border-emerald-800/70",
    warning: "bg-amber-950/70 text-amber-300 border-amber-800/70",
    error: "bg-rose-950/70 text-rose-300 border-rose-800/70",
    info: "bg-sky-950/70 text-sky-300 border-sky-800/70",
    purple: "bg-purple-950/70 text-purple-300 border-purple-800/70",
    brand: "bg-brand-950/80 text-brand-300 border-brand-800/80",
    outline: "bg-transparent text-surface-300 border-surface-700",
  };

  const sizeStyles = {
    xs: "px-1.5 py-0.2 text-[10px] font-mono",
    sm: "px-2 py-0.5 text-xs font-medium",
    md: "px-2.5 py-1 text-xs font-medium",
    lg: "px-3 py-1.5 text-sm font-semibold",
  };

  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border tracking-tight shadow-sm select-none",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
    >
      {dot && (
        <span
          className={cn(
            "w-1.5 h-1.5 rounded-full shrink-0",
            dotColor ||
              (variant === "success"
                ? "bg-emerald-400"
                : variant === "warning"
                ? "bg-amber-400"
                : variant === "error"
                ? "bg-rose-400"
                : variant === "info"
                ? "bg-sky-400"
                : variant === "purple"
                ? "bg-purple-400"
                : variant === "brand"
                ? "bg-brand-400"
                : "bg-surface-400")
          )}
        />
      )}
      {children}
    </span>
  );
}
