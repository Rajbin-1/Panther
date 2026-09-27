import React, { useState, useEffect } from 'react';
import { AgentStatus, TaskDetails, ScreenStateData, ScreenDiffData } from '../types/agent';
import { api } from '../services/api';
import {
  Play,
  Pause,
  Square,
  AlertCircle,
  CheckCircle2,
  Eye,
  Layers,
  GitCommit,
  RefreshCw,
  Monitor,
  MousePointer,
  Sparkles,
  Info
} from 'lucide-react';

interface AgentViewProps {
  status: AgentStatus | null;
  onRefreshStatus: () => void;
}

export const AgentView: React.FC<AgentViewProps> = ({ status, onRefreshStatus }) => {
  const [goalInput, setGoalInput] = useState('');
  const [activeTaskDetails, setActiveTaskDetails] = useState<TaskDetails | null>(null);
  const [screenState, setScreenState] = useState<ScreenStateData | null>(null);
  const [screenDiff, setScreenDiff] = useState<ScreenDiffData | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'turns' | 'screen' | 'diff'>('turns');
  const [filterQuery, setFilterQuery] = useState('');
  const [isRefreshingScreen, setIsRefreshingScreen] = useState(false);

  const isBusy = status && status.state !== 'IDLE' && status.state !== 'COMPLETE' && status.state !== 'FAILED' && status.state !== 'CANCELLED';

  // Load details of the current active task or last task
  useEffect(() => {
    let timer: NodeJS.Timeout;

    const fetchCurrentTask = async () => {
      if (status?.active_task_id) {
        try {
          const details = await api.getTaskDetails(status.active_task_id);
          setActiveTaskDetails(details);
        } catch {
          // ignore
        }
      } else if (!activeTaskDetails) {
        try {
          const hist = await api.getTaskHistory(1);
          if (hist.tasks.length > 0) {
            const details = await api.getTaskDetails(hist.tasks[0].id);
            setActiveTaskDetails(details);
          }
        } catch {
          // ignore
        }
      }
    };

    fetchCurrentTask();

    if (isBusy) {
      timer = setInterval(fetchCurrentTask, 800);
    }

    return () => {
      if (timer) clearInterval(timer);
    };
  }, [status?.active_task_id, isBusy]);

  // Fetch screen state and diff when requested or while active
  const refreshScreenData = async () => {
    setIsRefreshingScreen(true);
    try {
      const [screen, diff] = await Promise.all([
        api.getCurrentScreen(),
        api.getScreenDiff()
      ]);
      setScreenState(screen);
      setScreenDiff(diff);
    } catch {
      // ignore
    } finally {
      setIsRefreshingScreen(false);
    }
  };

  useEffect(() => {
    refreshScreenData();
    let screenTimer: NodeJS.Timeout;
    if (isBusy) {
      screenTimer = setInterval(refreshScreenData, 1500);
    }
    return () => {
      if (screenTimer) clearInterval(screenTimer);
    };
  }, [isBusy]);

  const handleStartTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!goalInput.trim() || isSubmitting) return;

    setIsSubmitting(true);
    setActionError(null);

    try {
      const res = await api.startTask(goalInput.trim());
      if (!res.success) {
        setActionError(res.error || 'Failed to start task.');
      } else {
        setGoalInput('');
        onRefreshStatus();
        refreshScreenData();
      }
    } catch (err: any) {
      setActionError(err.message || 'Error communicating with runtime.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePause = async () => {
    await api.pauseTask();
    onRefreshStatus();
  };

  const handleResume = async () => {
    await api.resumeTask();
    onRefreshStatus();
    refreshScreenData();
  };

  const handleCancel = async () => {
    await api.cancelTask();
    onRefreshStatus();
  };

  // State Machine stages for visual progress
  const stages = ['IDLE', 'OBSERVE', 'REASON', 'ACT', 'VERIFY', 'GOAL_CHECK', 'COMPLETE'];
  const currentState = status?.state || 'IDLE';

  // Filter nodes for the OCR inspector
  const ocrElements = screenState?.ocr_elements || screenState?.nodes || [];
  const filteredNodes = filterQuery.trim()
    ? ocrElements.filter((n) => n.text.toLowerCase().includes(filterQuery.toLowerCase()) || n.node_id.includes(filterQuery))
    : ocrElements;

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100 flex items-center gap-2">
            <span>Panther Agent Controller</span>
            <span className="text-xs font-mono font-normal px-2 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-300">
              Stage 2 Runtime
            </span>
          </h2>
          <p className="text-sm text-zinc-400 mt-0.5">
            Supervised local desktop agent: deterministic verification, strict action safety, and low-resource governance.
          </p>
        </div>

        {status?.activity && isBusy && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-850 border border-zinc-700 rounded-full text-xs text-zinc-300 animate-pulse">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            <span>{status.activity}</span>
          </div>
        )}
      </div>

      {/* Goal Input Section */}
      <div className="bg-zinc-900 border border-zinc-800 rounded p-5 space-y-4">
        <form onSubmit={handleStartTask} className="space-y-3">
          <label htmlFor="goal-input" className="block text-xs font-medium text-zinc-300 uppercase tracking-wide flex items-center justify-between">
            <span>User Goal Specification</span>
            <span className="text-[11px] font-normal text-zinc-500 normal-case">
              Target application will be observed and verified deterministically
            </span>
          </label>
          <div className="flex gap-3">
            <input
              id="goal-input"
              type="text"
              value={goalInput}
              onChange={(e) => setGoalInput(e.target.value)}
              placeholder="e.g. Open Calculator and calculate total, or Inspect File Explorer window"
              disabled={Boolean(isBusy) || isSubmitting}
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-zinc-500 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={Boolean(isBusy) || isSubmitting || !goalInput.trim()}
              className="px-4 py-2 bg-zinc-100 text-zinc-900 hover:bg-zinc-200 text-sm font-medium rounded flex items-center gap-2 disabled:opacity-50 transition"
            >
              <Play className="w-4 h-4" />
              <span>Execute Goal</span>
            </button>
          </div>
        </form>

        {actionError && (
          <div className="p-3 bg-rose-950/40 border border-rose-900 rounded text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{actionError}</span>
          </div>
        )}

        {/* Runtime Controls when running */}
        {isBusy && (
          <div className="pt-3 border-t border-zinc-800 flex items-center justify-between">
            <div className="text-xs text-zinc-400 flex items-center gap-2">
              <span>Task:</span>
              <span className="font-mono text-zinc-200 bg-zinc-800 px-2 py-0.5 rounded border border-zinc-700">
                {status?.active_task_id}
              </span>
              {status?.activity && (
                <span className="text-zinc-400 italic">({status.activity})</span>
              )}
            </div>
            <div className="flex gap-2">
              {status?.is_paused ? (
                <button
                  onClick={handleResume}
                  className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded border border-zinc-700 flex items-center gap-1.5"
                >
                  <Play className="w-3.5 h-3.5" />
                  <span>Resume</span>
                </button>
              ) : (
                <button
                  onClick={handlePause}
                  className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium rounded border border-zinc-700 flex items-center gap-1.5"
                >
                  <Pause className="w-3.5 h-3.5" />
                  <span>Pause</span>
                </button>
              )}
              <button
                onClick={handleCancel}
                className="px-3 py-1.5 bg-rose-950/60 hover:bg-rose-900 text-rose-300 text-xs font-medium rounded border border-rose-900 flex items-center gap-1.5"
              >
                <Square className="w-3.5 h-3.5" />
                <span>Cancel Task</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* State Machine Lifecycle Stages */}
      <div className="bg-zinc-900 border border-zinc-800 rounded p-5 space-y-3">
        <div className="flex items-center justify-between text-xs text-zinc-400">
          <span className="font-medium text-zinc-300 uppercase tracking-wide">
            Autonomous Lifecycle Control Loop
          </span>
          <span className="font-mono">
            {currentState === 'RECOVERY' ? (
              <span className="text-amber-400 font-semibold">RECOVERY (Handling anomaly)</span>
            ) : (
              <span>State: {currentState}</span>
            )}
          </span>
        </div>
        <div className="grid grid-cols-7 gap-2 text-center text-xs">
          {stages.map((stage) => {
            const isActive = currentState === stage;
            const isCompletedStage =
              currentState === 'COMPLETE' ||
              (stages.indexOf(currentState) > stages.indexOf(stage) && currentState !== 'IDLE');

            return (
              <div
                key={stage}
                className={`py-2 px-1 rounded border font-mono transition-colors ${
                  isActive
                    ? 'bg-zinc-800 border-zinc-500 text-zinc-100 font-semibold shadow-sm'
                    : isCompletedStage
                    ? 'bg-zinc-850 border-zinc-700 text-zinc-300'
                    : 'bg-zinc-950 border-zinc-850 text-zinc-600'
                }`}
              >
                {stage}
              </div>
            );
          })}
        </div>
      </div>

      {/* Segmented View Selector: Turns | Screen Observer | State Diff */}
      <div className="bg-zinc-900 border border-zinc-800 rounded overflow-hidden">
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 pt-3">
          <div className="flex gap-2 text-xs font-medium">
            <button
              onClick={() => setActiveTab('turns')}
              className={`pb-3 px-3 border-b-2 flex items-center gap-2 transition ${
                activeTab === 'turns'
                  ? 'border-zinc-300 text-zinc-100'
                  : 'border-transparent text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <GitCommit className="w-3.5 h-3.5" />
              <span>Turn Verification Stream</span>
              {activeTaskDetails?.events && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-zinc-800 text-zinc-300">
                  {activeTaskDetails.events.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('screen')}
              className={`pb-3 px-3 border-b-2 flex items-center gap-2 transition ${
                activeTab === 'screen'
                  ? 'border-zinc-300 text-zinc-100'
                  : 'border-transparent text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Eye className="w-3.5 h-3.5" />
              <span>Screen Observer & OCR</span>
              {screenState?.observation_id && (
                <span className="font-mono text-[10px] text-zinc-500">
                  [{screenState.observation_id}]
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('diff')}
              className={`pb-3 px-3 border-b-2 flex items-center gap-2 transition ${
                activeTab === 'diff'
                  ? 'border-zinc-300 text-zinc-100'
                  : 'border-transparent text-zinc-400 hover:text-zinc-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>State Diff Inspector</span>
              {screenDiff?.changed && (
                <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              )}
            </button>
          </div>

          <button
            onClick={refreshScreenData}
            disabled={isRefreshingScreen}
            className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1.5 pb-2 transition"
            title="Refresh active observation and diff"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshingScreen ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {/* TAB 1: Execution Turns & Verification Stream */}
        {activeTab === 'turns' && (
          <div className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-zinc-200">
                {activeTaskDetails ? `Turns: ${activeTaskDetails.title}` : 'Execution Turns & Verification Stream'}
              </h3>
              {activeTaskDetails && (
                <span
                  className={`text-xs px-2 py-0.5 rounded border font-mono ${
                    activeTaskDetails.success
                      ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300'
                      : activeTaskDetails.state === 'FAILED'
                      ? 'bg-rose-950/40 border-rose-800 text-rose-300'
                      : 'bg-zinc-800 border-zinc-700 text-zinc-400'
                  }`}
                >
                  {activeTaskDetails.state}
                </span>
              )}
            </div>

            {activeTaskDetails?.events && activeTaskDetails.events.length > 0 ? (
              <div className="space-y-3">
                {activeTaskDetails.events.map((ev) => (
                  <div
                    key={ev.id}
                    className="p-3.5 bg-zinc-950 border border-zinc-800 rounded space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between text-zinc-400">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-zinc-300 font-semibold">Turn {ev.turn_index}</span>
                        <span className="text-zinc-600">•</span>
                        <span className="font-mono text-zinc-400">Action: {ev.action_type || 'none'}</span>
                      </div>
                      <div className="flex items-center gap-1.5 font-mono">
                        {ev.verification_passed ? (
                          <span className="text-emerald-400 flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            Verified
                          </span>
                        ) : (
                          <span className="text-amber-400 flex items-center gap-1">
                            <AlertCircle className="w-3.5 h-3.5" />
                            Unverified / In Recovery
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Concise Decision Summary (NO CoT) */}
                    <p className="text-zinc-200">{ev.proposal_summary}</p>

                    {/* Technical Execution & Verification Rule Details */}
                    <div className="grid grid-cols-2 gap-3 pt-2 border-t border-zinc-850 text-zinc-400 font-mono text-[11px]">
                      <div>
                        <span className="text-zinc-500">Parameters: </span>
                        <span className="text-zinc-300">
                          {ev.action_params ? JSON.stringify(ev.action_params) : 'none'}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500">Verification Result: </span>
                        <span className="text-zinc-300">{ev.verification_details || 'Pending check'}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-zinc-500 space-y-1">
                <p>No execution turns recorded yet.</p>
                <p className="text-zinc-600">Enter a goal above and click 'Execute Goal' to start an action loop.</p>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: Screen Observer & OCR Inspector */}
        {activeTab === 'screen' && (
          <div className="p-5 space-y-4">
            {/* Screen Metadata Bar */}
            <div className="grid grid-cols-4 gap-3 bg-zinc-950 border border-zinc-800 rounded p-3 text-xs font-mono">
              <div>
                <span className="text-zinc-500 block">Observation ID</span>
                <span className="text-zinc-200">{screenState?.observation_id || 'None'}</span>
              </div>
              <div>
                <span className="text-zinc-500 block">Active Window</span>
                <span className="text-zinc-200 truncate block" title={screenState?.active_window}>
                  {screenState?.active_window || 'Desktop'}
                </span>
              </div>
              <div>
                <span className="text-zinc-500 block">Display Resolution</span>
                <span className="text-zinc-200">
                  {screenState?.width || 1920} x {screenState?.height || 1080} (DPI {screenState?.dpi_scaling || 1.0}x)
                </span>
              </div>
              <div>
                <span className="text-zinc-500 block">Fingerprint Hash</span>
                <span className="text-zinc-300">{screenState?.screen_fingerprint || 'N/A'}</span>
              </div>
            </div>

            {/* Element Search / Filter */}
            <div className="flex items-center justify-between gap-3">
              <input
                type="text"
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                placeholder="Filter OCR elements by text or node ID..."
                className="bg-zinc-800 border border-zinc-700 rounded px-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 flex-1 focus:outline-none focus:border-zinc-500"
              />
              <span className="text-xs text-zinc-400 font-mono">
                {filteredNodes.length} of {ocrElements.length} elements
              </span>
            </div>

            {/* OCR Elements Table */}
            {filteredNodes.length > 0 ? (
              <div className="border border-zinc-800 rounded overflow-hidden max-h-80 overflow-y-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-zinc-950 border-b border-zinc-800 text-zinc-400 font-mono sticky top-0">
                    <tr>
                      <th className="py-2 px-3">Node ID</th>
                      <th className="py-2 px-3">Detected Text</th>
                      <th className="py-2 px-3">Bounds (X, Y, W, H)</th>
                      <th className="py-2 px-3">Center</th>
                      <th className="py-2 px-3">Confidence</th>
                      <th className="py-2 px-3">Type</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-850">
                    {filteredNodes.map((n) => (
                      <tr key={n.node_id} className="hover:bg-zinc-850/50 transition">
                        <td className="py-2 px-3 font-mono text-zinc-400">{n.node_id}</td>
                        <td className="py-2 px-3 font-medium text-zinc-200">{n.text}</td>
                        <td className="py-2 px-3 font-mono text-zinc-400">
                          {n.x}, {n.y}, {n.width}x{n.height}
                        </td>
                        <td className="py-2 px-3 font-mono text-zinc-400">
                          ({n.center_x}, {n.center_y})
                        </td>
                        <td className="py-2 px-3 font-mono text-zinc-300">
                          {Math.round(n.confidence * 100)}%
                        </td>
                        <td className="py-2 px-3">
                          {n.interactive ? (
                            <span className="px-1.5 py-0.5 rounded bg-blue-950/60 border border-blue-800 text-blue-300 text-[10px] font-mono">
                              Interactive
                            </span>
                          ) : (
                            <span className="text-zinc-500 text-[10px] font-mono">Static</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-zinc-500">
                No OCR elements match query.
              </div>
            )}
          </div>
        )}

        {/* TAB 3: State Diff Inspector */}
        {activeTab === 'diff' && (
          <div className="p-5 space-y-4">
            <div className="flex items-center justify-between text-xs">
              <span className="text-zinc-400">
                Deterministic comparison between previous and current screen states.
              </span>
              <span className="font-mono text-zinc-300">
                Status: {screenDiff?.changed ? (
                  <span className="text-emerald-400 font-semibold">MUTATION DETECTED</span>
                ) : (
                  <span className="text-zinc-400">NO CHANGE (Cache Reused)</span>
                )}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 text-xs font-mono">
              {/* Newly Appeared Text */}
              <div className="bg-zinc-950 border border-zinc-800 rounded p-4 space-y-2">
                <span className="text-emerald-400 font-semibold block uppercase tracking-wide text-[11px]">
                  + Text Appeared ({screenDiff?.text_appeared?.length || 0})
                </span>
                {screenDiff?.text_appeared && screenDiff.text_appeared.length > 0 ? (
                  <ul className="space-y-1 text-zinc-200">
                    {screenDiff.text_appeared.map((t, idx) => (
                      <li key={idx} className="flex items-center gap-1.5">
                        <span className="text-emerald-500">+</span>
                        <span>"{t}"</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-zinc-600 block">No new text appeared in this transition.</span>
                )}
              </div>

              {/* Disappeared Text */}
              <div className="bg-zinc-950 border border-zinc-800 rounded p-4 space-y-2">
                <span className="text-rose-400 font-semibold block uppercase tracking-wide text-[11px]">
                  - Text Disappeared ({screenDiff?.text_disappeared?.length || 0})
                </span>
                {screenDiff?.text_disappeared && screenDiff.text_disappeared.length > 0 ? (
                  <ul className="space-y-1 text-zinc-400">
                    {screenDiff.text_disappeared.map((t, idx) => (
                      <li key={idx} className="flex items-center gap-1.5">
                        <span className="text-rose-500">-</span>
                        <span>"{t}"</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="text-zinc-600 block">No text disappeared in this transition.</span>
                )}
              </div>
            </div>

            {/* Window & Region Shift Details */}
            <div className="bg-zinc-950 border border-zinc-800 rounded p-4 text-xs font-mono space-y-2">
              <span className="text-zinc-400 font-semibold block uppercase tracking-wide text-[11px]">
                Window & Structural Delta
              </span>
              <div className="grid grid-cols-2 gap-3 text-zinc-300">
                <div>
                  <span className="text-zinc-500">Active Window Change: </span>
                  <span>{screenDiff?.window_changed ? 'Yes' : 'No'}</span>
                  {screenDiff?.active_window_curr && (
                    <span className="block text-zinc-400 mt-0.5">
                      Current: "{screenDiff.active_window_curr}"
                    </span>
                  )}
                </div>
                <div>
                  <span className="text-zinc-500">Regions Mutated: </span>
                  <span>
                    {screenDiff?.regions_changed && screenDiff.regions_changed.length > 0
                      ? screenDiff.regions_changed.join(', ')
                      : 'None'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
