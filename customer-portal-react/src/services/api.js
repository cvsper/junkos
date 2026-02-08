import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds
});

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add any auth tokens here if needed
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
    // Handle errors globally
    const message = error.response?.data?.error || error.message || 'An error occurred';
    console.error('API Error:', message);
    return Promise.reject(error);
  }
);

// API methods
export const api = {
  // Validate address with Google Maps
  validateAddress: async (address) => {
    try {
      const response = await apiClient.post('/bookings/validate-address', { address });
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.error || 'Failed to validate address');
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
      throw new Error(error.response?.data?.error || 'Failed to upload photos');
    }
  },

  // Get price estimate
  getPriceEstimate: async (bookingData) => {
    try {
      const response = await apiClient.post('/bookings/estimate', bookingData);
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.error || 'Failed to get price estimate');
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
      throw new Error(error.response?.data?.error || 'Failed to fetch available slots');
    }
  },

  // Create booking
  createBooking: async (bookingData) => {
    try {
      const response = await apiClient.post('/bookings/create', bookingData);
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.error || 'Failed to create booking');
    }
  },

  // Create payment intent
  createPaymentIntent: async (bookingId, amount) => {
    try {
      const response = await apiClient.post('/payments/create-intent-simple', {
        bookingId,
        amount,
      });
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.error || 'Failed to create payment intent');
    }
  },

  // Confirm payment
  confirmPayment: async (paymentIntentId, bookingId) => {
    try {
      const response = await apiClient.post('/payments/confirm-simple', {
        paymentIntentId,
        bookingId,
      });
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.error || 'Failed to confirm payment');
    }
  },
};

export default apiClient;
