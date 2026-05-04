/**
 * Signup form component for new user registration
 */

import React, { useState } from 'react';
import { UserPlus, Mail, Lock, User, Building, AlertCircle, CheckCircle } from 'lucide-react';
import { signup, validatePassword, getPasswordRequirements, type AuthError } from '../../services/authService';

interface SignupFormProps {
  onSuccess: (email: string) => void;
  onLogin: () => void;
}

export const SignupForm: React.FC<SignupFormProps> = ({ onSuccess, onLogin }) => {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    name: '',
    company: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [passwordErrors, setPasswordErrors] = useState<string[]>([]);
  const [showPasswordRequirements, setShowPasswordRequirements] = useState(false);

  const handleChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    
    // Validate password on change
    if (field === 'password') {
      const validation = validatePassword(value);
      setPasswordErrors(validation.errors);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate password
    const passwordValidation = validatePassword(formData.password);
    if (!passwordValidation.valid) {
      setError('Password does not meet requirements');
      setPasswordErrors(passwordValidation.errors);
      return;
    }

    // Check password confirmation
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      const result = await signup(
        formData.email,
        formData.password,
        formData.name,
        formData.company || undefined
      );

      if (result.userConfirmed) {
        // User is auto-confirmed, can proceed to login
        onSuccess(formData.email);
      } else {
        // User needs to verify email
        onSuccess(formData.email);
      }
    } catch (err) {
      const authError = err as AuthError;
      setError(authError.message);
    } finally {
      setLoading(false);
    }
  };

  const passwordRequirements = getPasswordRequirements();

  return (
    <div className="w-full max-w-md mx-auto">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-100 dark:bg-emerald-900 rounded-full mb-4">
            <UserPlus className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            Create Account
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Sign up to get started
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
          {/* Name Field */}
          <div>
            <label
              htmlFor="name"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
            >
              Full Name *
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <User className="h-5 w-5 text-gray-400" />
              </div>
              <input
                id="name"
                type="text"
                value={formData.name}
                onChange={(e) => handleChange('name', e.target.value)}
                required
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
                placeholder="John Doe"
                disabled={loading}
              />
            </div>
          </div>

          {/* Email Field */}
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
            >
              Email Address *
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Mail className="h-5 w-5 text-gray-400" />
              </div>
              <input
                id="email"
                type="email"
                value={formData.email}
                onChange={(e) => handleChange('email', e.target.value)}
                required
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
                placeholder="you@example.com"
                disabled={loading}
              />
            </div>
          </div>

          {/* Company Field (Optional) */}
          <div>
            <label
              htmlFor="company"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
            >
              Company (Optional)
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Building className="h-5 w-5 text-gray-400" />
              </div>
              <input
                id="company"
                type="text"
                value={formData.company}
                onChange={(e) => handleChange('company', e.target.value)}
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
                placeholder="Your Company"
                disabled={loading}
              />
            </div>
          </div>

          {/* Password Field */}
          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
            >
              Password *
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Lock className="h-5 w-5 text-gray-400" />
              </div>
              <input
                id="password"
                type="password"
                value={formData.password}
                onChange={(e) => handleChange('password', e.target.value)}
                onFocus={() => setShowPasswordRequirements(true)}
                required
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400"
                placeholder="••••••••••••"
                disabled={loading}
              />
            </div>
            
            {/* Password Requirements */}
            {showPasswordRequirements && formData.password && (
              <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <p className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Password Requirements:
                </p>
                <ul className="space-y-1">
                  {passwordRequirements.map((req, index) => {
                    const isValid = !passwordErrors.some((err) => err.toLowerCase().includes(req.toLowerCase().split(' ')[1]));
                    return (
                      <li key={index} className="flex items-center gap-2 text-xs">
                        {isValid ? (
                          <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400" />
                        ) : (
                          <AlertCircle className="w-4 h-4 text-gray-400" />
                        )}
                        <span className={isValid ? 'text-green-700 dark:text-green-300' : 'text-gray-600 dark:text-gray-400'}>
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
              Confirm Password *
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
            disabled={loading || passwordErrors.length > 0}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-400 text-white font-medium rounded-lg transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
          >
            {loading ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Creating account...</span>
              </>
            ) : (
              <>
                <UserPlus className="w-5 h-5" />
                <span>Create Account</span>
              </>
            )}
          </button>
        </form>

        {/* Login Link */}
        <div className="mt-6 text-center">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Already have an account?{' '}
            <button
              type="button"
              onClick={onLogin}
              className="text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 font-medium"
              disabled={loading}
            >
              Sign in
            </button>
          </p>
        </div>
      </div>
    </div>
  );
};
