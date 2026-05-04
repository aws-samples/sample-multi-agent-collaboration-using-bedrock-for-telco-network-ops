/**
 * Protected route component that requires authentication
 */

import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Bot } from 'lucide-react';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuth, loading } = useAuth();

  // Show loading state while checking authentication
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-full shadow-lg mb-4">
            <Bot className="w-8 h-8 text-white animate-pulse" />
          </div>
          <p className="text-slate-600 dark:text-slate-400 text-lg">
            Checking authentication...
          </p>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuth) {
    return <Navigate to="/login" replace />;
  }

  // Render children if authenticated
  return <>{children}</>;
};
