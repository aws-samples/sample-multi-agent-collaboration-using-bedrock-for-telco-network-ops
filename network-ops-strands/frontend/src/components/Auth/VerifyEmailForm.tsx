/**
 * Email verification form component
 */

import React, { useState } from 'react';
import { Mail, AlertCircle, CheckCircle } from 'lucide-react';
import { confirmSignup, type AuthError } from '../../services/authService';

interface VerifyEmailFormProps {
  email: string;
  onSuccess: () => void;
  onResendCode?: () => void;
}

export const VerifyEmailForm: React.FC<VerifyEmailFormProps> = ({
  email,
  onSuccess,
  onResendCode,
}) => {
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await confirmSignup(email, code);
      setSuccess(true);
      setTimeout(() => {
        onSuccess();
      }, 1500);
    } catch (err) {
      const authError = err as AuthError;
      setError(authError.message);
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="w-full max-w-md mx-auto">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8">
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full mb-4">
              <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
              Email Verified!
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              Your email has been successfully verified. Redirecting to login...
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md mx-auto">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-100 dark:bg-emerald-900 rounded-full mb-4">
            <Mail className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Verify Your Email
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            We've sent a verification code to
          </p>
          <p className="text-emerald-600 dark:text-emerald-400 font-medium mt-1">
            {email}
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Verification Code Field */}
          <div>
            <label
              htmlFor="code"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
            >
              Verification Code
            </label>
            <input
              id="code"
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              required
              maxLength={6}
              className="block w-full px-4 py-3 text-center text-2xl tracking-widest border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
              placeholder="000000"
              disabled={loading}
            />
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400 text-center">
              Enter the 6-digit code from your email
            </p>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading || code.length !== 6}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-400 text-white font-medium rounded-lg transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
          >
            {loading ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Verifying...</span>
              </>
            ) : (
              <>
                <CheckCircle className="w-5 h-5" />
                <span>Verify Email</span>
              </>
            )}
          </button>
        </form>

        {/* Resend Code */}
        {onResendCode && (
          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Didn't receive the code?{' '}
              <button
                type="button"
                onClick={onResendCode}
                className="text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 font-medium"
                disabled={loading}
              >
                Resend code
              </button>
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
