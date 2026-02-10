import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Shield, Cpu, KeyRound, Link2, Eye, EyeOff, Loader2, RefreshCw, ExternalLink } from 'lucide-react';
import { useToast } from '@/hooks/useToast';
import { useAuthStore } from '@/stores/authStore';
import aiConfigApi, { type AIProviderConfig, type UpdateAIProviderConfigRequest } from '@/services/aiConfigApi';

const FASTGPT_DOC_URL = 'https://doc.fastgpt.io/docs/introduction/development/openapi/chat';

interface FormState {
  provider: string;
  api_base_url: string;
  api_key: string;
}

const normalizeConfig = (config: AIProviderConfig): FormState => ({
  provider: config.provider || 'custom',
  api_base_url: config.api_base_url || '',
  api_key: config.api_key || '',
});

const ProviderSettings: React.FC = () => {
  const { t } = useTranslation();
  const { showSuccess, showError } = useToast();
  const { user } = useAuthStore();
  const [form, setForm] = useState<FormState>({ provider: 'custom', api_base_url: '', api_key: '' });
  const [initialConfig, setInitialConfig] = useState<FormState | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [showApiKey, setShowApiKey] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const isAdmin = user?.role === 'admin';

  const fetchConfig = useCallback(async () => {
    if (!isAdmin) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const config = await aiConfigApi.getConfig();
      const normalized = normalizeConfig(config);
      setForm(normalized);
      setInitialConfig(normalized);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : t('settings.providers.error.load', '加载 AI 配置失败，请稍后重试。');
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [isAdmin, t]);

  useEffect(() => {
    void fetchConfig();
  }, [fetchConfig]);

  const handleInputChange = (field: keyof FormState) => (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const value = event.target.value;
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const hasChanges = useMemo(() => {
    if (!initialConfig) return false;
    return (
      initialConfig.provider !== form.provider ||
      initialConfig.api_base_url !== form.api_base_url ||
      initialConfig.api_key !== form.api_key
    );
  }, [form, initialConfig]);

  const handleReset = () => {
    if (initialConfig) {
      setForm(initialConfig);
      setShowApiKey(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!hasChanges || saving) return;

    const payload: UpdateAIProviderConfigRequest = {};
    if (!initialConfig || initialConfig.provider !== form.provider) {
      payload.provider = form.provider.trim() || 'custom';
    }
    if (!initialConfig || initialConfig.api_base_url !== form.api_base_url) {
      payload.api_base_url = form.api_base_url.trim();
    }
    if (!initialConfig || initialConfig.api_key !== form.api_key) {
      const trimmedKey = form.api_key.trim();
      payload.api_key = trimmedKey ? trimmedKey : null;
    }

    setSaving(true);
    try {
      const updated = await aiConfigApi.updateConfig(payload);
      const normalized = normalizeConfig(updated);
      setForm(normalized);
      setInitialConfig(normalized);
      showSuccess(t('common.success', '操作成功'), t('settings.providers.toast.updated', 'AI 配置已保存'));
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : t('settings.providers.error.save', '保存失败，请稍后重试。');
      setError(message);
      showError(t('common.error', '发生错误'), message);
    } finally {
      setSaving(false);
    }
  };

  if (!isAdmin) {
    return (
      <div className="p-6">
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
            <Shield className="w-5 h-5" />
            <h2 className="text-lg font-semibold">{t('settings.providers.title', '模型提供商')}</h2>
          </div>
          <p className="mt-4 text-sm text-gray-600 dark:text-gray-300">
            {t('settings.providers.permission', '只有管理员可以管理 AI 接入配置，请联系管理员。')}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-2">
        <Cpu className="w-5 h-5 text-gray-600 dark:text-gray-300" />
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
          {t('settings.providers.title', '模型提供商')}
        </h2>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 dark:border-red-800/70 dark:bg-red-900/30 p-4 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[2fr,1fr]">
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6 shadow-sm">
          {loading ? (
            <div className="flex items-center justify-center py-24">
              <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
            </div>
          ) : (
            <form className="space-y-6" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-200">{t('settings.providers.fields.kind', '提供商')}</label>
                <select
                  value={form.provider}
                  onChange={handleInputChange('provider')}
                  className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="custom">{t('settings.providers.provider.custom', '自定义 (FastGPT/OpenAI 兼容)')}</option>
                  <option value="fastgpt">FastGPT</option>
                </select>
                <p className="text-xs text-gray-500 dark:text-gray-400">{t('settings.providers.description', '当前版本仅支持通过一个 OpenAI 兼容的入口来调用 FastGPT 或其他服务。')}</p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-200 flex items-center gap-2">
                  <Link2 className="w-4 h-4 text-blue-500" />
                  {t('settings.providers.fields.baseUrl', 'API Base URL')}
                </label>
                <input
                  type="url"
                  value={form.api_base_url}
                  onChange={handleInputChange('api_base_url')}
                  placeholder="https://fastgpt.example.com"
                  className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t('settings.providers.helper.baseUrl', '这里只填写基础域名（例如 https://fastgpt.example.com ），系统会自动请求 /api/v1/chat/completions 接口，确保该地址在服务器网络内可达。')}
                </p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-200 flex items-center gap-2">
                  <KeyRound className="w-4 h-4 text-blue-500" />
                  {t('settings.providers.fields.apiKey', 'API Key')}
                </label>
                <div className="relative">
                  <input
                    type={showApiKey ? 'text' : 'password'}
                    value={form.api_key}
                    onChange={handleInputChange('api_key')}
                    placeholder={t('settings.providers.placeholder.apiKey', '在此粘贴 FastGPT/OpenAI 的 API Key') as string}
                    className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey((prev) => !prev)}
                    className="absolute inset-y-0 right-2 flex items-center text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
                    aria-label={showApiKey ? t('settings.providers.hideKey', '隐藏密钥') : t('settings.providers.showKey', '显示密钥')}
                  >
                    {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t('settings.providers.helper.apiKey', '如需停用 AI，可以留空密钥字段。')}
                </p>
              </div>

              <div className="flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={handleReset}
                  disabled={!hasChanges || saving}
                  className="inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-200 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
                >
                  <RefreshCw className="w-4 h-4" />
                  {t('common.reset', '重置')}
                </button>
                <button
                  type="submit"
                  disabled={!hasChanges || saving}
                  className="inline-flex items-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                  {t('common.save', '保存')}
                </button>
              </div>
            </form>
          )}
        </div>

        <aside className="space-y-4">
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800 rounded-xl p-5">
            <div className="flex items-center gap-2 text-blue-700 dark:text-blue-200">
              <Shield className="w-4 h-4" />
              <p className="text-sm font-semibold">{t('settings.providers.note.secure', '密钥安全提示')}</p>
            </div>
            <p className="mt-3 text-xs text-blue-700/80 dark:text-blue-100/80">
              {t('settings.providers.note.description', '配置会保存在服务器数据库中，仅管理员可修改。确保 API Key 具有最小权限，并定期轮换。')}
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 space-y-3">
            <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-100">{t('settings.providers.helper.fastgpt', '如何获取 FastGPT API')}</h3>
            <ol className="text-xs text-gray-600 dark:text-gray-300 space-y-2 list-decimal list-inside">
              <li>{t('settings.providers.helper.steps.0', '在 FastGPT 控制台中创建 OpenAPI Key')}</li>
              <li>{t('settings.providers.helper.steps.1', '复制兼容 OpenAI 的 Base URL')}</li>
              <li>{t('settings.providers.helper.steps.2', '将上述信息粘贴到左侧表单并保存')}</li>
            </ol>
            <a
              href={FASTGPT_DOC_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-500"
            >
              {t('settings.providers.docs', '查看 FastGPT 文档')}
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default ProviderSettings;
