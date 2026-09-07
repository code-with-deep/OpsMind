export function OpsMindLogo({ className = "w-8 h-8" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <rect
        x="2"
        y="2"
        width="36"
        height="36"
        rx="10"
        className="fill-surface-950 stroke-accent-500/60"
        strokeWidth="1.5"
      />
      <path
        d="M12 26c0-5.523 4.477-10 10-10s10 4.477 10 10"
        className="stroke-accent-400"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="14" cy="16" r="2.5" className="fill-accent-400" />
      <circle cx="26" cy="16" r="2.5" className="fill-accent-500" />
      <circle cx="20" cy="26" r="2.5" className="fill-accent-300" />
      <path
        d="M14 16l6 10M26 16l-6 10"
        className="stroke-accent-500/50"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
      <circle cx="20" cy="20" r="1.5" className="fill-white" />
    </svg>
  );
}
