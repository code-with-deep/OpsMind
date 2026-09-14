import { ReactNode, useState } from "react";
import { Link } from "react-router-dom";
import {
  BookOpen,
  CheckCircle2,
  Circle,
  ClipboardCheck,
  Database,
  Lock,
  Play,
  Rocket,
  Sparkles,
  UserPlus,
} from "lucide-react";
import { api, errorMessage, OnboardingStatus } from "../../lib/api";
import { routes } from "../../lib/routes";
import { formatDay } from "../../lib/utils";
import { Button } from "../common/Button";
import { FormAlert } from "../common/FormField";

interface GetStartedChecklistProps {
  status: OnboardingStatus;
  launching: boolean;
  onRunQuestion: (question: string) => void;
  onAskOwnQuestion: () => void;
  onOpenInvestigation: (id: string) => void;
  onRefresh: () => Promise<void>;
  onHide: () => void;
}

type Step = {
  key: string;
  title: string;
  icon: ReactNode;
  done: boolean;
  locked?: boolean;
  body: ReactNode;
  actions?: ReactNode;
};

function SetupLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-1.5 rounded-lg border border-surface-700 px-3 py-1.5 text-xs font-medium text-surface-200 hover:border-surface-500 hover:text-white transition-colors"
    >
      {children}
    </Link>
  );
}

const count = (n: number) => n.toLocaleString();

/** Guides a new workspace from signup to its first reviewed report. Steps tick
 * off by themselves as data, playbooks, runs and reviews appear (live updates). */
