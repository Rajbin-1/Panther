import React, { useState, useEffect } from 'react';
import { TaskHistoryItem, TaskDetails } from '../types/agent';
import { api } from '../services/api';
import { CheckCircle2, XCircle, Clock, ChevronRight } from 'lucide-react';

export const TasksView: React.FC = () => {
  const [tasks, setTasks] = useState<TaskHistoryItem[]>([]);
  const [selectedTask, setSelectedTask] = useState<TaskDetails | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const data = await api.getTaskHistory(50);
      setTasks(data.tasks);
      if (data.tasks.length > 0 && !selectedTask) {
        loadTaskDetails(data.tasks[0].id);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const loadTaskDetails = async (id: string) => {
    try {
      const details = await api.getTaskDetails(id);
      setSelectedTask(details);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    fetchTasks();
  }, []);

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">Task History</h2>
          <p className="text-sm text-zinc-400">
            Persistent execution audit log stored in local SQLite database.
          </p>
        </div>
        <button
          onClick={fetchTasks}
          className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded border border-zinc-700 text-xs font-medium"
        >
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Task List */}
        <div className="md:col-span-1 bg-zinc-900 border border-zinc-800 rounded overflow-hidden">
          <div className="p-3 border-b border-zinc-800 text-xs font-medium text-zinc-400 uppercase tracking-wide">
            Completed & Active Runs ({tasks.length})
          </div>

          <div className="divide-y divide-zinc-800 max-h-[550px] overflow-y-auto">
            {loading ? (
              <div className="p-6 text-center text-xs text-zinc-500">Loading history...</div>
            ) : tasks.length === 0 ? (
              <div className="p-6 text-center text-xs text-zinc-500">No recorded tasks found.</div>
            ) : (
              tasks.map((t) => {
                const isSelected = selectedTask?.id === t.id;
                return (
                  <button
                    key={t.id}
                    onClick={() => loadTaskDetails(t.id)}
                    className={`w-full p-3 text-left transition flex items-center justify-between ${
                      isSelected ? 'bg-zinc-800 text-zinc-100' : 'hover:bg-zinc-850 text-zinc-300'
                    }`}
                  >
                    <div className="truncate pr-2">
                      <div className="text-xs font-medium truncate">{t.title}</div>
                      <div className="text-[11px] text-zinc-500 font-mono mt-0.5">
                        {new Date(t.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} • {t.total_turns} turns
                      </div>
                    </div>
                    <div className="shrink-0">
                      {t.success ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      ) : t.state === 'FAILED' ? (
                        <XCircle className="w-4 h-4 text-rose-400" />
                      ) : (
                        <Clock className="w-4 h-4 text-zinc-400" />
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* Task Details Breakdown */}
        <div className="md:col-span-2 bg-zinc-900 border border-zinc-800 rounded p-5 space-y-4">
          {selectedTask ? (
            <>
              <div className="border-b border-zinc-800 pb-3 flex items-start justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-zinc-100">{selectedTask.title}</h3>
                  <p className="text-xs text-zinc-400 mt-1">Goal: "{selectedTask.goal}"</p>
                </div>
                <span
                  className={`text-xs px-2 py-0.5 rounded border font-mono ${
                    selectedTask.success
                      ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300'
                      : 'bg-zinc-800 border-zinc-700 text-zinc-400'
                  }`}
                >
                  {selectedTask.state}
                </span>
              </div>

              {/* Task Metadata */}
              <div className="grid grid-cols-3 gap-2 text-xs font-mono text-zinc-400 bg-zinc-950 p-3 rounded border border-zinc-850">
                <div>
                  <span className="text-zinc-600 block">ID</span>
                  <span className="text-zinc-300">{selectedTask.id}</span>
                </div>
                <div>
                  <span className="text-zinc-600 block">Started</span>
                  <span className="text-zinc-300">{new Date(selectedTask.started_at).toLocaleTimeString()}</span>
                </div>
                <div>
                  <span className="text-zinc-600 block">Turns</span>
                  <span className="text-zinc-300">{selectedTask.total_turns}</span>
                </div>
              </div>

              {selectedTask.termination_reason && (
                <div className="text-xs p-3 rounded bg-zinc-850 border border-zinc-750 text-zinc-300">
                  <span className="text-zinc-500 font-medium">Outcome: </span>
                  {selectedTask.termination_reason}
                </div>
              )}

              {/* Turn Events */}
              <div className="space-y-2">
                <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
                  Step Turn History
                </h4>
                <div className="space-y-2 max-h-[320px] overflow-y-auto">
                  {selectedTask.events.map((ev) => (
                    <div
                      key={ev.id}
                      className="p-3 bg-zinc-950 border border-zinc-850 rounded text-xs space-y-1.5"
                    >
                      <div className="flex items-center justify-between font-mono text-[11px] text-zinc-400">
                        <span>Turn {ev.turn_index}: {ev.action_type || 'wait'}</span>
                        <span className={ev.verification_passed ? 'text-emerald-400' : 'text-amber-400'}>
                          {ev.verification_passed ? 'Verified' : 'Unverified'}
                        </span>
                      </div>
                      <p className="text-zinc-200">{ev.proposal_summary}</p>
                      {ev.verification_details && (
                        <div className="text-[11px] font-mono text-zinc-400 border-t border-zinc-900 pt-1">
                          Verifier: {ev.verification_details}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="py-16 text-center text-xs text-zinc-500">
              Select a task from the left panel to inspect step breakdown and verification audits.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
