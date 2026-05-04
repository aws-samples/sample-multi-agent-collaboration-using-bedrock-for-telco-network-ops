import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { AlertCircle } from 'lucide-react';

interface IIconWithFallbackProps {
  icon: LucideIcon;
  fallback?: React.ReactNode;
  className?: string;
  size?: number;
  strokeWidth?: number;
}

/**
 * IconWithFallback Component
 * 
 * Renders a Lucide icon with error boundary fallback.
 * If the icon fails to render, displays a fallback UI.
 * 
 * @param icon - The Lucide icon component to render
 * @param fallback - Optional custom fallback UI (defaults to AlertCircle)
 * @param className - Additional CSS classes
 * @param size - Icon size in pixels
 * @param strokeWidth - Icon stroke width
 */
export const IconWithFallback: React.FC<IIconWithFallbackProps> = ({
  icon: Icon,
  fallback,
  className = '',
  size,
  strokeWidth,
}) => {
  try {
    return (
      <Icon 
        className={className}
        size={size}
        strokeWidth={strokeWidth}
      />
    );
  } catch (error) {
    console.error('Icon rendering error:', error);
    
    if (fallback) {
      return <>{fallback}</>;
    }
    
    // Default fallback: AlertCircle icon
    return (
      <AlertCircle 
        className={className || 'w-5 h-5 text-red-500'}
        size={size}
        strokeWidth={strokeWidth}
      />
    );
  }
};
