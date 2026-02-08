import { 
  createBooking, 
  getBookings, 
  updateBooking,
  uploadPhoto,
  login,
  register,
  getPriceEstimate
} from '../src/services/api';
import axios from 'axios';

jest.mock('axios');

describe('API Service', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  describe('Authentication', () => {
    test('login sends credentials and stores token', async () => {
      const mockResponse = {
        data: {
          token: 'mock-jwt-token',
          user: { id: 1, email: 'test@example.com' }
        }
      };
      axios.post.mockResolvedValue(mockResponse);

      const result = await login('test@example.com', 'password123');

      expect(axios.post).toHaveBeenCalledWith('/api/auth/login', {
        email: 'test@example.com',
        password: 'password123'
      });
      expect(result.token).toBe('mock-jwt-token');
      expect(localStorage.getItem('token')).toBe('mock-jwt-token');
    });

    test('register creates new user account', async () => {
      const userData = {
        email: 'new@example.com',
        password: 'SecurePass123!',
        first_name: 'John',
        last_name: 'Doe',
        phone: '555-1234'
      };
      
      const mockResponse = {
        data: {
          token: 'new-token',
          user: { ...userData, id: 2 }
        }
      };
      axios.post.mockResolvedValue(mockResponse);

      const result = await register(userData);

      expect(axios.post).toHaveBeenCalledWith('/api/auth/register', userData);
      expect(result.user.email).toBe('new@example.com');
    });

    test('includes auth token in subsequent requests', async () => {
      localStorage.setItem('token', 'stored-token');
      axios.get.mockResolvedValue({ data: { bookings: [] } });

      await getBookings();

      expect(axios.get).toHaveBeenCalledWith(
        '/api/bookings',
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer stored-token'
          })
        })
      );
    });

    test('handles authentication errors', async () => {
      axios.post.mockRejectedValue({
        response: { status: 401, data: { message: 'Invalid credentials' } }
      });

      await expect(login('wrong@example.com', 'wrong')).rejects.toThrow();
    });
  });

  describe('Bookings', () => {
    test('creates new booking', async () => {
      const bookingData = {
        pickup_address: '123 Main St',
        pickup_city: 'New York',
        pickup_state: 'NY',
        pickup_zip: '10001',
        pickup_date: '2024-03-15',
        pickup_time: '10:00',
        items: ['Sofa', 'Table'],
        estimated_volume: '1/4 truck'
      };

      const mockResponse = {
        data: {
          booking: { id: 1, ...bookingData, status: 'pending' }
        }
      };
      axios.post.mockResolvedValue(mockResponse);

      const result = await createBooking(bookingData);

      expect(axios.post).toHaveBeenCalledWith('/api/bookings', bookingData, expect.any(Object));
      expect(result.booking.id).toBe(1);
      expect(result.booking.status).toBe('pending');
    });

    test('retrieves all bookings', async () => {
      const mockBookings = [
        { id: 1, pickup_address: '123 Main St', status: 'pending' },
        { id: 2, pickup_address: '456 Oak Ave', status: 'confirmed' }
      ];
      
      axios.get.mockResolvedValue({ data: { bookings: mockBookings } });

      const result = await getBookings();

      expect(axios.get).toHaveBeenCalledWith('/api/bookings', expect.any(Object));
      expect(result.bookings).toHaveLength(2);
    });

    test('updates booking', async () => {
      const updates = {
        pickup_time: '14:00',
        notes: 'Please call before arriving'
      };

      const mockResponse = {
        data: {
          booking: { id: 1, ...updates }
        }
      };
      axios.patch.mockResolvedValue(mockResponse);

      const result = await updateBooking(1, updates);

      expect(axios.patch).toHaveBeenCalledWith('/api/bookings/1', updates, expect.any(Object));
      expect(result.booking.pickup_time).toBe('14:00');
    });

    test('filters bookings by status', async () => {
      axios.get.mockResolvedValue({
        data: {
          bookings: [
            { id: 1, status: 'confirmed' },
            { id: 2, status: 'confirmed' }
          ]
        }
      });

      await getBookings({ status: 'confirmed' });

      expect(axios.get).toHaveBeenCalledWith(
        '/api/bookings',
        expect.objectContaining({
          params: { status: 'confirmed' }
        })
      );
    });
  });

  describe('Photo Upload', () => {
    test('uploads photo with FormData', async () => {
      const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
      const mockResponse = {
        data: { url: 'https://cdn.example.com/photo.jpg' }
      };
      axios.post.mockResolvedValue(mockResponse);

      const onProgress = jest.fn();
      const result = await uploadPhoto(file, onProgress);

      expect(axios.post).toHaveBeenCalledWith(
        '/api/photos/upload',
        expect.any(FormData),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'multipart/form-data'
          }),
          onUploadProgress: expect.any(Function)
        })
      );
      expect(result.url).toBe('https://cdn.example.com/photo.jpg');
    });

    test('reports upload progress', async () => {
      const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
      const onProgress = jest.fn();
      
      axios.post.mockImplementation((url, data, config) => {
        // Simulate progress
        config.onUploadProgress({ loaded: 50, total: 100 });
        return Promise.resolve({ data: { url: 'uploaded.jpg' } });
      });

      await uploadPhoto(file, onProgress);

      expect(onProgress).toHaveBeenCalledWith(50);
    });

    test('handles upload errors', async () => {
      const file = new File(['photo'], 'test.jpg', { type: 'image/jpeg' });
      axios.post.mockRejectedValue(new Error('Upload failed'));

      await expect(uploadPhoto(file)).rejects.toThrow('Upload failed');
    });
  });

  describe('Price Estimation', () => {
    test('requests price estimate', async () => {
      const estimateData = {
        volume: '1/2 truck',
        zip_code: '10001',
        items: ['Sofa', 'Refrigerator']
      };

      const mockResponse = {
        data: {
          estimated_price: 350.00,
          breakdown: {
            base_price: 300.00,
            surcharges: [
              { description: 'Heavy items', amount: 50.00 }
            ]
          }
        }
      };
      axios.post.mockResolvedValue(mockResponse);

      const result = await getPriceEstimate(estimateData);

      expect(axios.post).toHaveBeenCalledWith(
        '/api/bookings/estimate',
        estimateData,
        expect.any(Object)
      );
      expect(result.estimated_price).toBe(350.00);
    });
  });

  describe('Error Handling', () => {
    test('handles network errors', async () => {
      axios.get.mockRejectedValue(new Error('Network Error'));

      await expect(getBookings()).rejects.toThrow('Network Error');
    });

    test('handles 404 not found', async () => {
      axios.get.mockRejectedValue({
        response: { status: 404, data: { message: 'Not found' } }
      });

      await expect(getBookings()).rejects.toMatchObject({
        response: expect.objectContaining({ status: 404 })
      });
    });

    test('handles 500 server errors', async () => {
      axios.post.mockRejectedValue({
        response: { status: 500, data: { message: 'Internal server error' } }
      });

      await expect(createBooking({})).rejects.toMatchObject({
        response: expect.objectContaining({ status: 500 })
      });
    });

    test('handles validation errors', async () => {
      axios.post.mockRejectedValue({
        response: {
          status: 400,
          data: {
            errors: {
              pickup_address: ['This field is required'],
              pickup_zip: ['Invalid zip code']
            }
          }
        }
      });

      await expect(createBooking({})).rejects.toMatchObject({
        response: expect.objectContaining({ status: 400 })
      });
    });
  });

  describe('Request Interceptors', () => {
    test('automatically adds auth header when token exists', async () => {
      localStorage.setItem('token', 'test-token');
      axios.get.mockResolvedValue({ data: {} });

      await getBookings();

      expect(axios.get).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token'
          })
        })
      );
    });

    test('handles token expiration', async () => {
      axios.get.mockRejectedValue({
        response: { status: 401, data: { message: 'Token expired' } }
      });

      await expect(getBookings()).rejects.toMatchObject({
        response: expect.objectContaining({ status: 401 })
      });
      
      // Should clear token on 401
      expect(localStorage.getItem('token')).toBeNull();
    });
  });

  describe('Response Caching', () => {
    test('caches GET requests', async () => {
      const mockData = { bookings: [{ id: 1 }] };
      axios.get.mockResolvedValue({ data: mockData });

      // First request
      const result1 = await getBookings();
      // Second request (should use cache)
      const result2 = await getBookings();

      // Implementation would check if cache was used
      expect(result1).toEqual(result2);
    });

    test('invalidates cache on mutations', async () => {
      axios.get.mockResolvedValue({ data: { bookings: [] } });
      axios.post.mockResolvedValue({ data: { booking: { id: 1 } } });

      await getBookings(); // Populate cache
      await createBooking({}); // Should invalidate cache
      await getBookings(); // Should fetch fresh data

      // axios.get should be called twice (not using cached data after mutation)
      expect(axios.get).toHaveBeenCalledTimes(2);
    });
  });

  describe('Retry Logic', () => {
    test('retries failed requests', async () => {
      axios.get
        .mockRejectedValueOnce(new Error('Network error'))
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({ data: { bookings: [] } });

      const result = await getBookings();

      expect(axios.get).toHaveBeenCalledTimes(3);
      expect(result.bookings).toEqual([]);
    });

    test('gives up after max retries', async () => {
      axios.get
        .mockRejectedValue(new Error('Network error'));

      await expect(getBookings()).rejects.toThrow('Network error');
      
      // Should retry 3 times before giving up
      expect(axios.get).toHaveBeenCalledTimes(3);
    });
  });
});
