// ============================================
// JunkOS Platform TypeScript Types
// ============================================

export type UserRole = "customer" | "driver" | "admin";

export interface User {
  id: string;
  email: string;
  name: string;
  phone: string;
  role: UserRole;
  avatarUrl?: string;
  emailVerified: boolean;
  createdAt: string;
  updatedAt: string;
}

export type JobStatus =
  | "pending"
  | "confirmed"
  | "assigned"
  | "en_route"
  | "arrived"
  | "in_progress"
  | "completed"
  | "cancelled";

export interface Address {
  street: string;
  unit?: string;
  city: string;
  state: string;
  zip: string;
  lat: number;
  lng: number;
}

export interface JobItem {
  id: string;
  name: string;
  category: string;
  quantity: number;
  estimatedWeight?: number;
}

export interface Job {
  id: string;
  customerId: string;
  customer?: User;
  contractorId?: string;
  contractor?: Contractor;
  status: JobStatus;
  address: Address;
  items: JobItem[];
  photos: string[];
  scheduledDate: string;
  scheduledTimeSlot: string;
  estimatedPrice: number;
  finalPrice?: number;
  notes?: string;
  rating?: Rating;
  payment?: Payment;
  truckLoad: number; // percentage 0-100
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
}

export interface Contractor {
  id: string;
  userId: string;
  user?: User;
  vehicleType: string;
  licensePlate: string;
  insuranceVerified: boolean;
  backgroundCheckPassed: boolean;
  isActive: boolean;
  isAvailable: boolean;
  currentLocation?: {
    lat: number;
    lng: number;
  };
  rating: number;
  totalJobs: number;
  serviceAreas: string[];
  createdAt: string;
}

export interface Rating {
  id: string;
  jobId: string;
  customerId: string;
  contractorId: string;
  score: number; // 1-5
  comment?: string;
  createdAt: string;
}

export type PaymentStatus = "pending" | "authorized" | "captured" | "refunded" | "failed";

export interface Payment {
  id: string;
  jobId: string;
  stripePaymentIntentId: string;
  amount: number;
  currency: string;
  status: PaymentStatus;
  tip?: number;
  createdAt: string;
}

export type PricingType = "base" | "per_item" | "per_load" | "per_weight" | "minimum";

export interface PricingRule {
  id: string;
  name: string;
  type: PricingType;
  category?: string;
  basePrice: number;
  pricePerUnit?: number;
  minimumCharge: number;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

// Booking flow types
export interface BookingFormData {
  step: number;
  address: Partial<Address>;
  photos: File[];
  photoUrls: string[];
  items: JobItem[];
  scheduledDate: string;
  scheduledTimeSlot: string;
  notes: string;
  estimatedPrice: number;
}

// Tracking types
export interface TrackingUpdate {
  jobId: string;
  status: JobStatus;
  contractorLocation?: {
    lat: number;
    lng: number;
  };
  eta?: number; // minutes
  message?: string;
  timestamp: string;
}
