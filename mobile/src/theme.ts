import { MD3LightTheme as DefaultTheme } from 'react-native-paper';

export const colors = {
  primary: '#6366F1',      // Indigo
  secondary: '#818CF8',    // Light Indigo
  cta: '#DC2626',          // Red
  background: '#F5F3FF',   // Light Purple
  text: '#1E1B4B',         // Dark Indigo
  success: '#16A34A',
  warning: '#F59E0B',
  error: '#EF4444',
  info: '#3B82F6',
  muted: '#64748B',
  border: '#E2E8F0',
  white: '#FFFFFF',
};

export const theme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: colors.primary,
    secondary: colors.secondary,
    error: colors.error,
    background: colors.background,
    surface: colors.white,
    onSurface: colors.text,
    onPrimary: colors.white,
  },
  fonts: {
    ...DefaultTheme.fonts,
    displayLarge: {
      fontFamily: 'Poppins-Bold',
      fontSize: 48,
      lineHeight: 58,
    },
    headlineLarge: {
      fontFamily: 'Poppins-SemiBold',
      fontSize: 36,
      lineHeight: 43,
    },
    headlineMedium: {
      fontFamily: 'Poppins-Medium',
      fontSize: 28,
      lineHeight: 34,
    },
    titleLarge: {
      fontFamily: 'Poppins-Medium',
      fontSize: 20,
      lineHeight: 28,
    },
    bodyLarge: {
      fontFamily: 'OpenSans-Regular',
      fontSize: 18,
      lineHeight: 29,
    },
    bodyMedium: {
      fontFamily: 'OpenSans-Regular',
      fontSize: 16,
      lineHeight: 26,
    },
    bodySmall: {
      fontFamily: 'OpenSans-Regular',
      fontSize: 14,
      lineHeight: 22,
    },
    labelSmall: {
      fontFamily: 'OpenSans-Regular',
      fontSize: 12,
      lineHeight: 19,
    },
  },
};
