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

  signup: (email: string, password: string, name: string, phone: string) =>
    apiFetch<AuthResponse>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, name, phone }),
    }),

  me: () => apiFetch<User>("/api/auth/me"),
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

export const jobsApi = {
  list: (status?: string) => {
    const params = status ? `?status=${status}` : "";
    return apiFetch<{ success: boolean; jobs: CustomerJobResponse[] }>(`/api/jobs${params}`);
  },

  get: (id: string) =>
    apiFetch<{ success: boolean; job: CustomerJobResponse }>(`/api/jobs/${id}`),

  cancel: (id: string) =>
    apiFetch<{ success: boolean; job: CustomerJobResponse }>(`/api/jobs/${id}/cancel`, {
      method: "POST",
    }),
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

export const bookingApi = {
  estimate: (items: JobItem[], address: Partial<Address>) =>
    apiFetch<EstimateResponse>("/api/booking/estimate", {
      method: "POST",
      body: JSON.stringify({ items, address } satisfies EstimateRequest),
    }),

  submit: (bookingData: BookingFormData) =>
    apiFetch<Job>("/api/booking", {
      method: "POST",
      body: JSON.stringify(bookingData),
    }),
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

// Re-export the error class for consumers
export { ApiError };
