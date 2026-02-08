"use client";

import { useState } from "react";
import {
  CreditCard,
  User,
  Mail,
  Phone,
  CheckCircle2,
  Loader2,
  Shield,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useBookingStore } from "@/stores/booking-store";

function formatPhoneNumber(value: string): string {
  // Strip everything except digits
  const digits = value.replace(/\D/g, "");
  if (digits.length === 0) return "";
  if (digits.length <= 3) return `(${digits}`;
  if (digits.length <= 6) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
  return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6, 10)}`;
}

function generateBookingId(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let id = "JNK-";
  for (let i = 0; i < 6; i++) {
    id += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return id;
}

const TIME_SLOT_LABELS: Record<string, string> = {
  "8-10": "8-10 AM",
  "10-12": "10 AM-12 PM",
  "12-14": "12-2 PM",
  "14-16": "2-4 PM",
  "16-18": "4-6 PM",
};

function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  const [year, month, day] = dateStr.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

interface FormErrors {
  name?: string;
  email?: string;
  phone?: string;
}

export function Step6Payment() {
  const {
    address,
    scheduledDate,
    scheduledTimeSlot,
    estimatedPrice,
    isSubmitting,
    setIsSubmitting,
  } = useBookingStore();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSuccess, setIsSuccess] = useState(false);
  const [bookingId, setBookingId] = useState("");

  const handlePhoneChange = (value: string) => {
    setPhone(formatPhoneNumber(value));
    if (errors.phone) setErrors((prev) => ({ ...prev, phone: undefined }));
  };

  const validate = (): boolean => {
    const newErrors: FormErrors = {};

    if (name.trim().length < 2) {
      newErrors.name = "Please enter your full name.";
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      newErrors.email = "Please enter a valid email address.";
    }

    const phoneDigits = phone.replace(/\D/g, "");
    if (phoneDigits.length < 10) {
      newErrors.phone = "Please enter a valid 10-digit phone number.";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;

    setIsSubmitting(true);

    // Simulate API call / booking submission
    try {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const id = generateBookingId();
      setBookingId(id);
      setIsSuccess(true);
    } catch {
      // Handle error silently - would show toast in production
    } finally {
      setIsSubmitting(false);
    }
  };

  // SUCCESS STATE
  if (isSuccess) {
    return (
      <div className="flex flex-col items-center text-center py-8 space-y-6">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/30">
          <CheckCircle2 className="h-10 w-10 text-emerald-600" />
        </div>

        <div>
          <h2 className="font-display text-3xl font-bold tracking-tight text-foreground">
            Booking Confirmed!
          </h2>
          <p className="mt-2 text-muted-foreground">
            Your junk removal has been scheduled successfully.
          </p>
        </div>

        <div className="rounded-lg border border-border bg-card p-5 w-full max-w-sm space-y-3">
          <div className="text-center">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              Booking ID
            </p>
            <p className="text-lg font-bold font-display text-primary mt-0.5">
              {bookingId}
            </p>
          </div>

          <div className="border-t border-border pt-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Address</span>
              <span className="font-medium text-foreground text-right max-w-[200px] truncate">
                {address.street}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Date</span>
              <span className="font-medium text-foreground">
                {formatDate(scheduledDate)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Time</span>
              <span className="font-medium text-foreground">
                {TIME_SLOT_LABELS[scheduledTimeSlot] || scheduledTimeSlot}
              </span>
            </div>
            <div className="flex justify-between border-t border-border pt-2">
              <span className="font-semibold text-foreground">Total</span>
              <span className="font-bold text-primary text-lg">
                ${estimatedPrice.toFixed(2)}
              </span>
            </div>
          </div>
        </div>

        <p className="text-sm text-muted-foreground max-w-sm">
          A confirmation email has been sent to{" "}
          <span className="font-medium text-foreground">{email}</span>. Our team
          will contact you before your scheduled pickup.
        </p>

        <Button
          onClick={() => {
            useBookingStore.getState().reset();
            setIsSuccess(false);
            setName("");
            setEmail("");
            setPhone("");
            setBookingId("");
          }}
          variant="outline"
          className="mt-4"
        >
          Book Another Pickup
        </Button>
      </div>
    );
  }

  // PAYMENT FORM STATE
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="font-display text-2xl font-bold tracking-tight text-foreground">
          Complete Your Booking
        </h2>
        <p className="mt-1 text-muted-foreground">
          Enter your contact information and confirm payment.
        </p>
      </div>

      {/* Customer Info */}
      <div className="space-y-5">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
          Contact Information
        </h3>

        <div className="space-y-4">
          {/* Name */}
          <div className="space-y-2">
            <Label htmlFor="customer-name" className="text-sm font-medium">
              Full Name
            </Label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="customer-name"
                type="text"
                placeholder="John Doe"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  if (errors.name)
                    setErrors((prev) => ({ ...prev, name: undefined }));
                }}
                className="pl-10 h-11"
              />
            </div>
            {errors.name && (
              <p className="text-sm text-destructive font-medium">
                {errors.name}
              </p>
            )}
          </div>

          {/* Email */}
          <div className="space-y-2">
            <Label htmlFor="customer-email" className="text-sm font-medium">
              Email Address
            </Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="customer-email"
                type="email"
                placeholder="john@example.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (errors.email)
                    setErrors((prev) => ({ ...prev, email: undefined }));
                }}
                className="pl-10 h-11"
              />
            </div>
            {errors.email && (
              <p className="text-sm text-destructive font-medium">
                {errors.email}
              </p>
            )}
          </div>

          {/* Phone */}
          <div className="space-y-2">
            <Label htmlFor="customer-phone" className="text-sm font-medium">
              Phone Number
            </Label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="customer-phone"
                type="tel"
                placeholder="(555) 123-4567"
                value={phone}
                onChange={(e) => handlePhoneChange(e.target.value)}
                className="pl-10 h-11"
              />
            </div>
            {errors.phone && (
              <p className="text-sm text-destructive font-medium">
                {errors.phone}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Payment Placeholder */}
      <div className="space-y-5">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
          Payment Method
        </h3>

        <div className="rounded-lg border-2 border-dashed border-border bg-muted/30 p-8 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 mx-auto mb-3">
            <CreditCard className="h-6 w-6 text-primary" />
          </div>
          <p className="text-sm font-semibold text-foreground">
            Stripe Payment Integration
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Stripe payment form will be integrated here
          </p>
          <div className="flex items-center justify-center gap-1.5 mt-3">
            <Shield className="h-3.5 w-3.5 text-emerald-600" />
            <span className="text-xs text-muted-foreground">
              Secure, encrypted payment processing
            </span>
          </div>
        </div>
      </div>

      {/* Total and Submit */}
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="flex items-center justify-between mb-4">
          <span className="text-base font-bold text-foreground">
            Total Due
          </span>
          <span className="text-2xl font-bold text-primary">
            ${estimatedPrice.toFixed(2)}
          </span>
        </div>

        <Button
          onClick={handleSubmit}
          disabled={isSubmitting}
          className="w-full h-12 text-base font-semibold"
          size="lg"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <CheckCircle2 className="mr-2 h-5 w-5" />
              Complete Booking
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
