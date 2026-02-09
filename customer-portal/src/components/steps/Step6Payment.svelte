<script>
  import { CreditCard, Loader, Check, AlertCircle, Lock } from 'lucide-svelte';
  import { fade, fly, scale } from 'svelte/transition';
  import { onMount } from 'svelte';
  import { formData, isLoading, error, prevStep, resetForm } from '../../stores/bookingStore';
  import { api } from '../../services/api';
  import { loadStripe } from '@stripe/stripe-js';
  
  const STRIPE_PUBLIC_KEY = import.meta.env.VITE_STRIPE_PUBLIC_KEY || 'pk_test_51HK...'; // Use test key

  let stripe = null;
  let cardElement = null;
  let bookingId = null;
  let paymentSuccess = false;
  let processingPayment = false;
  let cardholderName = $formData.customerInfo.name || '';
  let cardError = '';

  onMount(async () => {
    // Load Stripe
    stripe = await loadStripe(STRIPE_PUBLIC_KEY);
    
    if (stripe) {
      const elements = stripe.elements();
      cardElement = elements.create('card', {
        style: {
          base: {
            fontSize: '16px',
            color: '#1e293b',
            '::placeholder': {
              color: '#94a3b8',
            },
          },
          invalid: {
            color: '#ef4444',
          },
        },
      });
      
      cardElement.mount('#card-element');
      
      cardElement.on('change', (event) => {
        cardError = event.error ? event.error.message : '';
      });
    }

    // Create booking
    await createBooking();
  });

  async function createBooking() {
    try {
      const result = await api.createBooking({
        address: $formData.address,
        addressDetails: $formData.addressDetails,
        itemCategory: $formData.itemCategory,
        itemDescription: $formData.itemDescription,
        quantity: $formData.quantity,
        photoUrls: $formData.photoUrls,
        selectedDate: $formData.selectedDate,
        selectedTime: $formData.selectedTime,
        estimate: $formData.estimate,
        customerInfo: $formData.customerInfo,
        totalAmount: $formData.estimate?.total || 0,
      });

      bookingId = result.bookingId || 'BOOK-' + Date.now();
    } catch (err) {
      error.set('Failed to create booking: ' + err.message);
    }
  }

  async function handlePayment(e) {
    e.preventDefault();

    if (!cardholderName.trim()) {
      cardError = 'Cardholder name is required';
      return;
    }

    if (!stripe || !cardElement) {
      error.set('Payment system not loaded. Please refresh the page.');
      return;
    }

    processingPayment = true;
    error.set(null);
    cardError = '';

    try {
      // Create payment intent
      const { clientSecret } = await api.createPaymentIntent(
        bookingId,
        $formData.estimate.total
      );

      // Confirm payment
      const { error: stripeError, paymentIntent } = await stripe.confirmCardPayment(
        clientSecret,
        {
          payment_method: {
            card: cardElement,
            billing_details: {
              name: cardholderName,
              email: $formData.customerInfo.email,
            },
          },
        }
      );

      if (stripeError) {
        cardError = stripeError.message;
      } else if (paymentIntent.status === 'succeeded') {
        // Confirm with backend
        await api.confirmPayment(paymentIntent.id, bookingId);
        paymentSuccess = true;
      }
    } catch (err) {
      error.set(err.message);
    } finally {
      processingPayment = false;
    }
  }

  function handleNewBooking() {
    resetForm();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
</script>

{#if paymentSuccess}
  <!-- Success Screen -->
  <div class="card text-center" in:scale={{ duration: 500 }}>
    <div class="mb-6">
      <div class="w-20 h-20 bg-cta-100 rounded-full flex items-center justify-center mx-auto mb-4" in:scale={{ delay: 200, duration: 500 }}>
        <Check class="w-10 h-10 text-cta-600" />
      </div>
      <h2 class="text-3xl font-bold text-gray-900 font-heading mb-2">Booking Confirmed!</h2>
      <p class="text-gray-600">
        Your junk removal has been scheduled successfully.
      </p>
    </div>

    <div class="bg-gradient-to-br from-primary-50 to-indigo-50 rounded-xl p-6 mb-6 text-left">
      <h3 class="font-semibold text-gray-900 mb-3">Booking Details</h3>
      <div class="space-y-2 text-sm">
        <div class="flex justify-between">
          <span class="text-gray-600">Booking ID:</span>
          <span class="font-mono font-semibold text-primary-600">{bookingId}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-600">Total Amount:</span>
          <span class="font-semibold text-gray-900">${$formData.estimate.total.toFixed(2)}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-600">Scheduled:</span>
          <span class="font-semibold text-gray-900">{$formData.selectedTime}</span>
        </div>
      </div>
    </div>

    <div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 text-left">
      <h4 class="font-semibold text-blue-900 mb-2">📧 Confirmation Email Sent</h4>
      <p class="text-sm text-blue-800">
        We've sent a confirmation email to <strong>{$formData.customerInfo.email}</strong> with 
        your booking details and what to expect on the day of service.
      </p>
    </div>

    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6 text-left">
      <h4 class="font-semibold text-yellow-900 mb-2">📱 Day of Service</h4>
      <ul class="text-sm text-yellow-800 space-y-1">
        <li>• We'll text you 30 minutes before arrival</li>
        <li>• Our crew will confirm the final price on-site</li>
        <li>• Payment is secured, no additional charges</li>
        <li>• We'll handle all the heavy lifting!</li>
      </ul>
    </div>

    <div class="bg-emerald-50 border border-emerald-200 rounded-lg p-4 mb-6 text-left">
      <h4 class="font-semibold text-emerald-900 mb-2">Track Your Booking</h4>
      <p class="text-sm text-emerald-800 mb-3">
        Follow your pickup in real-time once a driver is assigned.
      </p>
      <a
        href="?track={bookingId}"
        class="inline-flex items-center gap-2 bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 transition-colors text-sm font-medium"
      >
        Track Live
      </a>
    </div>

    <div class="flex flex-col sm:flex-row gap-3">
      <button
        on:click={handleNewBooking}
        class="btn-primary flex-1"
      >
        Book Another Pickup
      </button>
      <button
        on:click={() => window.print()}
        class="btn-secondary flex-1"
      >
        Print Confirmation
      </button>
    </div>
  </div>
{:else}
  <!-- Payment Form -->
  <div class="card" in:fly={{ x: 20, duration: 300 }}>
    <div class="mb-6">
      <div class="flex items-center gap-3 mb-2">
        <div class="bg-cta-100 p-2 rounded-lg">
          <CreditCard class="w-6 h-6 text-cta-600" />
        </div>
        <h2 class="text-2xl font-bold text-gray-900 font-heading">Secure Payment</h2>
      </div>
      <p class="text-gray-600">
        Complete your booking with a secure payment.
      </p>
    </div>

    <!-- Payment Summary -->
    <div class="bg-gradient-to-br from-cta-50 to-emerald-50 rounded-xl p-6 mb-6 border-2 border-cta-200">
      <div class="flex justify-between items-center">
        <div>
          <p class="text-gray-600 text-sm">Total Amount Due</p>
          <p class="text-3xl font-bold text-cta-600">${$formData.estimate.total.toFixed(2)}</p>
        </div>
        <div class="text-right">
          <p class="text-gray-600 text-sm">Booking ID</p>
          <p class="font-mono text-sm font-semibold text-gray-900">{bookingId || 'Generating...'}</p>
        </div>
      </div>
    </div>

    <form on:submit={handlePayment} class="space-y-6">
      <!-- Cardholder Name -->
      <div>
        <label for="cardholder-name" class="block text-sm font-medium text-gray-700 mb-2">
          Cardholder Name
        </label>
        <input
          type="text"
          id="cardholder-name"
          bind:value={cardholderName}
          placeholder="John Doe"
          disabled={processingPayment}
          class="input-field"
        />
      </div>

      <!-- Card Element -->
      <div>
        <div class="block text-sm font-medium text-gray-700 mb-2">
          Card Information
        </div>
        <div 
          id="card-element" 
          class="input-field"
          class:border-red-500={cardError}
        ></div>
        {#if cardError}
          <div class="error-message mt-2" transition:fly={{ y: -10, duration: 200 }}>
            <AlertCircle class="w-4 h-4" />
            <span>{cardError}</span>
          </div>
        {/if}
      </div>

      <!-- Security Notice -->
      <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 flex gap-3">
        <Lock class="w-5 h-5 text-gray-600 mt-0.5 flex-shrink-0" />
        <div class="text-sm text-gray-700">
          <p class="font-semibold mb-1">🔒 Secure Payment</p>
          <p>
            Your payment information is encrypted and secure. We use Stripe for payment processing 
            and never store your card details.
          </p>
        </div>
      </div>

      <!-- Test Card Info (only in development) -->
      <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p class="text-sm text-blue-900 font-semibold mb-1">💳 Test Mode</p>
        <p class="text-xs text-blue-800">
          Use card: <strong>4242 4242 4242 4242</strong> | Exp: Any future date | CVC: Any 3 digits
        </p>
      </div>

      <!-- Navigation -->
      <div class="flex justify-between pt-4">
        <button
          type="button"
          on:click={prevStep}
          disabled={processingPayment}
          class="btn-secondary"
        >
          ← Back
        </button>
        
        <button
          type="submit"
          disabled={processingPayment || !bookingId}
          class="btn-primary flex items-center gap-2"
        >
          {#if processingPayment}
            <Loader class="w-5 h-5 animate-spin" />
            <span>Processing...</span>
          {:else}
            <Lock class="w-4 h-4" />
            <span>Pay ${$formData.estimate.total.toFixed(2)}</span>
          {/if}
        </button>
      </div>
    </form>
  </div>
{/if}
