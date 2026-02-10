import { createBrowserRouter, Navigate } from 'react-router-dom';
import RootLayout from '../components/layout/RootLayout';
import Layout from '../components/layout/Layout';
import ProtectedRoute from '../components/auth/ProtectedRoute';
import ChatPage from '../pages/ChatPage';
import VisitorManagement from '../pages/VisitorManagement';
import LoginPage from '../pages/LoginPage';
import RegisterPage from '../pages/RegisterPage';
import SetupWizard from '../pages/SetupWizard';

import { useTranslation } from 'react-i18next';

// Placeholder component for platforms index that uses i18n
const PlatformPlaceholder: React.FC = () => {
  const { t } = useTranslation();
  return (
    <div className="flex-1 flex items-center justify-center p-6 text-gray-500">
      <div className="text-center">
        <p className="text-sm">{t('channels.placeholder.selectOrCreate', '请选择左侧平台，或点击“＋”创建一个新平台。')}</p>
      </div>
    </div>
  );
};
import PlatformManagement from '../pages/PlatformManagement';
import PlatformConfigPage from '../pages/PlatformConfigPage';
import SettingsLayout from '../pages/SettingsLayout';

import GeneralSettings from '../components/settings/GeneralSettings';
import ProfileSettings from '../components/settings/ProfileSettings';
import StaffSettings from '../components/settings/StaffSettings';
import NotificationSettings from '../components/settings/NotificationSettings';
import AboutSettings from '../components/settings/AboutSettings';
import ProviderSettings from '../components/settings/ProviderSettings';
import MarkdownTestPage from '../pages/MarkdownTestPage';

// Import SaaS routes if they exist (will be resolved via Vite alias or empty default)
// @ts-ignore
import { saasRoutes } from 'saas-routes';

/**
 * Router configuration for the application
 */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { path: 'setup', element: <SetupWizard /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      {
        path: '/',
        element: (
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        ),
        children: [
          { index: true, element: <Navigate to="/chat" replace /> },
          {
            path: 'chat',
            element: <ChatPage />,
            children: [
              { index: true, element: null },
              { path: ':channelType/:channelId', element: null }
            ]
          },
          { path: 'visitors', element: <VisitorManagement /> },
          {
            path: 'platforms',
            element: <PlatformManagement />,
            children: [
              { index: true, element: <PlatformPlaceholder /> },
              { path: ':platformId', element: <PlatformConfigPage /> }
            ]
          },
          {
            path: 'settings',
            element: <SettingsLayout />,
            children: [
              { index: true, element: <Navigate to="/settings/profile" replace /> },
              { path: 'profile', element: <ProfileSettings /> },
              { path: 'general', element: <GeneralSettings /> },
              { path: 'notifications', element: <NotificationSettings /> },
              { path: 'staff', element: <StaffSettings /> },
              { path: 'providers', element: <ProviderSettings /> },
              { path: 'about', element: <AboutSettings /> },
              ...(saasRoutes || [])
                .filter((r: any) => r.path.startsWith('/settings/'))
                .map((r: any) => ({
                  ...r,
                  path: r.path.replace('/settings/', '')
                }))
            ]
          },
          { path: 'test/markdown', element: <MarkdownTestPage /> },
          ...(saasRoutes || []).filter((r: any) => !r.path.startsWith('/settings/'))
        ]
      }
    ]
  }
]);
