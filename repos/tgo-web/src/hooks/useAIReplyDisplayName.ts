import { useEffect, useMemo, useState } from 'react';
import aiConfigApi, { type AIProviderConfigOption } from '@/services/aiConfigApi';

const AI_REPLY_CHANNEL_SUFFIX = '-aireply';

let cachedOptions: AIProviderConfigOption[] | null = null;
let pendingOptionsRequest: Promise<AIProviderConfigOption[]> | null = null;

const getAIReplyIdFromChannelId = (channelId?: string): string | null => {
  if (!channelId || !channelId.endsWith(AI_REPLY_CHANNEL_SUFFIX)) {
    return null;
  }
  return channelId.slice(0, -AI_REPLY_CHANNEL_SUFFIX.length) || null;
};

const getCachedOptionName = (aiReplyId: string | null): string | null => {
  if (!aiReplyId || !cachedOptions) {
    return null;
  }
  const option = cachedOptions.find((item) => item.id === aiReplyId);
  return option?.name ?? null;
};

const loadAIReplyOptions = async (): Promise<AIProviderConfigOption[]> => {
  if (cachedOptions) {
    return cachedOptions;
  }

  if (!pendingOptionsRequest) {
    pendingOptionsRequest = aiConfigApi
      .listConfigOptions()
      .then((options) => {
        cachedOptions = options;
        return options;
      })
      .finally(() => {
        pendingOptionsRequest = null;
      });
  }

  return pendingOptionsRequest;
};

export const useAIReplyDisplayName = (channelId?: string): string | null => {
  const aiReplyId = useMemo(() => getAIReplyIdFromChannelId(channelId), [channelId]);
  const [displayName, setDisplayName] = useState<string | null>(() => getCachedOptionName(aiReplyId));

  useEffect(() => {
    setDisplayName(getCachedOptionName(aiReplyId));

    if (!aiReplyId || getCachedOptionName(aiReplyId)) {
      return;
    }

    let cancelled = false;

    const load = async (): Promise<void> => {
      try {
        const options = await loadAIReplyOptions();
        if (cancelled) {
          return;
        }
        const option = options.find((item) => item.id === aiReplyId);
        setDisplayName(option?.name ?? null);
      } catch {
        if (!cancelled) {
          setDisplayName(null);
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [aiReplyId]);

  return displayName;
};

export const isAIReplyChannelId = (channelId?: string): boolean =>
  Boolean(channelId && channelId.endsWith(AI_REPLY_CHANNEL_SUFFIX));
