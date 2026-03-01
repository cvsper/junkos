"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Star,
  Briefcase,
  TrendingUp,
  Calendar,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Loader2,
  LogOut,
  Trash2,
  Pencil,
  X,
  ExternalLink,
} from "lucide-react";
import { driverApi, authApi, ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { DriverProfile } from "@/types";

// ---------------------------------------------------------------------------
// Toast notification
// ---------------------------------------------------------------------------

type ToastType = "success" | "error";

interface Toast {
  id: number;
  type: ToastType;
  message: string;
}

let toastId = 0;

function ToastContainer({ toasts }: { toasts: Toast[] }) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`rounded-lg border px-4 py-3 text-sm shadow-lg transition-all animate-in slide-in-from-top-2 ${
            t.type === "success"
              ? "border-green-200 bg-green-50 text-green-800"
              : "border-red-200 bg-red-50 text-red-800"
          }`}
        >
          {t.message}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Truck type options
// ---------------------------------------------------------------------------

const TRUCK_TYPES = [
  { value: "pickup", label: "Pickup Truck" },
  { value: "cargo_van", label: "Cargo Van" },
  { value: "box_truck_sm", label: "Box Truck (Small)" },
  { value: "box_truck_lg", label: "Box Truck (Large)" },
  { value: "flatbed", label: "Flatbed" },
  { value: "dump_truck", label: "Dump Truck" },
];

// ---------------------------------------------------------------------------
// Driver Profile Page
// ---------------------------------------------------------------------------

