import { Link } from "react-router-dom";
import { OpsMindLogo } from "../components/common/OpsMindLogo";
import { routes } from "../lib/routes";

export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <div className="app-shell min-h-screen flex flex-col font-sans selection:bg-accent-500 selection:text-surface-950">
      <div className="flex-1 flex flex-col items-center justify-center px-4 py-10 pb-[max(2.5rem,env(safe-area-inset-bottom))]">
        <Link to={routes.home} className="flex items-center gap-2.5 mb-8 group">
          <OpsMindLogo className="w-10 h-10 group-hover:scale-105 transition-transform" />
          <span className="font-app-heading text-2xl text-white tracking-tight">OpsMind</span>
        </Link>

        <div className="w-full max-w-md app-panel p-5 sm:p-6 animate-slide-up">
          <h1 className="font-app-heading text-xl sm:text-2xl text-white">{title}</h1>
          <p className="text-sm text-surface-400 mt-1.5 leading-relaxed">{subtitle}</p>
          <div className="mt-5 space-y-4">{children}</div>
          {footer ? <div className="mt-5 pt-4 border-t border-surface-800/60 text-sm text-surface-400">{footer}</div> : null}
        </div>
      </div>
    </div>
  );
}
