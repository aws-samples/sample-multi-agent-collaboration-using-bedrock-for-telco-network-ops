import { useState, useEffect } from 'react';
import { Bot } from 'lucide-react';
import { Header } from './components/Header';
import { Dashboard } from './components/Dashboard';
import { NetworkTopology } from './components/NetworkTopology';
import { ChatInterface } from './components/ChatInterface';
import { LoginForm } from './components/Auth/LoginForm';
import { api } from './services/api';
import { isAgentCoreMode } from './services/agentcoreService';
import type { IWhitelabelConfig } from './types';

// Initialize Cognito auth if in AgentCore mode
const AGENTCORE = isAgentCoreMode();
if (AGENTCORE) {
  const userPoolId = import.meta.env.VITE_USER_POOL_ID || '';
  const userPoolClientId = import.meta.env.VITE_USER_POOL_CLIENT_ID || '';
  if (userPoolId && userPoolClientId) {
    import('./services/authService').then(({ configureAuth }) => {
      configureAuth({
        region: import.meta.env.VITE_REGION || 'us-east-1',
        userPoolId,
        userPoolClientId,
        identityPoolId: import.meta.env.VITE_IDENTITY_POOL_ID,
      });
    });
  }
}

function App() {
  const [config, setConfig] = useState<IWhitelabelConfig | null>(null);
  const [initialQuery, setInitialQuery] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState<string>('anonymous');
  const [currentUserDisplay, setCurrentUserDisplay] = useState<string>('');
  const [isAuthenticated, setIsAuthenticated] = useState(!AGENTCORE);

  // Persist current view in URL hash so refresh preserves it
  const getInitialView = (): 'dashboard' | 'topology' | 'chat' => {
    const hash = window.location.hash.replace('#', '');
    if (hash === 'chat' || hash === 'topology' || hash === 'dashboard') return hash;
    return 'dashboard';
  };
  const [currentView, setCurrentView] = useState<'dashboard' | 'topology' | 'chat'>(getInitialView);

  const handleViewChange = (view: 'dashboard' | 'topology' | 'chat') => {
    setCurrentView(view);
    window.location.hash = view;
  };

  // Listen for browser back/forward
  useEffect(() => {
    const onHashChange = () => {
      const hash = window.location.hash.replace('#', '') as 'dashboard' | 'topology' | 'chat';
      if (['dashboard', 'topology', 'chat'].includes(hash)) {
        setCurrentView(hash);
      }
    };
    window.addEventListener('hashchange', onHashChange);
    // Set initial hash if not present
    if (!window.location.hash) window.location.hash = 'dashboard';
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const handleNavigateToChat = (query: string, autoSend: boolean = false) => {
    setInitialQuery(JSON.stringify({ query, autoSend, ts: Date.now() }));
    handleViewChange('chat');
  };

  useEffect(() => {
    loadConfig();
    if (AGENTCORE) {
      checkAuth();
    }
  }, []);

  const checkAuth = async () => {
    try {
      const { isAuthenticated: checkIsAuth } = await import('./services/authService');
      const authed = await checkIsAuth();
      setIsAuthenticated(authed);
      if (authed) {
        const { getUser } = await import('./services/authService');
        const user = await getUser();
        if (user?.username) {
          // Use Cognito sub/username as actor ID (alphanumeric, no special chars)
          setCurrentUser(user.username);
          setCurrentUserDisplay(user.email || user.username);
        }
      }
    } catch {
      setIsAuthenticated(false);
    }
  };

  const handleLogout = async () => {
    try {
      const { logout } = await import('./services/authService');
      await logout();
    } catch (e) {
      console.warn('Logout error:', e);
    }
    // Clear local session data
    localStorage.removeItem(`netops_session_${currentUser}`);
    setIsAuthenticated(false);
    setCurrentUser('anonymous');
    setCurrentUserDisplay('');
    handleViewChange('dashboard');
  };

  const loadConfig = async () => {
    try {
      const brandingConfig = await api.getConfig();
      setConfig(brandingConfig);
      
      if (brandingConfig.primaryColor) {
        document.documentElement.style.setProperty('--color-primary', brandingConfig.primaryColor);
      }
      if (brandingConfig.secondaryColor) {
        document.documentElement.style.setProperty('--color-secondary', brandingConfig.secondaryColor);
      }
      
      document.title = brandingConfig.companyName || 'Network Operations Platform';
    } catch (error) {
      console.error('Failed to load config:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-full shadow-lg mb-4">
            <Bot className="w-8 h-8 text-white animate-pulse" />
          </div>
          <p className="text-slate-600 dark:text-slate-400 text-lg">Loading...</p>
        </div>
      </div>
    );
  }

  // Show login screen in AgentCore mode if not authenticated
  if (AGENTCORE && !isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
        <div className="w-full max-w-md px-4">
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              {config?.companyName || 'Network Operations Platform'}
            </h1>
          </div>
          <LoginForm
            onSuccess={() => {
              checkAuth();
            }}
            onForgotPassword={() => {}}
            onSignup={() => {}}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      <Header config={config} currentView={currentView} onViewChange={handleViewChange} currentUser={currentUserDisplay || currentUser} onLogout={AGENTCORE ? handleLogout : undefined} />
      <main className="flex-1 overflow-hidden">
        {currentView === 'dashboard' ? (
          <Dashboard onNavigateToChat={handleNavigateToChat} />
        ) : currentView === 'topology' ? (
          <NetworkTopology profile="datacenter" />
        ) : (
          <ChatInterface initialQuery={initialQuery} onQuerySent={() => setInitialQuery('')} userId={currentUser} />
        )}
      </main>
    </div>
  );
}

export default App;
