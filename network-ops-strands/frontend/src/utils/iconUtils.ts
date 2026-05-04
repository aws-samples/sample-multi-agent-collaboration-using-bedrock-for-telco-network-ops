import { ICON_SIZES, type IconSize } from '../constants/icons';

/**
 * Icon Utility Functions
 * 
 * Helper functions for working with icons throughout the application.
 */

/**
 * Get the Tailwind CSS class for a given icon size
 * 
 * @param size - The icon size (sm, md, lg, xl, 2xl)
 * @returns The corresponding Tailwind CSS class string
 */
export const getIconSizeClass = (size: IconSize = 'md'): string => {
  return ICON_SIZES[size];
};

/**
 * Get the numeric pixel value for a given icon size
 * 
 * @param size - The icon size (sm, md, lg, xl, 2xl)
 * @returns The size in pixels
 */
export const getIconSizePixels = (size: IconSize = 'md'): number => {
  const sizeMap: Record<IconSize, number> = {
    sm: 16,
    md: 20,
    lg: 24,
    xl: 32,
    '2xl': 48,
  };
  
  return sizeMap[size];
};

/**
 * Combine icon size class with additional classes
 * 
 * @param size - The icon size
 * @param additionalClasses - Additional CSS classes to apply
 * @returns Combined class string
 */
export const combineIconClasses = (
  size: IconSize = 'md',
  additionalClasses: string = ''
): string => {
  const sizeClass = getIconSizeClass(size);
  return additionalClasses ? `${sizeClass} ${additionalClasses}` : sizeClass;
};

/**
 * Type guard to check if a string is a valid IconSize
 * 
 * @param size - The size string to check
 * @returns True if the size is valid
 */
export const isValidIconSize = (size: string): size is IconSize => {
  return ['sm', 'md', 'lg', 'xl', '2xl'].includes(size);
};
