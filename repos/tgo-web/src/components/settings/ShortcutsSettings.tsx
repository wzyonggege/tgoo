import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Keyboard, Plus, Save, Trash2 } from 'lucide-react';
import { useToast } from '@/hooks/useToast';
import {
  quickRepliesApiService,
  type QuickReply,
  type QuickReplyCreateRequest,
} from '@/services/quickRepliesApi';

interface QuickReplyFormState {
  id: string | null;
  title: string;
  shortcut: string;
  content: string;
  category: string;
  sortOrder: number;
  isActive: boolean;
}

const EMPTY_FORM: QuickReplyFormState = {
  id: null,
  title: '',
  shortcut: '',
  content: '',
  category: '',
  sortOrder: 100,
  isActive: true,
};

const ShortcutsSettings: React.FC = () => {
  const { t } = useTranslation();
  const { showSuccess, showError } = useToast();
  const [items, setItems] = useState<QuickReply[]>([]);
  const [search, setSearch] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [loading, setLoading] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [form, setForm] = useState<QuickReplyFormState>(EMPTY_FORM);

  const loadQuickReplies = useCallback(async () => {
    setLoading(true);
    try {
      const response = await quickRepliesApiService.listQuickReplies({
        active_only: false,
        limit: 500,
        offset: 0,
      });
      setItems(response.data);
    } catch (error) {
      const message = error instanceof Error ? error.message : t('settings.shortcuts.error.load', '加载快捷回复失败');
      showError(t('common.error', '错误'), message);
    } finally {
      setLoading(false);
    }
  }, [showError, t]);

  useEffect(() => {
    void loadQuickReplies();
  }, [loadQuickReplies]);

  const categories = useMemo(() => {
    const unique = new Set<string>();
    items.forEach((item) => {
      if (item.category) unique.add(item.category);
    });
    return ['all', ...Array.from(unique).sort()];
  }, [items]);

  const filteredItems = useMemo(() => {
    const lowerSearch = search.trim().toLowerCase();
    return items.filter((item) => {
      if (categoryFilter !== 'all' && item.category !== categoryFilter) return false;
      if (!lowerSearch) return true;
      return (
        item.title.toLowerCase().includes(lowerSearch) ||
        item.shortcut.toLowerCase().includes(lowerSearch) ||
        item.content.toLowerCase().includes(lowerSearch)
      );
    });
  }, [items, search, categoryFilter]);

  const selectItem = (item: QuickReply): void => {
    setForm({
      id: item.id,
      title: item.title,
      shortcut: item.shortcut,
      content: item.content,
      category: item.category || '',
      sortOrder: item.sort_order,
      isActive: item.is_active,
    });
  };

  const resetForm = (): void => {
    setForm(EMPTY_FORM);
  };

  const handleSave = async (): Promise<void> => {
    const normalizedShortcut = form.shortcut.trim().replace(/^\/+/, '').toLowerCase();
    if (!form.title.trim() || !normalizedShortcut || !form.content.trim()) {
      showError(
        t('common.error', '错误'),
        t('settings.shortcuts.error.required', '标题、快捷词和内容均为必填项')
      );
      return;
    }

    const payload: QuickReplyCreateRequest = {
      title: form.title.trim(),
      shortcut: normalizedShortcut,
      content: form.content.trim(),
      category: form.category.trim() || null,
      sort_order: form.sortOrder,
      is_active: form.isActive,
    };

    setSaving(true);
    try {
      if (form.id) {
        await quickRepliesApiService.updateQuickReply(form.id, payload);
      } else {
        await quickRepliesApiService.createQuickReply(payload);
      }
      showSuccess(
        t('common.success', '成功'),
        t('settings.shortcuts.saved', '快捷回复已保存')
      );
      resetForm();
      await loadQuickReplies();
    } catch (error) {
      const message = error instanceof Error ? error.message : t('settings.shortcuts.error.save', '保存快捷回复失败');
      showError(t('common.error', '错误'), message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (item: QuickReply): Promise<void> => {
    if (!window.confirm(t('settings.shortcuts.deleteConfirm', '确定删除该快捷回复吗？'))) {
      return;
    }
    try {
      await quickRepliesApiService.deleteQuickReply(item.id);
      showSuccess(t('common.success', '成功'), t('settings.shortcuts.deleted', '快捷回复已删除'));
      if (form.id === item.id) resetForm();
      await loadQuickReplies();
    } catch (error) {
      const message = error instanceof Error ? error.message : t('settings.shortcuts.error.delete', '删除快捷回复失败');
      showError(t('common.error', '错误'), message);
    }
  };

  return (
    <div className="p-6 space-y-4 h-full">
      <div className="flex items-center gap-2">
        <Keyboard className="w-5 h-5 text-gray-600 dark:text-gray-400" />
        <h2 className="text-lg font-medium text-gray-800 dark:text-gray-100">{t('settings.shortcuts.title', '快捷回复')}</h2>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4 h-[calc(100%-3rem)] min-h-[480px]">
        <section className="xl:col-span-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 flex flex-col min-h-0">
          <div className="flex gap-2 mb-3">
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('settings.shortcuts.search', '搜索标题、快捷词、内容')}
              className="flex-1 px-3 py-2 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-transparent dark:text-gray-100"
            />
            <select
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value)}
              className="px-3 py-2 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-transparent dark:text-gray-100"
            >
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat === 'all' ? t('settings.shortcuts.allCategories', '全部分类') : cat}
                </option>
              ))}
            </select>
          </div>
          <div className="overflow-y-auto flex-1 space-y-2 pr-1">
            {loading ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">{t('common.loading', '加载中...')}</p>
            ) : filteredItems.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">{t('settings.shortcuts.empty', '暂无快捷回复')}</p>
            ) : (
              filteredItems.map((item) => (
                <div
                  key={item.id}
                  className={`rounded-md border p-3 cursor-pointer transition-colors ${
                    form.id === item.id
                      ? 'border-blue-400 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-blue-300'
                  }`}
                  onClick={() => selectItem(item)}
                >
                  <div className="flex items-center justify-between">
                    <div className="font-medium text-sm text-gray-900 dark:text-gray-100">{item.title}</div>
                    <div className="text-xs text-blue-600 dark:text-blue-300 font-mono">/{item.shortcut}</div>
                  </div>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">{item.content}</p>
                  <div className="flex items-center justify-between mt-2 text-[11px] text-gray-500 dark:text-gray-400">
                    <span>{item.category || t('settings.shortcuts.noCategory', '未分类')}</span>
                    <span>{t('settings.shortcuts.usedCount', '使用 {{count}} 次', { count: item.usage_count })}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="xl:col-span-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-100">
              {form.id ? t('settings.shortcuts.edit', '编辑快捷回复') : t('settings.shortcuts.create', '新建快捷回复')}
            </h3>
            <button
              onClick={resetForm}
              className="text-xs inline-flex items-center gap-1 px-2 py-1 rounded border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              <Plus className="w-3 h-3" />
              {t('settings.shortcuts.new', '新建')}
            </button>
          </div>
          <div className="space-y-3">
            <input
              value={form.title}
              onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
              placeholder={t('settings.shortcuts.form.title', '标题')}
              className="w-full px-3 py-2 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-transparent dark:text-gray-100"
            />
            <input
              value={form.shortcut}
              onChange={(event) => setForm((prev) => ({ ...prev, shortcut: event.target.value }))}
              placeholder={t('settings.shortcuts.form.shortcut', '快捷词（如 refund）')}
              className="w-full px-3 py-2 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-transparent font-mono dark:text-gray-100"
            />
            <input
              value={form.category}
              onChange={(event) => setForm((prev) => ({ ...prev, category: event.target.value }))}
              placeholder={t('settings.shortcuts.form.category', '分类（可选）')}
              className="w-full px-3 py-2 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-transparent dark:text-gray-100"
            />
            <textarea
              value={form.content}
              onChange={(event) => setForm((prev) => ({ ...prev, content: event.target.value }))}
              placeholder={t('settings.shortcuts.form.content', '回复内容')}
              rows={6}
              className="w-full px-3 py-2 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-transparent resize-none dark:text-gray-100"
            />
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-600 dark:text-gray-400">{t('settings.shortcuts.form.order', '排序')}</label>
              <input
                type="number"
                value={form.sortOrder}
                min={0}
                max={9999}
                onChange={(event) => setForm((prev) => ({ ...prev, sortOrder: Number(event.target.value) || 0 }))}
                className="w-24 px-2 py-1 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-transparent dark:text-gray-100"
              />
              <label className="ml-auto text-xs inline-flex items-center gap-1 text-gray-600 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={form.isActive}
                  onChange={(event) => setForm((prev) => ({ ...prev, isActive: event.target.checked }))}
                />
                {t('settings.shortcuts.form.active', '启用')}
              </label>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => void handleSave()}
                disabled={saving}
                className="inline-flex items-center gap-1 px-3 py-2 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60"
              >
                <Save className="w-4 h-4" />
                {saving ? t('common.saving', '保存中...') : t('common.save', '保存')}
              </button>
              {form.id && (
                <button
                  onClick={() => {
                    const target = items.find((item) => item.id === form.id);
                    if (target) void handleDelete(target);
                  }}
                  className="inline-flex items-center gap-1 px-3 py-2 text-sm rounded-md border border-red-200 text-red-600 hover:bg-red-50 dark:border-red-700/40 dark:hover:bg-red-900/20"
                >
                  <Trash2 className="w-4 h-4" />
                  {t('common.delete', '删除')}
                </button>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default ShortcutsSettings;
