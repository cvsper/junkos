/**
 * Validation utilities for forms and user input
 */

export const validation = {
  /**
   * Validate email format
   */
  email(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  },

  /**
   * Validate password strength
   * Requirements: 8+ chars, 1 uppercase, 1 lowercase, 1 number
   */
  password(password: string): boolean {
    if (password.length < 8) return false;
    if (!/[A-Z]/.test(password)) return false;
    if (!/[a-z]/.test(password)) return false;
    if (!/[0-9]/.test(password)) return false;
    return true;
  },

  /**
   * Get password strength message
   */
  passwordStrength(password: string): string {
    if (password.length === 0) return '';
    if (password.length < 8) return 'Too short (min 8 characters)';
    if (!/[A-Z]/.test(password)) return 'Add an uppercase letter';
    if (!/[a-z]/.test(password)) return 'Add a lowercase letter';
    if (!/[0-9]/.test(password)) return 'Add a number';
    return 'Strong password';
  },

  /**
   * Validate US phone number
   */
  phone(phone: string): boolean {
    const cleaned = phone.replace(/\D/g, '');
    return cleaned.length === 10 || cleaned.length === 11;
  },

  /**
   * Format phone number for display
   */
  formatPhone(phone: string): string {
    const cleaned = phone.replace(/\D/g, '');
    if (cleaned.length === 10) {
      return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
    }
    return phone;
  },

  /**
   * Validate US ZIP code
   */
  zipCode(zip: string): boolean {
    return /^\d{5}(-\d{4})?$/.test(zip);
  },

  /**
   * Validate credit card number (basic Luhn algorithm)
   */
  creditCard(number: string): boolean {
    const cleaned = number.replace(/\D/g, '');
    if (cleaned.length < 13 || cleaned.length > 19) return false;

    let sum = 0;
    let isEven = false;

    for (let i = cleaned.length - 1; i >= 0; i--) {
      let digit = parseInt(cleaned[i], 10);

      if (isEven) {
        digit *= 2;
        if (digit > 9) {
          digit -= 9;
        }
      }

      sum += digit;
      isEven = !isEven;
    }

    return sum % 10 === 0;
  },

  /**
   * Validate required field
   */
  required(value: any): boolean {
    if (typeof value === 'string') {
      return value.trim().length > 0;
    }
    return value != null && value !== '';
  },

  /**
   * Validate minimum length
   */
  minLength(value: string, min: number): boolean {
    return value.length >= min;
  },

  /**
   * Validate maximum length
   */
  maxLength(value: string, max: number): boolean {
    return value.length <= max;
  },

  /**
   * Validate URL format
   */
  url(url: string): boolean {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  },

  /**
   * Validate date is in future
   */
  futureDate(date: Date): boolean {
    return date > new Date();
  },

  /**
   * Validate date is within range
   */
  dateInRange(date: Date, minDays: number, maxDays: number): boolean {
    const now = new Date();
    const min = new Date(now.getTime() + minDays * 24 * 60 * 60 * 1000);
    const max = new Date(now.getTime() + maxDays * 24 * 60 * 60 * 1000);
    return date >= min && date <= max;
  },
};

/**
 * Form validation helper
 */
export interface ValidationRule {
  validator: (value: any) => boolean;
  message: string;
}

export function validateField(value: any, rules: ValidationRule[]): string | null {
  for (const rule of rules) {
    if (!rule.validator(value)) {
      return rule.message;
    }
  }
  return null;
}

/**
 * Common validation rules
 */
export const rules = {
  required: (message = 'This field is required'): ValidationRule => ({
    validator: validation.required,
    message,
  }),
  email: (message = 'Invalid email address'): ValidationRule => ({
    validator: validation.email,
    message,
  }),
  password: (message = 'Password must be 8+ characters with uppercase, lowercase, and number'): ValidationRule => ({
    validator: validation.password,
    message,
  }),
  minLength: (min: number, message?: string): ValidationRule => ({
    validator: (value) => validation.minLength(value, min),
    message: message || `Must be at least ${min} characters`,
  }),
  maxLength: (max: number, message?: string): ValidationRule => ({
    validator: (value) => validation.maxLength(value, max),
    message: message || `Must be no more than ${max} characters`,
  }),
};
