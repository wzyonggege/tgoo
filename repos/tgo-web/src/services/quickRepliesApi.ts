import { BaseApiService } from './base/BaseApiService';

export interface QuickReply {
  id: string;
  project_id: string;
  title: string;
  shortcut: string;
  content: string;
  category: string | null;
  is_active: boolean;
  sort_order: number;
  usage_count: number;
  last_used_at: string | null;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface QuickReplyListResponse {
  data: QuickReply[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

export interface QuickReplyListParams {
  q?: string;
  category?: string;
  active_only?: boolean;
  limit?: number;
  offset?: number;
}

export interface QuickReplyCreateRequest {
  title: string;
  shortcut: string;
  content: string;
  category?: string | null;
  is_active?: boolean;
  sort_order?: number;
}

export interface QuickReplyUpdateRequest {
  title?: string;
  shortcut?: string;
  content?: string;
  category?: string | null;
  is_active?: boolean;
  sort_order?: number;
}

class QuickRepliesApiService extends BaseApiService {
  protected readonly apiVersion = 'v1';
  protected readonly endpoints = {
    LIST: `/${this.apiVersion}/quick-replies`,
    DETAIL: (id: string) => `/${this.apiVersion}/quick-replies/${id}`,
    USE: (id: string) => `/${this.apiVersion}/quick-replies/${id}/use`,
  } as const;

  async listQuickReplies(params?: QuickReplyListParams): Promise<QuickReplyListResponse> {
    const qs = new URLSearchParams();
    if (params?.q) qs.append('q', params.q);
    if (params?.category) qs.append('category', params.category);
    if (params?.active_only !== undefined) qs.append('active_only', String(params.active_only));
    if (params?.limit !== undefined) qs.append('limit', String(params.limit));
    if (params?.offset !== undefined) qs.append('offset', String(params.offset));
    const endpoint = qs.toString() ? `${this.endpoints.LIST}?${qs.toString()}` : this.endpoints.LIST;
    return this.get<QuickReplyListResponse>(endpoint);
  }

  async createQuickReply(payload: QuickReplyCreateRequest): Promise<QuickReply> {
    return this.post<QuickReply>(this.endpoints.LIST, payload);
  }

  async updateQuickReply(id: string, payload: QuickReplyUpdateRequest): Promise<QuickReply> {
    return this.patch<QuickReply>(this.endpoints.DETAIL(id), payload);
  }

  async deleteQuickReply(id: string): Promise<void> {
    await this.delete<void>(this.endpoints.DETAIL(id));
  }

  async markUsed(id: string): Promise<void> {
    await this.post<void>(this.endpoints.USE(id), {});
  }
}

export const quickRepliesApiService = new QuickRepliesApiService();
