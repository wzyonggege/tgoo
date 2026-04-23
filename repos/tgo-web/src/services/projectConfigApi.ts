import BaseApiService from './base/BaseApiService';

export interface ProjectAIConfigResponse {
  id: string;
  project_id: string;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  default_chat_provider_id: string | null;
  default_chat_model: string | null;
  default_embedding_provider_id: string | null;
  default_embedding_model: string | null;
}

export interface ProjectAIConfigUpdate {
  default_chat_provider_id?: string | null;
  default_chat_model?: string | null;
  default_embedding_provider_id?: string | null;
  default_embedding_model?: string | null;
}

export interface ProjectBridgeConfigResponse {
  project_id: string;
  bridge_enabled: boolean;
  bridge_bot_token: string | null;
  bridge_chat_id: string | null;
  bridge_admin_only: boolean;
}

export interface ProjectBridgeConfigUpdate {
  bridge_enabled?: boolean;
  bridge_bot_token?: string | null;
  bridge_chat_id?: string | null;
  bridge_admin_only?: boolean;
}

export interface ProjectBridgeChatProbeRequest {
  bot_token: string;
}

export interface ProjectBridgeChatCandidate {
  chat_id: string;
  title: string;
  type: string;
  username: string | null;
  is_forum: boolean;
}

export interface ProjectBridgeChatProbeResponse {
  bot_id: number;
  bot_username: string | null;
  chats: ProjectBridgeChatCandidate[];
  warning: string | null;
}

export interface ProjectBridgeObservabilitySummary {
  total_bindings: number;
  pending_outbox: number;
  processing_outbox: number;
  failed_outbox: number;
  completed_outbox: number;
  last_binding_at: string | null;
  last_outbox_at: string | null;
  last_failed_at: string | null;
}

export interface ProjectBridgeObservabilityFailure {
  outbox_id: string;
  binding_id: string;
  status: string;
  retry_count: number;
  error_message: string | null;
  dedupe_key: string;
  fetched_at: string;
  processed_at: string | null;
  source_platform_id: string | null;
  source_platform_name: string | null;
  source_display_name: string | null;
  source_from_uid: string | null;
  telegram_chat_id: string | null;
  topic_id: number | null;
  topic_name: string | null;
}

export interface ProjectBridgeObservabilityBinding {
  binding_id: string;
  source_platform_id: string;
  source_platform_name: string | null;
  source_platform_type: string;
  source_display_name: string | null;
  source_from_uid: string;
  telegram_chat_id: string;
  topic_id: number | null;
  topic_name: string | null;
  last_message_at: string | null;
  updated_at: string;
}

export interface ProjectBridgeObservabilityResponse {
  project_id: string;
  summary: ProjectBridgeObservabilitySummary;
  recent_failures: ProjectBridgeObservabilityFailure[];
  recent_bindings: ProjectBridgeObservabilityBinding[];
}

class ProjectConfigApiService extends BaseApiService {
  protected readonly apiVersion = 'v1';
  protected readonly endpoints = {
    AI_CONFIG: (projectId: string) => `/${this.apiVersion}/projects/${projectId}/ai-config`,
    BRIDGE_CONFIG: (projectId: string) => `/${this.apiVersion}/projects/${projectId}/bridge-config`,
    BRIDGE_PROBE_CHATS: (projectId: string) => `/${this.apiVersion}/projects/${projectId}/bridge-config/probe-chats`,
    BRIDGE_OBSERVABILITY: (projectId: string) => `/${this.apiVersion}/projects/${projectId}/bridge-observability`,
  } as const;

  private aiConfigEndpoint(projectId: string) {
    return this.endpoints.AI_CONFIG(projectId);
  }

  private bridgeConfigEndpoint(projectId: string) {
    return this.endpoints.BRIDGE_CONFIG(projectId);
  }

  private bridgeProbeChatsEndpoint(projectId: string) {
    return this.endpoints.BRIDGE_PROBE_CHATS(projectId);
  }

  private bridgeObservabilityEndpoint(projectId: string) {
    return this.endpoints.BRIDGE_OBSERVABILITY(projectId);
  }

  async getAIConfig(projectId: string): Promise<ProjectAIConfigResponse> {
    return this.get<ProjectAIConfigResponse>(this.aiConfigEndpoint(projectId));
  }

  async upsertAIConfig(projectId: string, payload: ProjectAIConfigUpdate): Promise<ProjectAIConfigResponse> {
    return this.put<ProjectAIConfigResponse>(this.aiConfigEndpoint(projectId), payload);
  }

  async getBridgeConfig(projectId: string): Promise<ProjectBridgeConfigResponse> {
    return this.get<ProjectBridgeConfigResponse>(this.bridgeConfigEndpoint(projectId));
  }

  async updateBridgeConfig(projectId: string, payload: ProjectBridgeConfigUpdate): Promise<ProjectBridgeConfigResponse> {
    return this.patch<ProjectBridgeConfigResponse>(this.bridgeConfigEndpoint(projectId), payload);
  }

  async probeBridgeChats(projectId: string, payload: ProjectBridgeChatProbeRequest): Promise<ProjectBridgeChatProbeResponse> {
    return this.post<ProjectBridgeChatProbeResponse>(this.bridgeProbeChatsEndpoint(projectId), payload);
  }

  async getBridgeObservability(projectId: string): Promise<ProjectBridgeObservabilityResponse> {
    return this.get<ProjectBridgeObservabilityResponse>(this.bridgeObservabilityEndpoint(projectId));
  }
}

export const projectConfigApiService = new ProjectConfigApiService();
export default projectConfigApiService;
