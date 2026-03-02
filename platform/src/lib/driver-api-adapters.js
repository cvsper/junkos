const STATUS_MAP = {
  accepted: "assigned",
  started: "in_progress",
};

function normalizeAcceptanceRate(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return 0;
  return value <= 1 ? Math.round(value * 100) : Math.round(value);
}

function normalizeDriverStatus(status) {
  if (!status) return "pending";
  return STATUS_MAP[status] || status;
}

export function normalizeDriverJob(job) {
  if (!job) return null;

  const distanceKm =
    typeof job.distance_km === "number" ? job.distance_km : null;
  const distanceMiles =
    typeof job.distance_miles === "number"
      ? job.distance_miles
      : distanceKm == null
        ? null
        : Math.round(distanceKm * 0.621371 * 10) / 10;

  return {
    id: job.id,
    customer_id: job.customer_id ?? null,
    driver_id: job.driver_id ?? null,
    operator_id: job.operator_id ?? null,
    status: normalizeDriverStatus(job.status),
    address: job.address ?? "",
    city: job.city ?? "",
    lat: typeof job.lat === "number" ? job.lat : 0,
    lng: typeof job.lng === "number" ? job.lng : 0,
    items: Array.isArray(job.items) ? job.items : [],
    photos: Array.isArray(job.photos) ? job.photos : [],
    before_photos: Array.isArray(job.before_photos) ? job.before_photos : [],
    after_photos: Array.isArray(job.after_photos) ? job.after_photos : [],
    scheduled_at: job.scheduled_at ?? null,
    total_price: typeof job.total_price === "number" ? job.total_price : 0,
    base_price: typeof job.base_price === "number" ? job.base_price : 0,
    notes: job.notes ?? null,
    distance_miles: distanceMiles,
    customer_name: job.customer_name ?? null,
    customer_phone: job.customer_phone ?? null,
    created_at: job.created_at ?? null,
    updated_at: job.updated_at ?? null,
    started_at: job.started_at ?? null,
    completed_at: job.completed_at ?? null,
  };
}

export function normalizeDriverProfile(profile, stats, stripeStatus) {
  return {
    id: profile?.id ?? "",
    user_id: profile?.user_id ?? "",
    name: profile?.name ?? null,
    email: profile?.email ?? null,
    phone: profile?.phone ?? null,
    truck_type: profile?.truck_type ?? profile?.vehicle_type ?? null,
    license_plate: profile?.license_plate ?? null,
    is_online: Boolean(profile?.is_online),
    approval_status: profile?.approval_status ?? profile?.status ?? "pending",
    onboarding_status: profile?.onboarding_status ?? "pending",
    avg_rating:
      typeof profile?.avg_rating === "number"
        ? profile.avg_rating
        : typeof profile?.rating === "number"
          ? profile.rating
          : 0,
    total_jobs:
      typeof stats?.total_jobs === "number"
        ? stats.total_jobs
        : typeof profile?.total_jobs === "number"
          ? profile.total_jobs
          : 0,
    acceptance_rate: normalizeAcceptanceRate(stats?.acceptance_rate),
    stripe_account_id: profile?.stripe_account_id ?? null,
    stripe_onboarding_complete: Boolean(
      profile?.stripe_onboarding_complete ??
        (stripeStatus?.details_submitted && stripeStatus?.payouts_enabled)
    ),
    created_at: profile?.created_at ?? null,
    updated_at: profile?.updated_at ?? profile?.created_at ?? null,
  };
}

export function normalizeDriverStats(stats) {
  return {
    today_earnings: typeof stats?.today_earnings === "number" ? stats.today_earnings : 0,
    today_jobs: typeof stats?.today_jobs === "number" ? stats.today_jobs : 0,
    rating: typeof stats?.rating === "number" ? stats.rating : 0,
    acceptance_rate: normalizeAcceptanceRate(stats?.acceptance_rate),
    total_earnings:
      typeof stats?.total_earnings === "number"
        ? stats.total_earnings
        : typeof stats?.total_earned === "number"
          ? stats.total_earned
          : 0,
    total_jobs: typeof stats?.total_jobs === "number" ? stats.total_jobs : 0,
    weekly_earnings: Array.isArray(stats?.weekly_earnings)
      ? stats.weekly_earnings
      : [],
  };
}

export function normalizeAvailabilityResponse(response) {
  return {
    success: Boolean(response?.success),
    is_online: Boolean(response?.is_online ?? response?.contractor?.is_online),
  };
}

export function normalizeActiveJobsResponse(response) {
  const jobs = Array.isArray(response?.jobs)
    ? response.jobs
    : response?.job
      ? [response.job]
      : [];

  return {
    success: Boolean(response?.success),
    jobs: jobs.map(normalizeDriverJob).filter(Boolean),
  };
}

export function normalizePagedJobsResponse(response) {
  const jobs = Array.isArray(response?.jobs)
    ? response.jobs.map(normalizeDriverJob).filter(Boolean)
    : [];
  const total =
    typeof response?.total === "number" ? response.total : jobs.length;
  const perPage =
    typeof response?.per_page === "number" && response.per_page > 0
      ? response.per_page
      : jobs.length || 1;
  const pages =
    typeof response?.pages === "number" && response.pages > 0
      ? response.pages
      : Math.max(1, Math.ceil(total / perPage));

  return {
    success: Boolean(response?.success),
    jobs,
    total,
    page: typeof response?.page === "number" ? response.page : 1,
    pages,
  };
}
