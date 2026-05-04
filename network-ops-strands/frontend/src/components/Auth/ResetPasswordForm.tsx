/**
 * Reset password form component for confirming password reset with code
 */

import React, { useState } from 'react';
import { Lock, AlertCircle, CheckCircle } from 'lucide-react';
import {
  confirmPasswordReset,
  validatePassword,
  getPasswordRequirements,
  type AuthError,
} from '../../services/authService';

interface ResetPasswordFormProps {
  email: string;
  onSuccess: () => void;
}

export const ResetPasswordForm: React.FC<ResetPasswordFormProps> = ({
  email,
  onSuccess,
}) => {
  const [formData, setFormData] = useState({
    code: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [passwordErrors, setPasswordErrors] = useState<string[]>([]);
  const [showPasswordRequirements, setShowPasswordRequirements] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));

    // Validate password on change
    if (field === 'newPassword') {
      const validation = validatePassword(value);
      setPasswordErrors(validation.errors);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate password
    const passwordValidation = validatePassword(formData.newPassword);
    if (!passwordValidation.valid) {
      setError('Password does not meet requirements');
      setPasswordErrors(passwordValidation.errors);
      return;
    }

    // Check password confirmation
    if (formData.newPassword !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      await confirmPasswordReset(email, formData.code, formData.newPassword);
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
              Password Reset!
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              Your password has been successfully reset. Redirecting to login...
            </p>
          </div>
        </div>
      </div>
    );
  }

  const passwordRequirements = getPasswordRequirements();

  return (
    <div className="w-full max-w-md mx-auto">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-100 dark:bg-emerald-900 rounded-full mb-4">
            <Lock className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Reset Your Password
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Enter the code sent to
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
        <form onSubmit={handleSubmit} className="space-y-5">
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
              value={formData.code}
              onChange={(e) => handleChange('code', e.target.value.replace(/\D/g, ''))}
              required
              maxLength={6}
              className="block w-full px-4 py-2 text-center text-lg tracking-widest border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
              placeholder="000000"
              disabled={loading}
            />
          </div>

          {/* New Password Field */}
          <div>
            <label
              htmlFor="newPassword"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
            >
              New Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Lock className="h-5 w-5 text-gray-400" />
              </div>
              <input
                id="newPassword"
                type="password"
                value={formData.newPassword}
                onChange={(e) => handleChange('newPassword', e.target.value)}
                onFocus={() => setShowPasswordRequirements(true)}
                required
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
                placeholder="••••••••••••"
                disabled={loading}
              />
            </div>

            {/* Password Requirements */}
            {showPasswordRequirements && formData.newPassword && (
              <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Password Requirements:
                </p>
                <ul className="space-y-1">
                  {passwordRequirements.map((req, index) => {
                    const isValid = !passwordErrors.some((err) =>
                      err.toLowerCase().includes(req.toLowerCase().split(' ')[1])
                    );
                    return (
                      <li key={index} className="flex items-center gap-2 text-xs">
                        {isValid ? (
                          <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400" />
                        ) : (
                          <AlertCircle className="w-4 h-4 text-gray-400" />
                        )}
                        <span
                          className={
                            isValid
                              ? 'text-green-700 dark:text-green-300'
                              : 'text-gray-600 dark:text-gray-400'
                          }
                        >
                          {req}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>

          {/* Confirm Password Field */}
          <div>
            <label
              htmlFor="confirmPassword"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
            >
              Confirm New Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Lock className="h-5 w-5 text-gray-400" />
              </div>
              <input
                id="confirmPassword"
                type="password"
                value={formData.confirmPassword}
                onChange={(e) => handleChange('confirmPassword', e.target.value)}
                required
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
                placeholder="••••••••••••"
                disabled={loading}
              />
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading || passwordErrors.length > 0 || formData.code.length !== 6}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-400 text-white font-medium rounded-lg transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
          >
            {loading ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Resetting password...</span>
              </>
            ) : (
              <>
                <Lock className="w-5 h-5" />
                <span>Reset Password</span>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};
