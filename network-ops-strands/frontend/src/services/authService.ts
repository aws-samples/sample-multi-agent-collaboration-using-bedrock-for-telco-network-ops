/**
 * Authentication service using AWS Amplify and Cognito
 */

import { Amplify } from 'aws-amplify';
import {
  signIn,
  signOut,
  signUp,
  confirmSignUp,
  resetPassword,
  confirmResetPassword,
  getCurrentUser,
  fetchAuthSession,
  type SignInInput,
  type SignUpInput,
} from 'aws-amplify/auth';

// Auth configuration interface
interface AuthConfig {
  region: string;
  userPoolId: string;
  userPoolClientId: string;
  identityPoolId?: string;
}

// User interface
export interface User {
  username: string;
  email: string;
  attributes?: Record<string, string>;
}

// Auth error interface
export interface AuthError {
  code: string;
  message: string;
  name: string;
}

/**
 * Initialize Amplify with Cognito configuration
 */
export const configureAuth = (config: AuthConfig): void => {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: config.userPoolId,
        userPoolClientId: config.userPoolClientId,
        identityPoolId: config.identityPoolId || '',
        loginWith: {
          oauth: {
            domain: `${config.userPoolClientId}.auth.${config.region}.amazoncognito.com`,
            scopes: ['email', 'openid', 'profile'],
            redirectSignIn: [window.location.origin + '/callback', 'http://localhost:3000/callback'],
            redirectSignOut: [window.location.origin + '/logout', 'http://localhost:3000/logout'],
            responseType: 'code',
          },
        },
      },
    },
  });
};

/**
 * Sign in user with email and password
 */
export const login = async (email: string, password: string): Promise<User> => {
  try {
    const input: SignInInput = {
      username: email,
      password,
    };
    
    const { isSignedIn, nextStep } = await signIn(input);
    
    if (!isSignedIn) {
      throw new Error(`Sign in incomplete: ${nextStep.signInStep}`);
    }
    
    const user = await getCurrentUser();
    return {
      username: user.username,
      email: user.signInDetails?.loginId || email,
    };
  } catch (error) {
    console.error('Login error:', error);
    throw formatAuthError(error);
  }
};

/**
 * Sign up new user
 */
export const signup = async (
  email: string,
  password: string,
  name: string,
  company?: string
): Promise<{ userConfirmed: boolean; userId: string }> => {
  try {
    const input: SignUpInput = {
      username: email,
      password,
      options: {
        userAttributes: {
          email,
          name,
          ...(company && { 'custom:company': company }),
        },
      },
    };
    
    const { isSignUpComplete, userId, nextStep: _nextStep } = await signUp(input);
    
    return {
      userConfirmed: isSignUpComplete,
      userId: userId || '',
    };
  } catch (error) {
    console.error('Signup error:', error);
    throw formatAuthError(error);
  }
};

/**
 * Confirm signup with verification code
 */
export const confirmSignup = async (email: string, code: string): Promise<void> => {
  try {
    await confirmSignUp({
      username: email,
      confirmationCode: code,
    });
  } catch (error) {
    console.error('Confirm signup error:', error);
    throw formatAuthError(error);
  }
};

/**
 * Sign out current user
 */
export const logout = async (): Promise<void> => {
  try {
    await signOut();
  } catch (error) {
    console.error('Logout error:', error);
    throw formatAuthError(error);
  }
};

/**
 * Request password reset
 */
export const requestPasswordReset = async (email: string): Promise<void> => {
  try {
    await resetPassword({ username: email });
  } catch (error) {
    console.error('Password reset request error:', error);
    throw formatAuthError(error);
  }
};

/**
 * Confirm password reset with code
 */
export const confirmPasswordReset = async (
  email: string,
  code: string,
  newPassword: string
): Promise<void> => {
  try {
    await confirmResetPassword({
      username: email,
      confirmationCode: code,
      newPassword,
    });
  } catch (error) {
    console.error('Password reset confirmation error:', error);
    throw formatAuthError(error);
  }
};

/**
 * Get current authenticated user
 */
export const getUser = async (): Promise<User | null> => {
  try {
    const user = await getCurrentUser();
    return {
      username: user.username,
      email: user.signInDetails?.loginId || '',
    };
  } catch (error) {
    return null;
  }
};

/**
 * Get current auth session with tokens
 */
export const getSession = async (): Promise<{
  accessToken: string;
  idToken: string;
  refreshToken?: string;
} | null> => {
  try {
    const session = await fetchAuthSession();
    
    if (!session.tokens) {
      return null;
    }
    
    return {
      accessToken: session.tokens.accessToken.toString(),
      idToken: session.tokens.idToken?.toString() || '',
      refreshToken: (session.tokens as any).refreshToken?.toString(),
    };
  } catch (error) {
    console.error('Get session error:', error);
    return null;
  }
};

/**
 * Check if user is authenticated
 */
export const isAuthenticated = async (): Promise<boolean> => {
  try {
    const user = await getCurrentUser();
    return !!user;
  } catch (error) {
    return false;
  }
};

/**
 * Format auth errors for display
 */
const formatAuthError = (error: any): AuthError => {
  const authError: AuthError = {
    code: error.code || 'UNKNOWN_ERROR',
    message: error.message || 'An unknown error occurred',
    name: error.name || 'AuthError',
  };
  
  // Provide user-friendly messages
  switch (authError.code) {
    case 'UserNotFoundException':
      authError.message = 'No account found with this email address';
      break;
    case 'NotAuthorizedException':
      authError.message = 'Incorrect email or password';
      break;
    case 'UserNotConfirmedException':
      authError.message = 'Please verify your email address';
      break;
    case 'CodeMismatchException':
      authError.message = 'Invalid verification code';
      break;
    case 'ExpiredCodeException':
      authError.message = 'Verification code has expired';
      break;
    case 'InvalidPasswordException':
      authError.message = 'Password does not meet requirements';
      break;
    case 'UsernameExistsException':
      authError.message = 'An account with this email already exists';
      break;
    case 'LimitExceededException':
      authError.message = 'Too many attempts. Please try again later';
      break;
  }
  
  return authError;
};

/**
 * Get password requirements
 */
export const getPasswordRequirements = (): string[] => {
  return [
    'At least 12 characters long',
    'Contains uppercase letter (A-Z)',
    'Contains lowercase letter (a-z)',
    'Contains number (0-9)',
    'Contains special character (!@#$%^&*)',
  ];
};

/**
 * Validate password against requirements
 */
export const validatePassword = (password: string): { valid: boolean; errors: string[] } => {
  const errors: string[] = [];
  
  if (password.length < 12) {
    errors.push('Password must be at least 12 characters long');
  }
  
  if (!/[A-Z]/.test(password)) {
    errors.push('Password must contain at least one uppercase letter');
  }
  
  if (!/[a-z]/.test(password)) {
    errors.push('Password must contain at least one lowercase letter');
  }
  
  if (!/[0-9]/.test(password)) {
    errors.push('Password must contain at least one number');
  }
  
  if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) {
    errors.push('Password must contain at least one special character');
  }
  
  return {
    valid: errors.length === 0,
    errors,
  };
};
