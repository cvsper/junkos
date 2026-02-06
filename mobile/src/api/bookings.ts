import { apiClient } from './client';
import { Booking, PaymentIntent } from '../types';

export const bookingsApi = {
  create: async (booking: Booking): Promise<Booking> => {
    return apiClient.post<Booking>('/bookings', booking);
  },

  getById: async (id: number): Promise<Booking> => {
    return apiClient.get<Booking>(`/bookings/${id}`);
  },

  getAll: async (): Promise<Booking[]> => {
    return apiClient.get<Booking[]>('/bookings');
  },

  update: async (id: number, booking: Partial<Booking>): Promise<Booking> => {
    return apiClient.put<Booking>(`/bookings/${id}`, booking);
  },

  cancel: async (id: number): Promise<void> => {
    return apiClient.delete(`/bookings/${id}`);
  },

  uploadPhoto: async (file: any): Promise<{ url: string }> => {
    return apiClient.uploadFile('/bookings/photos', file, 'photo');
  },

  estimatePrice: async (items: any[], address: any): Promise<{ estimatedPrice: number }> => {
    return apiClient.post('/bookings/estimate', { items, address });
  },

  createPaymentIntent: async (bookingId: number): Promise<PaymentIntent> => {
    return apiClient.post<PaymentIntent>(`/bookings/${bookingId}/payment-intent`);
  },

  confirmPayment: async (bookingId: number, paymentIntentId: string): Promise<Booking> => {
    return apiClient.post<Booking>(`/bookings/${bookingId}/confirm-payment`, {
      paymentIntentId,
    });
  },
};
