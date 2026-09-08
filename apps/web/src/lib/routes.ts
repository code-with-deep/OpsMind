export type ConsoleSubView = "report" | "evidence" | "timeline";

export const routes = {
  home: "/",
  login: "/login",
  signup: "/signup",
  join: "/join",
  settings: "/settings",
  console: "/console",
  consoleInvestigation: (id: string, view?: Exclude<ConsoleSubView, "report">) =>
    view ? `/console/${id}/${view}` : `/console/${id}`,
  history: "/history",
  cases: "/cases",
} as const;

export function parseConsoleSubView(segment?: string): ConsoleSubView {
  if (segment === "evidence") return "evidence";
  if (segment === "timeline") return "timeline";
  return "report";
}

export function getActiveTabFromPath(pathname: string) {
  if (pathname.startsWith("/console")) return "investigation" as const;
  if (pathname.startsWith("/history")) return "history" as const;
  if (pathname.startsWith("/cases")) return "cases" as const;
  if (pathname.startsWith("/settings")) return "settings" as const;
  return "overview" as const;
}
