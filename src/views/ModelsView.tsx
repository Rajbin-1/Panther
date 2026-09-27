import React, { useState, useEffect } from 'react';
import { ModelItem } from '../types/agent';
import { api } from '../services/api';
import { Cpu, CheckCircle2, AlertCircle, RefreshCw, Check } from 'lucide-react';

export const ModelsView: React.FC = () => {
  const [models, setModels] = useState<ModelItem[]>([]);
  const [activeModel, setActiveModel] = useState<string>('llama3.2:1b');
  const [health, setHealth] = useState<{ connected: boolean; endpoint: string; message?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState<string | null>(null);

  const fetchModelsAndHealth = async () => {
    setLoading(true);
    try {
      const [modelsData, healthData] = await Promise.all([
        api.getModels(),
        api.checkModelHealth(),
      ]);
      setModels(modelsData.models);
      setActiveModel(modelsData.active_model);
      setHealth(healthData);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModelsAndHealth();
  }, []);

  const handleSelectModel = async (id: string) => {
    setSelecting(id);
    try {
      await api.selectModel(id);
      setActiveModel(id);
    } catch {
      // ignore
    } finally {
      setSelecting(null);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">Local Model Architecture</h2>
          <p className="text-sm text-zinc-400">
            Ollama-compatible local inference with strictly enforced low-RAM parameters.
          </p>
        </div>
        <button
          onClick={fetchModelsAndHealth}
          className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded border border-zinc-700 text-xs font-medium flex items-center gap-1.5"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Probe Ollama</span>
        </button>
      </div>

      {/* Ollama Endpoint Status */}
      <div className="bg-zinc-900 border border-zinc-800 rounded p-4 flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <Cpu className="w-5 h-5 text-zinc-400" />
          <div>
            <div className="font-medium text-zinc-200">
              Ollama Endpoint: <span className="font-mono text-zinc-400">{health?.endpoint || 'http://127.0.0.1:11434'}</span>
            </div>
            <div className="text-zinc-500 mt-0.5">
              {health?.connected
                ? 'Local Ollama service active and responding.'
                : 'Local Ollama offline. Panther Agent high-reliability local planner active.'}
            </div>
          </div>
        </div>
        <span
          className={`px-2.5 py-1 rounded border font-mono ${
            health?.connected
              ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300'
              : 'bg-zinc-800 border-zinc-700 text-zinc-400'
          }`}
        >
          {health?.connected ? 'Ollama Online' : 'Local Planner Active'}
        </span>
      </div>

      {/* 6GB Hardware Budget Notice */}
      <div className="bg-zinc-950 border border-zinc-800 rounded p-4 text-xs text-zinc-400 space-y-1.5">
        <div className="font-medium text-zinc-300 flex items-center gap-1.5">
          <AlertCircle className="w-4 h-4 text-amber-400" />
          <span>6 GB RAM Target Hardware Constraint</span>
        </div>
        <p>
          On a 6 GB Windows machine with integrated graphics, models larger than 3B parameters risk OS memory paging and UI stutter.
          Panther Agent restricts active context window to 2,048 tokens and enforces Q4 quantization.
        </p>
      </div>

      {/* Recommended Models Table */}
      <div className="bg-zinc-900 border border-zinc-800 rounded overflow-hidden">
        <div className="p-4 border-b border-zinc-800 text-xs font-medium text-zinc-400 uppercase tracking-wide">
          Configured Local Models ({models.length})
        </div>

        <div className="divide-y divide-zinc-800">
          {models.map((m) => {
            const isSelected = activeModel === m.id;
            return (
              <div
                key={m.id}
                className="p-4 flex items-center justify-between hover:bg-zinc-850/50 transition"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-zinc-100">{m.name}</span>
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-300">
                      {m.id}
                    </span>
                    {m.suitable_for_6gb && (
                      <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-950/40 border border-emerald-900 text-emerald-400">
                        6GB Suitable
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-zinc-500 font-mono">
                    Provider: {m.provider} • Est. Footprint: ~{m.ram_estimate_mb} MB RAM
                  </div>
                </div>

                <div>
                  {isSelected ? (
                    <span className="px-3 py-1.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-200 text-xs font-medium flex items-center gap-1.5">
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Active</span>
                    </span>
                  ) : (
                    <button
                      onClick={() => handleSelectModel(m.id)}
                      disabled={selecting === m.id}
                      className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded border border-zinc-700 text-xs font-medium transition"
                    >
                      {selecting === m.id ? 'Setting...' : 'Select Model'}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
