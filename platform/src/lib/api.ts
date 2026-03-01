import { useAuthStore } from "@/stores/auth-store";
import type {
  User,
  Job,
  JobItem,
  Address,
  BookingFormData,
  TrackingUpdate,
} from "@/types";

// ---------------------------------------------------------------------------
// Base configuration
// ---------------------------------------------------------------------------

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001";

// ---------------------------------------------------------------------------
// Generic fetch wrapper
// ---------------------------------------------------------------------------

class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = useAuthStore.getState().token;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  // Handle 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  let data: unknown;
  try {
    data = await res.json();
  } catch {
    data = null;
  }

  if (!res.ok) {
    const message =
      (data as Record<string, string>)?.message ||
      (data as Record<string, string>)?.error ||
      res.statusText;
    throw new ApiError(message, res.status, data);
  }

  return data as T;
}

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------

interface AuthResponse {
  user: User;
  token: string;
}

export const authApi = {
  login: (email: string, password: string) =>
    apiFetch<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  signup: (email: string, password: string, name: string, phone: string, referralCode?: string) => {
    // Check localStorage for a referral code if none was provided
    // Try new key first, fall back to legacy key for migration
    const refCode =
      referralCode ||
      (typeof window !== "undefined"
        ? localStorage.getItem("umuve_referral_code") ||
          localStorage.getItem("junkos_referral_code") ||
          undefined
        : undefined);

    return apiFetch<AuthResponse>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        name,
        phone,
        ...(refCode ? { referral_code: refCode } : {}),
      }),
    });
  },

  me: () => apiFetch<User>("/api/auth/me"),

  updateProfile: (data: { name?: string; email?: string; phone?: string }) =>
    apiFetch<{ success: boolean; user: User }>("/api/auth/me", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  changePassword: (data: { current_password: string; new_password: string }) =>
    apiFetch<{ success: boolean; message: string }>("/api/auth/change-password", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteAccount: () =>
    apiFetch<{ success: boolean; message: string }>("/api/auth/me", {
      method: "DELETE",
    }),
};

// ---------------------------------------------------------------------------
// Jobs API
// ---------------------------------------------------------------------------

interface CustomerJobResponse {
  id: string;
  customer_id: string;
  driver_id: string | null;
  status: string;
  address: string;
  items: { category: string; quantity: number }[];
  photos: string[];
  before_photos: string[];
  after_photos: string[];
  proof_submitted_at: string | null;
  scheduled_at: string | null;
  total_price: number;
  base_price: number;
  item_total: number;
  service_fee: number;
  surge_multiplier: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  payment?: {
    id: string;
    amount: number;
    payment_status: string;
    tip_amount: number;
  } | null;
  rating?: {
    id: string;
    stars: number;
    comment: string | null;
    created_at: string;
  } | null;
  contractor?: {
    id: string;
    user: { name: string | null; phone: string | null } | null;
    truck_type: string | null;
    avg_rating: number;
    total_jobs: number;
  } | null;
}

interface PublicJobLookupResponse {
  id: string;
  confirmation_code: string;
  status: string;
  address: string;
  items: { category: string; quantity: number }[];
  photos: string[];
  before_photos: string[];
  after_photos: string[];
  scheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  total_price: number;
  created_at: string;
  notes: string | null;
  contractor?: {
    name: string | null;
    truck_type: string | null;
    avg_rating: number;
    total_jobs: number;
  } | null;
}

export const jobsApi = {
  /** Public lookup by confirmation code — no auth required */
  lookup: async (code: string): Promise<{ success: boolean; job: PublicJobLookupResponse }> => {
    const res = await fetch(`${API_BASE_URL}/api/jobs/lookup/${encodeURIComponent(code)}`, {
      headers: { "Content-Type": "application/json" },
    });
    const data = await res.json();
    if (!res.ok) {
      throw new ApiError(data?.error || res.statusText, res.status, data);
    }
    return data;
  },

  list: (status?: string) => {
    const params = status ? `?status=${status}` : "";
    return apiFetch<{ success: boolean; jobs: CustomerJobResponse[] }>(`/api/jobs${params}`);
  },

  get: (id: string) =>
    apiFetch<{ success: boolean; job: CustomerJobResponse }>(`/api/jobs/${id}`),

  cancel: (id: string) =>
    apiFetch<{ success: boolean; job: CustomerJobResponse; cancellation_fee?: number }>(`/api/jobs/${id}/cancel`, {
      method: "PUT",
    }),

  reschedule: (id: string, data: { scheduled_date: string; scheduled_time: string }) =>
    apiFetch<{ success: boolean; job: CustomerJobResponse }>(`/api/jobs/${id}/reschedule`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  /** GET /api/jobs/:id/photos -- get all photos (before/after) for a job */
  getPhotos: (id: string) =>
    apiFetch<{
      success: boolean;
      job_id: string;
      photos: string[];
      before_photos: string[];
      after_photos: string[];
      proof_submitted_at: string | null;
    }>(`/api/jobs/${id}/photos`),
};

// ---------------------------------------------------------------------------
// Booking API
// ---------------------------------------------------------------------------

interface EstimateRequest {
  items: JobItem[];
  address: Partial<Address>;
}

interface EstimateResponse {
  estimatedPrice: number;
  breakdown: { label: string; amount: number }[];
}

interface RawEstimateResponse {
  success: boolean;
  estimate: {
    items_subtotal: number;
    items: { category: string; quantity: number; unit_price: number; line_total: number }[];
    volume_discount: number;
    volume_discount_label: string;
    surge_amount: number;
    surge_reasons: string[];
    base_price: number;
    service_fee: number;
    total: number;
    minimum_applied: boolean;
    minimum_job_price: number;
  };
}

export const bookingApi = {
  estimate: async (items: JobItem[], address: Partial<Address>): Promise<EstimateResponse> => {
    const raw = await apiFetch<RawEstimateResponse>("/api/booking/estimate", {
      method: "POST",
      body: JSON.stringify({ items, address } satisfies EstimateRequest),
    });
    const est = raw.estimate;
    const breakdown: { label: string; amount: number }[] = [
      { label: "Items Subtotal", amount: est.items_subtotal },
    ];
    if (est.volume_discount > 0) {
      breakdown.push({ label: est.volume_discount_label || "Volume Discount", amount: -est.volume_discount });
    }
    if (est.surge_amount > 0) {
      breakdown.push({ label: `Surge (${est.surge_reasons.join(", ")})`, amount: est.surge_amount });
    }
    breakdown.push({ label: "Service Fee", amount: est.service_fee });
    if (est.minimum_applied) {
      const diff = est.total - (est.base_price + est.service_fee + est.surge_amount);
      if (diff > 0) {
        breakdown.push({ label: "Minimum Adjustment", amount: diff });
      }
    }
    return { estimatedPrice: est.total, breakdown };
  },

  submit: (bookingData: BookingFormData) =>
    apiFetch<Job>("/api/booking", {
      method: "POST",
      body: JSON.stringify(bookingData),
    }),
};

// ---------------------------------------------------------------------------
// AI Analysis API
// ---------------------------------------------------------------------------

export interface AiAnalysisItem {
  category: string;
  size: string;
  quantity: number;
  description: string;
}

export interface AiAnalysisResult {
  items: AiAnalysisItem[];
  estimatedVolume: number;
  truckSize: string;
  confidence: number;
  notes: string;
}

interface AiAnalysisResponse {
  success: boolean;
  analysis?: AiAnalysisResult;
  error?: string;
}

export const aiApi = {
  /** POST /api/ai/analyze-photos — analyze photos with GPT-4o-mini Vision */
  analyzePhotos: async (files: File[]): Promise<AiAnalysisResult | null> => {
    const formData = new FormData();
    files.forEach((file) => formData.append("photos", file));

    try {
      const res = await fetch(`${API_BASE_URL}/api/ai/analyze-photos`, {
        method: "POST",
        body: formData,
        // No Content-Type header — browser sets multipart boundary automatically
      });
      const data: AiAnalysisResponse = await res.json();
      if (data.success && data.analysis) {
        return data.analysis;
      }
      return null;
    } catch {
      return null;
    }
  },
};

// ---------------------------------------------------------------------------
// Payments API
// ---------------------------------------------------------------------------

interface CreatePaymentIntentResponse {
  clientSecret: string;
  paymentIntentId: string;
}

interface ConfirmPaymentResponse {
  success: boolean;
  payment: {
    id: string;
    amount: number;
    status: string;
  };
}

export const paymentsApi = {
  createIntent: (bookingId: string, amount: number) =>
    apiFetch<CreatePaymentIntentResponse>(
      "/api/payments/create-intent-simple",
      {
        method: "POST",
        body: JSON.stringify({ bookingId, amount }),
      }
    ),

  confirm: (paymentIntentId: string, bookingId: string) =>
    apiFetch<ConfirmPaymentResponse>("/api/payments/confirm-simple", {
      method: "POST",
      body: JSON.stringify({ paymentIntentId, bookingId }),
    }),
};

// ---------------------------------------------------------------------------
// Tracking API
// ---------------------------------------------------------------------------

export const trackingApi = {
  getStatus: (jobId: string) =>
    apiFetch<TrackingUpdate>(`/api/tracking/${jobId}`),
};

// ---------------------------------------------------------------------------
// Ratings API
// ---------------------------------------------------------------------------

interface RatingResponse {
  id: string;
  job_id: string;
  from_user_id: string;
  to_user_id: string;
  stars: number;
  comment: string | null;
  created_at: string;
  from_user?: { id: string; name: string | null } | null;
}

export const ratingsApi = {
  /** Submit a rating for a completed job */
  submit: (jobId: string, stars: number, comment?: string) =>
    apiFetch<{ success: boolean; rating: RatingResponse }>(
      "/api/ratings",
      {
        method: "POST",
        body: JSON.stringify({ job_id: jobId, stars, comment: comment || null }),
      }
    ),

  /** Get the rating for a specific job (returns null if not yet rated) */
  getForJob: (jobId: string) =>
    apiFetch<{ success: boolean; rating: RatingResponse | null }>(
      `/api/ratings/job/${jobId}`
    ),

  /** Get all ratings for a contractor with pagination */
  getForContractor: (contractorId: string, page?: number, perPage?: number) => {
    const params = new URLSearchParams();
    if (page) params.append("page", String(page));
    if (perPage) params.append("per_page", String(perPage));
    const query = params.toString();
    return apiFetch<{
      success: boolean;
      contractor_id: string;
      avg_rating: number;
      ratings: RatingResponse[];
      total: number;
      page: number;
      pages: number;
    }>(`/api/ratings/contractor/${contractorId}${query ? `?${query}` : ""}`);
  },
};

// ---------------------------------------------------------------------------
// Admin API
// ---------------------------------------------------------------------------

export interface DashboardData {
  total_jobs: number;
  completed_jobs: number;
  pending_jobs: number;
  active_jobs: number;
  total_users: number;
  total_contractors: number;
  approved_contractors: number;
  online_contractors: number;
  revenue_30d: number;
  commission_30d: number;
}

export interface AdminJobRecord {
  id: string;
  customer_name: string;
  customer_email: string;
  address: string;
  status: string;
  operator_id?: string;
  delegated_at?: string;
  scheduled_date: string;
  scheduled_time_slot: string;
  estimated_price: number;
  final_price?: number;
  created_at: string;
}

export interface AdminContractorRecord {
  id: string;
  name: string;
  email: string;
  phone: string;
  truck_type: string;
  approval_status: string;
  rating: number;
  total_jobs: number;
  is_online: boolean;
  is_operator?: boolean;
  operator_id?: string;
  operator_name?: string;
  fleet_size?: number;
  created_at: string;
}

export interface AdminCustomerRecord {
  id: string;
  name: string;
  email: string;
  phone: string;
  total_jobs: number;
  total_spent: number;
  created_at: string;
}

export interface AdminPaymentRecord {
  id: string;
  job_id: string;
  amount: number;
  commission: number;
  driver_payout_amount: number;
  operator_payout_amount: number;
  payout_status: string;
  payment_status: string;
  tip_amount: number;
  created_at: string | null;
  job_address: string | null;
  job_status: string | null;
  driver_name: string | null;
  operator_name: string | null;
  customer_name: string | null;
}

export interface AdminPaymentTotals {
  total_revenue: number;
  total_commission: number;
  total_driver_payouts: number;
  total_operator_payouts: number;
}

interface AdminPaymentsResponse {
  success: boolean;
  payments: AdminPaymentRecord[];
  totals: AdminPaymentTotals;
  total: number;
  page: number;
  pages: number;
}

interface AdminFilters {
  [key: string]: string | number | boolean | undefined;
}

interface PaginatedResponse<T> {
  success: boolean;
  total: number;
  page: number;
  pages: number;
  jobs?: T[];
  contractors?: T[];
  customers?: T[];
}

export const adminApi = {
  dashboard: () =>
    apiFetch<{ success: boolean; dashboard: DashboardData }>(
      "/api/admin/dashboard"
    ),

  jobs: (filters?: AdminFilters) => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== "") params.append(key, String(value));
      });
    }
    const query = params.toString();
    return apiFetch<PaginatedResponse<AdminJobRecord>>(
      `/api/admin/jobs${query ? `?${query}` : ""}`
    );
  },

  contractors: (filters?: AdminFilters) => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== "") params.append(key, String(value));
      });
    }
    const query = params.toString();
    return apiFetch<PaginatedResponse<AdminContractorRecord>>(
      `/api/admin/contractors${query ? `?${query}` : ""}`
    );
  },

  customers: (filters?: AdminFilters) => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== "") params.append(key, String(value));
      });
    }
    const query = params.toString();
    return apiFetch<PaginatedResponse<AdminCustomerRecord>>(
      `/api/admin/customers${query ? `?${query}` : ""}`
    );
  },

  approveContractor: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/admin/contractors/${id}/approve`, {
      method: "PUT",
    }),

  suspendContractor: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/admin/contractors/${id}/suspend`, {
      method: "PUT",
    }),

  promoteToOperator: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/admin/contractors/${id}/promote-operator`, {
      method: "PUT",
    }),

  /** GET /api/admin/payments -- payment records with 3-way split data */
  payments: (filters?: AdminFilters) => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== "") params.append(key, String(value));
      });
    }
    const query = params.toString();
    return apiFetch<AdminPaymentsResponse>(
      `/api/admin/payments${query ? `?${query}` : ""}`
    );
  },

  /** GET /api/admin/analytics -- dashboard chart data */
  analytics: () =>
    apiFetch<{ success: boolean; analytics: AdminAnalytics }>(
      "/api/admin/analytics"
    ),

  /** GET /api/admin/reviews -- list all reviews */
  getReviews: (rating?: number) => {
    const params = rating ? `?rating=${rating}` : "";
    return apiFetch<{ success: boolean; reviews: ReviewRecord[] }>(
      `/api/admin/reviews${params}`
    );
  },

  /** GET /api/admin/pricing/rules -- list all pricing rules */
  pricingRules: () =>
    apiFetch<{ success: boolean; rules: AdminPricingRule[] }>(
      "/api/admin/pricing/rules"
    ),

  /** PUT /api/admin/pricing/rules -- bulk upsert pricing rules */
  updatePricingRules: (rules: Partial<AdminPricingRule>[]) =>
    apiFetch<{ success: boolean; rules: AdminPricingRule[] }>(
      "/api/admin/pricing/rules",
      { method: "PUT", body: JSON.stringify({ rules }) }
    ),

  /** GET /api/admin/pricing/surge -- list all surge zones */
  surgeZones: () =>
    apiFetch<{ success: boolean; surge_zones: AdminSurgeZone[] }>(
      "/api/admin/pricing/surge"
    ),

  /** POST /api/admin/pricing/surge -- create or update a surge zone */
  upsertSurgeZone: (data: SurgeZoneUpsertData) =>
    apiFetch<{ success: boolean; surge_zone: AdminSurgeZone }>(
      "/api/admin/pricing/surge",
      { method: "POST", body: JSON.stringify(data) }
    ),

  /** PUT /api/admin/jobs/:id/assign -- assign contractor to job */
  assignJob: (jobId: string, contractorId: string) =>
    apiFetch<{ success: boolean }>(`/api/admin/jobs/${jobId}/assign`, {
      method: "PUT",
      body: JSON.stringify({ contractor_id: contractorId }),
    }),

  /** PUT /api/admin/jobs/:id/cancel -- cancel a job */
  cancelJob: (jobId: string) =>
    apiFetch<{ success: boolean }>(`/api/admin/jobs/${jobId}/cancel`, {
      method: "PUT",
    }),

  /** GET /api/pricing/config -- full pricing configuration */
  getPricingConfig: () =>
    apiFetch<{ success: boolean; config: PricingConfigData }>(
      "/api/pricing/config"
    ),

  /** PUT /api/admin/pricing/config -- update pricing configuration */
  updatePricingConfig: (config: Partial<PricingConfigUpdatePayload>) =>
    apiFetch<{ success: boolean; config: Record<string, unknown> }>(
      "/api/admin/pricing/config",
      { method: "PUT", body: JSON.stringify({ config }) }
    ),

  /** GET /api/admin/onboarding -- onboarding readiness checks */
  getOnboardingStatus: () =>
    apiFetch<{ success: boolean; checks: OnboardingChecks }>(
      "/api/admin/onboarding"
    ),

  /** GET /api/admin/map-data -- live map contractors + jobs */
  mapData: () =>
    apiFetch<{
      success: boolean;
      contractors: MapContractorPoint[];
      jobs: MapJobPoint[];
    }>("/api/admin/map-data"),

  notifications: (includeRead?: boolean) =>
    apiFetch<NotificationsResponse>(
      `/api/admin/notifications${includeRead ? "?include_read=true" : ""}`
    ),

  markNotificationRead: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/admin/notifications/${id}/read`, {
      method: "PUT",
    }),

  markAllNotificationsRead: () =>
    apiFetch<{ success: boolean }>("/api/admin/notifications/read-all", {
      method: "PUT",
    }),

  /** GET /api/admin/onboarding/applications -- list onboarding applications */
  onboardingApplications: (filters?: AdminFilters) => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== "") params.append(key, String(value));
      });
    }
    const query = params.toString();
    return apiFetch<{
      success: boolean;
      applications: OnboardingApplicationRecord[];
      total: number;
      page: number;
      pages: number;
    }>(`/api/admin/onboarding/applications${query ? `?${query}` : ""}`);
  },

  /** PUT /api/admin/onboarding/:id/review -- approve or reject onboarding */
  reviewOnboarding: (contractorId: string, action: "approve" | "reject", rejectionReason?: string) =>
    apiFetch<{ success: boolean; contractor: OnboardingApplicationRecord; action: string }>(
      `/api/admin/onboarding/${contractorId}/review`,
      {
        method: "PUT",
        body: JSON.stringify({
          action,
          ...(rejectionReason ? { rejection_reason: rejectionReason } : {}),
        }),
      }
    ),

  /** GET /api/admin/promos -- list all promo codes */
  promos: (filters?: AdminFilters) => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== "") params.append(key, String(value));
      });
    }
    const query = params.toString();
    return apiFetch<{
      success: boolean;
      promos: AdminPromoCodeRecord[];
      total: number;
      page: number;
      pages: number;
    }>(`/api/admin/promos${query ? `?${query}` : ""}`);
  },

  /** POST /api/admin/promos -- create a new promo code */
  createPromo: (data: PromoCodeCreatePayload) =>
    apiFetch<{ success: boolean; promo: AdminPromoCodeRecord }>(
      "/api/admin/promos",
      { method: "POST", body: JSON.stringify(data) }
    ),

  /** PUT /api/admin/promos/:id -- update a promo code */
  updatePromo: (id: string, data: Partial<PromoCodeCreatePayload>) =>
    apiFetch<{ success: boolean; promo: AdminPromoCodeRecord }>(
      `/api/admin/promos/${id}`,
      { method: "PUT", body: JSON.stringify(data) }
    ),

  /** DELETE /api/admin/promos/:id -- deactivate a promo code */
  deactivatePromo: (id: string) =>
    apiFetch<{ success: boolean; promo: AdminPromoCodeRecord }>(
      `/api/admin/promos/${id}`,
      { method: "DELETE" }
    ),
};

