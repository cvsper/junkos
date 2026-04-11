"use client";

import { useState, useEffect } from "react";
import { Gift, Copy, Check, Share2, MessageCircle, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { referralsApi } from "@/lib/api";

export function ReferralPrompt() {
  const [referralCode, setReferralCode] = useState<string>("");
  const [copied, setCopied] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    referralsApi.getMyCode()
      .then(res => {
        setReferralCode(res.referral_code);
      })
      .catch(err => {
        console.error("Failed to fetch referral code", err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  const shareUrl = `https://goumuve.com/book?ref=${referralCode}`;
  const shareText = `Get $20 off your first junk removal with Umuve! Use my code ${referralCode} or book here: ${shareUrl}`;

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy link.");
    }
  };

  const shareViaSMS = () => {
    window.location.href = `sms:?&body=${encodeURIComponent(shareText)}`;
  };

  const shareViaWhatsApp = () => {
    window.open(`https://wa.me/?text=${encodeURIComponent(shareText)}`, "_blank");
  };

  const shareViaEmail = () => {
    window.location.href = `mailto:?subject=${encodeURIComponent("Get $20 off Umuve Junk Removal")}&body=${encodeURIComponent(shareText)}`;
  };

  if (isLoading || !referralCode) return null;

  return (
    <div className="w-full max-w-sm mt-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="rounded-xl border-2 border-primary/20 bg-primary/5 p-6 text-center space-y-4">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
          <Gift className="h-6 w-6 text-primary" />
        </div>
        
        <div>
          <h3 className="font-display text-xl font-bold text-foreground">
            Share & Save $20
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            Give friends $20 off their first pickup, and you&apos;ll get $20 off your next one!
          </p>
        </div>

        <div className="flex items-center gap-2 bg-background border border-border rounded-lg p-2 pl-4">
          <code className="flex-1 text-left font-mono font-bold text-primary text-lg tracking-wider">
            {referralCode}
          </code>
          <Button 
            size="sm" 
            variant="ghost" 
            onClick={copyToClipboard}
            className="h-9 w-9 p-0"
          >
            {copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
          </Button>
        </div>

        <div className="grid grid-cols-3 gap-3 pt-2">
          <Button variant="outline" size="sm" onClick={shareViaSMS} className="flex flex-col h-auto py-3 gap-2 border-border/60">
            <Share2 className="h-4 w-4 text-blue-500" />
            <span className="text-[10px] uppercase font-bold tracking-wider">SMS</span>
          </Button>
          <Button variant="outline" size="sm" onClick={shareViaWhatsApp} className="flex flex-col h-auto py-3 gap-2 border-border/60">
            <MessageCircle className="h-4 w-4 text-emerald-500" />
            <span className="text-[10px] uppercase font-bold tracking-wider">WhatsApp</span>
          </Button>
          <Button variant="outline" size="sm" onClick={shareViaEmail} className="flex flex-col h-auto py-3 gap-2 border-border/60">
            <Mail className="h-4 w-4 text-primary" />
            <span className="text-[10px] uppercase font-bold tracking-wider">Email</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
