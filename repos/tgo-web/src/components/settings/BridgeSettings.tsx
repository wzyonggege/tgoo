import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link2, Loader2, MessageSquare, Save, Search, ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useToast } from '@/hooks/useToast';
import { useAuthStore } from '@/stores/authStore';
import projectConfigApi, {
  type ProjectBridgeChatCandidate,
  type ProjectBridgeChatProbeResponse,
  type ProjectBridgeConfigResponse,
  type ProjectBridgeConfigUpdate,
} from '@/services/projectConfigApi';

interface BridgeFormState {
  bridgeEnabled: boolean;
  bridgeBotToken: string;
  bridgeChatId: string;
  bridgeAdminOnly: boolean;
}

const EMPTY_FORM: BridgeFormState = {
  bridgeEnabled: false,
  bridgeBotToken: '',
  bridgeChatId: '',
  bridgeAdminOnly: true,
};

const toFormState = (config: ProjectBridgeConfigResponse): BridgeFormState => ({
  bridgeEnabled: config.bridge_enabled,
  bridgeBotToken: config.bridge_bot_token || '',
  bridgeChatId: config.bridge_chat_id || '',
  bridgeAdminOnly: config.bridge_admin_only,
});

const BridgeSettings: React.FC = () => {
  const { t } = useTranslation();
  const { showSuccess, showError } = useToast();
  const projectId = useAuthStore((state) => state.user?.project_id);

  const [form, setForm] = useState<BridgeFormState>(EMPTY_FORM);
  const [savedForm, setSavedForm] = useState<BridgeFormState>(EMPTY_FORM);
  const [loading, setLoading] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [probing, setProbing] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [probeResult, setProbeResult] = useState<ProjectBridgeChatProbeResponse | null>(null);

  const loadData = useCallback(async () => {
    if (!projectId) {
      setLoadError(t('settings.bridge.noProject', '当前账号没有可用项目'));
      return;
    }

    setLoading(true);
    try {
      const bridgeConfig = await projectConfigApi.getBridgeConfig(projectId);
      const nextForm = toFormState(bridgeConfig);
      setForm(nextForm);
      setSavedForm(nextForm);
      setProbeResult(null);
      setLoadError(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : t('settings.bridge.loadError', '加载桥接配置失败');
      setLoadError(message);
    } finally {
      setLoading(false);
    }
  }, [projectId, t]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const hasChanges = useMemo(() => JSON.stringify(form) !== JSON.stringify(savedForm), [form, savedForm]);

  const handleProbeChats = async (): Promise<void> => {
    if (!projectId) {
      showError(t('common.error', '错误'), t('settings.bridge.noProject', '当前账号没有可用项目'));
      return;
    }
    if (!form.bridgeBotToken.trim()) {
      showError(t('common.error', '错误'), t('settings.bridge.validation.botTokenRequired', '启用桥接时必须填写桥接 Bot Token'));
      return;
    }

    setProbing(true);
    try {
      const result = await projectConfigApi.probeBridgeChats(projectId, {
        bot_token: form.bridgeBotToken.trim(),
      });
      setProbeResult(result);
      if (result.warning) {
        showError(t('settings.bridge.probeNotice', '探测提示'), result.warning);
      } else {
        showSuccess(
          t('common.success', '成功'),
          t('settings.bridge.probeSuccess', '已探测到 {{count}} 个群', { count: result.chats.length })
        );
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : t('settings.bridge.probeError', '探测群聊失败');
      showError(t('common.error', '错误'), message);
    } finally {
      setProbing(false);
    }
  };

  const applyChatCandidate = (chat: ProjectBridgeChatCandidate): void => {
    setForm((prev) => ({ ...prev, bridgeChatId: chat.chat_id }));
  };

  const handleSave = async (): Promise<void> => {
    if (!projectId) {
      showError(t('common.error', '错误'), t('settings.bridge.noProject', '当前账号没有可用项目'));
      return;
    }

    if (form.bridgeEnabled) {
      if (!form.bridgeBotToken.trim()) {
        showError(t('common.error', '错误'), t('settings.bridge.validation.botTokenRequired', '启用桥接时必须填写桥接 Bot Token'));
        return;
      }
      if (!form.bridgeChatId.trim()) {
        showError(t('common.error', '错误'), t('settings.bridge.validation.chatIdRequired', '启用桥接时必须填写 Telegram 群 Chat ID'));
        return;
      }
    }

    const payload: ProjectBridgeConfigUpdate = {
      bridge_enabled: form.bridgeEnabled,
      bridge_bot_token: form.bridgeBotToken.trim() || null,
      bridge_chat_id: form.bridgeChatId.trim() || null,
      bridge_admin_only: form.bridgeAdminOnly,
    };

    setSaving(true);
    try {
      const saved = await projectConfigApi.updateBridgeConfig(projectId, payload);
      const nextForm = toFormState(saved);
      setForm(nextForm);
      setSavedForm(nextForm);
      showSuccess(t('common.success', '成功'), t('settings.bridge.saveSuccess', 'Telegram 中继配置已保存'));
    } catch (error) {
      const message = error instanceof Error ? error.message : t('settings.bridge.saveError', '保存桥接配置失败');
      showError(t('common.error', '错误'), message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 space-y-4 h-full">
      <div className="flex items-center gap-2">
        <MessageSquare className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        <h2 className="text-lg font-medium text-gray-800 dark:text-gray-100">
          {t('settings.bridge.title', 'Telegram 中继')}
        </h2>
      </div>

      <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-100">
        <p className="font-medium">{t('settings.bridge.summaryTitle', '项目级配置')}</p>
        <p className="mt-1">
          {t('settings.bridge.summaryText', '这里定义“全渠道 -> Telegram 群 topic”的统一中继目标，并直接配置独立桥接 Bot 的凭据。')}
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4 h-[calc(100%-5rem)] min-h-[420px]">
        <section className="xl:col-span-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-4">
          {loading ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">{t('common.loading', '加载中...')}</p>
          ) : loadError ? (
            <p className="text-sm text-red-500 dark:text-red-400">{loadError}</p>
          ) : (
            <>
              <label className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 dark:border-gray-700 px-4 py-3">
                <span>
                  <span className="block text-sm font-medium text-gray-800 dark:text-gray-100">
                    {t('settings.bridge.enableLabel', '启用 Telegram 群中继')}
                  </span>
                  <span className="block text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {t('settings.bridge.enableHint', '开启后，所有渠道用户消息都会旁路转发到选定 Telegram 群的 topic。')}
                  </span>
                </span>
                <input
                  type="checkbox"
                  checked={form.bridgeEnabled}
                  onChange={(event) => setForm((prev) => ({ ...prev, bridgeEnabled: event.target.checked }))}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
              </label>

              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-200">
                  <Link2 className="w-4 h-4" />
                  {t('settings.bridge.botTokenLabel', '桥接 Bot Token')}
                </label>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={form.bridgeBotToken}
                    onChange={(event) => setForm((prev) => ({ ...prev, bridgeBotToken: event.target.value }))}
                    placeholder={t('settings.bridge.botTokenPlaceholder', '例如: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz') as string}
                    className="flex-1 rounded-md border border-gray-200 dark:border-gray-700 bg-transparent px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
                  />
                  <button
                    type="button"
                    disabled={probing || !form.bridgeBotToken.trim()}
                    onClick={() => void handleProbeChats()}
                    className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium ${
                      !probing && form.bridgeBotToken.trim()
                        ? 'bg-slate-700 text-white hover:bg-slate-800 dark:bg-slate-600 dark:hover:bg-slate-500'
                        : 'bg-gray-200 text-gray-500 cursor-not-allowed dark:bg-gray-700 dark:text-gray-400'
                    }`}
                  >
                    {probing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                    {t('settings.bridge.probeButton', '探测群聊')}
                  </button>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t('settings.bridge.botTokenHint', '这里填写独立桥接 Bot 的 Token，它不属于任何 Telegram 渠道平台。')}
                </p>
                {probeResult && (
                  <div className="rounded-md border border-gray-200 dark:border-gray-700 p-3 space-y-2">
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {t('settings.bridge.probeSummary', 'Bot @{{username}} 最近可见的群聊', {
                        username: probeResult.bot_username || probeResult.bot_id,
                      })}
                    </div>
                    {probeResult.warning && (
                      <div className="rounded bg-amber-50 px-2 py-1 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-100">
                        {probeResult.warning}
                      </div>
                    )}
                    {probeResult.chats.length === 0 ? (
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {t('settings.bridge.probeEmpty', '暂无可见群聊，先把 Bot 拉进目标群并在群里发一条消息后再试。')}
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {probeResult.chats.map((chat) => (
                          <button
                            key={chat.chat_id}
                            type="button"
                            onClick={() => applyChatCandidate(chat)}
                            className={`w-full rounded-md border px-3 py-2 text-left transition-colors ${
                              form.bridgeChatId === chat.chat_id
                                ? 'border-blue-300 bg-blue-50 dark:border-blue-700 dark:bg-blue-900/30'
                                : 'border-gray-200 hover:border-blue-200 hover:bg-gray-50 dark:border-gray-700 dark:hover:border-blue-800 dark:hover:bg-gray-900/40'
                            }`}
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div className="min-w-0">
                                <div className="truncate text-sm font-medium text-gray-800 dark:text-gray-100">{chat.title}</div>
                                <div className="truncate text-xs text-gray-500 dark:text-gray-400">{chat.chat_id}</div>
                              </div>
                              <div className="shrink-0 text-right text-xs text-gray-500 dark:text-gray-400">
                                <div>{chat.type}</div>
                                <div>{chat.is_forum ? t('settings.bridge.forumOn', '已开启 Topic') : t('settings.bridge.forumOff', '未开启 Topic')}</div>
                              </div>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-200">
                  {t('settings.bridge.chatIdLabel', '目标群 Chat ID')}
                </label>
                <input
                  type="text"
                  value={form.bridgeChatId}
                  onChange={(event) => setForm((prev) => ({ ...prev, bridgeChatId: event.target.value }))}
                  placeholder={t('settings.bridge.chatIdPlaceholder', '例如: -1001234567890') as string}
                  className="w-full rounded-md border border-gray-200 dark:border-gray-700 bg-transparent px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {t('settings.bridge.chatIdHint', '目标群需要开启 Forum Topics，并给 Bot 建 topic 与发消息权限。')}
                </p>
              </div>

              <label className="flex items-center justify-between gap-3 rounded-lg border border-gray-200 dark:border-gray-700 px-4 py-3">
                <span className="flex items-start gap-2">
                  <ShieldCheck className="w-4 h-4 mt-0.5 text-gray-500 dark:text-gray-400" />
                  <span>
                    <span className="block text-sm font-medium text-gray-800 dark:text-gray-100">
                      {t('settings.bridge.adminOnlyLabel', '仅管理员可回发')}
                    </span>
                    <span className="block text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {t('settings.bridge.adminOnlyHint', '开启后，只有 Telegram 群管理员在 topic 内回复才会回发到原渠道。')}
                    </span>
                  </span>
                </span>
                <input
                  type="checkbox"
                  checked={form.bridgeAdminOnly}
                  onChange={(event) => setForm((prev) => ({ ...prev, bridgeAdminOnly: event.target.checked }))}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
              </label>

              <div className="flex justify-end">
                <button
                  type="button"
                  disabled={!hasChanges || saving || loading}
                  onClick={() => void handleSave()}
                  className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium ${
                    hasChanges && !saving && !loading
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-gray-200 text-gray-500 cursor-not-allowed dark:bg-gray-700 dark:text-gray-400'
                  }`}
                >
                  <Save className="w-4 h-4" />
                  {saving ? t('common.saving', '保存中...') : t('common.save', '保存')}
                </button>
              </div>
            </>
          )}
        </section>

        <section className="xl:col-span-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3">
          <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-100">
            {t('settings.bridge.statusTitle', '当前桥接状态')}
          </h3>
          <div className="rounded-md border border-gray-200 dark:border-gray-700 p-3 text-sm space-y-2">
            <p className="text-gray-700 dark:text-gray-200">
              {t('settings.bridge.statusEnabled', '是否启用')}: {form.bridgeEnabled ? t('common.enabled', '已启用') : t('common.disabled', '未启用')}
            </p>
            <p className="text-gray-700 dark:text-gray-200">
              {t('settings.bridge.statusBotToken', '桥接 Bot Token')}: {form.bridgeBotToken ? '******' : t('settings.bridge.notConfigured', '未配置')}
            </p>
            <p className="text-gray-700 dark:text-gray-200 break-all">
              {t('settings.bridge.statusChatId', '目标群 Chat ID')}: {form.bridgeChatId || t('settings.bridge.notConfigured', '未配置')}
            </p>
            <p className="text-gray-700 dark:text-gray-200">
              {t('settings.bridge.statusAdminOnly', '管理员限制')}: {form.bridgeAdminOnly ? t('settings.bridge.adminOnlyOn', '仅管理员回发') : t('settings.bridge.adminOnlyOff', '所有成员都可回发')}
            </p>
          </div>

          <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-100">
            <p className="font-medium">{t('settings.bridge.noticeTitle', '注意')}</p>
            <p className="mt-1">
              {t('settings.bridge.noticeText', '桥接是旁路中继，不会阻塞原渠道消息主链路；若 Telegram 发送失败，只影响中继，不影响用户原消息接收。')}
            </p>
          </div>
        </section>
      </div>
    </div>
  );
};

export default BridgeSettings;
