import React from 'react';
import type { LucideIcon } from 'lucide-react';

interface IAccessibleIconProps {
  icon: LucideIcon;
  label: string;
  decorative?: boolean;
  className?: string;
  size?: number;
  strokeWidth?: number;
}

/**
 * AccessibleIcon Component
 * 
 * Renders a Lucide icon with proper accessibility attributes.
 * Ensures icons are properly announced by screen readers.
 * 
 * @param icon - The Lucide icon component to render
 * @param label - Accessible label for the icon (required for non-decorative icons)
 * @param decorative - If true, icon is hidden from screen readers (default: false)
 * @param className - Additional CSS classes
 * @param size - Icon size in pixels
 * @param strokeWidth - Icon stroke width
 */
export const AccessibleIcon: React.FC<IAccessibleIconProps> = ({
  icon: Icon,
  label,
  decorative = false,
  className = '',
  size,
  strokeWidth,
}) => {
  return (
    <Icon
      className={className}
      size={size}
      strokeWidth={strokeWidth}
      aria-label={decorative ? undefined : label}
      aria-hidden={decorative}
      role={decorative ? 'presentation' : 'img'}
    />
  );
};
