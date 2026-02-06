export interface User {
  id: number;
  email: string;
  firstName: string;
  lastName: string;
  phone?: string;
}

export interface AuthResponse {
  access_token: string;
  user: User;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
  phone?: string;
}

export interface Address {
  street: string;
  city: string;
  state: string;
  zipCode: string;
  latitude?: number;
  longitude?: number;
}

export interface BookingItem {
  name: string;
  category: string;
  quantity: number;
  description?: string;
}

export interface Booking {
  id?: number;
  address: Address;
  items: BookingItem[];
  photos: string[];
  scheduledDate: string;
  scheduledTime: string;
  estimatedPrice?: number;
  notes?: string;
  status?: 'pending' | 'confirmed' | 'completed' | 'cancelled';
}

export interface PaymentIntent {
  clientSecret: string;
  amount: number;
}

export type RootStackParamList = {
  Welcome: undefined;
  Login: undefined;
  AddressInput: undefined;
  PhotoUpload: { address: Address };
  ItemSelection: { address: Address; photos: string[] };
  DateTimePicker: { address: Address; photos: string[]; items: BookingItem[] };
  Payment: { booking: Booking };
  Confirmation: { bookingId: number };
};
