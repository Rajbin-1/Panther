export type AgentState =
  | 'IDLE'
  | 'OBSERVE'
  | 'REASON'
  | 'ACT'
  | 'VERIFY'
  | 'GOAL_CHECK'
  | 'COMPLETE'
  | 'RECOVERY'
  | 'PAUSED'
  | 'CANCELLED'
  | 'FAILED';

export type SystemPressure = 'NORMAL' | 'MODERATE' | 'HIGH' | 'CRITICAL';

export interface ResourceMetrics {
  total_ram_mb: number;
  available_ram_mb: number;
  used_ram_mb: number;
  ram_used_percent: number;
  process_memory_mb: number;
  model_process_memory_mb: number;
  application_memory_mb: number;
  cpu_percent: number;
  system_pressure: SystemPressure;
  pressure_reason: string;
  timestamp: number;
  platform: string;
}

export interface AgentStatus {
  state: AgentState;
  active_task_id: string | null;
  active_task_goal: string | null;
  activity?: string;
  is_paused: boolean;
  current_observation_id?: string | null;
  active_window?: string | null;
  total_nodes?: number;
  last_diff_summary?: {
    changed: boolean;
    text_appeared: string[];
    text_disappeared: string[];
  } | null;
  resource_metrics: ResourceMetrics;
}

export interface OcrNodeData {
  node_id: string;
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
  center_x: number;
  center_y: number;
  confidence: number;
  interactive: boolean;
  region: string;
}

export interface ScreenStateData {
  observation_id: string | null;
  timestamp?: number;
  width?: number;
  height?: number;
  active_display?: string;
  dpi_scaling?: number;
  active_window?: string;
  active_window_bounds?: { x: number; y: number; width: number; height: number };
  screen_fingerprint?: string;
  total_nodes?: number;
  ocr_elements?: OcrNodeData[];
  nodes?: OcrNodeData[];
}

export interface ScreenDiffData {
  changed?: boolean;
  fingerprint_changed?: boolean;
  text_appeared?: string[];
  text_disappeared?: string[];
  nodes_added?: string[];
  nodes_removed?: string[];
  nodes_moved?: Array<{ text: string; from: [number, number]; to: [number, number] }>;
  regions_changed?: string[];
  window_changed?: boolean;
  active_window_prev?: string | null;
  active_window_curr?: string | null;
}

export interface TaskHistoryItem {
  id: string;
  title: string;
  goal: string;
  state: AgentState;
  started_at: string;
  ended_at: string | null;
  total_turns: number;
  success: number;
  termination_reason: string | null;
}

export interface TaskTurnEvent {
  id: string;
  task_id: string;
  turn_index: number;
  state: AgentState;
  proposal_summary: string | null;
  action_type: string | null;
  action_params: Record<string, any> | null;
  action_result: Record<string, any> | null;
  verification_rule: Record<string, any> | null;
  verification_passed: number;
  verification_details: string | null;
  timestamp: string;
}

export interface TaskDetails extends TaskHistoryItem {
  events: TaskTurnEvent[];
}

export interface DeviceProfile {
  id: string;
  hostname: string;
  os_version: string;
  arch: string;
  cpu_cores: number;
  total_ram_mb: number;
  primary_display: string;
  dpi_scale: number;
  meets_min_target: boolean;
  low_resource_profile: boolean;
  tier?: number;
  tier_name?: string;
  recommended_model_id?: string;
  meets_minimum_requirements?: boolean;
  tier_assessment?: string;
  os?: {
    name: string;
    version: string;
    build: string;
    architecture: string;
    is_64bit: boolean;
    windows_capabilities: Record<string, boolean>;
  };
  cpu?: {
    name: string;
    physical_cores: number;
    logical_processors: number;
    architecture: string;
    features: string[];
    current_usage_percent: number;
  };
  memory?: {
    total_mb: number;
    available_mb: number;
    used_mb: number;
    process_mb: number;
    system_memory_pressure: SystemPressure;
    ram_used_percent: number;
  };
  gpu?: {
    name: string;
    type: 'integrated' | 'discrete' | 'none';
    vram_mb: number;
    api: string;
    has_discrete_gpu: boolean;
  };
  display?: {
    count: number;
    width: number;
    height: number;
    resolution: string;
    dpi_scale: number;
    primary: boolean;
    orientation: string;
  };
  storage?: {
    drive: string;
    data_path: string;
    total_mb: number;
    available_mb: number;
    adequate_for_models: boolean;
  };
  capabilities?: {
    screen_capture: boolean;
    ocr: boolean;
    input: boolean;
    network: boolean;
    offline_operational: boolean;
  };
}

export interface ModelCatalogItem {
  id: string;
  name: string;
  architecture: string;
  parameters: string;
  quantization: string;
  download_size_bytes: number;
  download_size_display: string;
  ram_required_mb: number;
  ram_display: string;
  disk_required_mb: number;
  recommended_tier: number;
  recommended_tier_name: string;
  speed_rating: string;
  provider: string;
  ollama_tag: string;
  sha256: string;
  filename: string;
  capabilities: string[];
  description: string;
  is_default_tier1?: boolean;
  is_default_tier2?: boolean;
  is_default_tier3?: boolean;
}

export interface ModelItem {
  id: string;
  name: string;
  provider: string;
  size_bytes: number;
  ram_estimate_mb: number;
  suitable_for_6gb: number | boolean;
  is_active: number | boolean;
}

export interface DiagnosticLog {
  id: number;
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG';
  component: string;
  message: string;
  metadata: string | null;
  created_at: string;
}

export interface SetupCheck {
  status: 'PASS' | 'INFO' | 'WARNING' | 'FAIL';
  details?: string;
  profile?: DeviceProfile;
}

export type SetupStateMachineState =
  | 'NOT_STARTED'
  | 'SCANNING_DEVICE'
  | 'ANALYZING_CAPABILITIES'
  | 'WAITING_FOR_MODEL_SELECTION'
  | 'DOWNLOADING_MODEL'
  | 'VERIFYING_MODEL'
  | 'TESTING_MODEL'
  | 'CONFIGURING_RUNTIME'
  | 'READY'
  | 'FAILED'
  | 'CANCELLED';

export interface DownloadProgress {
  status: string;
  downloaded_bytes: number;
  total_bytes: number;
  percent: number;
  speed_mbps: number;
  error?: string | null;
}

export interface VerificationStatus {
  passed?: boolean;
  details?: string;
  info?: {
    model_id?: string;
    verified_at?: string;
    sha256?: string;
    actual_sha256?: string;
    file_path?: string;
    file_size_bytes?: number;
  };
}

export interface RuntimeTestStatus {
  passed?: boolean;
  model_id?: string;
  model_name?: string;
  latency_ms?: number;
  tokens_per_second?: number;
  action_proposed?: string;
  target_node?: string;
  tested_at?: string;
  error?: string;
}

export interface SetupStatus {
  ready: boolean;
  completed?: boolean;
  current_state?: SetupStateMachineState;
  setup_version?: string;
  checkpoint?: string;
  selected_model?: string;
  recommended_model?: ModelCatalogItem;
  profile?: DeviceProfile;
  tier?: number;
  tier_name?: string;
  download_progress?: DownloadProgress;
  verification_status?: VerificationStatus;
  runtime_test_status?: RuntimeTestStatus;
  failure_info?: any;
  checks?: Record<string, SetupCheck>;
  timestamp?: string;
}
