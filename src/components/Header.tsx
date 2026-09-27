import React from 'react';
import { AgentStatus } from '../types/agent';
import { Activity, ShieldAlert, Cpu, HardDrive } from 'lucide-react';

interface HeaderProps {
  status: AgentStatus | null;
  onOpenSetup: () => void;
}

export const Header: React.FC<HeaderProps> = ({ status, onOpenSetup }) => {
  const state = status?.state || 'IDLE';
  const metrics = status?.resource_metrics;

  const getPressureColor = (pressure?: string) => {
    switch (pressure) {
      case 'CRITICAL':
        return 'text-rose-400 border-rose-900 bg-rose-950/40';
      case 'HIGH':
        return 'text-amber-400 border-amber-900 bg-amber-950/40';
      case 'MODERATE':
        return 'text-yellow-300 border-yellow-900 bg-yellow-950/30';
      default:
        return 'text-zinc-300 border-zinc-700 bg-zinc-850';
    }
  };

  return (
    <header className="h-14 border-b border-zinc-800 bg-zinc-900 px-6 flex items-center justify-between">
      {/* State Machine Status */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs uppercase font-mono text-zinc-400">State:</span>
          <span className="text-xs font-semibold px-2.5 py-1 rounded bg-zinc-800 border border-zinc-700 text-zinc-200">
            {state}
          </span>
        </div>

        {status?.active_task_goal && (
          <div className="text-xs text-zinc-400 truncate max-w-md hidden md:block">
            <span className="text-zinc-400">Task: </span>
            <span className="text-zinc-300 italic">"{status.active_task_goal}"</span>
          </div>
        )}
      </div>

      {/* Resource Governor Indicators */}
      <div className="flex items-center gap-4">
        {metrics && (
          <div className="flex items-center gap-3 text-xs">
            {/* RAM Governor */}
            <div className="flex items-center gap-1.5 text-zinc-300">
              <HardDrive className="w-3.5 h-3.5 text-zinc-400" />
              <span>
                {metrics.used_ram_mb} / {metrics.total_ram_mb} MB ({metrics.ram_used_percent}%)
              </span>
            </div>

            {/* CPU Governor */}
            <div className="flex items-center gap-1.5 text-zinc-300">
              <Cpu className="w-3.5 h-3.5 text-zinc-400" />
              <span>{metrics.cpu_percent}%</span>
            </div>

            {/* Governor Pressure */}
            <div
              className={`px-2 py-0.5 rounded border text-xs font-mono flex items-center gap-1 ${getPressureColor(
                metrics.system_pressure
              )}`}
              title={metrics.pressure_reason}
            >
              <Activity className="w-3 h-3" />
              <span>{metrics.system_pressure}</span>
            </div>
          </div>
        )}

        <button
          onClick={onOpenSetup}
          className="text-xs px-2.5 py-1 rounded border border-zinc-700 bg-zinc-800 text-zinc-300 hover:bg-zinc-700 transition"
        >
          Diagnostics
        </button>
      </div>
    </header>
  );
};
