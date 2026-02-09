import React, { useState, useEffect, useRef } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, CardElement, PaymentRequestButtonElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { CreditCard, Lock, Loader, CheckCircle, AlertCircle, Mail, Phone, User, Smartphone } from 'lucide-react';
import { validateEmail, validatePhone, formatPhoneNumber, formatCurrency } from '../../utils/validation';
import { api } from '../../services/api';

// Initialize Stripe
const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLIC_KEY || 'pk_test_placeholder');

const CARD_ELEMENT_OPTIONS = {
  style: {
    base: {
      fontSize: '16px',
      color: '#1f2937',
      fontFamily: 'Inter, system-ui, sans-serif',
      '::placeholder': {
        color: '#9ca3af',
      },
    },
    invalid: {
      color: '#dc2626',
      iconColor: '#dc2626',
    },
  },
};

const PaymentForm = ({ formData, updateCustomerInfo, prevStep, setError, resetForm }) => {
  const stripe = useStripe();
  const elements = useElements();

  const [isProcessing, setIsProcessing] = useState(false);
  const [paymentSuccess, setPaymentSuccess] = useState(false);
  const [bookingId, setBookingId] = useState(null);

  const [customerInfo, setCustomerInfo] = useState({
    name: formData.customerInfo?.name || '',
    email: formData.customerInfo?.email || '',
    phone: formData.customerInfo?.phone || '',
  });

  const [errors, setErrors] = useState({});
  const [cardComplete, setCardComplete] = useState(false);

  // Apple Pay / Google Pay
  const [paymentRequest, setPaymentRequest] = useState(null);
  const [canMakePayment, setCanMakePayment] = useState(null);
  const paymentRequestRef = useRef(null);

  useEffect(() => {
    if (!stripe || !formData.estimate?.total) return;

    const pr = stripe.paymentRequest({
      country: 'US',
      currency: 'usd',
      total: {
        label: 'JunkOS Junk Removal',
        amount: Math.round(formData.estimate.total * 100),
      },
      requestPayerName: true,
      requestPayerEmail: true,
      requestPayerPhone: true,
    });

    pr.canMakePayment().then((result) => {
      if (result) {
        setCanMakePayment(result);
        setPaymentRequest(pr);
        paymentRequestRef.current = pr;
      }
    });

    pr.on('paymentmethod', async (ev) => {
      try {
        // Extract payer info from Apple Pay / Google Pay
        const payerName = ev.payerName || '';
        const payerEmail = ev.payerEmail || '';
        const payerPhone = ev.payerPhone || '';

        // 1. Create booking
        const bookingData = {
          ...formData,
          customerInfo: { name: payerName, email: payerEmail, phone: payerPhone },
          totalAmount: formData.estimate.total,
        };
        const bookingResult = await api.createBooking(bookingData);
        const newBookingId = bookingResult.bookingId;

        // 2. Create payment intent
        const piResult = await api.createPaymentIntent(newBookingId, formData.estimate.total);

        // 3. Confirm with the payment method from Apple Pay / Google Pay
        const { error, paymentIntent } = await stripe.confirmCardPayment(
          piResult.clientSecret,
          { payment_method: ev.paymentMethod.id },
          { handleActions: false }
        );

        if (error) {
          ev.complete('fail');
          setError(error.message);
          return;
        }

        if (paymentIntent.status === 'requires_action') {
          const { error: actionError } = await stripe.confirmCardPayment(piResult.clientSecret);
          if (actionError) {
            ev.complete('fail');
            setError(actionError.message);
            return;
          }
        }

        ev.complete('success');

        // 4. Confirm in backend
        await api.confirmPayment(paymentIntent.id, newBookingId);

        // Update UI
        setBookingId(newBookingId);
        setPaymentSuccess(true);
        updateCustomerInfo('name', payerName);
        updateCustomerInfo('email', payerEmail);
        updateCustomerInfo('phone', payerPhone);
        setCustomerInfo({ name: payerName, email: payerEmail, phone: payerPhone });
      } catch (err) {
        ev.complete('fail');
        setError(err.message || 'Payment failed. Please try again.');
      }
    });

    return () => {
      paymentRequestRef.current = null;
    };
  }, [stripe, formData.estimate?.total]);

  const handleCustomerInfoChange = (field, value) => {
    setCustomerInfo((prev) => ({
      ...prev,
      [field]: field === 'phone' ? formatPhoneNumber(value) : value,
    }));
    
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: '' }));
    }
  };

  const validateCustomerInfo = () => {
    const newErrors = {};

    if (!customerInfo.name || customerInfo.name.trim().length < 2) {
      newErrors.name = 'Please enter your full name';
    }

    const emailError = validateEmail(customerInfo.email);
    if (emailError) {
      newErrors.email = emailError;
    }

    const phoneError = validatePhone(customerInfo.phone);
    if (phoneError) {
      newErrors.phone = phoneError;
    }

    return newErrors;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Validate customer info
    const validationErrors = validateCustomerInfo();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    if (!stripe || !elements || !cardComplete) {
      setError('Please complete your payment information');
      return;
    }

    setIsProcessing(true);
    setError(null);

    try {
      // 1. Create booking in backend
      const bookingData = {
        ...formData,
        customerInfo,
        totalAmount: formData.estimate.total,
      };

      const bookingResult = await api.createBooking(bookingData);
      const newBookingId = bookingResult.bookingId;
      setBookingId(newBookingId);

      // 2. Create payment intent
      const paymentIntentResult = await api.createPaymentIntent(
        newBookingId,
        formData.estimate.total
      );

      const clientSecret = paymentIntentResult.clientSecret;

      // 3. Confirm payment with Stripe
      const cardElement = elements.getElement(CardElement);
      const { error, paymentIntent } = await stripe.confirmCardPayment(clientSecret, {
        payment_method: {
          card: cardElement,
          billing_details: {
            name: customerInfo.name,
            email: customerInfo.email,
            phone: customerInfo.phone,
          },
        },
      });

      if (error) {
        throw new Error(error.message);
      }

      // 4. Confirm payment in backend
      await api.confirmPayment(paymentIntent.id, newBookingId);

      // Success!
      setPaymentSuccess(true);
      
      // Save customer info
      updateCustomerInfo('name', customerInfo.name);
      updateCustomerInfo('email', customerInfo.email);
      updateCustomerInfo('phone', customerInfo.phone);

    } catch (err) {
      setError(err.message || 'Payment failed. Please try again.');
      console.error('Payment error:', err);
    } finally {
      setIsProcessing(false);
    }
  };

  if (paymentSuccess) {
    return (
      <div className="card animate-fade-in">
        <div className="text-center pt-8 pb-4">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-green-100 rounded-full mb-5">
            <CheckCircle className="w-12 h-12 text-green-600" />
          </div>

          <h2 className="text-2xl font-bold text-gray-900 mb-2">
            Your pickup is booked.
          </h2>

          <p className="text-gray-600 mb-1">
            This is a no-obligation service — you'll know the exact cost before we start.
          </p>

          <p className="text-sm text-gray-500 mb-6">
            A confirmation email has been sent to <strong className="text-gray-700">{customerInfo.email}</strong>.
          </p>
        </div>

        {/* Booking summary */}
        <div className="bg-gray-50 rounded-lg p-5 mb-6">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-gray-500">Booking ID</span>
              <p className="font-medium text-gray-900">{bookingId?.slice(0, 8)}</p>
            </div>
            <div>
              <span className="text-gray-500">Amount</span>
              <p className="font-medium text-gray-900">{formatCurrency(formData.estimate.total)}</p>
            </div>
            <div>
              <span className="text-gray-500">Date</span>
              <p className="font-medium text-gray-900">
                {formData.selectedDate
                  ? new Date(formData.selectedDate).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
                  : 'TBD'}
              </p>
            </div>
            <div>
              <span className="text-gray-500">Time</span>
              <p className="font-medium text-gray-900">{formData.selectedTime || 'TBD'}</p>
            </div>
          </div>
        </div>

        {/* What happens next */}
        <div className="mb-6">
          <h3 className="font-semibold text-gray-900 mb-4">What happens next?</h3>

          <div className="space-y-5">
            {/* Step 1 */}
            <div className="flex gap-4">
              <div className="flex-shrink-0 w-8 h-8 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center font-bold text-sm">
                1
              </div>
              <div>
                <p className="font-semibold text-gray-900">We'll call to confirm your appointment</p>
                <p className="text-sm text-gray-600 mt-0.5">
                  You'll get a call 15–30 minutes before your scheduled window. We'll confirm the timing and go over any details.
                </p>
              </div>
            </div>

            {/* Step 2 */}
            <div className="flex gap-4">
              <div className="flex-shrink-0 w-8 h-8 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center font-bold text-sm">
                2
              </div>
              <div>
                <p className="font-semibold text-gray-900">We'll assess your items and give an exact price</p>
                <p className="text-sm text-gray-600 mt-0.5">
                  Our crew will look at everything on-site and provide an all-inclusive price. No obligation — if it doesn't work for you, there's no charge.
                </p>
              </div>
            </div>

            {/* Step 3 */}
            <div className="flex gap-4">
              <div className="flex-shrink-0 w-8 h-8 bg-primary-100 text-primary-700 rounded-full flex items-center justify-center font-bold text-sm">
                3
              </div>
              <div>
                <p className="font-semibold text-gray-900">We take care of everything, hassle-free</p>
                <p className="text-sm text-gray-600 mt-0.5">
                  Once you give the go-ahead, we'll remove your items, sweep up the area, and you're done. It's that easy.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Reminder note */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <div className="flex gap-3">
            <Mail className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-blue-900">
              We'll send you a reminder <strong>24 hours before</strong> your appointment with everything you need to know.
            </p>
          </div>
        </div>

        <button
          onClick={resetForm}
          className="btn-primary w-full"
        >
          Book Another Pickup
        </button>
      </div>
    );
  }

  return (
    <div className="card animate-fade-in">
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="bg-primary-100 p-2 rounded-lg">
            <CreditCard className="w-6 h-6 text-primary-600" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Payment Details</h2>
        </div>
        <p className="text-gray-600">
          Complete your booking with secure payment.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Amount Due */}
        <div className="bg-primary-50 border-2 border-primary-200 rounded-lg p-5">
          <div className="flex justify-between items-center">
            <span className="text-lg font-medium text-gray-900">Amount Due</span>
            <span className="text-3xl font-bold text-primary-600">
              {formatCurrency(formData.estimate.total)}
            </span>
          </div>
        </div>

        {/* Apple Pay / Google Pay */}
        {paymentRequest && canMakePayment && (
          <>
            <div>
              <PaymentRequestButtonElement
                options={{
                  paymentRequest,
                  style: {
                    paymentRequestButton: {
                      type: 'default',
                      theme: 'dark',
                      height: '48px',
                    },
                  },
                }}
              />
            </div>
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="bg-white px-4 text-gray-500">or pay with card</span>
              </div>
            </div>
          </>
        )}

        {/* Customer Information */}
        <div className="space-y-4">
          <h3 className="font-semibold text-gray-900">Contact Information</h3>
          
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
              <User className="inline w-4 h-4 mr-1" />
              Full Name
            </label>
            <input
              type="text"
              id="name"
              value={customerInfo.name}
              onChange={(e) => handleCustomerInfoChange('name', e.target.value)}
              placeholder="John Doe"
              disabled={isProcessing}
              className="input-field"
            />
            {errors.name && (
              <div className="error-message">
                <AlertCircle className="w-4 h-4" />
                <span>{errors.name}</span>
              </div>
            )}
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-2">
              <Mail className="inline w-4 h-4 mr-1" />
              Email Address
            </label>
            <input
              type="email"
              id="email"
              value={customerInfo.email}
              onChange={(e) => handleCustomerInfoChange('email', e.target.value)}
              placeholder="john@example.com"
              disabled={isProcessing}
              className="input-field"
            />
            {errors.email && (
              <div className="error-message">
                <AlertCircle className="w-4 h-4" />
                <span>{errors.email}</span>
              </div>
            )}
          </div>

          <div>
            <label htmlFor="phone" className="block text-sm font-medium text-gray-700 mb-2">
              <Phone className="inline w-4 h-4 mr-1" />
              Phone Number
            </label>
            <input
              type="tel"
              id="phone"
              value={customerInfo.phone}
              onChange={(e) => handleCustomerInfoChange('phone', e.target.value)}
              placeholder="(555) 123-4567"
              disabled={isProcessing}
              className="input-field"
            />
            {errors.phone && (
              <div className="error-message">
                <AlertCircle className="w-4 h-4" />
                <span>{errors.phone}</span>
              </div>
            )}
          </div>
        </div>

        {/* Card Information */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            <CreditCard className="inline w-4 h-4 mr-1" />
            Card Information
          </label>
          <div className="border-2 border-gray-300 rounded-lg p-4 focus-within:border-primary-500 focus-within:ring-2 focus-within:ring-primary-200 transition-all">
            <CardElement
              options={CARD_ELEMENT_OPTIONS}
              onChange={(e) => setCardComplete(e.complete)}
            />
          </div>
        </div>

        {/* Security Badge */}
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <Lock className="w-5 h-5 text-green-600" />
            <div className="text-sm text-gray-700">
              <p className="font-medium">Secure Payment</p>
              <p className="text-gray-600">
                Your payment information is encrypted and secure. We never store your card details.
              </p>
            </div>
          </div>
        </div>

        {/* Terms */}
        <div className="text-xs text-gray-600">
          <p>
            By completing this booking, you agree to our{' '}
            <a href="#" className="text-primary-600 hover:underline">Terms of Service</a>
            {' '}and{' '}
            <a href="#" className="text-primary-600 hover:underline">Privacy Policy</a>.
            Payment will be charged immediately upon confirmation.
          </p>
        </div>

        {/* Navigation Buttons */}
        <div className="flex justify-between pt-4">
          <button
            type="button"
            onClick={prevStep}
            disabled={isProcessing}
            className="btn-secondary"
          >
            ← Back
          </button>
          <button
            type="submit"
            disabled={isProcessing || !stripe || !cardComplete}
            className="btn-primary flex items-center gap-2"
          >
            {isProcessing ? (
              <>
                <Loader className="w-5 h-5 animate-spin" />
                Processing Payment...
              </>
            ) : (
              <>
                <Lock className="w-4 h-4" />
                Pay {formatCurrency(formData.estimate.total)}
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

const Step6Payment = (props) => {
  return (
    <Elements stripe={stripePromise}>
      <PaymentForm {...props} />
    </Elements>
  );
};

export default Step6Payment;