export default function DriverProfilePage() {
  const router = useRouter();

  // Data
  const [profile, setProfile] = useState<DriverProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit mode
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editTruckType, setEditTruckType] = useState("");
  const [saving, setSaving] = useState(false);

  // Availability toggle
  const [isOnline, setIsOnline] = useState(false);
  const [togglingAvailability, setTogglingAvailability] = useState(false);

  // Stripe
  const [stripeLoading, setStripeLoading] = useState(false);

  // Delete account
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Toasts
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((type: ToastType, message: string) => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  // ---------------------------------------------------------------------------
  // Load profile
  // ---------------------------------------------------------------------------

  const loadProfile = useCallback(async () => {
    try {
      setError(null);
      setLoading(true);
      const res = await driverApi.profile();
      setProfile(res.profile);
      setIsOnline(res.profile.is_online);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load profile");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  // ---------------------------------------------------------------------------
  // Edit handlers
  // ---------------------------------------------------------------------------

  const enterEditMode = () => {
    if (!profile) return;
    setEditName(profile.name || "");
    setEditPhone(profile.phone || "");
    setEditTruckType(profile.truck_type || "");
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await driverApi.updateProfile({
        name: editName.trim() || undefined,
        phone: editPhone.trim() || undefined,
        truck_type: editTruckType || undefined,
      });
      setProfile(res.profile);
      setEditing(false);
      addToast("success", "Profile updated successfully.");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to update profile.";
      addToast("error", message);
    } finally {
      setSaving(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Availability toggle
  // ---------------------------------------------------------------------------

  const handleToggleAvailability = async () => {
    setTogglingAvailability(true);
    try {
      const res = await driverApi.setAvailability(!isOnline);
      setIsOnline(res.is_online);
      addToast("success", res.is_online ? "You are now online." : "You are now offline.");
    } catch {
      addToast("error", "Failed to update availability.");
    } finally {
      setTogglingAvailability(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Stripe handlers
  // ---------------------------------------------------------------------------

  const handleStripeConnect = async () => {
    setStripeLoading(true);
    try {
      const res = await driverApi.stripeConnect();
      window.open(res.url, "_blank");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to connect Stripe.";
      addToast("error", message);
    } finally {
      setStripeLoading(false);
    }
  };

  const handleStripeDashboard = async () => {
    setStripeLoading(true);
    try {
      const res = await driverApi.stripeDashboard();
      window.open(res.url, "_blank");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to open Stripe dashboard.";
      addToast("error", message);
    } finally {
      setStripeLoading(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Delete account
  // ---------------------------------------------------------------------------

  const handleDeleteAccount = async () => {
    setDeleteLoading(true);
    try {
      await authApi.deleteAccount();
      useAuthStore.getState().logout();
      router.push("/");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to delete account.";
      addToast("error", message);
      setDeleteLoading(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  const getInitials = (name: string | null, email: string | null) => {
    if (name) {
      return name
        .split(" ")
        .map((w) => w[0])
        .join("")
        .toUpperCase()
        .slice(0, 2);
    }
    return (email?.[0] || "D").toUpperCase();
  };

  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "long",
      year: "numeric",
    });
  };

  const truckTypeLabel = (value: string | null) => {
    if (!value) return "Not set";
    const found = TRUCK_TYPES.find((t) => t.value === value);
    return found ? found.label : value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  };

  // ---------------------------------------------------------------------------
  // Loading skeleton
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="space-y-6 max-w-3xl mx-auto">
        {/* Header skeleton */}
        <div className="rounded-xl border border-border bg-card p-6 animate-pulse">
          <div className="flex flex-col sm:flex-row items-center gap-4">
            <div className="w-20 h-20 rounded-full bg-muted" />
            <div className="flex-1 space-y-2 text-center sm:text-left">
              <div className="h-6 bg-muted rounded w-40 mx-auto sm:mx-0" />
              <div className="h-4 bg-muted rounded w-56 mx-auto sm:mx-0" />
              <div className="h-5 bg-muted rounded w-16 mx-auto sm:mx-0" />
            </div>
            <div className="h-9 bg-muted rounded w-28" />
          </div>
        </div>
        {/* Info skeleton */}
        <div className="rounded-xl border border-border bg-card p-6 animate-pulse">
          <div className="h-5 bg-muted rounded w-36 mb-4" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="space-y-2">
                <div className="h-3 bg-muted rounded w-16" />
                <div className="h-5 bg-muted rounded w-40" />
              </div>
            ))}
          </div>
        </div>
        {/* Metrics skeleton */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-5 animate-pulse">
              <div className="h-8 bg-muted rounded w-8 mb-3" />
              <div className="h-6 bg-muted rounded w-16 mb-1" />
              <div className="h-3 bg-muted rounded w-20" />
            </div>
          ))}
        </div>
        {/* Additional skeletons */}
        {[...Array(3)].map((_, i) => (
          <div key={i} className="rounded-xl border border-border bg-card p-6 animate-pulse">
            <div className="h-5 bg-muted rounded w-40 mb-3" />
            <div className="h-4 bg-muted rounded w-3/4" />
          </div>
        ))}
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Error state
  // ---------------------------------------------------------------------------

  if (error) {
    return (
      <div className="space-y-6 max-w-3xl mx-auto">
        <h1 className="text-2xl font-display font-bold">Profile</h1>
        <div className="rounded-xl border border-red-200 bg-red-50 p-8 flex flex-col items-center text-center">
          <AlertTriangle className="h-10 w-10 text-red-400 mb-3" />
          <p className="text-red-700 font-medium mb-1">Something went wrong</p>
          <p className="text-sm text-red-600 mb-4">{error}</p>
          <button
            onClick={loadProfile}
            className="inline-flex items-center gap-2 text-sm bg-red-100 text-red-700 px-4 py-2 rounded-lg hover:bg-red-200 transition-colors font-medium"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!profile) return null;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <ToastContainer toasts={toasts} />

      {/* ================================================================== */}
      {/* Profile Header                                                      */}
      {/* ================================================================== */}
      <div className="rounded-xl border border-border bg-card p-6">
        <div className="flex flex-col sm:flex-row items-center gap-4">
          <div className="w-20 h-20 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
            <span className="text-2xl font-bold text-emerald-700">
              {getInitials(profile.name, profile.email)}
            </span>
          </div>
          <div className="flex-1 text-center sm:text-left min-w-0">
            <h1 className="text-xl font-display font-bold truncate">
              {profile.name || "Driver"}
            </h1>
            <p className="text-sm text-muted-foreground truncate">
              {profile.email || "No email on file"}
            </p>
            <span className="inline-block mt-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">
              Driver
            </span>
          </div>
          <button
            onClick={editing ? cancelEdit : enterEditMode}
            className={`inline-flex items-center gap-2 text-sm px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap ${
              editing
                ? "bg-muted text-muted-foreground hover:bg-muted/80"
                : "bg-emerald-600 text-white hover:bg-emerald-700"
            }`}
          >
            {editing ? (
              <>
                <X className="w-4 h-4" />
                Cancel
              </>
            ) : (
              <>
                <Pencil className="w-4 h-4" />
                Edit Profile
              </>
            )}
          </button>
        </div>
      </div>

      {/* ================================================================== */}
      {/* Profile Info Section                                                 */}
      {/* ================================================================== */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-4 sm:px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Profile Information</h2>
        </div>
        <div className="px-4 sm:px-6 py-4 sm:py-6">
          {editing ? (
            <div className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="edit-name" className="block text-sm font-medium">
                  Full Name
                </label>
                <input
                  id="edit-name"
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="Your full name"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="edit-phone" className="block text-sm font-medium">
                  Phone Number
                </label>
                <input
                  id="edit-phone"
                  type="tel"
                  value={editPhone}
                  onChange={(e) => setEditPhone(e.target.value)}
                  placeholder="+1 (555) 000-0000"
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                />
              </div>

              <div className="space-y-2">
                <label htmlFor="edit-truck" className="block text-sm font-medium">
                  Truck Type
                </label>
                <select
                  id="edit-truck"
                  value={editTruckType}
                  onChange={(e) => setEditTruckType(e.target.value)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  <option value="">Select truck type</option>
                  {TRUCK_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-3 pt-2">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="inline-flex items-center gap-2 text-sm bg-emerald-600 text-white px-5 py-2.5 rounded-lg hover:bg-emerald-700 transition-colors font-medium disabled:opacity-50"
                >
                  {saving ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    "Save Changes"
                  )}
                </button>
                <button
                  onClick={cancelEdit}
                  disabled={saving}
                  className="text-sm text-muted-foreground px-4 py-2.5 rounded-lg hover:bg-muted transition-colors font-medium"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <div>
                <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Name
                </dt>
                <dd className="text-sm mt-0.5">{profile.name || "Not set"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Email
                </dt>
                <dd className="text-sm mt-0.5">{profile.email || "Not set"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Phone
                </dt>
                <dd className="text-sm mt-0.5">{profile.phone || "Not set"}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Truck Type
                </dt>
                <dd className="text-sm mt-0.5">{truckTypeLabel(profile.truck_type)}</dd>
              </div>
            </dl>
          )}
        </div>
      </div>

      {/* ================================================================== */}
      {/* Performance Metrics                                                  */}
      {/* ================================================================== */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center mb-3">
            <Star className="w-5 h-5 text-amber-600" />
          </div>
          <p className="text-xl font-bold text-amber-600">
            {profile.avg_rating.toFixed(1)}
            <span className="text-sm font-normal text-muted-foreground"> / 5.0</span>
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">Rating</p>
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center mb-3">
            <Briefcase className="w-5 h-5 text-blue-600" />
          </div>
          <p className="text-xl font-bold text-blue-600">{profile.total_jobs}</p>
          <p className="text-xs text-muted-foreground mt-0.5">Total Jobs</p>
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <div className="w-9 h-9 rounded-lg bg-purple-50 flex items-center justify-center mb-3">
            <TrendingUp className="w-5 h-5 text-purple-600" />
          </div>
          <p className="text-xl font-bold text-purple-600">
            {Math.round(profile.acceptance_rate)}%
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">Acceptance Rate</p>
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center mb-3">
            <Calendar className="w-5 h-5 text-emerald-600" />
          </div>
          <p className="text-xl font-bold text-emerald-600 truncate">
            {formatDate(profile.created_at)}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">Member Since</p>
        </div>
      </div>

      {/* ================================================================== */}
      {/* Stripe Connect                                                       */}
      {/* ================================================================== */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-4 sm:px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Stripe Payouts</h2>
        </div>
        <div className="px-4 sm:px-6 py-4 sm:py-6">
          {profile.stripe_onboarding_complete ? (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center flex-shrink-0">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                </div>
                <div>
                  <p className="text-sm font-medium">Connected to Stripe</p>
                  <p className="text-xs text-muted-foreground">
                    Your payout account is set up and active.
                  </p>
                </div>
              </div>
              <button
                onClick={handleStripeDashboard}
                disabled={stripeLoading}
                className="inline-flex items-center gap-2 text-sm bg-muted text-foreground px-4 py-2 rounded-lg hover:bg-muted/80 transition-colors font-medium whitespace-nowrap self-start sm:self-center"
              >
                {stripeLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <ExternalLink className="w-4 h-4" />
                )}
                Manage Payouts
              </button>
            </div>
          ) : (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center flex-shrink-0">
                  <AlertTriangle className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <p className="text-sm font-medium">Stripe not connected</p>
                  <p className="text-xs text-muted-foreground">
                    Set up Stripe to receive payouts for completed jobs.
                  </p>
                </div>
              </div>
              <button
                onClick={handleStripeConnect}
                disabled={stripeLoading}
                className="inline-flex items-center gap-2 text-sm bg-emerald-600 text-white px-5 py-2.5 rounded-lg hover:bg-emerald-700 transition-colors font-medium whitespace-nowrap self-start sm:self-center"
              >
                {stripeLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    <ExternalLink className="w-4 h-4" />
                    Connect Stripe
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ================================================================== */}
      {/* Availability                                                         */}
      {/* ================================================================== */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-4 sm:px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Availability</h2>
        </div>
        <div className="px-4 sm:px-6 py-4 sm:py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span
                className={`inline-block w-3 h-3 rounded-full ${
                  isOnline ? "bg-emerald-500 animate-pulse" : "bg-muted-foreground/40"
                }`}
              />
              <div>
                <p className="text-sm font-medium">
                  {isOnline ? "Online" : "Offline"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {isOnline
                    ? "You are visible and can receive job offers."
                    : "You are not visible to dispatchers."}
                </p>
              </div>
            </div>
            <button
              onClick={handleToggleAvailability}
              disabled={togglingAvailability}
              className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
                isOnline ? "bg-emerald-600" : "bg-muted-foreground/30"
              }`}
              role="switch"
              aria-checked={isOnline}
            >
              {togglingAvailability ? (
                <span className="absolute inset-0 flex items-center justify-center">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-white" />
                </span>
              ) : (
                <span
                  className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-sm transition-transform ${
                    isOnline ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* ================================================================== */}
      {/* Danger Zone                                                          */}
      {/* ================================================================== */}
      <div className="rounded-xl border border-red-200 bg-card">
        <div className="px-4 sm:px-6 py-4 border-b border-border">
          <h2 className="font-semibold text-red-600">Danger Zone</h2>
        </div>
        <div className="px-4 sm:px-6 py-4 sm:py-6 space-y-4">
          {/* Sign Out */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium">Sign Out</p>
              <p className="text-xs text-muted-foreground">
                Log out of your driver account on this device.
              </p>
            </div>
            <button
              onClick={() => {
                useAuthStore.getState().logout();
                router.push("/driver/login");
              }}
              className="inline-flex items-center gap-2 text-sm border border-border text-foreground px-4 py-2 rounded-lg hover:bg-muted transition-colors font-medium whitespace-nowrap self-start sm:self-center"
            >
              <LogOut className="w-4 h-4" />
              Sign Out
            </button>
          </div>

          <div className="border-t border-border" />

          {/* Delete Account */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-red-600">Delete Account</p>
              <p className="text-xs text-muted-foreground">
                Permanently deactivate your account and remove all data.
              </p>
            </div>
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="inline-flex items-center gap-2 text-sm border border-red-300 text-red-600 px-4 py-2 rounded-lg hover:bg-red-50 hover:text-red-700 transition-colors font-medium whitespace-nowrap self-start sm:self-center"
            >
              <Trash2 className="w-4 h-4" />
              Delete Account
            </button>
          </div>
        </div>
      </div>

      {/* ================================================================== */}
      {/* Delete Confirmation Modal                                            */}
      {/* ================================================================== */}
      {showDeleteConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50"
          onClick={() => setShowDeleteConfirm(false)}
        >
          <div
            className="bg-card rounded-t-xl sm:rounded-xl border border-border shadow-xl w-full sm:max-w-md sm:mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="px-6 pt-6 pb-2">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
                  <Trash2 className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold">Delete Account</h3>
                  <p className="text-sm text-muted-foreground">
                    This action is permanent
                  </p>
                </div>
              </div>
            </div>

            {/* Content */}
            <div className="px-6 py-4">
              <p className="text-sm text-muted-foreground">
                Are you sure you want to delete your account? This action cannot
                be undone. All your data, earnings history, and job records will
                be permanently removed.
              </p>
            </div>

            {/* Footer */}
            <div className="px-6 pb-6 flex items-center gap-3 justify-end">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleteLoading}
                className="text-sm font-medium px-4 py-2.5 rounded-lg border border-border hover:bg-muted transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={deleteLoading}
                className="inline-flex items-center gap-2 text-sm font-medium px-4 py-2.5 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors disabled:opacity-50"
              >
                {deleteLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  "Delete Account"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
