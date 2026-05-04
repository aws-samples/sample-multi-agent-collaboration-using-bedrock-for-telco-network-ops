/**
 * Icon Mapping Constants
 * 
 * This file provides a centralized mapping of all icons used throughout the application.
 * All icons are from the Lucide React library for consistency.
 */

import {
  // Navigation & Layout
  LayoutDashboard,
  Network,
  MessageSquare,
  
  // Status & Alerts
  AlertTriangle,
  AlertCircle,
  XCircle,
  CheckCircle,
  
  // Actions & Tools
  Wrench,
  Send,
  ArrowRight,
  ChevronRight,
  
  // Monitoring & Metrics
  Radio,
  Zap,
  Activity,
  BarChart3,
  
  // User & Bot
  User,
  Bot,
  
  // Loading & Feedback
  Loader2,
  
  // Utility
  Lightbulb,
  type LucideIcon,
} from 'lucide-react';

/**
 * Icon size scale following Tailwind conventions
 */
export const ICON_SIZES = {
  sm: 'w-4 h-4',    // 16px
  md: 'w-5 h-5',    // 20px
  lg: 'w-6 h-6',    // 24px
  xl: 'w-8 h-8',    // 32px
  '2xl': 'w-12 h-12', // 48px
} as const;

export type IconSize = keyof typeof ICON_SIZES;

/**
 * Navigation icons
 */
export const NAV_ICONS = {
  dashboard: LayoutDashboard,
  topology: Network,
  chat: MessageSquare,
} as const;

/**
 * Metric card icons
 */
export const METRIC_ICONS = {
  alarms: AlertTriangle,
  maintenance: Wrench,
  sites: Radio,
  latency: Zap,
  performance: Activity,
  analytics: BarChart3,
} as const;

/**
 * User interface icons
 */
export const UI_ICONS = {
  user: User,
  bot: Bot,
  send: Send,
  arrowRight: ArrowRight,
  chevronRight: ChevronRight,
  lightbulb: Lightbulb,
} as const;

/**
 * Status and feedback icons
 */
export const STATUS_ICONS = {
  error: AlertCircle,
  warning: AlertTriangle,
  success: CheckCircle,
  close: XCircle,
  loading: Loader2,
} as const;

/**
 * Severity level color themes
 */
export const SEVERITY_COLORS = {
  critical: {
    text: 'text-red-700 dark:text-red-400',
    bg: 'bg-red-50 dark:bg-red-900/20',
    icon: 'text-red-600 dark:text-red-400',
    iconBg: 'bg-red-100 dark:bg-red-900/20',
  },
  major: {
    text: 'text-orange-700 dark:text-orange-400',
    bg: 'bg-orange-50 dark:bg-orange-900/20',
    icon: 'text-orange-600 dark:text-orange-400',
    iconBg: 'bg-orange-100 dark:bg-orange-900/20',
  },
  minor: {
    text: 'text-yellow-700 dark:text-yellow-400',
    bg: 'bg-yellow-50 dark:bg-yellow-900/20',
    icon: 'text-yellow-600 dark:text-yellow-400',
    iconBg: 'bg-yellow-100 dark:bg-yellow-900/20',
  },
  warning: {
    text: 'text-amber-700 dark:text-amber-400',
    bg: 'bg-amber-50 dark:bg-amber-900/20',
    icon: 'text-amber-600 dark:text-amber-400',
    iconBg: 'bg-amber-100 dark:bg-amber-900/20',
  },
} as const;

/**
 * Status color themes
 */
export const STATUS_COLORS = {
  success: {
    text: 'text-emerald-700 dark:text-emerald-400',
    bg: 'bg-emerald-50 dark:bg-emerald-900/20',
    icon: 'text-emerald-600 dark:text-emerald-400',
    iconBg: 'bg-emerald-100 dark:bg-emerald-900/20',
  },
  info: {
    text: 'text-indigo-700 dark:text-indigo-400',
    bg: 'bg-indigo-50 dark:bg-indigo-900/20',
    icon: 'text-indigo-600 dark:text-indigo-400',
    iconBg: 'bg-indigo-100 dark:bg-indigo-900/20',
  },
  error: {
    text: 'text-red-700 dark:text-red-400',
    bg: 'bg-red-50 dark:bg-red-900/20',
    icon: 'text-red-600 dark:text-red-400',
    iconBg: 'bg-red-100 dark:bg-red-900/20',
  },
} as const;

/**
 * Helper function to get icon size class
 */
export const getIconSizeClass = (size: IconSize = 'md'): string => {
  return ICON_SIZES[size];
};

/**
 * Export type for all icon components
 */
export type { LucideIcon };
