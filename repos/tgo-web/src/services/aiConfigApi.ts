import { BaseApiService } from './base/BaseApiService';

export interface AIProviderConfig {
  provider: string;
  api_base_url: string;
  api_key: string | null;
  model?: string | null;
  completions_path?: string | null;
  timeout?: number | null;
}

export interface UpdateAIProviderConfigRequest {
  provider?: string;
  api_base_url?: string;
  api_key?: string | null;
}

class AIConfigApiService extends BaseApiService {
  protected readonly apiVersion = 'v1';

  protected readonly endpoints = {
    CONFIG: `/${this.apiVersion}/ai/config`,
  } as const;

  async getConfig(): Promise<AIProviderConfig> {
    return this.get<AIProviderConfig>(this.endpoints.CONFIG);
  }

  async updateConfig(payload: UpdateAIProviderConfigRequest): Promise<AIProviderConfig> {
    return this.put<AIProviderConfig>(this.endpoints.CONFIG, payload);
  }
}

export const aiConfigApi = new AIConfigApiService();
export default aiConfigApi;

