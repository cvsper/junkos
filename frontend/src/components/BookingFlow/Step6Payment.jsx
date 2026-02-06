import React, { useState, useEffect } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { CreditCard, Lock, Loader, CheckCircle, AlertCircle, Mail, Phone, User } from 'lucide-react';
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
        <div className="text-center py-8">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-green-100 rounded-full mb-6">
            <CheckCircle className="w-12 h-12 text-green-600" />
          </div>
          
          <h2 className="text-3xl font-bold text-gray-900 mb-3">
            Booking Confirmed! 🎉
          </h2>
          
          <p className="text-lg text-gray-600 mb-6">
            Your junk removal is scheduled and paid for.
          </p>

          <div className="bg-gray-50 rounded-lg p-6 mb-6 text-left max-w-md mx-auto">
            <h3 className="font-semibold text-gray-900 mb-3">Booking Details</h3>
            <div className="space-y-2 text-sm">
              <p><strong>Booking ID:</strong> {bookingId}</p>
              <p><strong>Amount Paid:</strong> {formatCurrency(formData.estimate.total)}</p>
              <p><strong>Email:</strong> {customerInfo.email}</p>
              <p><strong>Phone:</strong> {customerInfo.phone}</p>
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-left max-w-md mx-auto">
            <div className="flex gap-3">
              <Mail className="w-5 h-5 text-blue-600 mt-0.5" />
              <div className="text-sm text-blue-900">
                <p className="font-medium mb-1">Confirmation Sent</p>
                <p className="text-blue-800">
                  We've sent a confirmation email to <strong>{customerInfo.email}</strong> with all your booking details.
                  We'll also send a reminder 24 hours before your appointment.
                </p>
              </div>
            </div>
          </div>

          <button
            onClick={resetForm}
            className="btn-primary"
          >
            Book Another Pickup
          </button>
        </div>
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
