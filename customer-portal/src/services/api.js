import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/api';

// Create axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.message || error.message || 'An error occurred';
    console.error('API Error:', message);
    return Promise.reject(error);
  }
);

// API methods
export const api = {
  // Validate address
  validateAddress: async (address) => {
    try {
      const response = await apiClient.post('/bookings/validate-address', { address });
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.message || 'Failed to validate address');
    }
  },

  // Upload photos
  uploadPhotos: async (files) => {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('photos', file);
    });

    try {
      const response = await apiClient.post('/bookings/upload-photos', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.message || 'Failed to upload photos');
    }
  },

  // Get price estimate
  getPriceEstimate: async (bookingData) => {
    try {
      const response = await apiClient.post('/bookings/estimate', bookingData);
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.message || 'Failed to get price estimate');
    }
  },

  // Check available time slots
  getAvailableSlots: async (date) => {
    try {
      const response = await apiClient.get('/bookings/available-slots', {
        params: { date: date.toISOString() },
      });
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.message || 'Failed to fetch available slots');
    }
  },

  // Create booking (no auth required)
  createBooking: async (bookingData) => {
    try {
      const response = await apiClient.post('/bookings/create', bookingData);
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.message || 'Failed to create booking');
    }
  },

  // Create payment intent (no auth required)
  createPaymentIntent: async (bookingId, amount) => {
    try {
      const response = await apiClient.post('/payments/create-intent-simple', {
        bookingId,
        amount,
      });
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.message || 'Failed to create payment intent');
    }
  },

  // Confirm payment (no auth required)
  confirmPayment: async (paymentIntentId, bookingId) => {
    try {
      const response = await apiClient.post('/payments/confirm-simple', {
        paymentIntentId,
        bookingId,
      });
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.message || 'Failed to confirm payment');
    }
  },

  // Get booking/tracking status (for tracking page)
  getBookingStatus: async (bookingId) => {
    try {
      const response = await apiClient.get(`/tracking/${bookingId}`);
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.message || 'Failed to get booking status');
    }
  },

  // Get driver location for a job
  getDriverLocation: async (jobId) => {
    try {
      const response = await apiClient.get(`/tracking/${jobId}/driver-location`);
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.message || 'Failed to get driver location');
    }
  },
};

export default apiClient;
