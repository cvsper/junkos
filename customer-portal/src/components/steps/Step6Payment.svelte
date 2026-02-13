<script>
  import { CreditCard, Loader, Check, AlertCircle, Lock, Truck } from 'lucide-svelte';
  import { fade, fly, scale } from 'svelte/transition';
  import { formData, isLoading, error, prevStep, resetForm } from '../../stores/bookingStore';
  import { api } from '../../services/api';
  import { loadStripe } from '@stripe/stripe-js';

  const STRIPE_PUBLIC_KEY = import.meta.env.VITE_STRIPE_PUBLIC_KEY || 'pk_test_51SyjNcIowMGOXFMncmnEP1ZcWi8XX7KdPuQhPCMbN1bMRb4NgH1rmLeB4SGlhy9aD9FMrBJQ2QcCsZFxJ98wtTCA00i4WfgNq6';

  let stripe = null;
  let cardElement = null;
  let cardMountEl = null;
  let applePayMountEl = null;
  let bookingId = null;
  let paymentSuccess = false;
  let processingPayment = false;
  let cardholderName = $formData.customerInfo.name || '';
  let cardError = '';
  let initialized = false;
  let canMakePayment = false;
  let paymentRequest = null;

  // Use reactive statement instead of onMount (fixes {#key} + svelte:component issue)
  $: if (cardMountEl && !initialized) {
    initialized = true;
    initPayment();
  }

  async function initPayment() {
    // Load Stripe
    stripe = await loadStripe(STRIPE_PUBLIC_KEY);

    if (stripe && cardMountEl) {
      const elements = stripe.elements();
      cardElement = elements.create('card', {
        style: {
          base: {
            fontFamily: '"DM Sans", system-ui, sans-serif',
            fontSize: '16px',
            color: '#3f3931',
            '::placeholder': {
              color: '#b8b0a3',
            },
          },
          invalid: {
            color: '#ef4444',
          },
        },
      });

      cardElement.mount(cardMountEl);

      cardElement.on('change', (event) => {
        cardError = event.error ? event.error.message : '';
      });

      // Set up Apple Pay / Google Pay
      setupPaymentRequest(stripe, elements);
    }

    // Create booking
    await createBooking();
  }

  async function setupPaymentRequest(stripe, elements) {
    const total = $formData.estimate?.total || 0;
    if (!total) return;

    const pr = stripe.paymentRequest({
      country: 'US',
      currency: 'usd',
      total: {
        label: 'Umuve Hauling',
        amount: Math.round(total * 100),
      },
      requestPayerName: true,
      requestPayerEmail: true,
      requestPayerPhone: true,
    });

    const result = await pr.canMakePayment();
    if (result) {
      canMakePayment = true;
      paymentRequest = pr;

      const prButton = elements.create('paymentRequestButton', {
        paymentRequest: pr,
        style: {
          paymentRequestButton: {
            type: 'default',
            theme: 'dark',
            height: '48px',
          },
        },
      });

      // Mount after a tick to ensure the DOM element exists
      setTimeout(() => {
        if (applePayMountEl) {
          prButton.mount(applePayMountEl);
        }
      }, 50);

      pr.on('paymentmethod', async (ev) => {
        try {
          const payerName = ev.payerName || '';
          const payerEmail = ev.payerEmail || '';

          // Ensure we have a booking
          if (!bookingId) {
            ev.complete('fail');
            error.set('No booking found. Please go back and try again.');
            return;
          }

          // Create payment intent
          const piResult = await api.createPaymentIntent(bookingId, total);

          // Confirm with the payment method from Apple Pay / Google Pay
          const { error: confirmError, paymentIntent } = await stripe.confirmCardPayment(
            piResult.clientSecret,
            { payment_method: ev.paymentMethod.id },
            { handleActions: false }
          );

          if (confirmError) {
            ev.complete('fail');
            cardError = confirmError.message;
          } else {
            ev.complete('success');
            if (paymentIntent.status === 'succeeded') {
              await api.confirmPayment(paymentIntent.id, bookingId);
              paymentSuccess = true;
            }
          }
        } catch (err) {
          ev.complete('fail');
          error.set(err.message || 'Payment failed');
        }
      });
    }
  }

  async function createBooking() {
    try {
      // Extract a 24h time string from the selected time slot (e.g. "8:00 AM - 10:00 AM" -> "08:00")
      let timeForBackend = $formData.selectedTime;
      if (typeof timeForBackend === 'string' && timeForBackend.includes('AM') || typeof timeForBackend === 'string' && timeForBackend.includes('PM')) {
        const match = timeForBackend.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)/i);
        if (match) {
          let hours = parseInt(match[1], 10);
          const minutes = match[2];
          const period = match[3].toUpperCase();
          if (period === 'PM' && hours !== 12) hours += 12;
          if (period === 'AM' && hours === 12) hours = 0;
          timeForBackend = `${String(hours).padStart(2, '0')}:${minutes}`;
        }
      }

      const result = await api.createBooking({
        address: $formData.address,
        addressDetails: $formData.addressDetails,
        itemCategory: $formData.itemCategory,
        itemDescription: $formData.itemDescription,
        quantity: $formData.quantity,
        photoUrls: $formData.photoUrls,
        selectedDate: $formData.selectedDate,
        selectedTime: timeForBackend,
        estimate: $formData.estimate,
        customerInfo: $formData.customerInfo,
        totalAmount: $formData.estimate?.total || 0,
      });

      bookingId = result.bookingId || result.booking_id || null;
      if (!bookingId) {
        console.error('Booking created but no bookingId returned:', result);
        error.set('Booking was created but we could not retrieve its ID. Please contact support.');
      }
    } catch (err) {
      console.error('Failed to create booking:', err);
      error.set('Could not create your booking. Please check your connection and try again.');
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

    if (!bookingId) {
      error.set('No booking found. Please go back and try again.');
      return;
    }

    processingPayment = true;
    error.set(null);
    cardError = '';

    try {
      // Create payment intent
      const { clientSecret } = await api.createPaymentIntent(
        bookingId,
        $formData.estimate?.total || 0
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
        try {
          await api.confirmPayment(paymentIntent.id, bookingId);
        } catch (_) {
          // Backend confirmation failed but payment succeeded
        }
        paymentSuccess = true;
      }
    } catch (err) {
      error.set(err.message || 'Payment failed. Please try again.');
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
    <div class="mb-8">
      <div class="w-16 h-16 bg-primary-100 rounded-2xl flex items-center justify-center mx-auto mb-5" in:scale={{ delay: 200, duration: 500 }}>
        <Check class="w-8 h-8 text-primary-600" />
      </div>
      <h2 class="text-3xl font-bold text-warm-900 font-heading mb-2">You're all set!</h2>
      <p class="text-warm-500">
        Your pickup has been scheduled.
      </p>
    </div>

    <div class="bg-warm-50 rounded-xl p-5 mb-6 text-left border border-warm-200">
      <div class="space-y-2.5 text-sm">
        <div class="flex justify-between">
          <span class="text-warm-500">Booking ID</span>
          <span class="font-mono font-semibold text-primary-700">{bookingId}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-warm-500">Total</span>
          <span class="font-heading font-bold text-warm-900">${($formData.estimate?.total || 0).toFixed(2)}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-warm-500">When</span>
          <span class="font-medium text-warm-800">{$formData.selectedTime}</span>
        </div>
      </div>
    </div>

    <div class="info-box-brand mb-6 text-left">
      <Truck class="w-4 h-4 text-primary-600 mt-0.5 flex-shrink-0" />
      <div>
        <p class="font-semibold text-sm mb-1">What happens next</p>
        <ul class="text-xs space-y-1 opacity-80">
          <li>We'll text you 30 min before arrival</li>
          <li>Crew confirms the price on-site</li>
          <li>We handle all the heavy lifting</li>
        </ul>
      </div>
    </div>

    <div class="info-box-blue mb-6 text-left">
      <Check class="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
      <div>
        <p class="font-semibold text-sm mb-0.5">Confirmation sent</p>
        <p class="text-xs opacity-80">
          Check <strong>{$formData.customerInfo.email}</strong> for details.
        </p>
      </div>
    </div>

    <a
      href="?track={bookingId}"
      class="btn-primary w-full flex items-center justify-center gap-2 mb-3"
    >
      Track Your Pickup
      <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <line x1="5" y1="12" x2="19" y2="12"></line>
        <polyline points="12 5 19 12 12 19"></polyline>
      </svg>
    </a>

    <button
      on:click={handleNewBooking}
      class="btn-secondary w-full"
    >
      Book Another Pickup
    </button>
  </div>
{:else}
  <!-- Payment Form -->
  <div class="card">
    <div class="mb-8">
      <h2 class="text-2xl font-bold text-warm-900 font-heading mb-1">Complete Payment</h2>
      <p class="text-warm-500">
        Secure checkout powered by Stripe.
      </p>
    </div>

    <!-- Global Error Display -->
    {#if $error}
      <div class="bg-red-50 border border-red-200 rounded-xl p-4 mb-6 flex items-start gap-3" transition:fly={{ y: -10, duration: 200 }}>
        <AlertCircle class="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
        <div>
          <p class="text-sm font-semibold text-red-800">Something went wrong</p>
          <p class="text-xs text-red-600 mt-0.5">{$error}</p>
        </div>
      </div>
    {/if}

    <!-- Payment Summary -->
    <div class="bg-warm-50 rounded-xl p-5 mb-6 border border-warm-200">
      <div class="flex justify-between items-center">
        <div>
          <p class="text-xs text-warm-400 uppercase tracking-wider font-semibold">Total Due</p>
          <p class="text-3xl font-heading font-bold text-primary-600 mt-0.5">${($formData.estimate?.total || 0).toFixed(2)}</p>
        </div>
        <div class="text-right">
          <p class="text-xs text-warm-400 uppercase tracking-wider font-semibold">Booking</p>
          <p class="font-mono text-sm font-semibold text-warm-700 mt-0.5">{bookingId || '...'}</p>
        </div>
      </div>
    </div>

    <!-- Apple Pay / Google Pay -->
    {#if canMakePayment}
      <div class="mb-6">
        <div bind:this={applePayMountEl}></div>
        <div class="relative my-5">
          <div class="absolute inset-0 flex items-center">
            <div class="w-full border-t border-warm-200"></div>
          </div>
          <div class="relative flex justify-center text-xs">
            <span class="bg-white px-4 text-warm-400 uppercase tracking-wider font-medium">or pay with card</span>
          </div>
        </div>
      </div>
    {/if}

    <form on:submit={handlePayment} class="space-y-5">
      <!-- Cardholder Name -->
      <div>
        <label for="cardholder-name" class="block text-sm font-semibold text-warm-700 mb-1.5">
          Name on Card
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
        <label class="block text-sm font-semibold text-warm-700 mb-1.5">
          Card Details
        </label>
        <div
          bind:this={cardMountEl}
          id="card-element"
          class="input-field"
          class:border-red-400={cardError}
        ></div>
        {#if cardError}
          <div class="error-message mt-1.5" transition:fly={{ y: -10, duration: 200 }}>
            <AlertCircle class="w-4 h-4" />
            <span>{cardError}</span>
          </div>
        {/if}
      </div>

      <!-- Security Notice -->
      <div class="flex items-center gap-2 text-xs text-warm-400">
        <Lock class="w-3.5 h-3.5" />
        <span>Encrypted with SSL. We never store your card details.</span>
      </div>

      <!-- Test Card Info -->
      <div class="info-box-blue">
        <CreditCard class="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
        <div>
          <p class="font-semibold text-sm mb-0.5">Test Mode</p>
          <p class="text-xs opacity-80">
            Use <span class="font-mono font-semibold">4242 4242 4242 4242</span> &middot; any future date &middot; any CVC
          </p>
        </div>
      </div>

      <!-- Navigation -->
      <div class="flex justify-between pt-2">
        <button
          type="button"
          on:click={prevStep}
          disabled={processingPayment}
          class="btn-secondary"
        >
          Back
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
            <span>Pay ${($formData.estimate?.total || 0).toFixed(2)}</span>
          {/if}
        </button>
      </div>
    </form>
  </div>
{/if}