export function GetStartedChecklist({
  status,
  launching,
  onRunQuestion,
  onAskOwnQuestion,
  onOpenInvestigation,
  onRefresh,
  onHide,
}: GetStartedChecklistProps) {
  const [loadingSample, setLoadingSample] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { steps, is_admin: isAdmin, data_coverage: coverage } = status;

  const loadSample = async () => {
    setLoadingSample(true);
    setError(null);
    try {
      await api.loadSampleData();
      await onRefresh();
    } catch (err) {
      setError(errorMessage(err, "Couldn't load the sample store. Please try again."));
    } finally {
      setLoadingSample(false);
    }
  };

  const adminAddsThis = (
    <p className="text-xs text-surface-500">Your workspace admin adds this in Settings.</p>
  );

  const items: Step[] = [
    {
      key: "business_data",
      title: "Add your business data",
      icon: <Database className="w-4 h-4" />,
      done: steps.business_data.done,
      body: steps.business_data.done
        ? `${count(steps.business_data.orders)} orders and ${count(steps.business_data.products)} products loaded${
            coverage ? `, covering ${formatDay(coverage.start)} – ${formatDay(coverage.end)}` : ""
          }.`
        : "Products, orders and order items as CSV files in one ZIP. No file handy? Start with our sample store and swap in your own data later.",
      actions: steps.business_data.done ? null : isAdmin ? (
        <>
          {status.sample_data_available ? (
            <Button variant="accent" size="sm" loading={loadingSample} onClick={() => void loadSample()}>
              Load sample store
            </Button>
          ) : null}
          <SetupLink to={`${routes.settings}#business-data`}>Upload my own data</SetupLink>
        </>
      ) : (
        adminAddsThis
      ),
    },
    {
      key: "playbooks",
      title: "Add your playbooks",
      icon: <BookOpen className="w-4 h-4" />,
      done: steps.playbooks.done,
      body: steps.playbooks.done
        ? `${count(steps.playbooks.count)} playbook${steps.playbooks.count === 1 ? "" : "s"} ready to cite.`
        : "Your standard operating procedures as Markdown files. Reports quote them when recommending what to do.",
      actions: steps.playbooks.done ? null : isAdmin ? (
        <>
          {steps.business_data.done && status.sample_data_available ? (
            <Button variant="secondary" size="sm" loading={loadingSample} onClick={() => void loadSample()}>
              Use sample playbooks
            </Button>
          ) : null}
          <SetupLink to={`${routes.settings}#playbooks`}>Upload playbooks</SetupLink>
        </>
      ) : (
        adminAddsThis
      ),
    },
    {
      key: "first_investigation",
      title: "Run your first investigation",
      icon: <Sparkles className="w-4 h-4" />,
      done: steps.first_investigation.done,
      locked: !status.ready_to_investigate,
      body: !status.ready_to_investigate
        ? "Unlocks after steps 1 and 2."
        : steps.first_investigation.done
        ? "Done — past runs are in History."
        : "Ask why something changed. The agents query your data, check your playbooks and fact-check the answer before showing it.",
      actions:
        steps.first_investigation.done || !status.ready_to_investigate ? null : (
          <div className="flex flex-col gap-2 w-full">
            {status.suggested_questions.slice(0, 2).map((suggestion) => (
              <button
                key={suggestion.question}
                type="button"
                disabled={launching}
                onClick={() => onRunQuestion(suggestion.question)}
                className="group flex items-center justify-between gap-3 rounded-lg border border-surface-700/70 bg-surface-950/40 px-3 py-2 text-left hover:border-accent-700/70 disabled:opacity-60 transition-colors"
              >
                <span className="min-w-0">
                  <span className="block text-xs font-medium text-surface-100 group-hover:text-accent-200">
                    {suggestion.title}
                  </span>
                  <span className="block text-[11px] text-surface-500 truncate">{suggestion.question}</span>
                </span>
                <Play className="w-3.5 h-3.5 text-accent-400 shrink-0" />
              </button>
            ))}
            <div>
              <Button variant="outline" size="sm" onClick={onAskOwnQuestion}>
                Ask my own question
              </Button>
            </div>
          </div>
        ),
    },
    {
      key: "first_review",
      title: "Review the report",
      icon: <ClipboardCheck className="w-4 h-4" />,
      done: steps.first_review.done,
      locked: !steps.first_investigation.done,
      body: !steps.first_investigation.done
        ? "Unlocks after your first investigation."
        : steps.first_review.done
        ? "Approved reports are saved to Case Memory and inform future investigations."
        : "Check the evidence behind each claim, then approve or reject. Approved reports become Case Memory for future investigations.",
      actions:
        !steps.first_review.done && steps.first_investigation.latest_id ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onOpenInvestigation(steps.first_investigation.latest_id as string)}
          >
            Open latest report
          </Button>
        ) : null,
    },
    ...(isAdmin
      ? [
          {
            key: "team",
            title: "Invite your team",
            icon: <UserPlus className="w-4 h-4" />,
            done: steps.team.done,
            body: steps.team.done
              ? "Teammates can request access with your invite code — you approve each one."
              : "Create an invite code and share it. Teammates request access and you approve each one.",
            actions: steps.team.done ? null : (
              <SetupLink to={`${routes.settings}#invites`}>Create invite code</SetupLink>
            ),
          },
        ]
      : []),
  ];

  const doneCount = items.filter((item) => item.done).length;
  const allDone = doneCount === items.length;
  const nextKey = items.find((item) => !item.done && !item.locked)?.key;

  return (
    <section className="app-card p-5 sm:p-6 space-y-5" aria-labelledby="get-started-title">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 id="get-started-title" className="font-app-heading text-lg text-white flex items-center gap-2">
            <Rocket className="w-5 h-5 text-accent-400" />
            {allDone ? "You're all set" : "Get started with OpsMind"}
          </h2>
          <p className="text-sm text-surface-400">
            {allDone
              ? "Your workspace is ready. Start a new investigation any time."
              : "A few quick steps to your first evidence-backed report."}
          </p>
        </div>
        <div className="space-y-1.5 shrink-0 sm:text-right">
          <span className="text-xs text-surface-400">
            {doneCount} of {items.length} done
          </span>
          <div
            className="h-1.5 w-full sm:w-40 rounded-full bg-surface-800 overflow-hidden"
            role="progressbar"
            aria-label="Setup progress"
            aria-valuenow={doneCount}
            aria-valuemin={0}
            aria-valuemax={items.length}
          >
            <div
              className="h-full bg-accent-500 transition-all duration-500"
              style={{ width: `${(doneCount / items.length) * 100}%` }}
            />
          </div>
        </div>
      </div>

      {error ? <FormAlert>{error}</FormAlert> : null}

      <ol className="space-y-3">
        {items.map((item, index) => {
          const isNext = item.key === nextKey;
          return (
            <li
              key={item.key}
              className={`rounded-xl border p-4 flex gap-3 transition-colors ${
                isNext ? "border-accent-700/60 bg-accent-950/20" : "border-surface-800/60"
              } ${item.locked ? "opacity-60" : ""}`}
            >
              <div className="shrink-0 mt-0.5" aria-hidden="true">
                {item.done ? (
                  <CheckCircle2 className="w-5 h-5 text-accent-400" />
                ) : item.locked ? (
                  <Lock className="w-5 h-5 text-surface-500" />
                ) : (
                  <Circle className="w-5 h-5 text-surface-500" />
                )}
              </div>
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-surface-500">{item.icon}</span>
                  <h3 className={`text-sm font-medium ${item.done ? "text-surface-400" : "text-white"}`}>
                    <span className="sr-only">
                      Step {index + 1}
                      {item.done ? " (done)" : item.locked ? " (locked)" : ""}:{" "}
                    </span>
                    {item.title}
                  </h3>
                  {isNext ? (
                    <span className="rounded-full bg-accent-900/60 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-accent-200">
                      Next
                    </span>
                  ) : null}
                </div>
                <p className="text-xs text-surface-400 leading-relaxed">{item.body}</p>
                {item.actions ? <div className="flex flex-wrap items-center gap-2 pt-1">{item.actions}</div> : null}
              </div>
            </li>
          );
        })}
      </ol>

      <div className="flex justify-end">
        <button type="button" onClick={onHide} className="text-xs text-surface-400 hover:text-surface-200">
          {allDone ? "Hide checklist" : "Hide for now"}
        </button>
      </div>
    </section>
  );
}
