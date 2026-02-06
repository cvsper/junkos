import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('authToken')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authAPI = {
  login: (credentials) => api.post('/api/auth/login', credentials),
  logout: () => api.post('/api/auth/logout'),
  getCurrentUser: () => api.get('/api/auth/me'),
}

// Jobs API
export const jobsAPI = {
  getAll: (params) => api.get('/api/jobs', { params }),
  getById: (id) => api.get(`/api/jobs/${id}`),
  create: (data) => api.post('/api/jobs', data),
  update: (id, data) => api.patch(`/api/jobs/${id}`, data),
  delete: (id) => api.delete(`/api/jobs/${id}`),
  updateStatus: (id, status) => api.patch(`/api/jobs/${id}/status`, { status }),
  assignDriver: (id, driverId) => api.patch(`/api/jobs/${id}/assign`, { driver_id: driverId }),
}

// Drivers API
export const driversAPI = {
  getAll: (params) => api.get('/api/drivers', { params }),
  getById: (id) => api.get(`/api/drivers/${id}`),
  create: (data) => api.post('/api/drivers', data),
  update: (id, data) => api.patch(`/api/drivers/${id}`, data),
  delete: (id) => api.delete(`/api/drivers/${id}`),
  updateAvailability: (id, available) => api.patch(`/api/drivers/${id}/availability`, { available }),
}

// Analytics API
export const analyticsAPI = {
  getDashboard: () => api.get('/api/analytics/dashboard'),
  getRevenue: (params) => api.get('/api/analytics/revenue', { params }),
  getJobStats: (params) => api.get('/api/analytics/jobs', { params }),
}

export default api