// ---------------------------------------------------------------------------
// Onboarding types
// ---------------------------------------------------------------------------

export interface OnboardingApplicationRecord {
  id: string;
  user_id: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  truck_type: string | null;
  onboarding_status: string;
  background_check_status: string;
  insurance_document_url: string | null;
  drivers_license_url: string | null;
  vehicle_registration_url: string | null;
  insurance_expiry: string | null;
  license_expiry: string | null;
  onboarding_completed_at: string | null;
  rejection_reason: string | null;
  approval_status: string;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Promo Code types
// ---------------------------------------------------------------------------

export interface AdminPromoCodeRecord {
  id: string;
  code: string;
  discount_type: "percentage" | "fixed";
  discount_value: number;
  min_order_amount: number;
  max_discount: number | null;
  max_uses: number | null;
  use_count: number;
  expires_at: string | null;
  is_active: boolean;
  created_at: string;
  created_by: string | null;
}

export interface PromoCodeCreatePayload {
  code: string;
  discount_type: "percentage" | "fixed";
  discount_value: number;
  min_order_amount?: number;
  max_discount?: number | null;
  max_uses?: number | null;
  expires_at?: string | null;
  is_active?: boolean;
}

export interface PromoValidationResponse {
  valid: boolean;
  error?: string;
  promo?: {
    id: string;
    code: string;
    discount_type: "percentage" | "fixed";
    discount_value: number;
    max_discount: number | null;
    min_order_amount: number;
  };
  discount_amount?: number;
  new_total?: number;
}

// ---------------------------------------------------------------------------
// Promos API (public)
// ---------------------------------------------------------------------------

export const promosApi = {
  /** POST /api/promos/validate -- validate a promo code */
  validate: (code: string, orderAmount: number) =>
    apiFetch<PromoValidationResponse>("/api/promos/validate", {
      method: "POST",
      body: JSON.stringify({ code, order_amount: orderAmount }),
    }),
};

// ---------------------------------------------------------------------------
// Admin sub-types (analytics, pricing, surge)
// ---------------------------------------------------------------------------

export interface AdminAnalytics {
  jobs_by_day: { date: string; count: number }[];
  revenue_by_week: { week_start: string; revenue: number }[];
  jobs_by_status: Record<string, number>;
  top_contractors: {
    id: string;
    name: string | null;
    total_jobs: number;
    avg_rating: number;
  }[];
  busiest_hours: { hour: number; count: number }[];
  avg_job_value: number;
}

export interface AdminPricingRule {
  id: string;
  item_type: string;
  base_price: number;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdminSurgeZone {
  id: string;
  name: string;
  boundary: unknown;
  surge_multiplier: number;
  is_active: boolean;
  start_time: string | null;
  end_time: string | null;
  days_of_week: string[];
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Admin Map types
// ---------------------------------------------------------------------------

export interface MapContractorPoint {
  id: string;
  name: string | null;
  truck_type: string | null;
  avg_rating: number;
  total_jobs: number;
  lat: number;
  lng: number;
}

export interface MapJobPoint {
  id: string;
  address: string;
  status: string;
  lat: number;
  lng: number;
  customer_name: string | null;
  driver_id: string | null;
  total_price: number;
}

// Pricing configuration types
export interface PricingConfigData {
  minimum_job_price: number;
  volume_discount_tiers: {
    min_qty: number;
    max_qty: number | null;
    discount_rate: number;
  }[];
  time_surge: {
    same_day: number;
    next_day: number;
    weekend: number;
  };
  commission_rate: number;
}

export interface PricingConfigUpdatePayload {
  minimum_job_price: number;
  volume_discount_tiers: {
    min_qty: number;
    max_qty: number | null;
    discount_rate: number;
  }[];
  same_day_surge: number;
  next_day_surge: number;
  weekend_surge: number;
  service_fee_rate: number;
}

export interface OnboardingChecks {
  stripe_configured: boolean;
  admin_created: boolean;
  pricing_configured: boolean;
  service_area_defined: boolean;
  contractor_registered: boolean;
}

interface SurgeZoneUpsertData {
  id?: string;
  name: string;
  boundary?: unknown;
  surge_multiplier: number;
  is_active?: boolean;
  start_time?: string;
  end_time?: string;
  days_of_week?: string[];
}

// ---------------------------------------------------------------------------
// Operator API
// ---------------------------------------------------------------------------

export interface OperatorDashboardData {
  fleet_size: number;
  online_count: number;
  pending_delegation: number;
  earnings_30d: number;
}

export interface OperatorFleetContractor {
  id: string;
  name: string | null;
  email: string | null;
  truck_type: string | null;
  is_online: boolean;
  avg_rating: number;
  total_jobs: number;
  approval_status: string;
}

export interface OperatorInvite {
  id: string;
  operator_id: string;
  invite_code: string;
  email: string | null;
  max_uses: number;
  use_count: number;
  expires_at: string | null;
  is_active: boolean;
  created_at: string;
}

export interface OperatorJobRecord {
  id: string;
  customer_id: string;
  driver_id: string | null;
  operator_id: string | null;
  status: string;
  address: string;
  total_price: number;
  created_at: string;
  delegated_at: string | null;
  driver_name: string | null;
  customer_name: string | null;
  customer_email: string | null;
}

export interface OperatorEarnings {
  total: number;
  earnings_30d: number;
  earnings_7d: number;
  per_contractor: {
    contractor_id: string;
    name: string | null;
    commission: number;
    jobs: number;
  }[];
}

export interface OperatorAnalytics {
  earnings_by_week: { week_start: string; amount: number }[];
  jobs_by_day: { date: string; count: number }[];
  per_contractor_jobs: {
    contractor_id: string;
    name: string | null;
    jobs: number;
    commission: number;
  }[];
  delegation_time_avg: number | null;
}

export interface NotificationRecord {
  id: string;
  user_id: string;
  type: string;
  title: string;
  body: string | null;
  data: Record<string, unknown> | null;
  is_read: boolean;
  created_at: string;
}

export interface NotificationsResponse {
  success: boolean;
  notifications: NotificationRecord[];
  unread_count: number;
}

export const operatorApi = {
  dashboard: () =>
    apiFetch<{ success: boolean; dashboard: OperatorDashboardData }>(
      "/api/operator/dashboard"
    ),

  fleet: () =>
    apiFetch<{ success: boolean; contractors: OperatorFleetContractor[] }>(
      "/api/operator/fleet"
    ),

  createInvite: (data: { email?: string; max_uses?: number; expires_days?: number }) =>
    apiFetch<{ success: boolean; invite: OperatorInvite }>(
      "/api/operator/invites",
      { method: "POST", body: JSON.stringify(data) }
    ),

  listInvites: () =>
    apiFetch<{ success: boolean; invites: OperatorInvite[] }>(
      "/api/operator/invites"
    ),

  revokeInvite: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/operator/invites/${id}`, {
      method: "DELETE",
    }),

  jobs: (filter?: string, page?: number) => {
    const params = new URLSearchParams();
    if (filter) params.append("filter", filter);
    if (page) params.append("page", String(page));
    const query = params.toString();
    return apiFetch<{
      success: boolean;
      jobs: OperatorJobRecord[];
      total: number;
      page: number;
      pages: number;
    }>(`/api/operator/jobs${query ? `?${query}` : ""}`);
  },

  delegateJob: (jobId: string, contractorId: string) =>
    apiFetch<{ success: boolean }>(`/api/operator/jobs/${jobId}/delegate`, {
      method: "PUT",
      body: JSON.stringify({ contractor_id: contractorId }),
    }),

  earnings: () =>
    apiFetch<{ success: boolean; earnings: OperatorEarnings }>(
      "/api/operator/earnings"
    ),

  /** GET /api/operator/analytics -- operator analytics chart data */
  analytics: () =>
    apiFetch<{ success: boolean; analytics: OperatorAnalytics }>(
      "/api/operator/analytics"
    ),

  notifications: (includeRead?: boolean) =>
    apiFetch<NotificationsResponse>(
      `/api/operator/notifications${includeRead ? "?include_read=true" : ""}`
    ),

  markNotificationRead: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/operator/notifications/${id}/read`, {
      method: "PUT",
    }),

  markAllNotificationsRead: () =>
    apiFetch<{ success: boolean }>("/api/operator/notifications/read-all", {
      method: "PUT",
    }),
};

// ---------------------------------------------------------------------------
// Referrals API
// ---------------------------------------------------------------------------

export interface ReferralRecord {
  id: string;
  referrer_id: string;
  referee_id: string | null;
  referral_code: string;
  status: "pending" | "signed_up" | "completed" | "rewarded";
  reward_amount: number;
  created_at: string;
  completed_at: string | null;
  referrer_name: string | null;
  referee_name: string | null;
}

export interface ReferralStats {
  total_referred: number;
  signed_up: number;
  completed: number;
  total_earned: number;
  reward_per_referral: number;
}

export const referralsApi = {
  /** GET /api/referrals/my-code -- get current user's referral code */
  getMyCode: () =>
    apiFetch<{
      success: boolean;
      referral_code: string;
      share_url: string;
    }>("/api/referrals/my-code"),

  /** GET /api/referrals/stats -- get referral statistics */
  getStats: () =>
    apiFetch<{
      success: boolean;
      stats: ReferralStats;
      referrals: ReferralRecord[];
    }>("/api/referrals/stats"),

  /** POST /api/referrals/validate/:code -- validate a referral code */
  validate: (code: string) =>
    apiFetch<{
      success: boolean;
      referrer_name: string;
      referral_code: string;
    }>(`/api/referrals/validate/${code}`, {
      method: "POST",
    }),
};

// ---------------------------------------------------------------------------
// Support API
// ---------------------------------------------------------------------------

export interface SupportMessageRecord {
  id: string;
  user_id: string | null;
  name: string;
  email: string;
  message: string;
  category: string;
  status: "open" | "resolved";
  created_at: string;
}

export const supportApi = {
  /** POST /api/support/message -- submit a support message (public) */
  send: (data: {
    name: string;
    email: string;
    message: string;
    category: string;
  }) =>
    apiFetch<{ success: boolean; id: string }>("/api/support/message", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  /** GET /api/admin/support-messages -- admin: list support messages */
  list: (filters?: { status?: string; page?: number; per_page?: number }) => {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined && value !== "")
          params.append(key, String(value));
      });
    }
    const query = params.toString();
    return apiFetch<{
      success: boolean;
      messages: SupportMessageRecord[];
      total: number;
      page: number;
      pages: number;
    }>(`/api/admin/support-messages${query ? `?${query}` : ""}`);
  },

  /** PUT /api/admin/support-messages/:id/resolve -- admin: resolve a message */
  resolve: (id: string) =>
    apiFetch<{ success: boolean; message: SupportMessageRecord }>(
      `/api/admin/support-messages/${id}/resolve`,
      { method: "PUT" }
    ),
};

