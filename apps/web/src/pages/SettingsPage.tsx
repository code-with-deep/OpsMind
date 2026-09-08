import { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Check,
  Copy,
  Database,
  Settings2,
  Ticket,
  Trash2,
  Upload,
  UserCheck,
  UserX,
  Users,
  X,
} from "lucide-react";
import { PageHeader } from "../components/common/PageHeader";
import { Button } from "../components/common/Button";
import { Badge } from "../components/common/Badge";
import {
  AccessRequest,
  AccessUser,
  api,
  AuthUser,
  DataReadyStatus,
  IngestJobItem,
  InviteItem,
  PlaybookItem,
  getStoredUser,
  setStoredUser,
} from "../lib/api";

type AccessTab = "pending" | "active" | "revoked";

export function SettingsPage() {
  const [user, setUser] = useState<AuthUser | null>(getStoredUser());
  const [invites, setInvites] = useState<InviteItem[]>([]);
  const [playbooks, setPlaybooks] = useState<PlaybookItem[]>([]);
  const [jobs, setJobs] = useState<IngestJobItem[]>([]);
  const [ready, setReady] = useState<DataReadyStatus | null>(null);
  const [freshCode, setFreshCode] = useState<string | null>(null);
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [savingCompany, setSavingCompany] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [csvUploading, setCsvUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const csvRef = useRef<HTMLInputElement>(null);

  // Access management state
  const [accessRequests, setAccessRequests] = useState<AccessRequest[]>([]);
  const [accessUsers, setAccessUsers] = useState<AccessUser[]>([]);
  const [accessTab, setAccessTab] = useState<AccessTab>("pending");
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [accessActionLoading, setAccessActionLoading] = useState<string | null>(null);
  const [revokeConfirmId, setRevokeConfirmId] = useState<string | null>(null);

  const isAdmin = user?.role === "admin";

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const me = await api.me();
      setUser(me.user);
      setStoredUser(me.user);
      setCompanyName(me.user.tenant.name);
      const [pb, status, jobList] = await Promise.all([
        api.listPlaybooks(),
        api.dataReady(),
        api.listIngestJobs(),
      ]);
      setPlaybooks(pb.playbooks || []);
      setReady(status);
      setJobs(jobList.jobs || []);
      if (me.user.role === "admin") {
        const [inv, requests, users] = await Promise.all([
          api.listInvites(),
          api.listAccessRequests("all"),
          api.listAccessUsers("all"),
        ]);
        setInvites(inv.invites || []);
        setAccessRequests(requests.requests || []);
        setAccessUsers(users.users || []);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // Scroll to #access if anchor is present
    if (window.location.hash === "#access") {
      setTimeout(() => {
        document.getElementById("access-management")?.scrollIntoView({ behavior: "smooth" });
      }, 400);
    }
  }, []);

  const createInvite = async () => {
    setCreating(true);
    setError(null);
    setFreshCode(null);
    try {
      const res = await api.createInvite();
      setFreshCode(res.invite.code);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create invite");
    } finally {
      setCreating(false);
    }
  };

  const revoke = async (id: string) => {
    setError(null);
    try {
      await api.revokeInvite(id);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to revoke invite");
    }
  };

  const copyCode = async () => {
    if (!freshCode) return;
    await navigator.clipboard.writeText(freshCode);
  };

  const saveCompany = async () => {
    if (!companyName.trim()) return;
    setSavingCompany(true);
    setError(null);
    try {
      const res = await api.updateTenant({ name: companyName.trim() });
      if (user) {
        const next = {
          ...user,
          tenant: { ...user.tenant, name: res.tenant.name, slug: res.tenant.slug },
        };
        setUser(next);
        setStoredUser(next);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update company");
    } finally {
      setSavingCompany(false);
    }
  };

  const onPickFile = async (file: File | null) => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await api.uploadPlaybook(file);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to upload playbook");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onPickCsv = async (file: File | null) => {
    if (!file) return;
    setCsvUploading(true);
    setError(null);
    try {
      await api.uploadCsv(file);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to upload CSV");
    } finally {
      setCsvUploading(false);
      if (csvRef.current) csvRef.current.value = "";
    }
  };

  const removePlaybook = async (id: string) => {
    setError(null);
    try {
      await api.deletePlaybook(id);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete playbook");
    }
  };

  // ── Access management actions ──────────────────────────────────────────────

  const approveRequest = async (id: string) => {
    setAccessActionLoading(id);
    setError(null);
    try {
      await api.approveAccessRequest(id);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to approve request");
    } finally {
      setAccessActionLoading(null);
    }
  };

  const rejectRequest = async (id: string) => {
    setAccessActionLoading(id);
    setError(null);
    try {
      await api.rejectAccessRequest(id, rejectReason.trim() || undefined);
      setRejectingId(null);
      setRejectReason("");
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to reject request");
    } finally {
      setAccessActionLoading(null);
    }
  };

  const revokeUser = async (userId: string) => {
    setAccessActionLoading(userId);
    setError(null);
    try {
      await api.revokeUserAccess(userId);
      setRevokeConfirmId(null);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to revoke access");
    } finally {
      setAccessActionLoading(null);
    }
  };

  const pendingRequests = accessRequests.filter((r) => r.status === "pending");
  const activeUsers = accessUsers.filter((u) => u.status === "active" && u.email !== user?.email);
  const revokedUsers = accessUsers.filter((u) => u.status === "revoked");

  return (
    <div className="space-y-5 animate-fadeIn">
      <PageHeader
        icon={<Settings2 className="w-5 h-5" />}
        title="Settings"
        description="Company data, playbooks, and access management for teammates."
      />

      {error ? (
        <div className="text-xs text-rose-300 bg-rose-950/50 border border-rose-800/60 rounded-xl px-3 py-2">
          {error}
        </div>
      ) : null}

      <section className="app-section">
        <div className="app-section-header">
          <h3 className="font-app-heading text-base text-white">Company</h3>
        </div>
        <div className="app-section-body app-prose space-y-3 text-sm">
          {user ? (
            <>
              {isAdmin ? (
                <div className="flex flex-col sm:flex-row gap-2 sm:items-end">
                  <label className="flex-1 min-w-0">
                    <span className="text-xs text-surface-400">Company name</span>
                    <input
                      className="mt-1 w-full rounded-xl border border-surface-700 bg-surface-950/60 px-3 py-2 text-sm text-surface-100"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                    />
                  </label>
                  <Button
                    variant="accent"
                    size="sm"
                    loading={savingCompany}
                    onClick={() => void saveCompany()}
                  >
                    Save
                  </Button>
                </div>
              ) : (
                <p>
                  <span className="text-surface-400">Company:</span>{" "}
                  <span className="text-surface-100">{user.tenant.name}</span>
                </p>
              )}
              <p>
                <span className="text-surface-400">Slug:</span>{" "}
                <code className="font-mono text-surface-300">{user.tenant.slug}</code>
              </p>
              <p>
                <span className="text-surface-400">You:</span>{" "}
                <span className="text-surface-100">{user.email}</span>{" "}
                <Badge variant="success" size="xs">
                  {user.role}
                </Badge>
              </p>
            </>
          ) : (
            <p className="text-surface-400">
              {loading
                ? "Loading…"
                : "Sign in with email/password to manage company settings. API-key-only sessions cannot manage invites."}
            </p>
          )}
        </div>
      </section>

      {user ? (
        <section className="app-section">
          <div className="app-section-header flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="font-app-heading text-base text-white">Business data</h3>
              <p className="text-xs text-surface-400 mt-1">
                Primary setup for most companies: upload a ZIP with products.csv, orders.csv,
                and order_items.csv. Investigations stay locked until this company has data.
              </p>
            </div>
            {isAdmin ? (
              <>
                <input
                  ref={csvRef}
                  type="file"
                  accept=".zip,application/zip"
                  className="hidden"
                  onChange={(e) => void onPickCsv(e.target.files?.[0] ?? null)}
                />
                <Button
                  variant="accent"
                  size="sm"
                  icon={<Upload className="w-3.5 h-3.5" />}
                  loading={csvUploading}
                  onClick={() => csvRef.current?.click()}
                >
                  Upload CSV ZIP
                </Button>
              </>
            ) : null}
          </div>
          <div className="app-section-body space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Database className="w-4 h-4 text-accent-400" />
              {ready?.ready ? (
                <Badge variant="success" size="xs">
                  ready to investigate
                </Badge>
              ) : (
                <Badge variant="error" size="xs">
                  upload required
                </Badge>
              )}
              <span className="text-xs text-surface-400">
                products {ready?.products ?? 0} · orders {ready?.orders ?? 0} · metrics{" "}
                {ready?.daily_metrics ?? 0}
              </span>
            </div>

            {jobs.length === 0 ? (
              <p className="app-empty text-sm">
                No CSV ingest jobs yet
                {isAdmin ? " — upload a ZIP to unlock investigations for this company." : "."}
              </p>
            ) : (
              <ul className="space-y-2">
                {jobs.map((job) => (
                  <li
                    key={job.id}
                    className="app-list-card flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm text-surface-100 truncate">{job.filename}</span>
                        {job.status === "done" ? (
                          <Badge variant="success" size="xs">done</Badge>
                        ) : job.status === "failed" ? (
                          <Badge variant="error" size="xs">failed</Badge>
                        ) : (
                          <Badge variant="default" size="xs">{job.status}</Badge>
                        )}
                      </div>
                      <p className="text-xs text-surface-400 mt-1 font-mono">
                        {job.status === "done"
                          ? Object.entries(job.row_counts || {})
                              .map(([k, v]) => `${k}:${v}`)
                              .join(" · ")
                          : job.error || "—"}
                      </p>
                    </div>
                    <p className="text-xs text-surface-500 shrink-0">
                      {job.created_at ? new Date(job.created_at).toLocaleString() : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      ) : null}

      {user ? (
        <section className="app-section">
          <div className="app-section-header flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="font-app-heading text-base text-white">Playbooks</h3>
              <p className="text-xs text-surface-400 mt-1">
                Company SOPs are chunked and embedded for RAG — never shared with other tenants.
              </p>
            </div>
            {isAdmin ? (
              <>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".md,.markdown,.txt,text/markdown,text/plain"
                  className="hidden"
                  onChange={(e) => void onPickFile(e.target.files?.[0] ?? null)}
                />
                <Button
                  variant="accent"
                  size="sm"
                  icon={<Upload className="w-3.5 h-3.5" />}
                  loading={uploading}
                  onClick={() => fileRef.current?.click()}
                >
                  Upload SOP
                </Button>
              </>
            ) : null}
          </div>
          <div className="app-section-body space-y-3">
            {playbooks.length === 0 ? (
              <p className="app-empty text-sm">
                {isAdmin
                  ? "No playbooks yet. Upload a Markdown SOP to ground investigations."
                  : "No playbooks uploaded for this company yet."}
              </p>
            ) : (
              <ul className="space-y-2">
                {playbooks.map((pb) => (
                  <li
                    key={pb.id}
                    className="app-list-card flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <div className="min-w-0 flex items-start gap-2">
                      <BookOpen className="w-4 h-4 text-accent-400 mt-0.5 shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm text-surface-100 truncate">{pb.title}</p>
                        <p className="text-xs text-surface-400 mt-1 font-mono">
                          {pb.doc_key} · {pb.chunk_count} chunk
                          {pb.chunk_count === 1 ? "" : "s"}
                          {pb.updated_at
                            ? ` · ${new Date(pb.updated_at).toLocaleDateString()}`
                            : ""}
                        </p>
                      </div>
                    </div>
                    {isAdmin ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Trash2 className="w-3.5 h-3.5" />}
                        onClick={() => void removePlaybook(pb.id)}
                      >
                        Delete
                      </Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      ) : null}

      {isAdmin ? (
        <section className="app-section">
          <div className="app-section-header flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="font-app-heading text-base text-white">Invite codes</h3>
              <p className="text-xs text-surface-400 mt-1">
                Investigators redeem a code to submit an access request for this tenant.
              </p>
            </div>
            <Button
              variant="accent"
              size="sm"
              icon={<Ticket className="w-3.5 h-3.5" />}
              loading={creating}
              onClick={() => void createInvite()}
            >
              Generate invite
            </Button>
          </div>
          <div className="app-section-body space-y-3">
            {freshCode ? (
              <div className="rounded-xl border border-accent-700/40 bg-accent-950/30 px-3 py-3 flex flex-col sm:flex-row sm:items-center gap-2 justify-between">
                <div>
                  <p className="text-xs text-accent-300 mb-1">Copy now — shown once</p>
                  <code className="font-mono text-sm text-white">{freshCode}</code>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Copy className="w-3.5 h-3.5" />}
                  onClick={() => void copyCode()}
                >
                  Copy
                </Button>
              </div>
            ) : null}

            {invites.length === 0 ? (
              <p className="app-empty text-sm">No invite codes yet.</p>
            ) : (
              <ul className="space-y-2">
                {invites.map((inv) => (
                  <li
                    key={inv.id}
                    className="app-list-card flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <code className="font-mono text-sm text-surface-100">
                          {inv.code_prefix}
                        </code>
                        {inv.active ? (
                          <Badge variant="success" size="xs">active</Badge>
                        ) : (
                          <Badge variant="error" size="xs">inactive</Badge>
                        )}
                      </div>
                      <p className="text-xs text-surface-400 mt-1">
                        Uses {inv.use_count}/{inv.max_uses}
                        {inv.expires_at
                          ? ` · expires ${new Date(inv.expires_at).toLocaleDateString()}`
                          : ""}
                      </p>
                    </div>
                    {inv.revoked_at == null ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Trash2 className="w-3.5 h-3.5" />}
                        onClick={() => void revoke(inv.id)}
                      >
                        Revoke
                      </Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      ) : null}

      {/* ── Access Management (admin only) ──────────────────────────────────── */}
      {isAdmin ? (
        <section className="app-section" id="access-management">
          <div className="app-section-header">
            <div>
              <h3 className="font-app-heading text-base text-white flex items-center gap-2">
                <Users className="w-4 h-4 text-accent-400" />
                Access Management
              </h3>
              <p className="text-xs text-surface-400 mt-1">
                Review access requests and manage workspace members.
              </p>
            </div>
          </div>

          {/* Tab pills */}
          <div className="px-4 pt-3 flex gap-2 flex-wrap">
            {(["pending", "active", "revoked"] as AccessTab[]).map((tab) => {
              const count =
                tab === "pending"
                  ? pendingRequests.length
                  : tab === "active"
                    ? activeUsers.length
                    : revokedUsers.length;
              return (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setAccessTab(tab)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    accessTab === tab
                      ? "bg-accent-500 text-surface-950"
                      : "bg-surface-900/60 border border-surface-700 text-surface-400 hover:text-surface-100"
                  }`}
                >
                  {tab === "pending" ? "Pending requests" : tab === "active" ? "Active users" : "Revoked"}
                  {count > 0 && (
                    <span
                      className={`px-1.5 py-0.5 rounded-full text-[9px] font-bold tabular-nums ${
                        accessTab === tab
                          ? "bg-surface-950/30 text-surface-950"
                          : tab === "pending"
                            ? "bg-rose-900/60 text-rose-300"
                            : "bg-surface-800 text-surface-400"
                      }`}
                    >
                      {count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <div className="app-section-body space-y-3">
            {/* Pending requests */}
            {accessTab === "pending" && (
              <>
                {pendingRequests.length === 0 ? (
                  <p className="app-empty text-sm">No pending access requests.</p>
                ) : (
                  <ul className="space-y-3">
                    {pendingRequests.map((req) => (
                      <li key={req.id} className="app-list-card space-y-2">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm text-surface-100 font-medium">
                                {req.requester_email}
                              </span>
                              <Badge variant="default" size="xs">pending</Badge>
                              {req.invite_code_prefix && (
                                <code className="text-[10px] font-mono text-surface-500">
                                  via {req.invite_code_prefix}
                                </code>
                              )}
                            </div>
                            <p className="text-xs text-surface-500 mt-0.5">
                              Requested {new Date(req.created_at).toLocaleString()}
                            </p>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <Button
                              variant="accent"
                              size="sm"
                              icon={<Check className="w-3.5 h-3.5" />}
                              loading={accessActionLoading === req.id}
                              onClick={() => void approveRequest(req.id)}
                            >
                              Approve
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              icon={<X className="w-3.5 h-3.5 text-rose-400" />}
                              onClick={() => {
                                setRejectingId(req.id);
                                setRejectReason("");
                              }}
                            >
                              Reject
                            </Button>
                          </div>
                        </div>
                        {/* Inline rejection form */}
                        {rejectingId === req.id && (
                          <div className="flex flex-col sm:flex-row gap-2 pt-2 border-t border-surface-800">
                            <input
                              type="text"
                              value={rejectReason}
                              onChange={(e) => setRejectReason(e.target.value)}
                              placeholder="Optional reason…"
                              className="flex-1 min-h-9 rounded-lg bg-surface-950 border border-surface-700 px-3 text-xs text-surface-100 focus:outline-none focus:ring-1 focus:ring-rose-500/40"
                            />
                            <div className="flex gap-2">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-rose-400 hover:text-rose-300 border border-rose-800/60"
                                loading={accessActionLoading === req.id}
                                onClick={() => void rejectRequest(req.id)}
                              >
                                Confirm reject
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setRejectingId(null)}
                              >
                                Cancel
                              </Button>
                            </div>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}

            {/* Active users */}
            {accessTab === "active" && (
              <>
                {activeUsers.length === 0 ? (
                  <p className="app-empty text-sm">No active users yet. Approve an access request to add members.</p>
                ) : (
                  <ul className="space-y-2">
                    {activeUsers.map((u) => (
                      <li
                        key={u.id}
                        className="app-list-card flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm text-surface-100">{u.email}</span>
                            <Badge
                              variant={u.role === "admin" ? "success" : "default"}
                              size="xs"
                            >
                              {u.role}
                            </Badge>
                          </div>
                          <p className="text-xs text-surface-500 mt-0.5">
                            Joined {new Date(u.created_at).toLocaleDateString()}
                            {u.approved_by_email
                              ? ` · approved by ${u.approved_by_email}`
                              : ""}
                          </p>
                        </div>
                        {u.role !== "admin" && (
                          <>
                            {revokeConfirmId === u.id ? (
                              <div className="flex items-center gap-2 shrink-0">
                                <span className="text-xs text-surface-400">Revoke access?</span>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="text-rose-400 hover:text-rose-300 border border-rose-800/60"
                                  loading={accessActionLoading === u.id}
                                  onClick={() => void revokeUser(u.id)}
                                >
                                  Yes, revoke
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setRevokeConfirmId(null)}
                                >
                                  Cancel
                                </Button>
                              </div>
                            ) : (
                              <Button
                                variant="ghost"
                                size="sm"
                                icon={<UserX className="w-3.5 h-3.5 text-rose-400" />}
                                onClick={() => setRevokeConfirmId(u.id)}
                              >
                                Revoke
                              </Button>
                            )}
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}

            {/* Revoked users */}
            {accessTab === "revoked" && (
              <>
                {revokedUsers.length === 0 ? (
                  <p className="app-empty text-sm">No revoked users.</p>
                ) : (
                  <ul className="space-y-2">
                    {revokedUsers.map((u) => (
                      <li
                        key={u.id}
                        className="app-list-card flex flex-col sm:flex-row sm:items-center justify-between gap-2 opacity-70"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm text-surface-300 line-through">{u.email}</span>
                            <Badge variant="error" size="xs">revoked</Badge>
                            <Badge variant="default" size="xs">{u.role}</Badge>
                          </div>
                          <p className="text-xs text-surface-500 mt-0.5">
                            Revoked {u.revoked_at ? new Date(u.revoked_at).toLocaleString() : "—"}
                          </p>
                        </div>
                        <UserCheck className="w-4 h-4 text-surface-600 shrink-0" />
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>
        </section>
      ) : null}
    </div>
  );
}
