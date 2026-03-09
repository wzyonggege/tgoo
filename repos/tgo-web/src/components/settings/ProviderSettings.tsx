import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CirclePlus,
  Cpu,
  ExternalLink,
  Eye,
  EyeOff,
  KeyRound,
  Link2,
  Loader2,
  PencilLine,
  Shield,
  Star,
  Trash2,
  UserPlus,
  X,
} from 'lucide-react';
import { useToast } from '@/hooks/useToast';
import { useAuthStore } from '@/stores/authStore';
import aiConfigApi, {
  type AIProviderConfig,
  type CreateAIProviderConfigRequest,
  type UpdateAIProviderConfigRequest,
} from '@/services/aiConfigApi';
import { showApiError, showSuccess } from '@/utils/toastHelpers';

const FASTGPT_DOC_URL = 'https://doc.fastgpt.io/docs/introduction/development/openapi/chat';

interface FormState {
  name: string;
  provider: string;
  api_base_url: string;
  api_key: string;
  is_default: boolean;
}

interface AIConfigDialogProps {
  open: boolean;
  config?: AIProviderConfig | null;
  isLoading?: boolean;
  onClose: () => void;
  onSubmit: (payload: CreateAIProviderConfigRequest | UpdateAIProviderConfigRequest) => Promise<void>;
}

const createEmptyForm = (): FormState => ({
  name: '',
  provider: 'custom',
  api_base_url: '',
  api_key: '',
  is_default: false,
});

const toFormState = (config: AIProviderConfig): FormState => ({
  name: config.name,
  provider: config.provider || 'custom',
  api_base_url: config.api_base_url || '',
  api_key: config.api_key || '',
  is_default: config.is_default,
});

const sortConfigs = (configs: AIProviderConfig[]): AIProviderConfig[] => {
  return [...configs].sort((left, right) => {
    if (left.is_default !== right.is_default) {
      return left.is_default ? -1 : 1;
    }
    return left.name.localeCompare(right.name, 'zh-CN');
  });
};

