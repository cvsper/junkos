"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { loadStripe } from "@stripe/stripe-js";
import {
  Elements,
  CardElement,
  PaymentRequestButtonElement,
  useStripe,
  useElements,
} from "@stripe/react-stripe-js";
import type { StripeCardElementChangeEvent, PaymentRequest } from "@stripe/stripe-js";
import {
  CreditCard,
  User,
  Mail,
  Phone,
  CheckCircle2,
  Loader2,
  Shield,
  Lock,
  AlertCircle,
  Tag,
  X,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useBookingStore } from "@/stores/booking-store";
import { bookingApi, paymentsApi, promosApi } from "@/lib/api";

// ---------------------------------------------------------------------------
// Stripe singleton
// ---------------------------------------------------------------------------

const stripePromise = loadStripe(
  process.env.NEXT_PUBLIC_STRIPE_KEY || ""
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatPhoneNumber(value: string): string {
  const digits = value.replace(/\D/g, "");
  if (digits.length === 0) return "";
  if (digits.length <= 3) return `(${digits}`;
  if (digits.length <= 6) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
  return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6, 10)}`;
}

function generateBookingId(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let id = "UMV-";
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

// ---------------------------------------------------------------------------
// Card element styling (adapts to theme via CSS custom properties)
// ---------------------------------------------------------------------------

const CARD_ELEMENT_OPTIONS = {
  style: {
    base: {
      fontSize: "16px",
      color: "#1f2937",
      fontFamily: "DM Sans, system-ui, -apple-system, sans-serif",
      fontSmoothing: "antialiased",
      "::placeholder": {
        color: "#9ca3af",
      },
    },
    invalid: {
      color: "#dc2626",
      iconColor: "#dc2626",
    },
  },
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FormErrors {
  name?: string;
  email?: string;
  phone?: string;
  card?: string;
  general?: string;
}

// ---------------------------------------------------------------------------
// Inner payment form (has access to Stripe context via useStripe / useElements)
// ---------------------------------------------------------------------------

function PaymentFormInner() {
  const stripe = useStripe();
  const elements = useElements();

  const {
    address,
    items,
    scheduledDate,
    scheduledTimeSlot,
    estimatedPrice,
    notes,
    photos,
    isSubmitting,
    setIsSubmitting,
    promoCode: appliedPromoCode,
    promoDiscount,
    promoApplied,
    applyPromo,
    clearPromo,
  } = useBookingStore();

  // Contact info
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");

  // Card state
  const [cardComplete, setCardComplete] = useState(false);
  const [cardError, setCardError] = useState<string | undefined>();

  // General state
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSuccess, setIsSuccess] = useState(false);
  const [bookingId, setBookingId] = useState("");
  const [confirmationCode, setConfirmationCode] = useState("");

  // Promo code state
  const [promoInput, setPromoInput] = useState("");
  const [promoLoading, setPromoLoading] = useState(false);
  const [promoError, setPromoError] = useState<string | undefined>();

  // Compute final price after discount
  const finalPrice = promoApplied
    ? Math.max(0, estimatedPrice - promoDiscount)
    : estimatedPrice;

  // Apple Pay / Google Pay
  const [paymentRequest, setPaymentRequest] = useState<PaymentRequest | null>(null);
  const [canMakePayment, setCanMakePayment] = useState(false);
  const paymentRequestRef = useRef<PaymentRequest | null>(null);

  // ---------------------------------------------------------------------------
  // Apple Pay / Google Pay setup
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!stripe || !finalPrice || finalPrice <= 0) return;

    const pr = stripe.paymentRequest({
      country: "US",
      currency: "usd",
      total: {
        label: "Umuve Junk Removal",
        amount: Math.round(finalPrice * 100),
      },
      requestPayerName: true,
      requestPayerEmail: true,
      requestPayerPhone: true,
    });

    pr.canMakePayment().then((result) => {
      if (result) {
        setCanMakePayment(true);
        setPaymentRequest(pr);
        paymentRequestRef.current = pr;
      }
    });

    // Handle the payment method event from Apple Pay / Google Pay
    pr.on("paymentmethod", async (ev) => {
      try {
        const payerName = ev.payerName || "";
        const payerEmail = ev.payerEmail || "";
        const payerPhone = ev.payerPhone || "";

        // 1. Submit booking to backend
        const bookingResult = await bookingApi.submit({
          step: 6,
          address,
          photos,
          photoUrls: [],
          items,
          scheduledDate,
          scheduledTimeSlot,
          notes,
          estimatedPrice: finalPrice,
          ...(promoApplied ? { promo_code: appliedPromoCode } : {}),
          customerName: payerName,
          customerEmail: payerEmail,
          customerPhone: payerPhone,
        });

        const newBookingId = bookingResult.id || generateBookingId();

        // 2. Create payment intent
        const piResult = await paymentsApi.createIntent(
          newBookingId,
          finalPrice
        );

        // 3. Confirm with the payment method from Apple Pay / Google Pay
        const { error, paymentIntent } = await stripe.confirmCardPayment(
          piResult.clientSecret,
          { payment_method: ev.paymentMethod.id },
          { handleActions: false }
        );

        if (error) {
          ev.complete("fail");
          setErrors((prev) => ({ ...prev, general: error.message }));
          return;
        }

        if (paymentIntent?.status === "requires_action") {
          const { error: actionError } = await stripe.confirmCardPayment(
            piResult.clientSecret
          );
          if (actionError) {
            ev.complete("fail");
            setErrors((prev) => ({ ...prev, general: actionError.message }));
            return;
          }
        }

        ev.complete("success");

        // 4. Confirm in backend
        if (paymentIntent) {
          await paymentsApi.confirm(paymentIntent.id, newBookingId);
        }

        // Update UI
        setName(payerName);
        setEmail(payerEmail);
        setPhone(payerPhone);
        setBookingId(newBookingId);
        // Extract confirmation code from nested job response
        const jobData = (bookingResult as unknown as Record<string, unknown>).job as Record<string, unknown> | undefined;
        setConfirmationCode((jobData?.confirmation_code as string) || "");
        setIsSuccess(true);
      } catch (err) {
        ev.complete("fail");
        const message =
          err instanceof Error ? err.message : "Payment failed. Please try again.";
        setErrors((prev) => ({ ...prev, general: message }));
      }
    });

    return () => {
      paymentRequestRef.current = null;
    };
  }, [stripe, finalPrice, estimatedPrice, address, items, scheduledDate, scheduledTimeSlot, notes, photos, promoApplied, appliedPromoCode]);

  // ---------------------------------------------------------------------------
  // Card change handler
  // ---------------------------------------------------------------------------
  const handleCardChange = useCallback((event: StripeCardElementChangeEvent) => {
    setCardComplete(event.complete);
    setCardError(event.error?.message);
    if (errors.card) {
      setErrors((prev) => ({ ...prev, card: undefined }));
    }
  }, [errors.card]);

  // ---------------------------------------------------------------------------
  // Phone formatting
  // ---------------------------------------------------------------------------
  const handlePhoneChange = (value: string) => {
    setPhone(formatPhoneNumber(value));
    if (errors.phone) setErrors((prev) => ({ ...prev, phone: undefined }));
  };

  // ---------------------------------------------------------------------------
  // Promo code handler
  // ---------------------------------------------------------------------------
  const handleApplyPromo = async () => {
    const code = promoInput.trim();
    if (!code) {
      setPromoError("Please enter a promo code.");
      return;
    }

    setPromoLoading(true);
    setPromoError(undefined);

    try {
      const result = await promosApi.validate(code, estimatedPrice);
      if (result.valid && result.discount_amount !== undefined) {
        applyPromo(code, result.discount_amount);
        setPromoInput("");
      } else {
        setPromoError(result.error || "Invalid promo code.");
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to validate promo code.";
      setPromoError(message);
    } finally {
      setPromoLoading(false);
    }
  };

  const handleRemovePromo = () => {
    clearPromo();
    setPromoError(undefined);
  };

  // ---------------------------------------------------------------------------
  // Validation
  // ---------------------------------------------------------------------------
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

    if (!cardComplete) {
      newErrors.card = "Please complete your card information.";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // ---------------------------------------------------------------------------
  // Submit handler (card payment)
  // ---------------------------------------------------------------------------
  const handleSubmit = async () => {
    if (!validate()) return;
    if (!stripe || !elements) {
      setErrors({ general: "Payment system is still loading. Please wait." });
      return;
    }

    setIsSubmitting(true);
    setErrors({});

    try {
      // 1. Submit the booking to the backend
      const bookingResult = await bookingApi.submit({
        step: 6,
        address,
        photos,
        photoUrls: [],
        items,
        scheduledDate,
        scheduledTimeSlot,
        notes,
        estimatedPrice: finalPrice,
        ...(promoApplied ? { promo_code: appliedPromoCode } : {}),
        customerName: name.trim(),
        customerEmail: email.trim(),
        customerPhone: phone.trim(),
      });

      const newBookingId = bookingResult.id || generateBookingId();

      // 2. Create payment intent on the server
      const paymentIntentResult = await paymentsApi.createIntent(
        newBookingId,
        finalPrice
      );

      const clientSecret = paymentIntentResult.clientSecret;

      // 3. Confirm the card payment with Stripe
      const cardElement = elements.getElement(CardElement);
      if (!cardElement) {
        throw new Error("Card element not found.");
      }

      const { error, paymentIntent } = await stripe.confirmCardPayment(
        clientSecret,
        {
          payment_method: {
            card: cardElement,
            billing_details: {
              name: name.trim(),
              email: email.trim(),
              phone: phone.trim(),
            },
          },
        }
      );

      if (error) {
        throw new Error(error.message || "Payment was declined.");
      }

      // 4. Confirm payment in the backend
      if (paymentIntent) {
        await paymentsApi.confirm(paymentIntent.id, newBookingId);
      }

      // Success
      setBookingId(newBookingId);
      // Extract confirmation code from nested job response
      const jobData = (bookingResult as unknown as Record<string, unknown>).job as Record<string, unknown> | undefined;
      setConfirmationCode((jobData?.confirmation_code as string) || "");
      setIsSuccess(true);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Payment failed. Please try again.";
      setErrors({ general: message });
    } finally {
      setIsSubmitting(false);
    }
  };

  // ---------------------------------------------------------------------------
  // SUCCESS STATE
  // ---------------------------------------------------------------------------
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

          {confirmationCode && (
            <div className="rounded-lg border-2 border-dashed border-primary/30 bg-primary/5 p-4 text-center">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">
                Confirmation Code
              </p>
              <p className="text-2xl font-bold font-mono tracking-widest text-primary">
                {confirmationCode}
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                Save this code to track your pickup at{" "}
                <span className="font-medium text-foreground">/dashboard</span>
              </p>
            </div>
          )}

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
            {promoApplied && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Promo Discount</span>
                <span className="font-medium text-emerald-600">
                  -${promoDiscount.toFixed(2)}
                </span>
              </div>
            )}
            <div className="flex justify-between border-t border-border pt-2">
              <span className="font-semibold text-foreground">Total Paid</span>
              <span className="font-bold text-primary text-lg">
                ${finalPrice.toFixed(2)}
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
            setConfirmationCode("");
            setCardComplete(false);
            setCardError(undefined);
            setErrors({});
          }}
          variant="outline"
          className="mt-4"
        >
          Book Another Pickup
        </Button>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // PAYMENT FORM STATE
  // ---------------------------------------------------------------------------
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="font-display text-2xl font-bold tracking-tight text-foreground">
          Complete Your Booking
        </h2>
        <p className="mt-1 text-muted-foreground">
          Enter your contact information and pay securely with Stripe.
        </p>
      </div>

      {/* Global error */}
      {errors.general && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
          <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-destructive">
              Payment Error
            </p>
            <p className="text-sm text-destructive/80 mt-0.5">
              {errors.general}
            </p>
          </div>
        </div>
      )}

      {/* Apple Pay / Google Pay */}
      {paymentRequest && canMakePayment && (
        <>
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
              Express Checkout
            </h3>
            <PaymentRequestButtonElement
              options={{
                paymentRequest,
                style: {
                  paymentRequestButton: {
                    type: "buy",
                    theme: "dark",
                    height: "48px",
                  },
                },
              }}
            />
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="bg-card px-4 text-muted-foreground">
                or pay with card
              </span>
            </div>
          </div>
        </>
      )}

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
                disabled={isSubmitting}
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
                disabled={isSubmitting}
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
                disabled={isSubmitting}
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

      {/* Card Information */}
      <div className="space-y-5">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
          Payment Method
        </h3>

        <div className="space-y-2">
          <Label className="text-sm font-medium flex items-center gap-2">
            <CreditCard className="h-4 w-4 text-muted-foreground" />
            Card Information
          </Label>
          <div className="rounded-lg border-2 border-border bg-background p-4 transition-all focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
            <CardElement
              options={CARD_ELEMENT_OPTIONS}
              onChange={handleCardChange}
            />
          </div>
          {(errors.card || cardError) && (
            <p className="text-sm text-destructive font-medium">
              {errors.card || cardError}
            </p>
          )}
        </div>

        {/* Security Badge */}
        <div className="flex items-center gap-3 rounded-lg bg-muted/50 border border-border p-3">
          <Shield className="h-5 w-5 text-emerald-600 shrink-0" />
          <div className="text-sm">
            <p className="font-medium text-foreground">
              Secure Payment
            </p>
            <p className="text-muted-foreground text-xs">
              Your payment info is encrypted end-to-end by Stripe. We never
              store your card details.
            </p>
          </div>
        </div>
      </div>

      {/* Promo Code */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
          Promo Code
        </h3>

        {promoApplied ? (
          <div className="flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-900/20 p-3">
            <div className="flex items-center gap-2">
              <Tag className="h-4 w-4 text-emerald-600" />
              <span className="text-sm font-medium text-emerald-700 dark:text-emerald-400">
                {appliedPromoCode}
              </span>
              <span className="text-sm text-emerald-600 dark:text-emerald-400">
                (-${promoDiscount.toFixed(2)})
              </span>
            </div>
            <button
              type="button"
              onClick={handleRemovePromo}
              className="text-muted-foreground hover:text-foreground transition-colors"
              disabled={isSubmitting}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <div className="flex gap-2">
            <Input
              placeholder="Enter promo code"
              value={promoInput}
              onChange={(e) => {
                setPromoInput(e.target.value.toUpperCase());
                if (promoError) setPromoError(undefined);
              }}
              disabled={isSubmitting || promoLoading}
              className="flex-1"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  handleApplyPromo();
                }
              }}
            />
            <Button
              type="button"
              variant="outline"
              onClick={handleApplyPromo}
              disabled={isSubmitting || promoLoading || !promoInput.trim()}
            >
              {promoLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Apply"
              )}
            </Button>
          </div>
        )}

        {promoError && (
          <p className="text-sm text-destructive font-medium">
            {promoError}
          </p>
        )}
      </div>

      {/* Total and Submit */}
      <div className="rounded-lg border border-border bg-card p-5">
        <div className="space-y-2 mb-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Subtotal</span>
            <span className="text-sm text-foreground">
              ${estimatedPrice.toFixed(2)}
            </span>
          </div>
          {promoApplied && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-emerald-600">Promo Discount</span>
              <span className="text-sm font-medium text-emerald-600">
                -${promoDiscount.toFixed(2)}
              </span>
            </div>
          )}
          <div className="flex items-center justify-between border-t border-border pt-2">
            <span className="text-base font-bold text-foreground">
              Total Due
            </span>
            <span className="text-2xl font-bold text-primary">
              ${finalPrice.toFixed(2)}
            </span>
          </div>
        </div>

        <Button
          onClick={handleSubmit}
          disabled={isSubmitting || !stripe || !elements}
          className="w-full h-12 text-base font-semibold"
          size="lg"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Processing Payment...
            </>
          ) : (
            <>
              <Lock className="mr-2 h-5 w-5" />
              Pay ${finalPrice.toFixed(2)}
            </>
          )}
        </Button>

        <p className="text-xs text-muted-foreground text-center mt-3">
          By completing this booking, you agree to our{" "}
          <a href="/terms" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
            Terms of Service
          </a>{" "}
          and{" "}
          <a href="/privacy" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
            Privacy Policy
          </a>
          .
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Exported wrapper -- wraps inner form in Stripe Elements provider
// ---------------------------------------------------------------------------

export function Step6Payment() {
  return (
    <Elements stripe={stripePromise}>
      <PaymentFormInner />
    </Elements>
  );
}
