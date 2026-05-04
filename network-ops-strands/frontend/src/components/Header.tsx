import React from 'react';
import { LayoutDashboard, Network, MessageSquare, User, LogOut } from 'lucide-react';
import type { IWhitelabelConfig } from '../types';

interface IHeaderProps {
  config: IWhitelabelConfig | null;
  currentView: 'dashboard' | 'topology' | 'chat';
  onViewChange: (view: 'dashboard' | 'topology' | 'chat') => void;
  currentUser?: string;
  onLogout?: () => void;
}

export const Header: React.FC<IHeaderProps> = ({
  config,
  currentView,
  onViewChange,
  currentUser,
  onLogout,
}) => {
  return (
    <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 shadow-sm">
      <div className="px-6 py-4">
        <div className="flex items-center justify-between">
          {/* Logo and Company Name */}
          <div className="flex items-center gap-4">
            {config?.logoUrl && (
              <img
                src={config.logoUrl}
                alt={config.companyName}
                className="h-8 w-auto"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                }}
              />
            )}
            <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">
              {config?.companyName || 'Network Operations Platform'}
            </h1>
          </div>

          <div className="flex items-center gap-4">
            {/* Navigation */}
            <nav className="flex gap-2">
              <button
                onClick={() => onViewChange('dashboard')}
                className={`px-5 py-2.5 rounded-xl font-medium transition-all flex items-center gap-2 ${
                  currentView === 'dashboard'
                    ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow-md'
                    : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700'
                }`}
              >
                <LayoutDashboard className="w-5 h-5" />
                <span>Dashboard</span>
              </button>
              <button
                onClick={() => onViewChange('topology')}
                className={`px-5 py-2.5 rounded-xl font-medium transition-all flex items-center gap-2 ${
                  currentView === 'topology'
                    ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow-md'
                    : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700'
                }`}
              >
                <Network className="w-5 h-5" />
                <span>Network Topology</span>
              </button>
              <button
                onClick={() => onViewChange('chat')}
                className={`px-5 py-2.5 rounded-xl font-medium transition-all flex items-center gap-2 ${
                  currentView === 'chat'
                    ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white shadow-md'
                    : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700'
                }`}
              >
                <MessageSquare className="w-5 h-5" />
                <span>Chat</span>
              </button>
            </nav>

            {/* Current User */}
            {currentUser && (
              <div className="flex items-center gap-2 pl-4 border-l border-slate-200 dark:border-slate-700">
                <User className="w-4 h-4 text-slate-500 dark:text-slate-400" />
                <span className="text-sm text-slate-600 dark:text-slate-400">
                  {currentUser}
                </span>
                {onLogout && (
                  <button
                    onClick={onLogout}
                    className="ml-1 p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                    title="Sign out"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
