// ============================================
// Umuve Platform TypeScript Types
// ============================================

export type UserRole = "customer" | "driver" | "admin" | "operator";

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
  | "delegating"
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
  promo_code?: string;
  customerName?: string;
  customerEmail?: string;
  customerPhone?: string;
}

// ============================================
// Driver Portal Types
// ============================================

export type DriverApprovalStatus = "pending" | "approved" | "rejected" | "suspended";
export type DriverOnboardingStep = "profile" | "documents" | "stripe" | "review";

export interface DriverProfile {
  id: string;
  user_id: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  truck_type: string | null;
  license_plate: string | null;
  is_online: boolean;
  approval_status: DriverApprovalStatus;
  onboarding_status: string;
  avg_rating: number;
  total_jobs: number;
  acceptance_rate: number;
  stripe_account_id: string | null;
  stripe_onboarding_complete: boolean;
  created_at: string;
  updated_at: string;
}

export interface DriverStats {
  today_earnings: number;
  today_jobs: number;
  rating: number;
  acceptance_rate: number;
  total_earnings: number;
  total_jobs: number;
  weekly_earnings: { day: string; amount: number }[];
}

export interface DriverJob {
  id: string;
  customer_id: string;
  driver_id: string | null;
  operator_id: string | null;
  status: string;
  address: string;
  city: string;
  lat: number;
  lng: number;
  items: { category: string; quantity: number }[];
  photos: string[];
  before_photos: string[];
  after_photos: string[];
  scheduled_at: string | null;
  total_price: number;
  base_price: number;
  notes: string | null;
  distance_miles: number | null;
  customer_name: string | null;
  customer_phone: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface DriverEarningsSummary {
  total: number;
  jobs_completed: number;
  avg_per_job: number;
  period: string;
}

export interface DriverEarningsRecord {
  id: string;
  job_id: string;
  address: string;
  amount: number;
  tip: number;
  payout_status: "pending" | "paid" | "processing";
  completed_at: string;
}

export interface DriverOnboardingStatus {
  current_step: DriverOnboardingStep;
  profile_complete: boolean;
  documents_uploaded: boolean;
  stripe_connected: boolean;
  submitted_for_review: boolean;
  approval_status: DriverApprovalStatus;
  rejection_reason: string | null;
  drivers_license_url: string | null;
  insurance_document_url: string | null;
  vehicle_registration_url: string | null;
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
