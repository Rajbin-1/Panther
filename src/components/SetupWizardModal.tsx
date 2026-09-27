import React, { useState, useEffect } from 'react';
import { SetupStatus } from '../types/agent';
import { api } from '../services/api';
import { CheckCircle2, AlertTriangle, XCircle, RefreshCw, X, ShieldCheck } from 'lucide-react';

interface SetupWizardModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SetupWizardModal: React.FC<SetupWizardModalProps> = ({ isOpen, onClose }) => {
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchStatus = async () => {
    try {
      const data = await api.getSetupStatus();
      setSetup(data);
    } catch {
      // ignore
    }
  };

  const runDiagnostics = async () => {
    setLoading(true);
    try {
      const data = await api.runSetupChecks();
      setSetup(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStatus();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
      <div className="bg-zinc-900 border border-zinc-700 rounded-lg max-w-xl w-full p-6 space-y-6 shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <h3 className="text-base font-semibold text-zinc-100">
              System Pre-Flight Diagnostics
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-xs text-zinc-400">
          Panther Agent runs hardware and sandbox verification against the 6 GB RAM Windows target specification.
        </p>

        {/* Check Items List */}
        <div className="space-y-3">
          {setup?.checks &&
            Object.entries(setup.checks).map(([key, check]) => {
              const label = key
                .split('_')
                .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                .join(' ');

              return (
                <div
                  key={key}
                  className="p-3 bg-zinc-950 border border-zinc-800 rounded flex items-start justify-between text-xs"
                >
                  <div className="space-y-0.5">
                    <div className="font-semibold text-zinc-200">{label}</div>
                    <div className="text-zinc-400">{check.details}</div>
                  </div>
                  <div className="shrink-0 font-mono font-medium ml-3">
                    {check.status === 'PASS' && (
                      <span className="text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="w-4 h-4" /> PASS
                      </span>
                    )}
                    {check.status === 'INFO' && (
                      <span className="text-sky-400 flex items-center gap-1">
                        <CheckCircle2 className="w-4 h-4" /> READY
                      </span>
                    )}
                    {check.status === 'WARNING' && (
                      <span className="text-amber-400 flex items-center gap-1">
                        <AlertTriangle className="w-4 h-4" /> WARNING
                      </span>
                    )}
                    {check.status === 'FAIL' && (
                      <span className="text-rose-400 flex items-center gap-1">
                        <XCircle className="w-4 h-4" /> FAIL
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-zinc-800">
          <button
            onClick={runDiagnostics}
            disabled={loading}
            className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded border border-zinc-700 text-xs font-medium flex items-center gap-1.5 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>{loading ? 'Testing...' : 'Re-run Pre-flight Checks'}</span>
          </button>

          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-zinc-100 hover:bg-zinc-200 text-zinc-900 rounded text-xs font-semibold transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
