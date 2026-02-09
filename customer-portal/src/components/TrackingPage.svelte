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
    pending: { label: 'Pending', color: 'text-amber-600', bg: 'bg-amber-50', icon: Clock, step: 0 },
    confirmed: { label: 'Confirmed', color: 'text-primary-600', bg: 'bg-primary-50', icon: CheckCircle, step: 1 },
    assigned: { label: 'Driver Assigned', color: 'text-primary-600', bg: 'bg-primary-50', icon: Truck, step: 2 },
    accepted: { label: 'Driver Accepted', color: 'text-primary-600', bg: 'bg-primary-50', icon: Truck, step: 2 },
    en_route: { label: 'Driver En Route', color: 'text-teal-600', bg: 'bg-teal-50', icon: Navigation, step: 3 },
    arrived: { label: 'Driver Arrived', color: 'text-primary-700', bg: 'bg-primary-50', icon: MapPin, step: 4 },
    started: { label: 'In Progress', color: 'text-primary-600', bg: 'bg-primary-50', icon: Package, step: 5 },
    completed: { label: 'Completed', color: 'text-primary-700', bg: 'bg-primary-50', icon: CheckCircle, step: 6 },
    cancelled: { label: 'Cancelled', color: 'text-red-600', bg: 'bg-red-50', icon: AlertCircle, step: -1 },
  };

  const STEPS = ['Booked', 'Confirmed', 'Assigned', 'En Route', 'Arrived', 'In Progress', 'Done'];

  $: statusConfig = STATUS_CONFIG[tracking?.status] || STATUS_CONFIG.pending;
  $: currentStep = statusConfig.step;

  onMount(async () => {
    await fetchTracking();
    setupSocket();
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

      // Handle various API response formats
      const data = result.tracking || result.booking || result.data || result;
      if (data && (data.status || data.job_id || data.address)) {
        tracking = data;
        if (tracking.driver) {
          driverLat = tracking.driver.lat;
          driverLng = tracking.driver.lng;
          updateMap();
        }
      } else if (!tracking) {
        error = 'Booking not found. It may still be processing.';
      }
    } catch (err) {
      if (!tracking) {
        error = 'Unable to load tracking data. Please check your booking ID.';
      }
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
          tracking = tracking;
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

    if (tracking?.lat && tracking?.lng) {
      jobMarker = new window.google.maps.Marker({
        position: { lat: tracking.lat, lng: tracking.lng },
        map,
        title: 'Pickup Location',
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: 10,
          fillColor: '#059669',
          fillOpacity: 1,
          strokeColor: '#047857',
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

  function loadGoogleMaps() {
    if (window.google && window.google.maps) {
      initMap();
      return;
    }
    const key = import.meta.env.VITE_GOOGLE_MAPS_KEY || '';
    if (!key) return;

    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${key}`;
    script.onload = initMap;
    document.head.appendChild(script);
  }

  $: if (tracking && mapElement) loadGoogleMaps();
</script>

{#if loading}
  <div class="flex items-center justify-center min-h-[400px]">
    <div class="text-center">
      <Loader class="w-8 h-8 text-primary-600 animate-spin mx-auto mb-4" />
      <p class="text-warm-500 text-sm">Loading tracking info...</p>
      <p class="text-xs text-warm-400 mt-2">Booking ID: {jobId}</p>
    </div>
  </div>
{:else if error}
  <div class="card text-center">
    <AlertCircle class="w-12 h-12 text-warm-300 mx-auto mb-4" />
    <h2 class="text-xl font-bold text-warm-900 font-heading mb-2">Booking Not Found</h2>
    <p class="text-warm-500 text-sm mb-4">{error}</p>
    <p class="text-xs text-warm-400 mb-4 font-mono">{jobId}</p>
    <a href="/" class="btn-primary inline-flex items-center gap-2">Book a Pickup</a>
  </div>
{:else if tracking}
  <div class="space-y-5">
    <!-- Status Header -->
    <div class="card">
      <div class="flex items-center gap-4 mb-5">
        <div class="p-3 rounded-xl {statusConfig.bg}">
          <svelte:component this={statusConfig.icon} class="w-6 h-6 {statusConfig.color}" />
        </div>
        <div>
          <h2 class="text-xl font-bold text-warm-900 font-heading">{statusConfig.label}</h2>
          <p class="text-xs text-warm-400 font-mono">#{tracking.job_id?.slice(0, 8)}</p>
        </div>
      </div>

      <!-- Progress Steps -->
      {#if currentStep >= 0}
        <div class="mt-4">
          <div class="flex items-center justify-between relative">
            <div class="absolute top-3.5 left-0 right-0 h-[2px] bg-warm-200"></div>
            <div
              class="absolute top-3.5 left-0 h-[2px] bg-primary-500 transition-all duration-700"
              style="width: {Math.max(0, (currentStep / (STEPS.length - 1)) * 100)}%"
            ></div>

            {#each STEPS as step, i}
              <div class="relative flex flex-col items-center z-10">
                <div
                  class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300
                    {i <= currentStep ? 'bg-primary-600 text-white' : 'bg-warm-100 text-warm-400'}"
                >
                  {#if i < currentStep}
                    <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                  {:else}
                    {i + 1}
                  {/if}
                </div>
                <span class="text-[10px] mt-1.5 {i <= currentStep ? 'text-primary-700 font-semibold' : 'text-warm-400'} hidden sm:block">
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
      <div class="card">
        <h3 class="text-xs font-semibold text-warm-400 uppercase tracking-wider mb-3">Your Driver</h3>
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 bg-primary-50 rounded-xl flex items-center justify-center">
            <span class="text-lg font-bold text-primary-700 font-heading">
              {tracking.driver.name ? tracking.driver.name[0].toUpperCase() : 'D'}
            </span>
          </div>
          <div class="flex-1">
            <p class="font-heading font-semibold text-warm-900">{tracking.driver.name || 'Driver'}</p>
            <div class="flex items-center gap-3 text-xs text-warm-500 mt-0.5">
              {#if tracking.driver.avg_rating}
                <span class="flex items-center gap-1">
                  <Star class="w-3 h-3 text-amber-400 fill-amber-400" />
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
      <div class="card text-center py-10">
        <Loader class="w-6 h-6 text-primary-500 animate-spin mx-auto mb-3" />
        <p class="text-warm-600 text-sm font-medium">Finding your driver...</p>
        <p class="text-xs text-warm-400 mt-1">You'll be notified once assigned</p>
      </div>
    {/if}

    <!-- Live Map -->
    {#if tracking.driver && driverLat != null && ['en_route', 'arrived', 'accepted', 'assigned'].includes(tracking.status)}
      <div class="card overflow-hidden p-0">
        <div class="px-6 pt-5 pb-3">
          <h3 class="text-xs font-semibold text-warm-400 uppercase tracking-wider">Live Location</h3>
        </div>
        <div bind:this={mapElement} class="w-full h-64 bg-warm-100"></div>
        {#if !import.meta.env.VITE_GOOGLE_MAPS_KEY}
          <div class="absolute inset-0 flex items-center justify-center bg-warm-100 rounded-b-2xl">
            <div class="text-center p-6">
              <MapPin class="w-8 h-8 text-warm-300 mx-auto mb-2" />
              <p class="text-warm-500 text-sm">Map requires API key</p>
              <p class="text-xs text-warm-400 mt-1 font-mono">{driverLat?.toFixed(4)}, {driverLng?.toFixed(4)}</p>
            </div>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Booking Details -->
    <div class="card">
      <h3 class="text-xs font-semibold text-warm-400 uppercase tracking-wider mb-4">Details</h3>
      <div class="space-y-3 text-sm">
        <div class="flex justify-between">
          <span class="text-warm-500 flex items-center gap-2">
            <MapPin class="w-3.5 h-3.5" /> Address
          </span>
          <span class="font-medium text-warm-800 text-right max-w-[60%]">{tracking.address}</span>
        </div>
        {#if tracking.scheduled_at}
          <div class="flex justify-between">
            <span class="text-warm-500 flex items-center gap-2">
              <Clock class="w-3.5 h-3.5" /> Scheduled
            </span>
            <span class="font-medium text-warm-800">
              {new Date(tracking.scheduled_at).toLocaleString()}
            </span>
          </div>
        {/if}
        <div class="flex justify-between border-t border-warm-100 pt-3">
          <span class="text-warm-500">Total</span>
          <span class="font-heading font-bold text-primary-600 text-lg">${tracking.total_price?.toFixed(2)}</span>
        </div>
        {#if tracking.payment_status}
          <div class="flex justify-between">
            <span class="text-warm-500">Payment</span>
            <span class="font-medium capitalize {tracking.payment_status === 'succeeded' ? 'text-primary-600' : 'text-amber-600'}">
              {tracking.payment_status}
            </span>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}
