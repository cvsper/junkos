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
    <div class="text-center mb-6" in:fade={{ duration: 400 }}>
      <h1 class="text-3xl md:text-4xl font-bold text-gray-900 mb-2 font-heading">
        Track Your Pickup
      </h1>
      <p class="text-gray-600">Real-time updates on your junk removal</p>
    </div>
    <TrackingPage jobId={trackingJobId} />
  {:else}
    <!-- Booking Flow -->

    <!-- Hero Section - Only show on step 1 -->
    {#if $currentStep === 1}
      <div class="text-center mb-8" in:fade={{ duration: 400 }}>
        <h1 class="text-4xl md:text-5xl lg:text-6xl font-bold text-gray-900 mb-4 font-heading bg-gradient-to-r from-primary-600 to-indigo-600 bg-clip-text text-transparent">
          Easy Junk Removal in Minutes
        </h1>
        <p class="text-xl md:text-2xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
          Schedule your pickup, get an instant estimate, and say goodbye to your junk.
          <br class="hidden md:block" />
          <span class="text-cta-600 font-semibold">Professional service, transparent pricing.</span>
        </p>
      </div>
    {/if}

    <!-- Progress Bar -->
    <ProgressBar />

    <!-- Error Message -->
    {#if $error}
      <div
        class="mb-6 bg-red-50 border-2 border-red-200 rounded-xl p-4 shadow-md"
        in:fly={{ y: -20, duration: 300 }}
        out:fade={{ duration: 200 }}
      >
        <div class="flex gap-3">
          <AlertCircle class="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
          <div class="flex-1">
            <p class="font-semibold text-red-900">Error</p>
            <p class="text-sm text-red-800 mt-1">{$error}</p>
          </div>
          <button
            on:click={dismissError}
            class="text-red-600 hover:text-red-800 transition-colors p-1"
            aria-label="Dismiss error"
          >
            <X class="w-5 h-5" />
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
