import {
  AgentStatus,
  TaskHistoryItem,
  TaskDetails,
  DeviceProfile,
  ModelItem,
  DiagnosticLog,
  SetupStatus,
  ScreenStateData,
  ScreenDiffData
} from '../types/agent';

const BASE_URL = '/api';

export const api = {
  async getStatus(): Promise<AgentStatus> {
    const res = await fetch(`${BASE_URL}/status`);
    if (!res.ok) throw new Error('Failed to retrieve runtime status');
    return res.json();
  },

  async startTask(goal: string, title?: string): Promise<{ success: boolean; task_id?: string; error?: string }> {
    const res = await fetch(`${BASE_URL}/tasks/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, title }),
    });
    return res.json();
  },

  async pauseTask(): Promise<{ success: boolean; message?: string }> {
    const res = await fetch(`${BASE_URL}/tasks/pause`, { method: 'POST' });
    return res.json();
  },

  async resumeTask(): Promise<{ success: boolean; message?: string }> {
    const res = await fetch(`${BASE_URL}/tasks/resume`, { method: 'POST' });
    return res.json();
  },

  async cancelTask(): Promise<{ success: boolean; message?: string }> {
    const res = await fetch(`${BASE_URL}/tasks/cancel`, { method: 'POST' });
    return res.json();
  },

  async getTaskHistory(limit = 50): Promise<{ tasks: TaskHistoryItem[] }> {
    const res = await fetch(`${BASE_URL}/tasks/history?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch task history');
    return res.json();
  },

  async getTaskDetails(taskId: string): Promise<TaskDetails> {
    const res = await fetch(`${BASE_URL}/tasks/${taskId}`);
    if (!res.ok) throw new Error(`Failed to fetch details for task ${taskId}`);
    return res.json();
  },

  async getDeviceProfile(): Promise<DeviceProfile> {
    const res = await fetch(`${BASE_URL}/device`);
    if (!res.ok) throw new Error('Failed to fetch device profile');
    return res.json();
  },

  async getModels(): Promise<{ models: ModelItem[]; active_model: string }> {
    const res = await fetch(`${BASE_URL}/models`);
    if (!res.ok) throw new Error('Failed to fetch models');
    return res.json();
  },

  async selectModel(modelId: string): Promise<{ success: boolean; selected_model: string }> {
    const res = await fetch(`${BASE_URL}/models/select`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId }),
    });
    return res.json();
  },

  async checkModelHealth(): Promise<{ connected: boolean; endpoint: string; detected_models: string[]; message?: string }> {
    const res = await fetch(`${BASE_URL}/models/health`);
    if (!res.ok) throw new Error('Failed to query model health');
    return res.json();
  },

  async getConfig(): Promise<Record<string, any>> {
    const res = await fetch(`${BASE_URL}/config`);
    if (!res.ok) throw new Error('Failed to fetch configuration');
    return res.json();
  },

  async updateConfig(section: string, updates: Record<string, any>): Promise<{ section: string; config: any }> {
    const res = await fetch(`${BASE_URL}/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ section, updates }),
    });
    return res.json();
  },

  async resetConfig(): Promise<{ message: string; config: any }> {
    const res = await fetch(`${BASE_URL}/config/reset`, { method: 'POST' });
    return res.json();
  },

  async getDiagnostics(limit = 100, level?: string): Promise<{ logs: DiagnosticLog[] }> {
    const query = new URLSearchParams({ limit: limit.toString() });
    if (level) query.set('level', level);
    const res = await fetch(`${BASE_URL}/diagnostics?${query.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch diagnostics');
    return res.json();
  },

  async getCurrentScreen(): Promise<ScreenStateData> {
    const res = await fetch(`${BASE_URL}/screen/current`);
    if (!res.ok) throw new Error('Failed to fetch active screen observation');
    return res.json();
  },

  async getScreenDiff(): Promise<ScreenDiffData> {
    const res = await fetch(`${BASE_URL}/screen/diff`);
    if (!res.ok) throw new Error('Failed to fetch screen diff');
    return res.json();
  },

  async getSetupStatus(): Promise<SetupStatus> {
    const res = await fetch(`${BASE_URL}/setup/status`);
    if (!res.ok) throw new Error('Failed to fetch setup status');
    return res.json();
  },

  async getModelCatalog(): Promise<{ catalog: import('../types/agent').ModelCatalogItem[]; tier: number }> {
    const res = await fetch(`${BASE_URL}/setup/catalog`);
    if (!res.ok) throw new Error('Failed to fetch model catalog');
    return res.json();
  },

  async scanDeviceAndCapabilities(): Promise<SetupStatus> {
    const res = await fetch(`${BASE_URL}/setup/scan`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to execute device scan');
    return res.json();
  },

  async selectSetupModel(modelId: string): Promise<SetupStatus> {
    const res = await fetch(`${BASE_URL}/setup/model/select`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId }),
    });
    if (!res.ok) throw new Error('Failed to select model');
    return res.json();
  },

  async startModelDownload(modelId?: string): Promise<SetupStatus> {
    const res = await fetch(`${BASE_URL}/setup/model/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId }),
    });
    if (!res.ok) throw new Error('Failed to initiate model download');
    return res.json();
  },

  async cancelModelDownload(): Promise<SetupStatus> {
    const res = await fetch(`${BASE_URL}/setup/model/download/cancel`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to cancel model download');
    return res.json();
  },

  async getDownloadProgress(): Promise<import('../types/agent').DownloadProgress> {
    const res = await fetch(`${BASE_URL}/setup/model/progress`);
    if (!res.ok) throw new Error('Failed to query download progress');
    return res.json();
  },

  async verifyAndTestModel(): Promise<SetupStatus> {
    const res = await fetch(`${BASE_URL}/setup/verify`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to verify and test model');
    return res.json();
  },

  async completeSetup(): Promise<SetupStatus> {
    const res = await fetch(`${BASE_URL}/setup/complete`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to complete setup');
    return res.json();
  },

  async resetSetup(): Promise<SetupStatus> {
    const res = await fetch(`${BASE_URL}/setup/reset`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to reset setup');
    return res.json();
  },

  async runSetupChecks(): Promise<SetupStatus> {
    const res = await fetch(`${BASE_URL}/setup/run`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to run setup checks');
    return res.json();
  },
};
