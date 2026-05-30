"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Gift,
  Users,
  Copy,
  Check,
  Loader2,
  Share2,
  Truck,
  PartyPopper,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { referralsApi, ApiError } from "@/lib/api";

const BONUS = 100; // mirrors CONTRACTOR_REFERRAL_BONUS default

export default function DriverReferralPage() {
  // --- "my code" side (existing hauler recruits) ---
  const [myCode, setMyCode] = useState<string | null>(null);
  const [totalReferrals, setTotalReferrals] = useState(0);
  const [creditsEarned, setCreditsEarned] = useState(0);
  const [loadingCode, setLoadingCode] = useState(true);
  const [copied, setCopied] = useState(false);

  // --- "apply a code" side (new hauler claims a referrer) ---
  const [codeInput, setCodeInput] = useState("");
  const [applying, setApplying] = useState(false);
  const [applyMsg, setApplyMsg] = useState<string | null>(null);
  const [applyErr, setApplyErr] = useState<string | null>(null);

  const loadCode = useCallback(async () => {
    try {
      const res = await referralsApi.getMyCode();
      setMyCode(res.referral_code);
      setTotalReferrals(res.total_referrals ?? 0);
      setCreditsEarned(res.credits_earned ?? 0);
    } catch {
      // non-fatal — the apply side still works
    } finally {
      setLoadingCode(false);
    }
  }, []);

  useEffect(() => {
    loadCode();
  }, [loadCode]);

  const copyCode = async () => {
    if (!myCode) return;
    try {
      await navigator.clipboard.writeText(myCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard blocked — no-op */
    }
  };

  const shareCode = async () => {
    if (!myCode) return;
    const text = `Drive with umuve — we send you paid junk-removal jobs, you accept from a text and get paid same day. Use my code ${myCode} and we each get $${BONUS} after your first job.`;
    if (typeof navigator !== "undefined" && "share" in navigator) {
      try {
        await (navigator as Navigator & { share: (d: ShareData) => Promise<void> }).share({
          title: "Drive with umuve",
          text,
        });
        return;
      } catch {
        /* user cancelled — fall through to copy */
      }
    }
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* no-op */
    }
  };

  const applyCode = async () => {
    const code = codeInput.trim().toUpperCase();
    setApplyErr(null);
    setApplyMsg(null);
    if (code.length !== 8) {
      setApplyErr("Referral codes are 8 characters.");
      return;
    }
    setApplying(true);
    try {
      const res = await referralsApi.applyContractorReferral(code);
      setApplyMsg(res.message);
      setCodeInput("");
    } catch (e) {
      const msg =
        e instanceof ApiError && e.data && typeof e.data === "object" && "error" in e.data
          ? String((e.data as { error: unknown }).error)
          : "Couldn't apply that code. Double-check it and try again.";
      setApplyErr(msg);
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="min-h-[80vh] bg-background">
      <div className="max-w-lg mx-auto px-4 py-6 sm:py-10 space-y-5">
        {/* Header */}
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-extrabold tracking-tight">
            Refer a hauler
          </h1>
          <p className="text-muted-foreground text-sm mt-1.5 leading-relaxed">
            Know someone with a truck? You both earn{" "}
            <span className="text-primary font-semibold">${BONUS}</span> once they
            finish their first umuve job.
          </p>
        </div>

        {/* Your code card */}
        <Card className="overflow-hidden border-border/60">
          <div className="bg-gradient-to-br from-primary/15 to-primary/[0.03] px-6 py-6 relative">
            <div className="pointer-events-none absolute -top-16 -right-10 h-40 w-40 rounded-full bg-primary/10 blur-3xl" />
            <div className="relative flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-semibold">
              <Gift className="w-4 h-4 text-primary" /> Your invite code
            </div>

            {loadingCode ? (
              <div className="flex items-center gap-2 mt-4 text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" /> Loading…
              </div>
            ) : myCode ? (
              <>
                <div className="mt-3 flex items-center gap-3">
                  <code className="font-display text-3xl font-extrabold tracking-[0.2em] text-foreground">
                    {myCode}
                  </code>
                  <button
                    onClick={copyCode}
                    aria-label="Copy code"
                    className="inline-flex items-center justify-center h-9 w-9 rounded-xl border border-border/70 bg-background/70 backdrop-blur hover:bg-background transition-colors"
                  >
                    {copied ? (
                      <Check className="w-4 h-4 text-primary" />
                    ) : (
                      <Copy className="w-4 h-4 text-muted-foreground" />
                    )}
                  </button>
                </div>
                <Button onClick={shareCode} size="sm" className="gap-2 mt-4">
                  <Share2 className="w-4 h-4" /> Share invite
                </Button>
              </>
            ) : (
              <p className="mt-3 text-sm text-muted-foreground">
                Your code will appear once your profile is set up.
              </p>
            )}
          </div>

          {/* rollup stats */}
          <CardContent className="grid grid-cols-2 divide-x divide-border/60 py-0 px-0">
            <Stat
              icon={<Users className="w-4 h-4" />}
              label="Haulers referred"
              value={String(totalReferrals)}
            />
            <Stat
              icon={<PartyPopper className="w-4 h-4" />}
              label="Bonuses earned"
              value={`$${creditsEarned.toFixed(0)}`}
            />
          </CardContent>
        </Card>

        {/* Apply a code card */}
        <Card className="border-border/60">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Truck className="w-4 h-4 text-muted-foreground" />
              Were you referred?
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Enter the code another hauler gave you. You&apos;ll both earn $
              {BONUS} after your first completed job.
            </p>
            <div className="flex gap-2">
              <Input
                value={codeInput}
                onChange={(e) => setCodeInput(e.target.value.toUpperCase())}
                placeholder="8-CHAR CODE"
                maxLength={8}
                className="font-mono tracking-[0.15em] uppercase"
                disabled={applying}
              />
              <Button
                onClick={applyCode}
                disabled={applying || codeInput.trim().length !== 8}
                className="gap-2 flex-shrink-0"
              >
                {applying ? <Loader2 className="w-4 h-4 animate-spin" /> : "Apply"}
              </Button>
            </div>

            {applyMsg && (
              <div className="rounded-lg border border-primary/30 bg-primary/5 px-3 py-2.5 text-sm text-foreground flex items-center gap-2">
                <Check className="w-4 h-4 text-primary flex-shrink-0" />
                <span>{applyMsg}</span>
              </div>
            )}
            {applyErr && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2.5 text-sm text-destructive">
                {applyErr}
              </div>
            )}
          </CardContent>
        </Card>

        {/* How it works */}
        <Card className="border-border/60 bg-muted/30">
          <CardContent className="py-5">
            <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-semibold mb-3">
              How it works
            </p>
            <ol className="space-y-2.5 text-sm">
              {[
                "Share your code with a hauler you trust.",
                "They enter it here when they sign up to drive.",
                `They complete their first job — you both get $${BONUS}.`,
              ].map((step, i) => (
                <li key={i} className="flex gap-3">
                  <span className="flex-shrink-0 mt-0.5 w-5 h-5 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center">
                    {i + 1}
                  </span>
                  <span className="text-muted-foreground">{step}</span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>

        <Badge
          variant="outline"
          className="gap-1.5 text-xs font-medium border-primary/30 text-primary"
        >
          <Gift className="w-3 h-3" />
          More trucks, faster pickups, more jobs for everyone
        </Badge>
      </div>
    </div>
  );
}

function Stat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-5 gap-1">
      <span className="text-muted-foreground">{icon}</span>
      <span className="font-display text-2xl font-extrabold">{value}</span>
      <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">
        {label}
      </span>
    </div>
  );
}