// ---------------------------------------------------------------------------
// Chat API
// ---------------------------------------------------------------------------

export interface ChatMessageRecord {
  id: string;
  job_id: string;
  sender_id: string;
  sender_role: "customer" | "driver";
  message: string;
  read_at: string | null;
  created_at: string;
}

export const chatApi = {
  /** GET /api/jobs/:id/messages -- get chat messages for a job */
  getMessages: (jobId: string, before?: string, limit?: number) => {
    const params = new URLSearchParams();
    if (before) params.append("before", before);
    if (limit) params.append("limit", String(limit));
    const query = params.toString();
    return apiFetch<{
      success: boolean;
      messages: ChatMessageRecord[];
      has_more: boolean;
    }>(`/api/jobs/${jobId}/messages${query ? `?${query}` : ""}`);
  },

  /** POST /api/jobs/:id/messages -- send a chat message */
  sendMessage: (jobId: string, message: string) =>
    apiFetch<{ success: boolean; message: ChatMessageRecord }>(
      `/api/jobs/${jobId}/messages`,
      { method: "POST", body: JSON.stringify({ message }) }
    ),

  /** PUT /api/jobs/:id/messages/read -- mark messages as read */
  markRead: (jobId: string) =>
    apiFetch<{ success: boolean; marked_read: number }>(
      `/api/jobs/${jobId}/messages/read`,
      { method: "PUT" }
    ),

  /** GET /api/jobs/:id/messages/unread-count -- get unread count */
  unreadCount: (jobId: string) =>
    apiFetch<{ success: boolean; unread_count: number }>(
      `/api/jobs/${jobId}/messages/unread-count`
    ),
};

