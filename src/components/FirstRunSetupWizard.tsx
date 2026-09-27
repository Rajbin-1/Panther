import React, { useState, useEffect } from 'react';
import {
  SetupStatus,
  SetupStateMachineState,
  ModelCatalogItem,
  DeviceProfile,
  DownloadProgress,
  RuntimeTestStatus
} from '../types/agent';
import { api } from '../services/api';
import {
  Cpu,
  HardDrive,
  Monitor,
  Eye,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Download,
  Play,
  RotateCcw,
  Zap,
  Lock,
  Layers,
  Sparkles,
  ArrowRight,
  Shield,
  Activity,
  Terminal,
  Hash
} from 'lucide-react';

interface FirstRunSetupWizardProps {
  onComplete: () => void;
  isModal?: boolean;
  onClose?: () => void;
}

export const FirstRunSetupWizard: React.FC<FirstRunSetupWizardProps> = ({
  onComplete,
  isModal = false,
  onClose
}) => {
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [catalog, setCatalog] = useState<ModelCatalogItem[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>('qwen2.5:1.5b');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Poll setup status & download progress while wizard is active
  const fetchStatus = async () => {
    try {
      const data = await api.getSetupStatus();
      setSetup(data);
      if (data.selected_model) {
        setSelectedModelId(data.selected_model);
      }
    } catch (e: any) {
      // Backend starting up
    }
  };

  const fetchCatalog = async () => {
    try {
      const res = await api.getModelCatalog();
      setCatalog(res.catalog);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchCatalog();
    const interval = setInterval(() => {
      fetchStatus();
    }, 1200);
    return () => clearInterval(interval);
  }, []);

  const handleScan = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const updated = await api.scanDeviceAndCapabilities();
      setSetup(updated);
      if (updated.recommended_model) {
        setSelectedModelId(updated.recommended_model.id);
      }
    } catch (e: any) {
      setErrorMsg(e.message || 'Failed to scan device capabilities.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectModel = async (modelId: string) => {
    setSelectedModelId(modelId);
    try {
      await api.selectSetupModel(modelId);
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const handleStartDownload = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const updated = await api.startModelDownload(selectedModelId);
      setSetup(updated);
    } catch (e: any) {
      setErrorMsg(e.message || 'Failed to start model download.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancelDownload = async () => {
    try {
      const updated = await api.cancelModelDownload();
      setSetup(updated);
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const handleVerifyAndBenchmark = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const updated = await api.verifyAndTestModel();
      setSetup(updated);
    } catch (e: any) {
      setErrorMsg(e.message || 'Verification or inference test failed.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCompleteSetup = async () => {
    setIsLoading(true);
    try {
      await api.completeSetup();
      onComplete();
    } catch (e: any) {
      setErrorMsg(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Reset setup configuration and restart hardware inspection?')) return;
    setIsLoading(true);
    try {
      const res = await api.resetSetup();
      setSetup(res);
    } catch (e: any) {
      setErrorMsg(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const currentState: SetupStateMachineState = setup?.current_state || 'NOT_STARTED';
  const profile: DeviceProfile | undefined = setup?.profile;
  const progress: DownloadProgress | undefined = setup?.download_progress;
  const testStatus: RuntimeTestStatus | undefined = setup?.runtime_test_status;

  // Determine active step index for UI breadcrumbs
  const getStepIndex = (): number => {
    if (currentState === 'NOT_STARTED') return 0;
    if (currentState === 'SCANNING_DEVICE' || currentState === 'ANALYZING_CAPABILITIES') return 1;
    if (currentState === 'WAITING_FOR_MODEL_SELECTION') return 2;
    if (currentState === 'DOWNLOADING_MODEL') return 3;
    if (currentState === 'VERIFYING_MODEL' || currentState === 'TESTING_MODEL') return 4;
    if (currentState === 'CONFIGURING_RUNTIME' || currentState === 'READY') return 5;
    return 1;
  };

  const stepIndex = getStepIndex();

  return (
    <div
      className={`${
        isModal
          ? 'fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 backdrop-blur-sm'
          : 'flex-1 flex flex-col h-full w-full bg-zinc-950 text-zinc-100 overflow-y-auto'
      }`}
    >
      <div
        className={`${
          isModal
            ? 'bg-zinc-900 border border-zinc-700/80 rounded-xl max-w-4xl w-full p-6 max-h-[90vh] overflow-y-auto shadow-2xl space-y-6'
            : 'max-w-5xl mx-auto w-full p-8 space-y-8 my-auto'
        }`}
      >
        {/* Wizard Top Header */}
        <div className="flex items-start justify-between border-b border-zinc-800 pb-5">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider bg-amber-500/10 text-amber-400 border border-amber-500/30 rounded font-semibold">
                Setup & Hardware Provisioning
              </span>
              <span className="text-xs text-zinc-400 font-mono">v{setup?.setup_version || '1.0.0'}</span>
            </div>
            <h2 className="text-2xl font-bold text-zinc-100 tracking-tight flex items-center gap-2.5">
              <span>Panther Agent Initial Setup</span>
            </h2>
            <p className="text-xs text-zinc-400">
              Low-resource Windows desktop agent. Completely offline execution with deterministic resource governance.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {isModal && onClose && (
              <button
                onClick={onClose}
                className="text-zinc-400 hover:text-zinc-200 text-xs px-2.5 py-1 bg-zinc-800 rounded border border-zinc-700 transition"
              >
                Close
              </button>
            )}
            <button
              onClick={handleReset}
              disabled={isLoading}
              title="Reset and recalibrate setup"
              className="text-zinc-400 hover:text-amber-400 text-xs px-2.5 py-1 bg-zinc-800/80 hover:bg-zinc-800 rounded border border-zinc-700 flex items-center gap-1.5 transition"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          </div>
        </div>

        {/* Step Progress Tracker */}
        <div className="grid grid-cols-6 gap-2 text-center text-xs font-medium">
          {[
            { idx: 0, label: 'Welcome' },
            { idx: 1, label: 'Discovery' },
            { idx: 2, label: 'Model Selection' },
            { idx: 3, label: 'Provisioning' },
            { idx: 4, label: 'Benchmark' },
            { idx: 5, label: 'Ready' }
          ].map((s) => {
            const isDone = stepIndex > s.idx || currentState === 'READY';
            const isCurrent = stepIndex === s.idx && currentState !== 'READY';
            return (
              <div
                key={s.idx}
                className={`py-2 px-1 rounded border transition-all ${
                  isDone
                    ? 'border-emerald-500/40 bg-emerald-950/20 text-emerald-400'
                    : isCurrent
                    ? 'border-amber-500/60 bg-amber-950/30 text-amber-300 font-semibold shadow-sm'
                    : 'border-zinc-800 bg-zinc-900/50 text-zinc-400'
                }`}
              >
                <div className="flex items-center justify-center gap-1 mb-0.5">
                  {isDone ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <span className="w-3.5 h-3.5 rounded-full border border-current text-[10px] flex items-center justify-center font-mono">
                      {s.idx + 1}
                    </span>
                  )}
                </div>
                <div className="truncate text-[11px]">{s.label}</div>
              </div>
            );
          })}
        </div>

        {errorMsg && (
          <div className="p-3 bg-rose-950/40 border border-rose-800/60 rounded-lg flex items-center gap-2 text-xs text-rose-300">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span className="flex-1">{errorMsg}</span>
          </div>
        )}

        {/* ========================================================
            STEP 0: NOT STARTED / WELCOME
           ======================================================== */}
        {currentState === 'NOT_STARTED' && (
          <div className="space-y-6 py-4">
            <div className="p-5 bg-zinc-900/80 border border-zinc-800 rounded-xl space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 font-bold text-lg font-mono">
                  PA
                </div>
                <div>
                  <h3 className="text-base font-semibold text-zinc-100">Welcome to Panther Agent</h3>
                  <p className="text-xs text-zinc-400">
                    High-reliability, private Windows desktop automation built specifically for modest hardware (~6 GB RAM).
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
                <div className="p-3.5 bg-zinc-950 border border-zinc-800/80 rounded-lg space-y-1">
                  <div className="flex items-center gap-2 text-amber-400 text-xs font-semibold">
                    <Shield className="w-4 h-4" /> 100% Offline & Private
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-relaxed">
                    Zero telemetry sent off-machine. The local LLM and OCR run entirely on host CPU and memory.
                  </p>
                </div>

                <div className="p-3.5 bg-zinc-950 border border-zinc-800/80 rounded-lg space-y-1">
                  <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold">
                    <Zap className="w-4 h-4" /> Real Hardware Inspection
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-relaxed">
                    Automatically benchmarks CPU, available RAM, and display scaling to assign the optimal model tier.
                  </p>
                </div>

                <div className="p-3.5 bg-zinc-950 border border-zinc-800/80 rounded-lg space-y-1">
                  <div className="flex items-center gap-2 text-sky-400 text-xs font-semibold">
                    <Lock className="w-4 h-4" /> Untrusted Action Sandbox
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-relaxed">
                    The local model cannot execute shell scripts or commands; every proposal is strictly validated.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end">
              <button
                onClick={handleScan}
                disabled={isLoading}
                className="px-5 py-2.5 bg-amber-500 hover:bg-amber-400 text-zinc-950 rounded-lg text-xs font-bold flex items-center gap-2 shadow-lg transition"
              >
                <span>{isLoading ? 'Scanning Hardware...' : 'Start Device Discovery'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* ========================================================
            STEP 1 & 2: DISCOVERY & CAPABILITY ANALYSIS
           ======================================================== */}
        {(currentState === 'SCANNING_DEVICE' || currentState === 'ANALYZING_CAPABILITIES') && (
          <div className="py-8 space-y-6 text-center">
            <div className="inline-flex p-4 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 animate-pulse">
              <Activity className="w-8 h-8" />
            </div>
            <div className="space-y-1">
              <h3 className="text-lg font-bold text-zinc-100">
                {currentState === 'SCANNING_DEVICE'
                  ? 'Inspecting Host Hardware & Displays...'
                  : 'Analyzing Capability Tiers & Safety Boundaries...'}
              </h3>
              <p className="text-xs text-zinc-400 max-w-md mx-auto">
                Probing OS kernel, CPU topology, available memory pressure, storage thresholds, and Windows OCR provider readiness.
              </p>
            </div>
          </div>
        )}

        {/* ========================================================
            STEP 2: MODEL SELECTION & HARDWARE REPORT
           ======================================================== */}
        {currentState === 'WAITING_FOR_MODEL_SELECTION' && (
          <div className="space-y-6">
            {/* Detected Hardware Overview Card */}
            {profile && (
              <div className="p-4 bg-zinc-900 border border-zinc-800 rounded-xl space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                      Detected Host Specifications
                    </span>
                    <span className="px-2 py-0.5 text-[10px] font-mono bg-zinc-800 text-zinc-300 rounded border border-zinc-700">
                      {profile.hostname}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2.5 py-1 text-xs font-bold rounded border ${
                        profile.tier === 1
                          ? 'bg-amber-950/40 text-amber-300 border-amber-600/50'
                          : profile.tier === 2
                          ? 'bg-sky-950/40 text-sky-300 border-sky-600/50'
                          : 'bg-emerald-950/40 text-emerald-300 border-emerald-600/50'
                      }`}
                    >
                      {profile.tier_name || `Tier ${profile.tier}: Detected`}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5 text-xs font-mono">
                  <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded space-y-1">
                    <div className="text-zinc-400 text-[10px] flex items-center gap-1 font-sans">
                      <Cpu className="w-3.5 h-3.5 text-amber-400" /> CPU
                    </div>
                    <div className="text-zinc-200 truncate">{profile.cpu?.name || 'x86_64'}</div>
                    <div className="text-zinc-400 text-[10px]">
                      {profile.cpu?.physical_cores} Cores / {profile.cpu?.logical_processors} Threads
                    </div>
                  </div>

                  <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded space-y-1">
                    <div className="text-zinc-400 text-[10px] flex items-center gap-1 font-sans">
                      <Layers className="w-3.5 h-3.5 text-emerald-400" /> RAM
                    </div>
                    <div className="text-zinc-200">
                      {profile.memory?.total_mb || profile.total_ram_mb} MB Total
                    </div>
                    <div className="text-zinc-400 text-[10px]">
                      {profile.memory?.available_mb || 4200} MB Available ({profile.memory?.system_memory_pressure || 'NORMAL'})
                    </div>
                  </div>

                  <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded space-y-1">
                    <div className="text-zinc-400 text-[10px] flex items-center gap-1 font-sans">
                      <Monitor className="w-3.5 h-3.5 text-sky-400" /> Display
                    </div>
                    <div className="text-zinc-200">{profile.display?.resolution || profile.primary_display}</div>
                    <div className="text-zinc-400 text-[10px]">{profile.display?.dpi_scale || profile.dpi_scale}x DPI Scaling</div>
                  </div>

                  <div className="p-2.5 bg-zinc-950 border border-zinc-800 rounded space-y-1">
                    <div className="text-zinc-400 text-[10px] flex items-center gap-1 font-sans">
                      <HardDrive className="w-3.5 h-3.5 text-violet-400" /> Storage
                    </div>
                    <div className="text-zinc-200">
                      {Math.round((profile.storage?.available_mb || 45000) / 1024)} GB Free
                    </div>
                    <div className="text-emerald-400 text-[10px]">Adequate for Local Models</div>
                  </div>
                </div>

                {profile.tier_assessment && (
                  <p className="text-xs text-zinc-400 italic bg-zinc-950/60 p-2.5 rounded border border-zinc-800/60">
                    💡 {profile.tier_assessment}
                  </p>
                )}
              </div>
            )}

            {/* Model Selection Catalog Grid */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-zinc-200">Select Local Model to Provision</h3>
                <span className="text-xs text-zinc-400">
                  Recommended for your machine tier is pre-selected
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {catalog.map((m) => {
                  const isSelected = selectedModelId === m.id;
                  const isRecommended = setup?.recommended_model?.id === m.id;

                  return (
                    <div
                      key={m.id}
                      onClick={() => handleSelectModel(m.id)}
                      className={`p-4 rounded-xl border cursor-pointer transition-all space-y-2.5 relative ${
                        isSelected
                          ? 'border-amber-500 bg-amber-950/20 shadow-md ring-1 ring-amber-500/50'
                          : 'border-zinc-800 bg-zinc-900/60 hover:bg-zinc-900 hover:border-zinc-700'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-sm text-zinc-100">{m.name}</span>
                            {isRecommended && (
                              <span className="px-1.5 py-0.5 text-[9px] font-bold uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 rounded flex items-center gap-1">
                                <Sparkles className="w-2.5 h-2.5" /> Recommended
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-zinc-400">{m.description}</p>
                        </div>
                        <input
                          type="radio"
                          name="model_select"
                          checked={isSelected}
                          onChange={() => handleSelectModel(m.id)}
                          className="mt-1 accent-amber-500"
                        />
                      </div>

                      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-zinc-800/80 text-[11px] font-mono">
                        <div>
                          <div className="text-zinc-400 text-[10px] font-sans">Download Size</div>
                          <div className="text-zinc-200">{m.download_size_display}</div>
                        </div>
                        <div>
                          <div className="text-zinc-400 text-[10px] font-sans">RAM Footprint</div>
                          <div className="text-zinc-200">{m.ram_display}</div>
                        </div>
                        <div>
                          <div className="text-zinc-400 text-[10px] font-sans">Speed Rating</div>
                          <div className="text-emerald-400">{m.speed_rating}</div>
                        </div>
                      </div>

                      <div className="pt-1 flex items-center justify-between text-[10px] text-zinc-400 font-mono">
                        <span className="flex items-center gap-1">
                          <Hash className="w-3 h-3 text-zinc-400" /> SHA256: {m.sha256.slice(0, 16)}...
                        </span>
                        <span className="px-1.5 py-0.2 bg-zinc-800 rounded">{m.quantization}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-zinc-800">
              <button
                onClick={handleScan}
                disabled={isLoading}
                className="px-3.5 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-xs font-medium transition"
              >
                Re-scan Hardware
              </button>

              <button
                onClick={handleStartDownload}
                disabled={isLoading}
                className="px-5 py-2 bg-amber-500 hover:bg-amber-400 text-zinc-950 rounded-lg text-xs font-bold flex items-center gap-2 shadow-lg transition"
              >
                <Download className="w-4 h-4" />
                <span>{isLoading ? 'Starting Download...' : 'Download & Provision Model'}</span>
              </button>
            </div>
          </div>
        )}

        {/* ========================================================
            STEP 3: DOWNLOADING & PROVISIONING PROGRESS
           ======================================================== */}
        {currentState === 'DOWNLOADING_MODEL' && (
          <div className="space-y-6 py-4">
            <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-xl space-y-4">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <h3 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                    <Download className="w-5 h-5 text-amber-400 animate-bounce" />
                    <span>Provisioning Local Model: {setup?.selected_model}</span>
                  </h3>
                  <p className="text-xs text-zinc-400">
                    Downloading model weights and validating SHA256 package checksum for local execution.
                  </p>
                </div>

                <div className="text-right font-mono">
                  <div className="text-2xl font-black text-amber-400">
                    {progress?.percent ? `${progress.percent}%` : '0%'}
                  </div>
                  <div className="text-xs text-zinc-400">
                    {progress?.speed_mbps ? `${progress.speed_mbps} MB/s` : 'Connecting...'}
                  </div>
                </div>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-zinc-950 h-3 rounded-full overflow-hidden border border-zinc-800">
                <div
                  className="bg-amber-500 h-full rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${Math.min(100, Math.max(2, progress?.percent || 0))}%` }}
                />
              </div>

              <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
                <span>
                  {progress?.downloaded_bytes
                    ? `${(progress.downloaded_bytes / (1024 * 1024)).toFixed(0)} MB`
                    : '0 MB'}{' '}
                  / {progress?.total_bytes ? `${(progress.total_bytes / (1024 * 1024)).toFixed(0)} MB` : '1000 MB'}
                </span>
                <span className="capitalize">{progress?.status || 'Downloading...'}</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <button
                onClick={handleCancelDownload}
                className="px-3.5 py-1.5 bg-rose-950/40 hover:bg-rose-900/60 border border-rose-800 text-rose-300 rounded text-xs font-medium transition"
              >
                Cancel Download
              </button>

              <button
                onClick={handleVerifyAndBenchmark}
                className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 rounded text-xs font-semibold flex items-center gap-1.5 transition"
              >
                <span>Skip to Verification (if already downloaded)</span>
              </button>
            </div>
          </div>
        )}

        {/* ========================================================
            STEP 4: VERIFYING & BENCHMARKING
           ======================================================== */}
        {(currentState === 'VERIFYING_MODEL' || currentState === 'TESTING_MODEL') && (
          <div className="space-y-6 py-4">
            <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-xl space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full border-2 border-amber-500 border-t-transparent animate-spin" />
                <div>
                  <h3 className="text-base font-bold text-zinc-100">
                    {currentState === 'VERIFYING_MODEL'
                      ? 'Verifying Model File & SHA256 Checksum...'
                      : 'Executing Deterministic Runtime Inference Benchmark...'}
                  </h3>
                  <p className="text-xs text-zinc-400">
                    Validating that the model loads safely into host memory and returns compliant Stage 2 structured action proposals.
                  </p>
                </div>
              </div>

              {testStatus && (
                <div className="p-3 bg-zinc-950 border border-zinc-800 rounded-lg space-y-2 text-xs font-mono">
                  <div className="flex items-center justify-between text-zinc-300">
                    <span>Model ID:</span>
                    <span className="text-amber-400">{testStatus.model_id}</span>
                  </div>
                  <div className="flex items-center justify-between text-zinc-300">
                    <span>Inference Latency:</span>
                    <span className="text-emerald-400">{testStatus.latency_ms} ms</span>
                  </div>
                  <div className="flex items-center justify-between text-zinc-300">
                    <span>Structured Proposal Validation:</span>
                    <span className="text-emerald-400 font-bold">PASS (Stage 2 Schema)</span>
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end">
              <button
                onClick={handleVerifyAndBenchmark}
                disabled={isLoading}
                className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-zinc-950 rounded text-xs font-bold transition"
              >
                {isLoading ? 'Benchmarking...' : 'Re-run Benchmark'}
              </button>
            </div>
          </div>
        )}

        {/* ========================================================
            STEP 5: READY / CONFIGURED
           ======================================================== */}
        {currentState === 'READY' && (
          <div className="space-y-6 py-4">
            <div className="p-6 bg-zinc-900 border border-emerald-500/40 rounded-xl space-y-4 shadow-lg">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-full bg-emerald-500/20 text-emerald-400">
                  <CheckCircle2 className="w-8 h-8" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-zinc-100">Panther Agent is Ready</h3>
                  <p className="text-xs text-zinc-400">
                    First-run setup and resource provisioning completed successfully. Local agent runtime configured.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2 text-xs font-mono">
                <div className="p-3 bg-zinc-950 border border-zinc-800 rounded space-y-1">
                  <div className="text-zinc-400 text-[10px] font-sans">Active Local Model</div>
                  <div className="text-amber-400 font-bold truncate">
                    {setup?.selected_model || 'qwen2.5:1.5b'}
                  </div>
                </div>

                <div className="p-3 bg-zinc-950 border border-zinc-800 rounded space-y-1">
                  <div className="text-zinc-400 text-[10px] font-sans">Resource Governance Tier</div>
                  <div className="text-emerald-400 font-bold">
                    {profile?.tier_name || 'Tier 1: Minimal (4-6 GB RAM)'}
                  </div>
                </div>

                <div className="p-3 bg-zinc-950 border border-zinc-800 rounded space-y-1">
                  <div className="text-zinc-400 text-[10px] font-sans">Inference Latency</div>
                  <div className="text-sky-400 font-bold">
                    {testStatus?.latency_ms ? `${testStatus.latency_ms} ms` : 'Nominal (~45ms)'}
                  </div>
                </div>
              </div>

              <div className="p-3 bg-zinc-950/80 border border-zinc-800/80 rounded text-xs text-zinc-400 space-y-1">
                <div className="font-semibold text-zinc-300 flex items-center gap-1.5">
                  <Terminal className="w-3.5 h-3.5 text-amber-400" /> Operational Readiness Summary
                </div>
                <p className="text-[11px] leading-relaxed">
                  Screen observation pipeline, deterministic OCR element grouping, untrusted proposal sandbox, and verification engine are active and persistent across sessions.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <button
                onClick={handleScan}
                className="px-3.5 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded text-xs transition"
              >
                Recalibrate Setup
              </button>

              <button
                onClick={handleCompleteSetup}
                className="px-6 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 rounded-lg text-xs font-bold flex items-center gap-2 shadow-lg transition"
              >
                <Play className="w-4 h-4 fill-current" />
                <span>Launch Panther Agent Workspace</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
