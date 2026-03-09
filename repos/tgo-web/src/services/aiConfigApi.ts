import { BaseApiService } from './base/BaseApiService';

export interface AIProviderConfigOption {
  id: string;
  name: string;
  provider: string;
  is_default: boolean;
}

export interface AIProviderConfigOptionListResponse {
  items: AIProviderConfigOption[];
}

export interface AIProviderConfig {
  id: string;
  name: string;
  provider: string;
  api_base_url: string;
  api_key: string | null;
  model?: string | null;
  completions_path?: string | null;
  timeout?: number | null;
  is_default: boolean;
}

export interface AIProviderConfigListResponse {
  items: AIProviderConfig[];
}

export interface CreateAIProviderConfigRequest {
  name: string;
  provider: string;
  api_base_url: string;
  api_key?: string | null;
  model?: string | null;
  completions_path?: string | null;
  timeout?: number | null;
  is_default?: boolean;
}

export interface UpdateAIProviderConfigRequest {
  name?: string;
  provider?: string;
  api_base_url?: string;
  api_key?: string | null;
  model?: string | null;
  completions_path?: string | null;
  timeout?: number | null;
  is_default?: boolean;
}

class AIConfigApiService extends BaseApiService {
  protected readonly apiVersion = 'v1';

  protected readonly endpoints = {
    CONFIG: `/${this.apiVersion}/ai/config`,
    CONFIGS: `/${this.apiVersion}/ai/configs`,
    CONFIG_OPTIONS: `/${this.apiVersion}/ai/configs/options`,
    CONFIG_BY_ID: (id: string) => `/${this.apiVersion}/ai/configs/${id}`,
  } as const;

  async getConfig(): Promise<AIProviderConfig> {
    return this.get<AIProviderConfig>(this.endpoints.CONFIG);
  }

  async listConfigs(): Promise<AIProviderConfig[]> {
    const response = await this.get<AIProviderConfigListResponse>(this.endpoints.CONFIGS);
    return response.items;
  }

  async listConfigOptions(): Promise<AIProviderConfigOption[]> {
    const response = await this.get<AIProviderConfigOptionListResponse>(this.endpoints.CONFIG_OPTIONS);
    return response.items;
  }

  async createConfig(payload: CreateAIProviderConfigRequest): Promise<AIProviderConfig> {
    return this.post<AIProviderConfig>(this.endpoints.CONFIGS, payload);
  }

  async updateConfig(id: string, payload: UpdateAIProviderConfigRequest): Promise<AIProviderConfig> {
    return this.patch<AIProviderConfig>(this.endpoints.CONFIG_BY_ID(id), payload);
  }

  async deleteConfig(id: string): Promise<void> {
    await this.delete<void>(this.endpoints.CONFIG_BY_ID(id));
  }
}

export const aiConfigApi = new AIConfigApiService();
export default aiConfigApi;
