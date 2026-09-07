import { useState } from "react";
import { Modal } from "../common/Modal";
import { Button } from "../common/Button";
import { getApiKey, setApiKey, api, DEMO_BOOTSTRAP_API_KEY } from "../../lib/api";
import { Key, CheckCircle2, AlertCircle } from "lucide-react";

interface ApiKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved?: () => void;
}

export function ApiKeyModal({ isOpen, onClose, onSaved }: ApiKeyModalProps) {
  const [keyInput, setKeyInput] = useState(getApiKey());
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const handleSave = () => {
    setApiKey(keyInput);
    onSaved?.();
    onClose();
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      setApiKey(keyInput);
      const res = await api.getSqlTemplates();
      setTestResult({
        success: true,
        message: `Authenticated successfully! Found ${res.templates?.length || 0} allowlisted SQL templates.`,
      });
    } catch (err: any) {
      setTestResult({
        success: false,
        message: err.message || "Failed to authenticate with API key.",
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <Key className="w-5 h-5 text-brand-400" />
          <span>OpsMind API Authentication (P5)</span>
        </div>
      }
      subtitle="Optional: paste a company API key for Tools / scripts. Console access still requires email login."
      maxWidth="md"
    >
      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-surface-300 mb-1.5">
            Company API key
          </label>
          <input
            type="password"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            placeholder={`e.g. omk_… or ${DEMO_BOOTSTRAP_API_KEY}`}
            className="w-full px-3 py-2 bg-surface-950 border border-surface-700 rounded-lg text-sm text-surface-100 placeholder:text-surface-600 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 font-mono"
          />
          <p className="text-xs text-surface-400 mt-1.5">
            Sign in with email for your company investigations. Pasting the demo key{" "}
            <code className="text-brand-300">{DEMO_BOOTSTRAP_API_KEY}</code> alone
            will not open Console/History — and the demo tenant may have no CSV data
            (you will see “upload company data”).
          </p>
        </div>

        {testResult && (
          <div
            className={`p-3 rounded-lg border text-xs flex items-start gap-2 ${
              testResult.success
                ? "bg-emerald-950/40 border-emerald-800 text-emerald-300"
                : "bg-rose-950/40 border-rose-800 text-rose-300"
            }`}
          >
            {testResult.success ? (
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400 mt-0.5" />
            ) : (
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
            )}
            <div>{testResult.message}</div>
          </div>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-surface-800">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            loading={testing}
            onClick={handleTestConnection}
          >
            Test Auth
          </Button>
          <div className="flex items-center gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="button" variant="primary" size="sm" onClick={handleSave}>
              Save Key
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
