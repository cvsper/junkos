<script>
  import { AlertCircle, X } from 'lucide-svelte';
  import { fade, fly } from 'svelte/transition';
  import Layout from './components/Layout.svelte';
  import ProgressBar from './components/ProgressBar.svelte';
  import TrackingPage from './components/TrackingPage.svelte';
  import Step1Address from './components/steps/Step1Address.svelte';
  import Step2Photos from './components/steps/Step2Photos.svelte';
  import Step3Items from './components/steps/Step3Items.svelte';
  import Step4DateTime from './components/steps/Step4DateTime.svelte';
  import Step5Estimate from './components/steps/Step5Estimate.svelte';
  import Step6Payment from './components/steps/Step6Payment.svelte';
  import { currentStep, error } from './stores/bookingStore';

  // Simple URL-based routing: /track/:jobId shows tracking page
  let trackingJobId = null;

  function checkRoute() {
    const path = window.location.pathname;
    const hash = window.location.hash;

    // Support both /track/:id and #/track/:id
    const pathMatch = path.match(/^\/track\/(.+)/);
    const hashMatch = hash.match(/^#\/track\/(.+)/);

    if (pathMatch) {
      trackingJobId = pathMatch[1];
    } else if (hashMatch) {
      trackingJobId = hashMatch[1];
    } else {
      trackingJobId = null;
    }

    // Also support ?track=jobId query param
    const params = new URLSearchParams(window.location.search);
    if (params.get('track')) {
      trackingJobId = params.get('track');
    }
  }

  checkRoute();
  // Listen for hash changes
  if (typeof window !== 'undefined') {
    window.addEventListener('hashchange', checkRoute);
    window.addEventListener('popstate', checkRoute);
  }

  $: currentStepComponent = getStepComponent($currentStep);

  function getStepComponent(step) {
    switch (step) {
      case 1: return Step1Address;
      case 2: return Step2Photos;
      case 3: return Step3Items;
      case 4: return Step4DateTime;
      case 5: return Step5Estimate;
      case 6: return Step6Payment;
      default: return Step1Address;
    }
  }

  function dismissError() {
    error.set(null);
  }
</script>

<Layout>
  {#if trackingJobId}
    <!-- Tracking Page -->
    <div class="text-center mb-8" in:fade={{ duration: 400 }}>
      <div class="section-badge mx-auto mb-4">Live Tracking</div>
      <h1 class="text-3xl md:text-4xl font-bold text-warm-900 mb-2 font-heading">
        Track Your Pickup
      </h1>
      <p class="text-warm-500">Real-time updates on your junk removal</p>
    </div>
    <TrackingPage jobId={trackingJobId} />
  {:else}
    <!-- Booking Flow -->

    <!-- Hero Section - Only show on step 1 -->
    {#if $currentStep === 1}
      <div class="text-center mb-10" in:fade={{ duration: 400 }}>
        <div class="section-badge mx-auto mb-5">Book in 60 Seconds</div>
        <h1 class="text-4xl md:text-5xl font-bold text-warm-900 mb-4 font-heading leading-[1.1] text-balance">
          Junk removal,<br class="hidden sm:block" />
          <span class="text-primary-600">made simple.</span>
        </h1>
        <p class="text-lg text-warm-500 max-w-lg mx-auto leading-relaxed">
          Get an instant estimate, pick a time, and we'll handle the rest.
          Same-day service available in South Florida.
        </p>
      </div>
    {/if}

    <!-- Progress Bar -->
    <ProgressBar />

    <!-- Error Message -->
    {#if $error}
      <div
        class="mb-6 bg-red-50 border border-red-200 rounded-xl p-4 shadow-soft"
        in:fly={{ y: -20, duration: 300 }}
        out:fade={{ duration: 200 }}
      >
        <div class="flex gap-3">
          <AlertCircle class="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" />
          <div class="flex-1">
            <p class="font-semibold text-red-900 text-sm">Something went wrong</p>
            <p class="text-sm text-red-700 mt-0.5">{$error}</p>
          </div>
          <button
            on:click={dismissError}
            class="text-red-400 hover:text-red-600 transition-colors p-1"
            aria-label="Dismiss error"
          >
            <X class="w-4 h-4" />
          </button>
        </div>
      </div>
    {/if}

    <!-- Current Step Component -->
    <div class="mb-8">
      {#key $currentStep}
        <svelte:component this={currentStepComponent} />
      {/key}
    </div>
  {/if}
</Layout>

<style>
  :global(body) {
    overflow-x: hidden;
  }
</style>
