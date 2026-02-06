import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BookingFlow } from '../src/components/BookingFlow';
import * as api from '../src/services/api';

jest.mock('../src/services/api');

describe('BookingFlow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Step Navigation', () => {
    test('renders first step (address) on initial load', () => {
      render(<BookingFlow />);
      
      expect(screen.getByText(/pickup address/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/street address/i)).toBeInTheDocument();
    });

    test('navigates to next step when form is valid', async () => {
      const user = userEvent.setup();
      render(<BookingFlow />);
      
      // Fill in address
      await user.type(screen.getByLabelText(/street address/i), '123 Main St');
      await user.type(screen.getByLabelText(/city/i), 'New York');
      await user.type(screen.getByLabelText(/zip/i), '10001');
      
      // Click next
      await user.click(screen.getByRole('button', { name: /next/i }));
      
      // Should navigate to photos step
      await waitFor(() => {
        expect(screen.getByText(/upload photos/i)).toBeInTheDocument();
      });
    });

    test('prevents navigation when form is invalid', async () => {
      const user = userEvent.setup();
      render(<BookingFlow />);
      
      // Try to click next without filling form
      await user.click(screen.getByRole('button', { name: /next/i }));
      
      // Should show validation error
      expect(screen.getByText(/required/i)).toBeInTheDocument();
      
      // Should still be on step 1
      expect(screen.getByLabelText(/street address/i)).toBeInTheDocument();
    });

    test('can navigate back to previous step', async () => {
      const user = userEvent.setup();
      render(<BookingFlow />);
      
      // Fill and go to step 2
      await user.type(screen.getByLabelText(/street address/i), '123 Main St');
      await user.type(screen.getByLabelText(/city/i), 'New York');
      await user.type(screen.getByLabelText(/zip/i), '10001');
      await user.click(screen.getByRole('button', { name: /next/i }));
      
      await waitFor(() => {
        expect(screen.getByText(/upload photos/i)).toBeInTheDocument();
      });
      
      // Click back
      await user.click(screen.getByRole('button', { name: /back/i }));
      
      // Should be back on step 1
      expect(screen.getByLabelText(/street address/i)).toBeInTheDocument();
      // Previous data should be preserved
      expect(screen.getByLabelText(/street address/i)).toHaveValue('123 Main St');
    });

    test('shows progress indicator with correct step', () => {
      render(<BookingFlow />);
      
      const progressBar = screen.getByRole('progressbar');
      expect(progressBar).toHaveAttribute('aria-valuenow', '1');
      expect(progressBar).toHaveAttribute('aria-valuemax', '6');
    });
  });

  describe('Form Validation', () => {
    test('validates required fields', async () => {
      const user = userEvent.setup();
      render(<BookingFlow />);
      
      const submitButton = screen.getByRole('button', { name: /next/i });
      await user.click(submitButton);
      
      expect(screen.getAllByText(/required/i).length).toBeGreaterThan(0);
    });

    test('validates zip code format', async () => {
      const user = userEvent.setup();
      render(<BookingFlow />);
      
      const zipInput = screen.getByLabelText(/zip/i);
      await user.type(zipInput, '123'); // Invalid zip
      await user.click(screen.getByRole('button', { name: /next/i }));
      
      expect(screen.getByText(/valid zip code/i)).toBeInTheDocument();
    });

    test('validates email format', async () => {
      const user = userEvent.setup();
      render(<BookingFlow />);
      
      // Navigate to contact step (assuming it's step 4 or so)
      // ... navigation code ...
      
      const emailInput = screen.getByLabelText(/email/i);
      await user.type(emailInput, 'invalid-email');
      
      expect(screen.getByText(/valid email/i)).toBeInTheDocument();
    });

    test('validates phone number format', async () => {
      const user = userEvent.setup();
      render(<BookingFlow />);
      
      // Navigate to contact step
      // ... navigation code ...
      
      const phoneInput = screen.getByLabelText(/phone/i);
      await user.type(phoneInput, '123');
      
      expect(screen.getByText(/valid phone/i)).toBeInTheDocument();
    });

    test('validates date is in future', async () => {
      const user = userEvent.setup();
      render(<BookingFlow />);
      
      // Navigate to date/time step
      // ... navigation code ...
      
      const dateInput = screen.getByLabelText(/pickup date/i);
      
      // Try to select yesterday
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      fireEvent.change(dateInput, { target: { value: yesterday.toISOString().split('T')[0] } });
      
      expect(screen.getByText(/future date/i)).toBeInTheDocument();
    });
  });

  describe('Data Persistence', () => {
    test('preserves form data when navigating between steps', async () => {
      const user = userEvent.setup();
      render(<BookingFlow />);
      
      // Fill step 1
      await user.type(screen.getByLabelText(/street address/i), '123 Main St');
      await user.type(screen.getByLabelText(/city/i), 'New York');
      await user.type(screen.getByLabelText(/zip/i), '10001');
      await user.click(screen.getByRole('button', { name: /next/i }));
      
      // Go to step 2, then back
      await waitFor(() => {
        expect(screen.getByText(/upload photos/i)).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /back/i }));
      
      // Data should be preserved
      expect(screen.getByLabelText(/street address/i)).toHaveValue('123 Main St');
      expect(screen.getByLabelText(/city/i)).toHaveValue('New York');
      expect(screen.getByLabelText(/zip/i)).toHaveValue('10001');
    });

    test('stores data in sessionStorage for recovery', async () => {
      const user = userEvent.setup();
      render(<BookingFlow />);
      
      await user.type(screen.getByLabelText(/street address/i), '123 Main St');
      
      // Check sessionStorage
      const stored = sessionStorage.getItem('bookingFormData');
      expect(stored).toBeTruthy();
      
      const data = JSON.parse(stored);
      expect(data.address).toBe('123 Main St');
    });
  });

  describe('Step Completion', () => {
    test('completes all steps and submits booking', async () => {
      const user = userEvent.setup();
      api.createBooking.mockResolvedValue({ id: 123, status: 'pending' });
      
      render(<BookingFlow />);
      
      // Step 1: Address
      await user.type(screen.getByLabelText(/street address/i), '123 Main St');
      await user.type(screen.getByLabelText(/city/i), 'New York');
      await user.type(screen.getByLabelText(/zip/i), '10001');
      await user.click(screen.getByRole('button', { name: /next/i }));
      
      // Step 2: Photos (skip)
      await waitFor(() => {
        expect(screen.getByText(/upload photos/i)).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /skip|next/i }));
      
      // Continue through remaining steps...
      // Final submission
      await user.click(screen.getByRole('button', { name: /submit|complete/i }));
      
      await waitFor(() => {
        expect(api.createBooking).toHaveBeenCalled();
      });
    });

    test('shows success message after submission', async () => {
      const user = userEvent.setup();
      api.createBooking.mockResolvedValue({ id: 123, status: 'pending' });
      
      render(<BookingFlow />);
      
      // Complete all steps (abbreviated)
      // ...
      
      await user.click(screen.getByRole('button', { name: /submit/i }));
      
      await waitFor(() => {
        expect(screen.getByText(/booking confirmed/i)).toBeInTheDocument();
      });
    });

    test('handles submission errors gracefully', async () => {
      const user = userEvent.setup();
      api.createBooking.mockRejectedValue(new Error('Network error'));
      
      render(<BookingFlow />);
      
      // Complete form and submit
      // ...
      
      await user.click(screen.getByRole('button', { name: /submit/i }));
      
      await waitFor(() => {
        expect(screen.getByText(/error|failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    test('has proper ARIA labels', () => {
      render(<BookingFlow />);
      
      expect(screen.getByLabelText(/street address/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
    });

    test('keyboard navigation works', async () => {
      const user = userEvent.setup();
      render(<BookingFlow />);
      
      // Tab through form fields
      await user.tab();
      expect(screen.getByLabelText(/street address/i)).toHaveFocus();
      
      await user.tab();
      expect(screen.getByLabelText(/city/i)).toHaveFocus();
    });

    test('announces errors to screen readers', async () => {
      const user = userEvent.setup();
      render(<BookingFlow />);
      
      await user.click(screen.getByRole('button', { name: /next/i }));
      
      const errorMessage = screen.getByText(/required/i);
      expect(errorMessage).toHaveAttribute('role', 'alert');
    });
  });
});
