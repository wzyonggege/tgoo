import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown } from 'lucide-react';
import { createPortal } from 'react-dom';

export type ChatTabType = 'mine' | 'unassigned' | 'recent' | 'all' | 'completed' | 'manual';

interface ChatListTabsProps {
  activeTab: ChatTabType;
  onTabChange: (tab: ChatTabType) => void;
  counts: {
    mine: number;
    unassigned: number;
  };
}

export const ChatListTabs: React.FC<ChatListTabsProps> = ({ activeTab, onTabChange, counts }) => {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const moreButtonRef = useRef<HTMLButtonElement>(null);
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0, opacity: 1 });
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, right: 0 });

  const allTabs = useMemo(() => [
    { key: 'mine' as ChatTabType, label: t('chat.list.tabs.mine', '我的'), count: counts.mine > 0 ? counts.mine : undefined },
    { key: 'unassigned' as ChatTabType, label: t('chat.list.tabs.unassigned', '未分配'), count: counts.unassigned > 0 ? counts.unassigned : undefined },
    { key: 'all' as ChatTabType, label: t('chat.list.tabs.all', '全部') },
    { key: 'recent' as ChatTabType, label: t('chat.list.tabs.recent', '最近在线') },
    { key: 'completed' as ChatTabType, label: t('chat.list.tabs.completed', '已完成') },
    { key: 'manual' as ChatTabType, label: t('chat.list.tabs.manual', '转人工') },
  ], [t, counts.mine, counts.unassigned]);

  const visibleTabs = allTabs.slice(0, 3);
  const hiddenTabs = allTabs.slice(3);
  const isActiveInMore = hiddenTabs.some((tab) => tab.key === activeTab);

  useEffect(() => {
    if (!containerRef.current) return;

    const activeButton = containerRef.current.querySelector(`[data-tab="${activeTab}"]`) as HTMLElement | null;
    if (activeButton) {
      setIndicatorStyle({
        left: activeButton.offsetLeft,
        width: activeButton.offsetWidth,
        opacity: 1,
      });
      return;
    }

    if (isActiveInMore && moreButtonRef.current) {
      setIndicatorStyle({
        left: moreButtonRef.current.offsetLeft,
        width: moreButtonRef.current.offsetWidth,
        opacity: 1,
      });
      return;
    }

    setIndicatorStyle((prev) => ({ ...prev, opacity: 0 }));
  }, [activeTab, isActiveInMore]);

  const toggleMore = (event: React.MouseEvent) => {
    event.stopPropagation();
    if (!moreButtonRef.current) return;
    const rect = moreButtonRef.current.getBoundingClientRect();
    setDropdownPos({
      top: rect.bottom + window.scrollY,
      right: window.innerWidth - rect.right,
    });
    setIsMoreOpen((prev) => !prev);
  };

  useEffect(() => {
    const handleClickOutside = () => setIsMoreOpen(false);
    if (isMoreOpen) {
      window.addEventListener('click', handleClickOutside);
    }
    return () => window.removeEventListener('click', handleClickOutside);
  }, [isMoreOpen]);

  return (
    <div
      ref={containerRef}
      className="relative flex items-stretch px-4 gap-5 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 overflow-hidden"
    >
      {visibleTabs.map((tab) => {
        const isActive = activeTab === tab.key;
        return (
          <button
            key={tab.key}
            data-tab={tab.key}
            onClick={() => onTabChange(tab.key)}
            className={`
              relative py-2.5 text-[13px] font-medium transition-all duration-200 outline-none
              flex items-center gap-1.5 whitespace-nowrap
              ${isActive
                ? 'text-gray-900 dark:text-white'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}
            `}
          >
            <span>{tab.label}</span>
            {tab.count !== undefined && (
              <span className="text-[11px] tabular-nums text-gray-400 dark:text-gray-500">{tab.count}</span>
            )}
          </button>
        );
      })}

      {hiddenTabs.length > 0 && (
        <button
          ref={moreButtonRef}
          onClick={toggleMore}
          className={`
            relative py-2.5 text-[13px] font-medium transition-all duration-200 outline-none
            flex items-center gap-1 min-w-[40px] justify-center
            ${isActiveInMore || isMoreOpen
              ? 'text-gray-900 dark:text-white'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}
          `}
        >
          <span>{t('common.more', '更多')}</span>
          <ChevronDown size={14} className={`transition-transform duration-200 ${isMoreOpen ? 'rotate-180' : ''}`} />
        </button>
      )}

      <div
        className="absolute bottom-0 h-0.5 bg-blue-500 dark:bg-blue-400 rounded-full transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
        style={{
          left: indicatorStyle.left,
          width: indicatorStyle.width,
          opacity: indicatorStyle.opacity,
          transform: 'translateZ(0)',
        }}
      />

      {isMoreOpen && createPortal(
        <div
          className="fixed z-[1000] bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl py-1 min-w-[120px] animate-in fade-in zoom-in-95 duration-100"
          style={{
            top: dropdownPos.top + 4,
            right: dropdownPos.right,
          }}
          onClick={(event) => event.stopPropagation()}
        >
          {hiddenTabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => {
                onTabChange(tab.key);
                setIsMoreOpen(false);
              }}
              className={`
                w-full px-4 py-2 text-left text-[13px] flex items-center justify-between
                transition-colors duration-150
                ${activeTab === tab.key
                  ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'}
              `}
            >
              <span>{tab.label}</span>
              {tab.count !== undefined && (
                <span className="text-[11px] tabular-nums bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded-full min-w-[18px] text-center ml-2">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>,
        document.body,
      )}
    </div>
  );
};

export default ChatListTabs;
