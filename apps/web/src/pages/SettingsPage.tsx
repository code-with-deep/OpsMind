import { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Copy,
  Database,
  KeyRound,
  Settings2,
  Ticket,
  Trash2,
  Upload,
} from "lucide-react";
import { PageHeader } from "../components/common/PageHeader";
import { Button } from "../components/common/Button";
import { Badge } from "../components/common/Badge";
import {
  api,
  ApiKeyItem,
  AuthUser,
  DataReadyStatus,
  IngestJobItem,
  InviteItem,
  PlaybookItem,
  WarehouseConnection,
  getStoredUser,
  setStoredUser,
} from "../lib/api";

export function SettingsPage() {
  const [user, setUser] = useState<AuthUser | null>(getStoredUser());
  const [invites, setInvites] = useState<InviteItem[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKeyItem[]>([]);
  const [playbooks, setPlaybooks] = useState<PlaybookItem[]>([]);
  const [jobs, setJobs] = useState<IngestJobItem[]>([]);
  const [ready, setReady] = useState<DataReadyStatus | null>(null);
  const [warehouse, setWarehouse] = useState<WarehouseConnection | null>(null);
  const [whHost, setWhHost] = useState("db");
  const [whPort, setWhPort] = useState("5432");
  const [whDatabase, setWhDatabase] = useState("opsmind");
  const [whUser, setWhUser] = useState("opsmind_readonly");
  const [whPassword, setWhPassword] = useState("");
  const [whSchema, setWhSchema] = useState("public");
  const [whBusy, setWhBusy] = useState(false);
  const [whNotice, setWhNotice] = useState<string | null>(null);
  const [freshCode, setFreshCode] = useState<string | null>(null);
  const [freshApiKey, setFreshApiKey] = useState<string | null>(null);
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [creatingKey, setCreatingKey] = useState(false);
  const [savingCompany, setSavingCompany] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [csvUploading, setCsvUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const csvRef = useRef<HTMLInputElement>(null);

  const isAdmin = user?.role === "admin";

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const me = await api.me();
      setUser(me.user);
      setStoredUser(me.user);
      setCompanyName(me.user.tenant.name);
      const [pb, status, jobList, wh] = await Promise.all([
        api.listPlaybooks(),
        api.dataReady(),
        api.listIngestJobs(),
        api.getWarehouse(),
      ]);
      setPlaybooks(pb.playbooks || []);
      setReady(status);
      setJobs(jobList.jobs || []);
      setWarehouse(wh.connection);
      if (wh.connection) {
        setWhHost(wh.connection.host);
        setWhPort(String(wh.connection.port));
        setWhDatabase(wh.connection.database);
        setWhUser(wh.connection.username);
        setWhSchema(wh.connection.schema_name);
      }
      if (me.user.role === "admin") {
        const [inv, keys] = await Promise.all([api.listInvites(), api.listApiKeys()]);
        setInvites(inv.invites || []);
        setApiKeys(keys.api_keys || []);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
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

  const createKey = async () => {
    setCreatingKey(true);
    setError(null);
    setFreshApiKey(null);
    try {
      const res = await api.createApiKey({ name: "console" });
      setFreshApiKey(res.api_key.key);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create API key");
    } finally {
      setCreatingKey(false);
    }
  };

  const revokeKey = async (id: string) => {
    setError(null);
    try {
      await api.revokeApiKey(id);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to revoke API key");
    }
  };

  const copyApiKey = async () => {
    if (!freshApiKey) return;
    await navigator.clipboard.writeText(freshApiKey);
  };

  const saveWarehouse = async () => {
    setWhBusy(true);
    setError(null);
    setWhNotice(null);
    try {
      await api.saveWarehouse({
        host: whHost.trim(),
        port: Number(whPort) || 5432,
        database: whDatabase.trim(),
        username: whUser.trim(),
        password: whPassword,
        schema_name: whSchema.trim() || "public",
      });
      setWhPassword("");
      setWhNotice("Warehouse connection verified and saved.");
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save warehouse");
    } finally {
      setWhBusy(false);
    }
  };

  const testWarehouse = async () => {
    setWhBusy(true);
    setError(null);
    setWhNotice(null);
    try {
      const res = await api.testWarehouse({
        host: whHost.trim(),
        port: Number(whPort) || 5432,
        database: whDatabase.trim(),
        username: whUser.trim(),
        password: whPassword,
        schema_name: whSchema.trim() || "public",
      });
      if (!res.ok) {
        setError(res.error || `Missing tables: ${(res.missing_tables || []).join(", ")}`);
      } else {
        setWhNotice("Connection OK — allowlisted tables found.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Warehouse test failed");
    } finally {
      setWhBusy(false);
    }
  };

  const removeWarehouse = async () => {
    setWhBusy(true);
    setError(null);
    try {
      await api.deleteWarehouse();
      setWarehouse(null);
      setWhPassword("");
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete warehouse");
    } finally {
      setWhBusy(false);
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

  return (
    <div className="space-y-5 animate-fadeIn">
      <PageHeader
        icon={<Settings2 className="w-5 h-5" />}
        title="Settings"
        description="Company data, playbooks, and invite codes for teammates."
      />

      {error ? (
        <div className="text-xs text-rose-300 bg-rose-950/50 border border-rose-800/60 rounded-xl px-3 py-2">
          {error}
        </div>
      ) : null}
      {whNotice ? (
        <div className="text-xs text-emerald-300 bg-emerald-950/40 border border-emerald-800/50 rounded-xl px-3 py-2">
          {whNotice}
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
                Upload a ZIP with products.csv, orders.csv, and order_items.csv. Investigations
                stay locked until this tenant has its own data.
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
                {ready?.warehouse_ready ? " · warehouse verified" : ""}
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
                          <Badge variant="success" size="xs">
                            done
                          </Badge>
                        ) : job.status === "failed" ? (
                          <Badge variant="error" size="xs">
                            failed
                          </Badge>
                        ) : (
                          <Badge variant="default" size="xs">
                            {job.status}
                          </Badge>
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

      {isAdmin ? (
        <section className="app-section">
          <div className="app-section-header">
            <div>
              <h3 className="font-app-heading text-base text-white">Warehouse connector</h3>
              <p className="text-xs text-surface-400 mt-1">
                Read-only Postgres with the OpsMind ecommerce schema. Password is never shown
                again after save.
              </p>
            </div>
          </div>
          <div className="app-section-body space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {warehouse?.status === "verified" ? (
                <Badge variant="success" size="xs">
                  verified
                </Badge>
              ) : warehouse?.status === "failed" ? (
                <Badge variant="error" size="xs">
                  failed
                </Badge>
              ) : warehouse ? (
                <Badge variant="default" size="xs">
                  {warehouse.status}
                </Badge>
              ) : (
                <Badge variant="default" size="xs">
                  not configured
                </Badge>
              )}
              {warehouse?.last_error ? (
                <span className="text-xs text-rose-300">{warehouse.last_error}</span>
              ) : null}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <label className="text-xs text-surface-400">
                Host
                <input
                  className="mt-1 w-full rounded-xl border border-surface-700 bg-surface-950/60 px-3 py-2 text-sm text-surface-100"
                  value={whHost}
                  onChange={(e) => setWhHost(e.target.value)}
                />
              </label>
              <label className="text-xs text-surface-400">
                Port
                <input
                  className="mt-1 w-full rounded-xl border border-surface-700 bg-surface-950/60 px-3 py-2 text-sm text-surface-100"
                  value={whPort}
                  onChange={(e) => setWhPort(e.target.value)}
                />
              </label>
              <label className="text-xs text-surface-400">
                Database
                <input
                  className="mt-1 w-full rounded-xl border border-surface-700 bg-surface-950/60 px-3 py-2 text-sm text-surface-100"
                  value={whDatabase}
                  onChange={(e) => setWhDatabase(e.target.value)}
                />
              </label>
              <label className="text-xs text-surface-400">
                Schema
                <input
                  className="mt-1 w-full rounded-xl border border-surface-700 bg-surface-950/60 px-3 py-2 text-sm text-surface-100"
                  value={whSchema}
                  onChange={(e) => setWhSchema(e.target.value)}
                />
              </label>
              <label className="text-xs text-surface-400">
                Username
                <input
                  className="mt-1 w-full rounded-xl border border-surface-700 bg-surface-950/60 px-3 py-2 text-sm text-surface-100"
                  value={whUser}
                  onChange={(e) => setWhUser(e.target.value)}
                />
              </label>
              <label className="text-xs text-surface-400">
                Password
                <input
                  type="password"
                  className="mt-1 w-full rounded-xl border border-surface-700 bg-surface-950/60 px-3 py-2 text-sm text-surface-100"
                  value={whPassword}
                  onChange={(e) => setWhPassword(e.target.value)}
                  placeholder={warehouse ? "••••••••" : ""}
                />
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                size="sm"
                loading={whBusy}
                onClick={() => void testWarehouse()}
              >
                Test connection
              </Button>
              <Button
                variant="accent"
                size="sm"
                loading={whBusy}
                onClick={() => void saveWarehouse()}
              >
                Save & verify
              </Button>
              {warehouse ? (
                <Button
                  variant="ghost"
                  size="sm"
                  loading={whBusy}
                  onClick={() => void removeWarehouse()}
                >
                  Disconnect
                </Button>
              ) : null}
            </div>
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
              <h3 className="font-app-heading text-base text-white">API keys</h3>
              <p className="text-xs text-surface-400 mt-1">
                Per-tenant keys for scripts and integrations. Prefer JWT for the web console.
              </p>
            </div>
            <Button
              variant="accent"
              size="sm"
              icon={<KeyRound className="w-3.5 h-3.5" />}
              loading={creatingKey}
              onClick={() => void createKey()}
            >
              Create API key
            </Button>
          </div>
          <div className="app-section-body space-y-3">
            {freshApiKey ? (
              <div className="rounded-xl border border-accent-700/40 bg-accent-950/30 px-3 py-3 flex flex-col sm:flex-row sm:items-center gap-2 justify-between">
                <div className="min-w-0">
                  <p className="text-xs text-accent-300 mb-1">Copy now — shown once</p>
                  <code className="font-mono text-xs sm:text-sm text-white break-all">
                    {freshApiKey}
                  </code>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<Copy className="w-3.5 h-3.5" />}
                  onClick={() => void copyApiKey()}
                >
                  Copy
                </Button>
              </div>
            ) : null}

            {apiKeys.length === 0 ? (
              <p className="app-empty text-sm">No API keys yet.</p>
            ) : (
              <ul className="space-y-2">
                {apiKeys.map((k) => (
                  <li
                    key={k.id}
                    className="app-list-card flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm text-surface-100">{k.name}</span>
                        <code className="font-mono text-xs text-surface-400">{k.key_prefix}</code>
                        {k.active ? (
                          <Badge variant="success" size="xs">
                            active
                          </Badge>
                        ) : (
                          <Badge variant="error" size="xs">
                            revoked
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-surface-400 mt-1">
                        {k.created_at ? new Date(k.created_at).toLocaleString() : ""}
                      </p>
                    </div>
                    {k.revoked_at == null ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Trash2 className="w-3.5 h-3.5" />}
                        onClick={() => void revokeKey(k.id)}
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

      {isAdmin ? (
        <section className="app-section">
          <div className="app-section-header flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="font-app-heading text-base text-white">Invite codes</h3>
              <p className="text-xs text-surface-400 mt-1">
                Investigators redeem a code to join this tenant only.
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
                          <Badge variant="success" size="xs">
                            active
                          </Badge>
                        ) : (
                          <Badge variant="error" size="xs">
                            inactive
                          </Badge>
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
    </div>
  );
}
