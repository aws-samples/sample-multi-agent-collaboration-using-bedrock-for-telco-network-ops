/**
 * Authentication context for managing auth state across the application
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import {
  getUser,
  isAuthenticated,
  logout as authLogout,
  type User,
} from '../services/authService';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isAuth: boolean;
  login: (user: User) => void;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuth, setIsAuth] = useState(false);

  // Check authentication status on mount
  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const authenticated = await isAuthenticated();
      setIsAuth(authenticated);

      if (authenticated) {
        const currentUser = await getUser();
        setUser(currentUser);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setIsAuth(false);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const login = (newUser: User) => {
    setUser(newUser);
    setIsAuth(true);
  };

  const logout = async () => {
    try {
      await authLogout();
      setUser(null);
      setIsAuth(false);
    } catch (error) {
      console.error('Logout failed:', error);
      // Still clear local state even if logout fails
      setUser(null);
      setIsAuth(false);
    }
  };

  const refreshUser = async () => {
    try {
      const currentUser = await getUser();
      setUser(currentUser);
    } catch (error) {
      console.error('User refresh failed:', error);
    }
  };

  const value: AuthContextType = {
    user,
    loading,
    isAuth,
    login,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

/**
 * Hook to use auth context
 */
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
