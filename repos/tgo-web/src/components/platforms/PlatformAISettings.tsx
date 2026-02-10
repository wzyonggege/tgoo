import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Bot, Clock3, Users } from 'lucide-react';
import type { Platform, PlatformAIMode } from '@/types';

interface PlatformAISettingsProps {
  platform: Platform;
  agentIds: string[];
  aiMode: PlatformAIMode;
  fallbackTimeout: number | null;
  onAgentIdsChange: (agentIds: string[]) => void;
  onAIModeChange: (mode: PlatformAIMode) => void;
  onFallbackTimeoutChange: (timeout: number | null) => void;
  defaultExpanded?: boolean;
}

/**
 * Placeholder for legacy AI team settings. Since外接 FastGPT 已接管 AI 能力，
 * 这里暂不提供额外配置，仅保留占位，避免大量平台配置页面需要条件渲染。
 */
const PlatformAISettings: React.FC<PlatformAISettingsProps> = ({
  platform,
  aiMode,
  fallbackTimeout,
  onAIModeChange,
  onFallbackTimeoutChange,
  defaultExpanded = false,
}) => {
  const { t } = useTranslation();

  const options = useMemo(
    () => [
      {
        value: 'auto' as PlatformAIMode,
        label: t('platforms.ai.auto.title', '默认由 AI 回复'),
        description: t('platforms.ai.auto.desc', '所有访客消息都会直接交给 AI 处理，人工可随时插入。'),
        icon: <Bot className="w-5 h-5 text-blue-500" />,
      },
      {
        value: 'assist' as PlatformAIMode,
        label: t('platforms.ai.assist.title', '人工优先，超时后转 AI'),
        description: t('platforms.ai.assist.desc', '先尝试分配人工客服，如果在设定时间内无人接待，则自动让 AI 接手。'),
        icon: <Clock3 className="w-5 h-5 text-amber-500" />,
      },
      {
        value: 'off' as PlatformAIMode,
        label: t('platforms.ai.off.title', '仅人工回复'),
        description: t('platforms.ai.off.desc', '所有访客消息都需要人工处理，AI 不会参与。'),
        icon: <Users className="w-5 h-5 text-gray-500" />,
      },
    ],
    [t],
  );

  const handleModeChange = (mode: PlatformAIMode) => {
    onAIModeChange(mode);
    if (mode !== 'assist') {
      onFallbackTimeoutChange(null);
    }
  };

  const assistTimeout = fallbackTimeout ?? 60;

  return (
    <details
      className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-800/60 p-5 shadow-sm"
      open={defaultExpanded}
    >
      <summary className="font-semibold text-gray-800 dark:text-gray-50 cursor-pointer select-none outline-none">
        {t('platforms.ai.sectionTitle', 'AI 回复策略')}
      </summary>
      <div className="mt-4 space-y-4">
        <p className="text-sm text-gray-600 dark:text-gray-300">
          {t(
            'platforms.ai.sectionDesc',
            '为 {name} 决定默认的应答策略，控制访客消息是直接由 AI 回复、人工优先，或完全关闭 AI。',
            { name: platform.name || platform.display_name || '' },
          )}
        </p>
        <div className="grid gap-3 md:grid-cols-3">
          {options.map((option) => {
            const active = option.value === aiMode;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => handleModeChange(option.value)}
                className={`text-left rounded-lg border p-4 transition-all ${
                  active
                    ? 'border-blue-500 bg-blue-50/70 dark:bg-blue-500/10'
                    : 'border-gray-200 hover:border-gray-300 dark:border-gray-700 dark:hover:border-gray-600'
                }`}
              >
                <div className="flex items-center gap-2">
                  {option.icon}
                  <span className="font-medium text-gray-900 dark:text-gray-100">{option.label}</span>
                </div>
                <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{option.description}</p>
              </button>
            );
          })}
        </div>
        {aiMode === 'assist' && (
          <div className="rounded-lg border border-dashed border-amber-300 dark:border-amber-600 bg-amber-50/60 dark:bg-amber-500/10 p-4">
            <label className="text-sm font-medium text-amber-900 dark:text-amber-200 flex items-center gap-2">
              <Clock3 className="w-4 h-4" />
              {t('platforms.ai.assist.timeoutLabel', 'AI 接管延迟（秒）')}
            </label>
            <div className="mt-2 flex items-center gap-2">
              <input
                type="number"
                min={0}
                max={900}
                value={assistTimeout}
                onChange={(event) => {
                  const value = Number(event.target.value);
                  if (Number.isNaN(value)) {
                    onFallbackTimeoutChange(null);
                    return;
                  }
                  const bounded = Math.max(0, Math.min(900, value));
                  onFallbackTimeoutChange(bounded);
                }}
                className="w-32 rounded-md border border-amber-200 dark:border-amber-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
              />
              <span className="text-xs text-amber-800 dark:text-amber-200">
                {t('platforms.ai.assist.timeoutHint', '0 表示一直等待人工，不会自动切换。')}
              </span>
            </div>
          </div>
        )}
      </div>
    </details>
  );
};

export default PlatformAISettings;