// ---------------------------------------------------------------------------
// Reviews API
// ---------------------------------------------------------------------------

export interface ReviewRecord {
  id: string;
  job_id: string;
  customer_id: string;
  contractor_id: string;
  rating: number;
  comment: string | null;
  customer_name: string | null;
  created_at: string | null;
}

export const reviewsApi = {
  /** POST /api/reviews -- create a review */
  create: (jobId: string, rating: number, comment?: string) =>
    apiFetch<{ success: boolean; review: ReviewRecord }>("/api/reviews", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId, rating, comment }),
    }),

  /** GET /api/reviews/job/:id -- get review for a job */
  getForJob: (jobId: string) =>
    apiFetch<{ success: boolean; review: ReviewRecord | null }>(
      `/api/reviews/job/${jobId}`
    ),

  /** GET /api/reviews/contractor/:id -- get all reviews for a contractor */
  getForContractor: (contractorId: string, page = 1) =>
    apiFetch<{
      success: boolean;
      reviews: ReviewRecord[];
      avg_rating: number;
      total_reviews: number;
      page: number;
      pages: number;
    }>(`/api/reviews/contractor/${contractorId}?page=${page}`),
};

// ---------------------------------------------------------------------------
// Driver API
// ---------------------------------------------------------------------------

export const driverApi = {
  /** POST /api/driver/register — register as a driver after signup */
  register: (data: { truck_type: string; invite_code?: string }) =>
    apiFetch<{ success: boolean; contractor: Record<string, unknown> }>(
      "/api/driver/register",
      { method: "POST", body: JSON.stringify(data) }
    ),

  /** GET /api/driver/profile — get driver profile */
  profile: () =>
    apiFetch<{ success: boolean; profile: import("@/types").DriverProfile }>(
      "/api/driver/profile"
    ),

  /** PUT /api/driver/profile — update driver profile */
  updateProfile: (data: { name?: string; phone?: string; truck_type?: string }) =>
    apiFetch<{ success: boolean; profile: import("@/types").DriverProfile }>(
      "/api/driver/profile",
      { method: "PUT", body: JSON.stringify(data) }
    ),

  /** GET /api/driver/stats — get driver stats */
  stats: () =>
    apiFetch<{ success: boolean; stats: import("@/types").DriverStats }>(
      "/api/driver/stats"
    ),

  /** PUT /api/driver/availability — toggle online/offline */
  setAvailability: (isOnline: boolean) =>
    apiFetch<{ success: boolean; is_online: boolean }>(
      "/api/driver/availability",
      { method: "PUT", body: JSON.stringify({ is_online: isOnline }) }
    ),

  /** PUT /api/driver/location — update current location */
  updateLocation: (lat: number, lng: number) =>
    apiFetch<{ success: boolean }>("/api/driver/location", {
      method: "PUT",
      body: JSON.stringify({ lat, lng }),
    }),

  /** GET /api/driver/onboarding — get onboarding status */
  onboardingStatus: () =>
    apiFetch<{
      success: boolean;
      onboarding: import("@/types").DriverOnboardingStatus;
    }>("/api/driver/onboarding"),

  /** POST /api/driver/onboarding/documents — upload documents (multipart) */
  uploadDocuments: async (files: {
    drivers_license?: File;
    insurance?: File;
    vehicle_registration?: File;
  }) => {
    const token = useAuthStore.getState().token;
    const formData = new FormData();
    if (files.drivers_license) formData.append("drivers_license", files.drivers_license);
    if (files.insurance) formData.append("insurance", files.insurance);
    if (files.vehicle_registration) formData.append("vehicle_registration", files.vehicle_registration);

    const res = await fetch(`${API_BASE_URL}/api/driver/onboarding/documents`, {
      method: "POST",
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new ApiError(data?.message || data?.error || res.statusText, res.status, data);
    return data as { success: boolean };
  },

  /** POST /api/driver/onboarding/submit — submit for review */
  submitOnboarding: () =>
    apiFetch<{ success: boolean }>("/api/driver/onboarding/submit", {
      method: "POST",
    }),

  /** POST /api/driver/stripe/connect — create Stripe Connect account */
  stripeConnect: () =>
    apiFetch<{ success: boolean; url: string }>("/api/driver/stripe/connect", {
      method: "POST",
    }),

  /** GET /api/driver/stripe/status — check Stripe Connect status */
  stripeStatus: () =>
    apiFetch<{
      success: boolean;
      connected: boolean;
      stripe_account_id: string | null;
      details_submitted: boolean;
      charges_enabled: boolean;
    }>("/api/driver/stripe/status"),

  /** GET /api/driver/stripe/dashboard — get Stripe Express dashboard link */
  stripeDashboard: () =>
    apiFetch<{ success: boolean; url: string }>("/api/driver/stripe/dashboard"),

  /** GET /api/driver/jobs/available — list available jobs */
  availableJobs: (radius?: number, page?: number) => {
    const params = new URLSearchParams();
    if (radius) params.append("radius", String(radius));
    if (page) params.append("page", String(page));
    const query = params.toString();
    return apiFetch<{
      success: boolean;
      jobs: import("@/types").DriverJob[];
      total: number;
      page: number;
      pages: number;
    }>(`/api/driver/jobs/available${query ? `?${query}` : ""}`);
  },

  /** GET /api/driver/jobs/active — list driver's active jobs */
  activeJobs: () =>
    apiFetch<{ success: boolean; jobs: import("@/types").DriverJob[] }>(
      "/api/driver/jobs/active"
    ),

  /** GET /api/driver/jobs/completed — list driver's completed jobs */
  completedJobs: (page?: number) => {
    const params = page ? `?page=${page}` : "";
    return apiFetch<{
      success: boolean;
      jobs: import("@/types").DriverJob[];
      total: number;
      page: number;
      pages: number;
    }>(`/api/driver/jobs/completed${params}`);
  },

  /** GET /api/driver/jobs/:id — get job detail */
  getJob: (id: string) =>
    apiFetch<{ success: boolean; job: import("@/types").DriverJob }>(
      `/api/driver/jobs/${id}`
    ),

  /** PUT /api/driver/jobs/:id/accept — accept a job */
  acceptJob: (id: string) =>
    apiFetch<{ success: boolean; job: import("@/types").DriverJob }>(
      `/api/driver/jobs/${id}/accept`,
      { method: "PUT" }
    ),

  /** PUT /api/driver/jobs/:id/decline — decline a job */
  declineJob: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/driver/jobs/${id}/decline`, {
      method: "PUT",
    }),

  /** PUT /api/driver/jobs/:id/status — update job status */
  updateJobStatus: (id: string, status: string, lat?: number, lng?: number) =>
    apiFetch<{ success: boolean; job: import("@/types").DriverJob }>(
      `/api/driver/jobs/${id}/status`,
      {
        method: "PUT",
        body: JSON.stringify({ status, ...(lat && lng ? { lat, lng } : {}) }),
      }
    ),

  /** POST /api/driver/jobs/:id/photos — upload job photos (multipart) */
  uploadJobPhotos: async (
    id: string,
    photos: File[],
    type: "before" | "after"
  ) => {
    const token = useAuthStore.getState().token;
    const formData = new FormData();
    photos.forEach((file) => formData.append("photos", file));
    formData.append("type", type);

    const res = await fetch(`${API_BASE_URL}/api/driver/jobs/${id}/photos`, {
      method: "POST",
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) throw new ApiError(data?.message || data?.error || res.statusText, res.status, data);
    return data as { success: boolean; urls: string[] };
  },

  /** GET /api/driver/earnings — get earnings summary */
  earnings: (period?: "today" | "week" | "month" | "all") => {
    const params = period ? `?period=${period}` : "";
    return apiFetch<{
      success: boolean;
      summary: import("@/types").DriverEarningsSummary;
      records: import("@/types").DriverEarningsRecord[];
      weekly_chart: { day: string; amount: number }[];
    }>(`/api/driver/earnings${params}`);
  },

  /** GET /api/driver/notifications — get driver notifications */
  notifications: (includeRead?: boolean) =>
    apiFetch<NotificationsResponse>(
      `/api/driver/notifications${includeRead ? "?include_read=true" : ""}`
    ),

  /** PUT /api/driver/notifications/:id/read — mark notification as read */
  markNotificationRead: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/driver/notifications/${id}/read`, {
      method: "PUT",
    }),

  /** PUT /api/driver/notifications/read-all — mark all notifications as read */
  markAllNotificationsRead: () =>
    apiFetch<{ success: boolean }>("/api/driver/notifications/read-all", {
      method: "PUT",
    }),
};

// Re-export the error class for consumers
export { ApiError };
