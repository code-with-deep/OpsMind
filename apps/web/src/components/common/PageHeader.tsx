import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

interface PageHeaderProps {
  icon: ReactNode;
  title: string;
  description?: string;
  badge?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function PageHeader({
  icon,
  title,
  description,
  badge,
  action,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "app-panel flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 sm:p-5",
        className
      )}
    >
      <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
        <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-b from-accent-500 to-accent-700 flex items-center justify-center text-white shadow-glow-accent shrink-0">
          {icon}
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="font-app-heading text-lg sm:text-xl text-white">{title}</h2>
            {badge}
          </div>
          {description && (
            <p className="text-sm text-surface-400 mt-1 leading-relaxed">
              {description}
            </p>
          )}
        </div>
      </div>
      {action && <div className="w-full sm:w-auto shrink-0">{action}</div>}
    </div>
  );
}
