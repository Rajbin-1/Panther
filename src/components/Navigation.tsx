import React from 'react';
import { Bot, ListTodo, Monitor, Cpu, Sliders, ShieldCheck } from 'lucide-react';

export type TabId = 'agent' | 'tasks' | 'devices' | 'models' | 'settings';

interface NavigationProps {
  activeTab: TabId;
  onSelectTab: (tab: TabId) => void;
  isReady: boolean;
}

export const Navigation: React.FC<NavigationProps> = ({ activeTab, onSelectTab, isReady }) => {
  const navItems: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: 'agent', label: 'Agent', icon: <Bot className="w-5 h-5" /> },
    { id: 'tasks', label: 'Tasks', icon: <ListTodo className="w-5 h-5" /> },
    { id: 'devices', label: 'Devices', icon: <Monitor className="w-5 h-5" /> },
    { id: 'models', label: 'Models', icon: <Cpu className="w-5 h-5" /> },
    { id: 'settings', label: 'Settings', icon: <Sliders className="w-5 h-5" /> },
  ];

  return (
    <aside className="w-60 bg-zinc-900 border-r border-zinc-800 flex flex-col justify-between select-none">
      <div>
        {/* App Title & Shell Branding */}
        <div className="px-5 py-4 border-b border-zinc-800 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded bg-zinc-800 border border-zinc-700 flex items-center justify-center font-bold text-zinc-200">
            PA
          </div>
          <div>
            <h1 className="text-sm font-semibold text-zinc-100 tracking-tight">Panther Agent</h1>
            <p className="text-xs text-zinc-400">Windows Desktop Shell</p>
          </div>
        </div>

        {/* Semantic Navigation Menu */}
        <nav aria-label="Main Navigation" className="p-3 space-y-1">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded text-sm font-medium transition-colors text-left ${
                  isActive
                    ? 'bg-zinc-800 text-zinc-100 border border-zinc-700'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-850'
                }`}
              >
                <span className={isActive ? 'text-zinc-200' : 'text-zinc-400'}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer Info: Sandbox & SQLite Integrity */}
      <div className="p-4 border-t border-zinc-800 text-xs text-zinc-400 space-y-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
          <span className="truncate">Safe Boundary Active</span>
        </div>
        <div className="flex justify-between items-center text-zinc-400">
          <span>Target: 6GB PC</span>
          <span className="font-mono text-zinc-400">v0.1.0</span>
        </div>
      </div>
    </aside>
  );
};
