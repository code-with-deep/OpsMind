import React from "react";
import { cn } from "../../lib/utils";
import { Loader2 } from "lucide-react";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "outline" | "success" | "brand";
  size?: "xs" | "sm" | "md" | "lg";
  loading?: boolean;
  icon?: React.ReactNode;
  iconPosition?: "left" | "right";
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  icon,
  iconPosition = "left",
  className,
  disabled,
  ...props
}: ButtonProps) {
  const variantStyles = {
    primary:
      "bg-brand-600 hover:bg-brand-500 active:bg-brand-700 text-white shadow-sm border border-brand-500/50 focus:ring-brand-500/40",
    brand:
      "bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 active:from-brand-700 active:to-indigo-700 text-white shadow-glow-sm border border-brand-400/40 focus:ring-brand-500/40",
    secondary:
      "bg-surface-800/90 hover:bg-surface-750 active:bg-surface-700 text-surface-200 hover:text-white border border-surface-700/80 focus:ring-surface-600 shadow-sm",
    success:
      "bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white shadow-sm border border-emerald-500/50 focus:ring-emerald-500/40",
    danger:
      "bg-rose-600 hover:bg-rose-500 active:bg-rose-700 text-white shadow-sm border border-rose-500/50 focus:ring-rose-500/40",
    ghost:
      "bg-transparent hover:bg-surface-800 active:bg-surface-750 text-surface-300 hover:text-surface-100 border-transparent",
    outline:
      "bg-transparent hover:bg-surface-800/80 active:bg-surface-800 text-surface-200 hover:text-white border border-surface-700/90 hover:border-surface-600",
  };

  const sizeStyles = {
    xs: "px-2 py-1 text-xs font-medium rounded-md gap-1.5",
    sm: "px-2.5 py-1.5 text-xs font-medium rounded-lg gap-1.5",
    md: "px-3.5 py-2 text-xs sm:text-sm font-medium rounded-lg gap-2",
    lg: "px-4 py-2.5 text-sm sm:text-base font-semibold rounded-xl gap-2.5",
  };

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center transition-all duration-150 outline-none focus:ring-2 focus:ring-offset-1 focus:ring-offset-surface-950 disabled:opacity-50 disabled:cursor-not-allowed select-none cursor-pointer",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin text-current" />
      ) : icon && iconPosition === "left" ? (
        <span className="shrink-0">{icon}</span>
      ) : null}
      {children}
      {!loading && icon && iconPosition === "right" ? (
        <span className="shrink-0">{icon}</span>
      ) : null}
    </button>
  );
}
