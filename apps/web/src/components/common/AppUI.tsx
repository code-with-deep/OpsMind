import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

/* ─── Section card ─── */
interface SectionCardProps {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  badge?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  noPadding?: boolean;
}

export function SectionCard({
  title,
  subtitle,
  icon,
  badge,
  action,
  children,
  className,
  bodyClassName,
  noPadding,
}: SectionCardProps) {
  return (
    <section className={cn("app-section", className)}>
      <div className="app-section-header">
        <div className="flex items-start gap-3 min-w-0 flex-1 basis-full sm:basis-auto">
          {icon && (
            <div className="app-section-icon shrink-0">{icon}</div>
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="font-app-heading text-base sm:text-lg text-white">{title}</h2>
            </div>
            {subtitle && (
              <p className="text-xs sm:text-sm text-surface-400 mt-0.5 leading-relaxed">{subtitle}</p>
            )}
          </div>
        </div>
        {badge && (
          <div className="flex flex-wrap items-center gap-1.5 w-full sm:w-auto sm:shrink-0 pl-12 sm:pl-0">
            {badge}
          </div>
        )}
        {action && <div className="shrink-0 w-full sm:w-auto">{action}</div>}
      </div>
      <div className={cn(!noPadding && "app-section-body", bodyClassName)}>{children}</div>
    </section>
  );
}

/* ─── Search bar ─── */
interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export function SearchBar({ value, onChange, placeholder, className }: SearchBarProps) {
  return (
    <div className={cn("app-search-wrap", className)}>
      <svg
        className="app-search-icon"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
        aria-hidden
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M21 21l-4.35-4.35M11 18a7 7 0 100-14 7 7 0 000 14z"
        />
      </svg>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="app-search-input"
      />
    </div>
  );
}

/* ─── Filter pills ─── */
export interface FilterOption {
  key: string;
  label: string;
  count?: number;
}

interface FilterPillsProps {
  options: FilterOption[];
  value: string;
  onChange: (key: string) => void;
  className?: string;
}

export function FilterPills({ options, value, onChange, className }: FilterPillsProps) {
  return (
    <div className={cn("app-filter-bar", className)}>
      {options.map((opt) => (
        <button
          key={opt.key}
          type="button"
          onClick={() => onChange(opt.key)}
          className={cn("app-filter-pill", value === opt.key && "app-filter-pill-active")}
        >
          {opt.label}
          {opt.count !== undefined && (
            <span className="opacity-70 font-mono text-[10px]">{opt.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}

/* ─── Sub-view tabs (console) ─── */
export interface TabItem {
  key: string;
  label: string;
  icon?: ReactNode;
  count?: number;
}

interface SubViewTabsProps {
  tabs: TabItem[];
  active: string;
  onChange: (key: string) => void;
}

export function SubViewTabs({ tabs, active, onChange }: SubViewTabsProps) {
  return (
    <div className="app-tab-bar">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onChange(tab.key)}
          className={cn("app-tab", active === tab.key && "app-tab-active")}
        >
          {tab.icon}
          <span>{tab.label}</span>
          {tab.count !== undefined && (
            <span className="app-tab-count">{tab.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}

/* ─── Empty state ─── */
interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="app-empty">
      <div className="app-empty-icon">{icon}</div>
      <h3 className="font-app-heading text-base text-white">{title}</h3>
      {description && <p className="app-empty-desc">{description}</p>}
      {action && <div className="pt-2">{action}</div>}
    </div>
  );
}

/* ─── List row card ─── */
interface ListCardProps {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}

export function ListCard({ children, onClick, className }: ListCardProps) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className={cn("app-list-card", onClick && "app-list-card-clickable group", className)}
    >
      {children}
    </Tag>
  );
}

/* ─── Readable prose block ─── */
export function ProseBlock({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("app-prose", className)}>{children}</div>;
}