const AIConfigDialog: React.FC<AIConfigDialogProps> = ({
  open,
  config,
  isLoading = false,
  onClose,
  onSubmit,
}) => {
  const { t } = useTranslation();
  const isEditing = Boolean(config);
  const [form, setForm] = useState<FormState>(createEmptyForm());
  const [showApiKey, setShowApiKey] = useState<boolean>(false);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});

  useEffect(() => {
    setForm(config ? toFormState(config) : createEmptyForm());
    setErrors({});
    setShowApiKey(false);
  }, [config, open]);

  const handleInputChange = (field: keyof FormState) => (
    event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    const value = field === 'is_default'
      ? (event.target as HTMLInputElement).checked
      : event.target.value;
    setForm((prev) => ({ ...prev, [field]: value as FormState[keyof FormState] }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const validate = (): boolean => {
    const nextErrors: Partial<Record<keyof FormState, string>> = {};
    if (!form.name.trim()) {
      nextErrors.name = t('settings.providers.errors.nameRequired', '请输入名称');
    }
    if (!form.api_base_url.trim()) {
      nextErrors.api_base_url = t('settings.providers.errors.baseUrlRequired', '请输入 API Base URL');
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!validate()) return;

    if (isEditing && config) {
      const payload: UpdateAIProviderConfigRequest = {};
      if (config.name !== form.name) payload.name = form.name.trim();
      if (config.provider !== form.provider) payload.provider = form.provider.trim() || 'custom';
      if (config.api_base_url !== form.api_base_url) payload.api_base_url = form.api_base_url.trim();
      if ((config.api_key || '') !== form.api_key) payload.api_key = form.api_key.trim() || null;
      if (config.is_default !== form.is_default) payload.is_default = form.is_default;
      await onSubmit(payload);
      return;
    }

    const payload: CreateAIProviderConfigRequest = {
      name: form.name.trim(),
      provider: form.provider.trim() || 'custom',
      api_base_url: form.api_base_url.trim(),
      api_key: form.api_key.trim() || null,
      is_default: form.is_default,
    };
    await onSubmit(payload);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="w-full max-w-2xl rounded-xl bg-white shadow-xl dark:bg-gray-800 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <UserPlus className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {isEditing
                ? t('settings.providers.editor.editTitle', '编辑 AI 回复接入')
                : t('settings.providers.editor.newTitle', '新增 AI 回复接入')}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-700 dark:hover:text-gray-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5 p-6">
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-200">
                {t('settings.providers.fields.name', '名称')}
              </label>
              <div className="relative">
                <PencilLine className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  value={form.name}
                  onChange={handleInputChange('name')}
                  placeholder={t('settings.providers.placeholder.name', '例如：官网客服 AI') as string}
                  className="w-full rounded-md border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
                />
              </div>
              {errors.name && <p className="mt-2 text-xs text-red-500">{errors.name}</p>}
            </div>

            <div>
              <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-200">
                {t('settings.providers.fields.kind', '接入类型')}
              </label>
              <div className="relative">
                <Cpu className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-gray-400" />
                <select
                  value={form.provider}
                  onChange={handleInputChange('provider')}
                  className="w-full rounded-md border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
                >
                  <option value="custom">{t('settings.providers.provider.custom', '自定义 (FastGPT/OpenAI 兼容)')}</option>
                </select>
              </div>
            </div>

            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-200">
                {t('settings.providers.fields.baseUrl', 'API Base URL')}
              </label>
              <div className="relative">
                <Link2 className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-gray-400" />
                <input
                  type="url"
                  value={form.api_base_url}
                  onChange={handleInputChange('api_base_url')}
                  placeholder={t('settings.providers.placeholder.baseUrl', 'https://fastgpt.example.com') as string}
                  className="w-full rounded-md border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
                />
              </div>
              {errors.api_base_url && <p className="mt-2 text-xs text-red-500">{errors.api_base_url}</p>}
              <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
                {t('settings.providers.helper.baseUrl', '这里只填写基础域名，系统会自动请求兼容 OpenAI 的聊天接口。')}
              </p>
            </div>

            <div className="md:col-span-2">
              <label className="mb-2 block text-sm font-medium text-gray-700 dark:text-gray-200">
                {t('settings.providers.fields.apiKey', 'API Key')}
              </label>
              <div className="relative">
                <KeyRound className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-gray-400" />
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={form.api_key}
                  onChange={handleInputChange('api_key')}
                  placeholder={t('settings.providers.placeholder.apiKey', '在此粘贴 FastGPT/OpenAI 的 API Key') as string}
                  className="w-full rounded-md border border-gray-300 bg-white py-2.5 pl-10 pr-11 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey((prev) => !prev)}
                  className="absolute right-3 top-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                  aria-label={showApiKey ? t('settings.providers.hideKey', '隐藏密钥') : t('settings.providers.showKey', '显示密钥')}
                >
                  {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>

          <label className="flex items-center gap-3 rounded-lg border border-gray-200 px-4 py-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-200">
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={handleInputChange('is_default')}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span>{t('settings.providers.fields.default', '设为系统默认 AI 回复接入')}</span>
          </label>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 dark:border-gray-600 dark:text-gray-200"
            >
              {t('common.cancel', '取消')}
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
              {isEditing ? t('common.save', '保存') : t('common.create', '创建')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const ProviderSettings: React.FC = () => {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'admin';

  const [configs, setConfigs] = useState<AIProviderConfig[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState<boolean>(false);
  const [editingConfig, setEditingConfig] = useState<AIProviderConfig | null>(null);

  const fetchConfigs = useCallback(async () => {
    if (!isAdmin) {
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const nextConfigs = await aiConfigApi.listConfigs();
      setConfigs(sortConfigs(nextConfigs));
      setError(null);
    } catch (fetchError) {
      const message = fetchError instanceof Error
        ? fetchError.message
        : t('settings.providers.error.load', '加载 AI 回复接入失败，请稍后重试。');
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [isAdmin, t]);

  useEffect(() => {
    void fetchConfigs();
  }, [fetchConfigs]);

  const defaultConfig = useMemo(
    () => configs.find((item) => item.is_default) ?? null,
    [configs],
  );

  const handleCreateClick = () => {
    setEditingConfig(null);
    setDialogOpen(true);
  };

  const handleEditClick = (config: AIProviderConfig) => {
    setEditingConfig(config);
    setDialogOpen(true);
  };

  const handleDialogSubmit = async (payload: CreateAIProviderConfigRequest | UpdateAIProviderConfigRequest) => {
    setSubmitting(true);
    try {
      if (editingConfig) {
        await aiConfigApi.updateConfig(editingConfig.id, payload as UpdateAIProviderConfigRequest);
      } else {
        await aiConfigApi.createConfig(payload as CreateAIProviderConfigRequest);
      }
      await fetchConfigs();
      setDialogOpen(false);
      setEditingConfig(null);
      showSuccess(
        showToast,
        editingConfig
          ? t('settings.providers.toast.updated', 'AI 回复接入已保存')
          : t('settings.providers.toast.created', 'AI 回复接入已新增'),
      );
    } catch (submitError) {
      showApiError(showToast, submitError);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (config: AIProviderConfig) => {
    const confirmed = window.confirm(
      t('settings.providers.deleteConfirm', '确定删除这个 AI 回复接入吗？渠道会自动回退到系统默认配置。'),
    );
    if (!confirmed) return;

    setDeletingId(config.id);
    try {
      await aiConfigApi.deleteConfig(config.id);
      await fetchConfigs();
      showSuccess(showToast, t('settings.providers.toast.deleted', 'AI 回复接入已删除'));
    } catch (deleteError) {
      showApiError(showToast, deleteError);
    } finally {
      setDeletingId(null);
    }
  };

  if (!isAdmin) {
    return (
      <div className="p-6">
        <div className="rounded-xl border border-gray-200 bg-white p-6 text-sm text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300">
          <h2 className="text-lg font-semibold">{t('settings.providers.title', 'AI 回复接入')}</h2>
          <p className="mt-2">
            {t('settings.providers.permission', '只有管理员可以管理 AI 回复接入配置，请联系管理员。')}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">
            {t('settings.providers.title', 'AI 回复接入')}
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {t('settings.providers.subtitle', '集中管理多个 FastGPT / OpenAI 兼容接入，并在渠道中选择对应的回复 AI。')}
          </p>
        </div>
        <button
          type="button"
          onClick={handleCreateClick}
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <CirclePlus className="h-4 w-4" />
          {t('settings.providers.actions.create', '新增 AI 回复')}
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800 overflow-hidden">
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 dark:border-gray-700">
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
            {t('settings.providers.listTitle', '已配置接入')}
          </h2>
          <button
            type="button"
            onClick={() => { void fetchConfigs(); }}
            className="text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            {t('common.refresh', '刷新')}
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center gap-3 px-6 py-10 text-gray-500 dark:text-gray-400">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>{t('settings.providers.loading', '加载中...')}</span>
          </div>
        ) : !configs.length ? (
          <div className="px-6 py-10 text-center text-sm text-gray-500 dark:text-gray-400">
            {t('settings.providers.empty', '还没有配置 AI 回复接入，点击右上角开始新增。')}
          </div>
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {configs.map((config) => (
              <div key={config.id} className="flex items-center justify-between gap-4 px-5 py-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <div className="truncate font-medium text-gray-900 dark:text-gray-100">{config.name}</div>
                    {config.is_default && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
                        <Star className="h-3 w-3" />
                        {t('common.default', '默认')}
                      </span>
                    )}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
                    <span>{config.provider}</span>
                    <span>{config.api_base_url}</span>
                    {defaultConfig?.id === config.id && (
                      <span>{t('settings.providers.defaultInUse', '系统默认接入')}</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleEditClick(config)}
                    className="inline-flex items-center gap-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700"
                  >
                    <PencilLine className="h-4 w-4" />
                    {t('common.edit', '编辑')}
                  </button>
                  <button
                    type="button"
                    onClick={() => { void handleDelete(config); }}
                    disabled={deletingId === config.id}
                    className="inline-flex items-center gap-1 rounded-md border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-60 dark:border-red-500/40 dark:text-red-300 dark:hover:bg-red-500/10"
                  >
                    {deletingId === config.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                    {t('common.delete', '删除')}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2 font-semibold text-gray-900 dark:text-gray-100">
            <Shield className="h-4 w-4 text-emerald-500" />
            {t('settings.providers.note.secure', '密钥安全提示')}
          </div>
          <p className="mt-3 text-sm text-gray-600 dark:text-gray-300">
            {t('settings.providers.note.description', '配置会保存在服务器数据库中，仅管理员可修改。确保 API Key 具有最小权限，并定期轮换。')}
          </p>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
          <div className="flex items-center gap-2 font-semibold text-gray-900 dark:text-gray-100">
            <Cpu className="h-4 w-4 text-blue-500" />
            {t('settings.providers.helper.fastgpt', '如何获取 FastGPT API')}
          </div>
          <ol className="mt-3 list-inside list-decimal space-y-2 text-sm text-gray-600 dark:text-gray-300">
            <li>{t('settings.providers.helper.steps.0', '在 FastGPT 控制台中创建 OpenAPI Key')}</li>
            <li>{t('settings.providers.helper.steps.1', '复制兼容 OpenAI 的 Base URL')}</li>
            <li>{t('settings.providers.helper.steps.2', '将上述信息粘贴到新增弹窗中并保存')}</li>
          </ol>
          <a
            href={FASTGPT_DOC_URL}
            target="_blank"
            rel="noreferrer"
            className="mt-4 inline-flex items-center gap-2 text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            {t('settings.providers.docs', '查看 FastGPT 文档')}
            <ExternalLink className="h-4 w-4" />
          </a>
        </div>
      </div>

      <AIConfigDialog
        open={dialogOpen}
        config={editingConfig}
        isLoading={submitting}
        onClose={() => {
          if (submitting) return;
          setDialogOpen(false);
          setEditingConfig(null);
        }}
        onSubmit={handleDialogSubmit}
      />
    </div>
  );
};

export default ProviderSettings;
