<script>
  import { onMount, onDestroy } from 'svelte';
  import { fade, fly, scale } from 'svelte/transition';
  import { MapPin, Truck, Clock, CheckCircle, AlertCircle, Loader, Phone, Star, Package, Navigation } from 'lucide-svelte';
  import { api } from '../services/api';
  import { io } from 'socket.io-client';

  export let jobId = '';

  const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8080/api').replace(/\/api$/, '');

  let tracking = null;
  let loading = true;
  let error = null;
  let socket = null;
  let driverLat = null;
  let driverLng = null;
  let mapElement = null;
  let map = null;
  let driverMarker = null;
  let jobMarker = null;
  let pollInterval = null;

  const STATUS_CONFIG = {
    pending: { label: 'Pending', color: 'text-yellow-600', bg: 'bg-yellow-100', icon: Clock, step: 0 },
    confirmed: { label: 'Confirmed', color: 'text-blue-600', bg: 'bg-blue-100', icon: CheckCircle, step: 1 },
    assigned: { label: 'Driver Assigned', color: 'text-indigo-600', bg: 'bg-indigo-100', icon: Truck, step: 2 },
    accepted: { label: 'Driver Accepted', color: 'text-indigo-600', bg: 'bg-indigo-100', icon: Truck, step: 2 },
    en_route: { label: 'Driver En Route', color: 'text-purple-600', bg: 'bg-purple-100', icon: Navigation, step: 3 },
    arrived: { label: 'Driver Arrived', color: 'text-green-600', bg: 'bg-green-100', icon: MapPin, step: 4 },
    started: { label: 'In Progress', color: 'text-emerald-600', bg: 'bg-emerald-100', icon: Package, step: 5 },
    completed: { label: 'Completed', color: 'text-green-700', bg: 'bg-green-100', icon: CheckCircle, step: 6 },
    cancelled: { label: 'Cancelled', color: 'text-red-600', bg: 'bg-red-100', icon: AlertCircle, step: -1 },
  };

  const STEPS = ['Booked', 'Confirmed', 'Assigned', 'En Route', 'Arrived', 'In Progress', 'Completed'];

  $: statusConfig = STATUS_CONFIG[tracking?.status] || STATUS_CONFIG.pending;
  $: currentStep = statusConfig.step;

  onMount(async () => {
    await fetchTracking();
    setupSocket();
    // Poll every 15 seconds as fallback
    pollInterval = setInterval(fetchTracking, 15000);
  });

  onDestroy(() => {
    if (socket) {
      socket.emit('customer:leave', { job_id: jobId });
      socket.disconnect();
    }
    if (pollInterval) clearInterval(pollInterval);
  });

  async function fetchTracking() {
    try {
      const result = await api.getBookingStatus(jobId);
      if (result.success) {
        tracking = result.tracking;
        // Update driver location from tracking data
        if (tracking.driver) {
          driverLat = tracking.driver.lat;
          driverLng = tracking.driver.lng;
          updateMap();
        }
      }
    } catch (err) {
      if (!tracking) error = err.message;
    } finally {
      loading = false;
    }
  }

  function setupSocket() {
    try {
      socket = io(API_BASE_URL, { transports: ['websocket', 'polling'] });

      socket.on('connect', () => {
        socket.emit('customer:join', { job_id: jobId });
      });

      socket.on('driver:location', (data) => {
        driverLat = data.lat;
        driverLng = data.lng;
        updateMap();
      });

      socket.on('job:status', (data) => {
        if (data.job_id === jobId && tracking) {
          tracking.status = data.status;
          tracking = tracking; // trigger reactivity
        }
      });

      socket.on('job:driver-assigned', (data) => {
        if (data.job_id === jobId && tracking) {
          tracking.driver = data.driver;
          tracking.status = 'assigned';
          tracking = tracking;
        }
      });
    } catch (err) {
      console.warn('Socket connection failed, using polling fallback');
    }
  }

  function initMap() {
    if (!mapElement || !window.google) return;

    const center = tracking?.lat && tracking?.lng
      ? { lat: tracking.lat, lng: tracking.lng }
      : { lat: 26.1224, lng: -80.1373 };

    map = new window.google.maps.Map(mapElement, {
      center,
      zoom: 14,
      disableDefaultUI: true,
      zoomControl: true,
      styles: [
        { featureType: 'poi', stylers: [{ visibility: 'off' }] },
        { featureType: 'transit', stylers: [{ visibility: 'off' }] },
      ],
    });

    // Job location marker
    if (tracking?.lat && tracking?.lng) {
      jobMarker = new window.google.maps.Marker({
        position: { lat: tracking.lat, lng: tracking.lng },
        map,
        title: 'Pickup Location',
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: 10,
          fillColor: '#6366F1',
          fillOpacity: 1,
          strokeColor: '#4338CA',
          strokeWeight: 2,
        },
      });
    }

    updateMap();
  }

  function updateMap() {
    if (!map || driverLat == null || driverLng == null) return;

    const pos = { lat: driverLat, lng: driverLng };

    if (driverMarker) {
      driverMarker.setPosition(pos);
    } else {
      driverMarker = new window.google.maps.Marker({
        position: pos,
        map,
        title: 'Driver',
        icon: {
          path: 'M 0,-8 L 6,8 L 0,4 L -6,8 Z',
          scale: 2,
          fillColor: '#059669',
          fillOpacity: 1,
          strokeColor: '#047857',
          strokeWeight: 1,
          rotation: 0,
        },
      });
    }
  }

  // Load Google Maps script
  function loadGoogleMaps() {
    if (window.google && window.google.maps) {
      initMap();
      return;
    }
    const key = import.meta.env.VITE_GOOGLE_MAPS_KEY || '';
    if (!key) return; // Skip map if no API key

    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${key}`;
    script.onload = initMap;
    document.head.appendChild(script);
  }

  $: if (tracking && mapElement) loadGoogleMaps();
</script>

{#if loading}
  <div class="flex items-center justify-center min-h-[400px]" in:fade>
    <div class="text-center">
      <Loader class="w-10 h-10 text-primary-600 animate-spin mx-auto mb-4" />
      <p class="text-gray-600">Loading tracking info...</p>
    </div>
  </div>
{:else if error}
  <div class="card text-center" in:fly={{ y: 20, duration: 300 }}>
    <AlertCircle class="w-16 h-16 text-red-400 mx-auto mb-4" />
    <h2 class="text-2xl font-bold text-gray-900 mb-2">Booking Not Found</h2>
    <p class="text-gray-600 mb-4">{error}</p>
    <p class="text-sm text-gray-500">Check your booking ID and try again.</p>
  </div>
{:else if tracking}
  <div class="space-y-6" in:fade={{ duration: 300 }}>
    <!-- Status Header -->
    <div class="card" in:fly={{ y: 20, duration: 300 }}>
      <div class="flex items-center gap-4 mb-4">
        <div class="p-3 rounded-xl {statusConfig.bg}">
          <svelte:component this={statusConfig.icon} class="w-8 h-8 {statusConfig.color}" />
        </div>
        <div>
          <h2 class="text-2xl font-bold text-gray-900 font-heading">{statusConfig.label}</h2>
          <p class="text-sm text-gray-500 font-mono">Booking #{tracking.job_id?.slice(0, 8)}</p>
        </div>
      </div>

      <!-- Progress Steps -->
      {#if currentStep >= 0}
        <div class="mt-6">
          <div class="flex items-center justify-between relative">
            <!-- Progress bar background -->
            <div class="absolute top-4 left-0 right-0 h-0.5 bg-gray-200"></div>
            <div
              class="absolute top-4 left-0 h-0.5 bg-emerald-500 transition-all duration-700"
              style="width: {Math.max(0, (currentStep / (STEPS.length - 1)) * 100)}%"
            ></div>

            {#each STEPS as step, i}
              <div class="relative flex flex-col items-center z-10">
                <div
                  class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300
                    {i <= currentStep ? 'bg-emerald-500 text-white' : 'bg-gray-200 text-gray-500'}"
                >
                  {#if i < currentStep}
                    <CheckCircle class="w-5 h-5" />
                  {:else}
                    {i + 1}
                  {/if}
                </div>
                <span class="text-xs mt-1 {i <= currentStep ? 'text-emerald-600 font-semibold' : 'text-gray-400'} hidden sm:block">
                  {step}
                </span>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>

    <!-- Driver Info Card -->
    {#if tracking.driver}
      <div class="card" in:fly={{ y: 20, duration: 300, delay: 100 }}>
        <h3 class="font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Truck class="w-5 h-5 text-emerald-600" />
          Your Driver
        </h3>
        <div class="flex items-center gap-4">
          <div class="w-14 h-14 bg-emerald-100 rounded-full flex items-center justify-center">
            <span class="text-xl font-bold text-emerald-600">
              {tracking.driver.name ? tracking.driver.name[0].toUpperCase() : 'D'}
            </span>
          </div>
          <div class="flex-1">
            <p class="font-semibold text-gray-900 text-lg">{tracking.driver.name || 'Driver'}</p>
            <div class="flex items-center gap-3 text-sm text-gray-600">
              {#if tracking.driver.avg_rating}
                <span class="flex items-center gap-1">
                  <Star class="w-4 h-4 text-yellow-500 fill-yellow-500" />
                  {tracking.driver.avg_rating.toFixed(1)}
                </span>
              {/if}
              {#if tracking.driver.total_jobs}
                <span>{tracking.driver.total_jobs} jobs</span>
              {/if}
              {#if tracking.driver.truck_type}
                <span class="capitalize">{tracking.driver.truck_type.replace('_', ' ')}</span>
              {/if}
            </div>
          </div>
        </div>
      </div>
    {:else if tracking.status !== 'completed' && tracking.status !== 'cancelled'}
      <div class="card text-center py-8" in:fly={{ y: 20, duration: 300, delay: 100 }}>
        <Loader class="w-8 h-8 text-indigo-500 animate-spin mx-auto mb-3" />
        <p class="text-gray-600">Looking for the best driver near you...</p>
        <p class="text-sm text-gray-400 mt-1">You'll be notified once a driver is assigned</p>
      </div>
    {/if}

    <!-- Live Map -->
    {#if tracking.driver && driverLat != null && ['en_route', 'arrived', 'accepted', 'assigned'].includes(tracking.status)}
      <div class="card overflow-hidden p-0" in:fly={{ y: 20, duration: 300, delay: 200 }}>
        <div class="px-6 pt-5 pb-3">
          <h3 class="font-semibold text-gray-900 flex items-center gap-2">
            <Navigation class="w-5 h-5 text-emerald-600" />
            Live Tracking
          </h3>
        </div>
        <div bind:this={mapElement} class="w-full h-72 bg-gray-100"></div>
        {#if !import.meta.env.VITE_GOOGLE_MAPS_KEY}
          <div class="absolute inset-0 flex items-center justify-center bg-gray-100 rounded-b-xl">
            <div class="text-center p-6">
              <MapPin class="w-10 h-10 text-gray-400 mx-auto mb-2" />
              <p class="text-gray-500 text-sm">Map requires Google Maps API key</p>
              <p class="text-xs text-gray-400 mt-1">Driver location: {driverLat?.toFixed(4)}, {driverLng?.toFixed(4)}</p>
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Booking Details -->
    <div class="card" in:fly={{ y: 20, duration: 300, delay: 300 }}>
      <h3 class="font-semibold text-gray-900 mb-3">Booking Details</h3>
      <div class="space-y-3 text-sm">
        <div class="flex justify-between">
          <span class="text-gray-600 flex items-center gap-2">
            <MapPin class="w-4 h-4" /> Address
          </span>
          <span class="font-medium text-gray-900 text-right max-w-[60%]">{tracking.address}</span>
        </div>
        {#if tracking.scheduled_at}
          <div class="flex justify-between">
            <span class="text-gray-600 flex items-center gap-2">
              <Clock class="w-4 h-4" /> Scheduled
            </span>
            <span class="font-medium text-gray-900">
              {new Date(tracking.scheduled_at).toLocaleString()}
            </span>
          </div>
        {/if}
        <div class="flex justify-between">
          <span class="text-gray-600">Total</span>
          <span class="font-bold text-emerald-600 text-lg">${tracking.total_price?.toFixed(2)}</span>
        </div>
        {#if tracking.payment_status}
          <div class="flex justify-between">
            <span class="text-gray-600">Payment</span>
            <span class="font-medium capitalize {tracking.payment_status === 'succeeded' ? 'text-green-600' : 'text-yellow-600'}">
              {tracking.payment_status}
            </span>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}
