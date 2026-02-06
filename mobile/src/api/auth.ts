import { apiClient } from './client';
import { AuthResponse, LoginCredentials, RegisterData, User } from '../types';

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    return apiClient.post<AuthResponse>('/auth/login', credentials);
  },

  register: async (data: RegisterData): Promise<AuthResponse> => {
    return apiClient.post<AuthResponse>('/auth/register', data);
  },

  getProfile: async (): Promise<User> => {
    return apiClient.get<User>('/auth/profile');
  },

  logout: async (): Promise<void> => {
    return apiClient.post('/auth/logout');
  },

  refreshToken: async (): Promise<{ access_token: string }> => {
    return apiClient.post('/auth/refresh');
  },
};
