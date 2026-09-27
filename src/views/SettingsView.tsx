import React, { useState, useEffect } from 'react';
import { DiagnosticLog } from '../types/agent';
import { api } from '../services/api';
import { Sliders, Shield, AlertTriangle, RefreshCw, RotateCcw, Check } from 'lucide-react';

interface SettingsViewProps {
  onOpenSetup?: () => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({ onOpenSetup }) => {
  const [config, setConfig] = useState<Record<string, any> | null>(null);
  const [logs, setLogs] = useState<DiagnosticLog[]>([]);
  const [logFilter, setLogFilter] = useState<string>('ALL');
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Form states for sections
  const [minRamMb, setMinRamMb] = useState(1024);
  const [maxCpuPercent, setMaxCpuPercent] = useState(85.0);
  const [ocrConfidence, setOcrConfidence] = useState(0.65);
  const [actionDelayMs, setActionDelayMs] = useState(350);
  const [maxContextTokens, setMaxContextTokens] = useState(2048);

  const fetchConfigAndLogs = async () => {
    try {
      const cfg = await api.getConfig();
      setConfig(cfg);
      if (cfg.resource_limits) {
        setMinRamMb(cfg.resource_limits.min_available_ram_mb ?? 1024);
        setMaxCpuPercent(cfg.resource_limits.max_cpu_percent_sustained ?? 85.0);
      }
      if (cfg.ocr) {
        setOcrConfidence(cfg.ocr.confidence_threshold ?? 0.65);
      }
      if (cfg.action_limits) {
        setActionDelayMs(cfg.action_limits.min_delay_between_actions_ms ?? 350);
      }
      if (cfg.model) {
        setMaxContextTokens(cfg.model.max_context_tokens ?? 2048);
      }

      const logData = await api.getDiagnostics(60);
      setLogs(logData.logs);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    fetchConfigAndLogs();
  }, []);

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(false);
    try {
      await api.updateConfig('resource_limits', {
        min_available_ram_mb: Number(minRamMb),
        max_cpu_percent_sustained: Number(maxCpuPercent),
      });
      await api.updateConfig('ocr', {
        confidence_threshold: Number(ocrConfidence),
      });
      await api.updateConfig('action_limits', {
        min_delay_between_actions_ms: Number(actionDelayMs),
      });
      await api.updateConfig('model', {
        max_context_tokens: Number(maxContextTokens),
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      fetchConfigAndLogs();
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (confirm('Reset all parameters to factory low-resource defaults?')) {
      await api.resetConfig();
      fetchConfigAndLogs();
    }
  };

  const filteredLogs = logFilter === 'ALL' ? logs : logs.filter((l) => l.level === logFilter);

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">System Settings & Governance</h2>
          <p className="text-sm text-zinc-400">
            Persistent hardware governor thresholds, safety gates, and diagnostic logs.
          </p>
        </div>
        <div className="flex gap-2">
          {onOpenSetup && (
            <button
              onClick={onOpenSetup}
              className="px-3 py-1.5 bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 rounded border border-amber-500/40 text-xs font-medium flex items-center gap-1.5 transition"
            >
              <Sliders className="w-3.5 h-3.5" />
              <span>Setup & Hardware Discovery</span>
            </button>
          )}
          <button
            onClick={handleReset}
            className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded border border-zinc-700 text-xs font-medium flex items-center gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Reset Defaults</span>
          </button>
        </div>
      </div>

      {/* Configuration Form */}
      <form onSubmit={handleSaveConfig} className="bg-zinc-900 border border-zinc-800 rounded p-6 space-y-6">
        <h3 className="text-sm font-semibold text-zinc-200 border-b border-zinc-800 pb-2">
          Resource Governor & Safety Parameters
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-xs">
          {/* Resource Thresholds */}
          <div className="space-y-4">
            <h4 className="font-medium text-zinc-400 uppercase tracking-wide">Resource Governor (6 GB RAM Target)</h4>
            <div>
              <label className="block text-zinc-300 mb-1">
                Min Available RAM Warning Threshold (MB)
              </label>
              <input
                type="number"
                value={minRamMb}
                onChange={(e) => setMinRamMb(Number(e.target.value))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-zinc-100 font-mono focus:outline-none"
              />
              <span className="text-[11px] text-zinc-500">Agent throttles when free system RAM drops below this limit.</span>
            </div>

            <div>
              <label className="block text-zinc-300 mb-1">
                Max CPU Sustained Limit (%)
              </label>
              <input
                type="number"
                value={maxCpuPercent}
                onChange={(e) => setMaxCpuPercent(Number(e.target.value))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-zinc-100 font-mono focus:outline-none"
              />
              <span className="text-[11px] text-zinc-500">Dual-core load ceiling before task pacing is delayed.</span>
            </div>
          </div>

          {/* Execution & OCR Limits */}
          <div className="space-y-4">
            <h4 className="font-medium text-zinc-400 uppercase tracking-wide">Action & Context Boundaries</h4>
            <div>
              <label className="block text-zinc-300 mb-1">
                Min Delay Between Actions (ms)
              </label>
              <input
                type="number"
                value={actionDelayMs}
                onChange={(e) => setActionDelayMs(Number(e.target.value))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-zinc-100 font-mono focus:outline-none"
              />
              <span className="text-[11px] text-zinc-500">Human-speed pacing to prevent input flooding.</span>
            </div>

            <div>
              <label className="block text-zinc-300 mb-1">
                Max Model Context Window (Tokens)
              </label>
              <input
                type="number"
                value={maxContextTokens}
                onChange={(e) => setMaxContextTokens(Number(e.target.value))}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-zinc-100 font-mono focus:outline-none"
              />
              <span className="text-[11px] text-zinc-500">Constrained to 2048 to prevent memory blowout on 6GB PCs.</span>
            </div>
          </div>
        </div>

        {/* Action Boundary Whitelist Information */}
        <div className="p-4 bg-zinc-950 border border-zinc-850 rounded text-xs space-y-2">
          <div className="flex items-center gap-2 font-medium text-zinc-300">
            <Shield className="w-4 h-4 text-emerald-400" />
            <span>Strict Security & Action Boundary Policy</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-zinc-400 font-mono text-[11px]">
            <div>• Arbitrary Shell Execution: <span className="text-rose-400">Disabled</span></div>
            <div>• Binary Launching: <span className="text-rose-400">Disabled</span></div>
            <div>• Filesystem Modification: <span className="text-rose-400">Disabled</span></div>
            <div>• Prohibited Keys Filter: <span className="text-emerald-400">Active</span></div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2">
          {saveSuccess ? (
            <span className="text-xs text-emerald-400 flex items-center gap-1.5">
              <Check className="w-4 h-4" />
              <span>Configuration saved and persisted to SQLite.</span>
            </span>
          ) : (
            <span />
          )}
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-zinc-100 text-zinc-900 hover:bg-zinc-200 text-xs font-semibold rounded disabled:opacity-50 transition"
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </form>

      {/* Diagnostics Logs Viewer */}
      <div className="bg-zinc-900 border border-zinc-800 rounded p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">Diagnostics & Structured Logs</h3>
            <p className="text-xs text-zinc-500">Direct query of SQLite diagnostics_logs table.</p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={logFilter}
              onChange={(e) => setLogFilter(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 text-zinc-300 rounded px-2.5 py-1 text-xs font-mono focus:outline-none"
            >
              <option value="ALL">All Levels</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
            </select>
            <button
              onClick={fetchConfigAndLogs}
              className="px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded border border-zinc-700 text-xs flex items-center gap-1"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        <div className="divide-y divide-zinc-800 max-h-64 overflow-y-auto font-mono text-[11px] bg-zinc-950 rounded border border-zinc-850 p-2">
          {filteredLogs.length === 0 ? (
            <div className="py-6 text-center text-zinc-600">No logs for selected level.</div>
          ) : (
            filteredLogs.map((log) => (
              <div key={log.id} className="py-1.5 px-2 flex items-start gap-2.5">
                <span className="text-zinc-600 shrink-0">
                  {new Date(log.created_at).toLocaleTimeString()}
                </span>
                <span
                  className={`font-semibold shrink-0 ${
                    log.level === 'ERROR'
                      ? 'text-rose-400'
                      : log.level === 'WARNING'
                      ? 'text-amber-400'
                      : 'text-zinc-400'
                  }`}
                >
                  [{log.level}]
                </span>
                <span className="text-zinc-500 shrink-0">[{log.component}]</span>
                <span className="text-zinc-300 break-all">{log.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
