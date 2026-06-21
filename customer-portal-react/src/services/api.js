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

  // Get price estimate (item-based)
  getPriceEstimate: async (bookingData) => {
    try {
      const response = await apiClient.post('/bookings/estimate', bookingData);
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.error || 'Failed to get price estimate');
    }
  },

  // Get price estimate (truck load volume-based)
  getLoadEstimate: async (loadData) => {
    try {
      const response = await apiClient.post('/booking/estimate-load', loadData);
      return response.data;
    } catch (error) {
      throw new Error(error.response?.data?.error || 'Failed to get load estimate');
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

  // Validate a promo code against an order amount (for funnel display).
  // Returns { valid, discount, final, message }.
  validatePromo: async (code, orderAmount) => {
    try {
      const response = await apiClient.post('/promos/validate', {
        code,
        order_amount: orderAmount,
      });
      return response.data;
    } catch (error) {
      return { valid: false, message: error.response?.data?.error || 'Invalid promo code' };
    }
  },

  // Create payment intent. promoCode (optional) is validated + applied
  // server-side; the backend returns the discounted amount.
  createPaymentIntent: async (bookingId, amount, promoCode = null) => {
    try {
      const response = await apiClient.post('/payments/create-intent-simple', {
        bookingId,
        amount,
        promoCode,
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
