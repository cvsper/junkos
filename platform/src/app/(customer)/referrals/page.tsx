"use client";

import { useEffect, useState, useCallback } from "react";
import { referralsApi } from "@/lib/api";
import type { ReferralStats, ReferralRecord } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Copy,
  Check,
  Gift,
  Users,
  DollarSign,
  Share2,
  UserPlus,
  Truck,
  Star,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800 border-yellow-200",
  signed_up: "bg-blue-100 text-blue-800 border-blue-200",
  completed: "bg-green-100 text-green-800 border-green-200",
  rewarded: "bg-emerald-100 text-emerald-800 border-emerald-200",
};

function statusLabel(status: string): string {
  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ReferralsPage() {
  const [referralCode, setReferralCode] = useState<string>("");
  const [shareUrl, setShareUrl] = useState<string>("");
  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [referrals, setReferrals] = useState<ReferralRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [codeRes, statsRes] = await Promise.all([
        referralsApi.getMyCode(),
        referralsApi.getStats(),
      ]);
      setReferralCode(codeRes.referral_code);
      setShareUrl(
        `${window.location.origin}/book?ref=${codeRes.referral_code}`
      );
      setStats(statsRes.stats);
      setReferrals(statsRes.referrals);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to load referral data.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const copyCode = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(referralCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
    }
  }, [referralCode]);

  const copyLink = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    } catch {
      // Fallback
    }
  }, [shareUrl]);

  const handleShare = useCallback(async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: "Get $10 off your first Umuve pickup!",
          text: `Use my referral code ${referralCode} to get $10 off your first junk removal pickup with Umuve!`,
          url: shareUrl,
        });
      } catch {
        // User cancelled or share failed
      }
    } else {
      copyLink();
    }
  }, [referralCode, shareUrl, copyLink]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8 sm:py-12">
        <div className="flex items-center justify-center py-24">
          <svg
            className="h-8 w-8 animate-spin text-primary"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <span className="ml-3 text-muted-foreground text-sm">
            Loading referral data...
          </span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8 sm:py-12">
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-8 text-center">
          <p className="text-destructive font-medium mb-1">
            Something went wrong
          </p>
          <p className="text-muted-foreground text-sm mb-4">{error}</p>
          <Button variant="outline" size="sm" onClick={fetchData}>
            Try Again
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 sm:py-12">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">
          Refer a Friend
        </h1>
        <p className="text-muted-foreground mt-1">
          Share your code and earn $10 for every friend who completes their
          first pickup.
        </p>
      </div>

      {/* Referral Code Card */}
      <Card className="mb-6 border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
        <CardContent className="p-6 sm:p-8">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6">
            {/* Code display */}
            <div className="flex-1">
              <p className="text-sm font-medium text-muted-foreground mb-2">
                Your Referral Code
              </p>
              <div className="flex items-center gap-3">
                <span className="font-mono text-3xl sm:text-4xl font-bold tracking-widest text-foreground">
                  {referralCode}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={copyCode}
                  className="gap-1.5"
                >
                  {copied ? (
                    <>
                      <Check className="h-4 w-4 text-green-600" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4" />
                      Copy
                    </>
                  )}
                </Button>
              </div>
            </div>

            {/* Share actions */}
            <div className="flex flex-col gap-2 w-full sm:w-auto">
              <Button onClick={handleShare} className="gap-2">
                <Share2 className="h-4 w-4" />
                Share Link
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={copyLink}
                className="gap-1.5 text-xs"
              >
                {copiedLink ? (
                  <>
                    <Check className="h-3.5 w-3.5 text-green-600" />
                    Link Copied!
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" />
                    Copy Share Link
                  </>
                )}
              </Button>
            </div>
          </div>

          {/* Share URL preview */}
          <div className="mt-4 p-3 rounded-md bg-muted/50 border border-border">
            <p className="text-xs text-muted-foreground mb-1">Share Link</p>
            <p className="text-sm font-mono text-foreground break-all">
              {shareUrl}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <Card>
            <CardContent className="p-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                  <Users className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">
                    People Referred
                  </p>
                  <p className="text-2xl font-bold">{stats.total_referred}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                  <Check className="h-5 w-5 text-green-600" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">
                    Jobs Completed
                  </p>
                  <p className="text-2xl font-bold">{stats.completed}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center">
                  <DollarSign className="h-5 w-5 text-emerald-600" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Total Earned</p>
                  <p className="text-2xl font-bold">
                    ${stats.total_earned.toFixed(2)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* How It Works */}
      <Card className="mb-8">
        <CardContent className="p-6 sm:p-8">
          <h2 className="font-display text-xl font-semibold mb-6">
            How It Works
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <div className="flex flex-col items-center text-center gap-3">
              <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center">
                <UserPlus className="h-7 w-7 text-primary" />
              </div>
              <div>
                <p className="font-medium text-sm">1. Share Your Code</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Send your unique referral code or link to friends and family.
                </p>
              </div>
            </div>

            <div className="flex flex-col items-center text-center gap-3">
              <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center">
                <Truck className="h-7 w-7 text-primary" />
              </div>
              <div>
                <p className="font-medium text-sm">2. They Book a Pickup</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Your friend signs up using your code and books their first
                  junk removal.
                </p>
              </div>
            </div>

            <div className="flex flex-col items-center text-center gap-3">
              <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center">
                <Gift className="h-7 w-7 text-primary" />
              </div>
              <div>
                <p className="font-medium text-sm">3. You Both Earn $10</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Once their first job is completed, you both receive a $10
                  reward.
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Referral History */}
      {referrals.length > 0 && (
        <div>
          <h2 className="font-display text-xl font-semibold mb-4">
            Referral History
          </h2>
          <div className="grid gap-3">
            {referrals.map((ref) => (
              <Card key={ref.id}>
                <CardContent className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-muted flex items-center justify-center">
                      <Star className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">
                        {ref.referee_name || "Pending signup"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(ref.created_at)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge
                      className={
                        STATUS_COLORS[ref.status] ??
                        "bg-muted text-muted-foreground"
                      }
                    >
                      {statusLabel(ref.status)}
                    </Badge>
                    {(ref.status === "completed" ||
                      ref.status === "rewarded") && (
                      <span className="text-sm font-semibold text-green-600">
                        +${ref.reward_amount.toFixed(2)}
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Empty referral state */}
      {referrals.length === 0 && (
        <div className="rounded-lg border border-dashed border-border bg-card p-12 text-center">
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
            <Gift className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="font-display text-lg font-semibold mb-1">
            No referrals yet
          </h3>
          <p className="text-muted-foreground text-sm mb-4 max-w-sm mx-auto">
            Share your referral code with friends and start earning rewards
            today!
          </p>
          <Button onClick={handleShare} className="gap-2">
            <Share2 className="h-4 w-4" />
            Share Your Code
          </Button>
        </div>
      )}
    </div>
  );
}
