// Local browser-test fixture only. No database, outbound requests, or real payments.
import http from 'node:http';
const job = { id: 'draft-job', customer_id: 'customer-draft', driver_id: 'driver-draft', status: 'accepted', address: '123 Test Ave, Boca Raton, FL 33432', lat: 26.3683, lng: -80.1289, items: [{ category: 'sofa', quantity: 1 }], photos: [], before_photos: [], after_photos: [], total_price: 200, driver_payout: 144, payout_status: 'pending_connect', base_price: 180, item_total: 180, service_fee: 20, version: 1, scheduled_at: '2026-09-16T14:00:00Z', customer_name: 'Local Customer', customer_phone: '5615550100', payment: { payment_status: 'succeeded', amount: 200, tip_amount: 0 }, created_at: '2026-09-12T14:00:00Z' };
const state = { job, requests: [], is_online: false, failUpload: false, loseStatus: false, loseBooking: false, failConfirm: false, booking: null, cancellationFee: 0 };
http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1:3108');
  res.setHeader('Access-Control-Allow-Origin', 'http://127.0.0.1:3107');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Checkout-Token');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS');
  if (req.method === 'OPTIONS') { res.writeHead(204); return res.end(); }
  const chunks = []; for await (const chunk of req) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString();
  let data = {}; try { data = JSON.parse(raw); } catch {}
  const reply = (body, code = 200) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify({ success: true, ...body })); };
  if (url.pathname === '/__state') return reply(state);
  if (url.pathname === '/__control') { Object.assign(state, data); return reply({}); }
  state.requests.push({ path: url.pathname, method: req.method, data, filesField: raw.includes('name="files"') });
  if (url.pathname === '/api/booking/availability') return reply({ date: url.searchParams.get('date'), any_available: true, slots: ['8-10','10-12','12-14','14-16','16-18'].map((slot, i) => ({ slot, label: ['8–10 AM','10 AM–12 PM','12–2 PM','2–4 PM','4–6 PM'][i], available: i === 1 || i === 3, crews: i === 1 || i === 3 ? 1 : 0 })) });
  if (url.pathname === '/api/booking/market-bounds') return reply({ market_timezone: 'America/New_York', bounds: { min_lat: 25.1, max_lat: 27.3, min_lng: -81, max_lng: -79.9 } });
  if (url.pathname === '/api/booking/estimate') return reply({ price_version: 'local-price', estimate: { total: 200, subtotal: 180, base_price: 0, item_total: 180, service_fee: 20, surge_amount: 0, items: [], price_version: 'local-price', breakdown: [] } });
  if (url.pathname === '/api/booking' && req.method === 'POST') {
    state.booking ||= { ...job, id: 'saved-booking', status: 'pending', confirmation_code: 'DRAFT001' };
    if (state.loseBooking) { state.loseBooking = false; return reply({ error: 'Simulated lost booking response' }, 503); }
    return reply({ job: state.booking, checkout_token: 'local-capability' });
  }
  if (url.pathname.endsWith('/photos') && req.method === 'POST') {
    if (state.failUpload) return reply({ error: 'Photo upload failed. Your photos are saved for retry.' }, 503);
    return reply({ urls: ['http://127.0.0.1:3107/logo.png'] }, 201);
  }
  if (url.pathname === '/api/payments/create-intent-simple') return reply({ clientSecret: 'pi_local_secret_fixture', paymentIntentId: 'pi_local' });
  if (url.pathname === '/api/payments/confirm-simple') {
    if (state.failConfirm) return reply({ error: 'Simulated lost payment response. Check saved payment.' }, 503);
    return reply({ job: state.booking, payment: { payment_status: 'succeeded' } });
  }
  if (url.pathname === '/api/driver/profile') return reply({ profile: { id: 'contractor-draft', user_id: 'driver-draft', name: 'Local Driver', email: 'driver@example.test', is_online: state.is_online, approval_status: 'approved', stripe_onboarding_complete: true } });
  if (url.pathname === '/api/driver/stats') return reply({ stats: { total_jobs: 4, today_jobs: 1, total_earnings: 576, today_earnings: 144, rating: 4.9, acceptance_rate: 1 } });
  if (url.pathname === '/api/payments/connect/status') return reply({ details_submitted: true, payouts_enabled: true });
  if (url.pathname === '/api/drivers/availability') { state.is_online = data.is_online; return reply({ is_online: state.is_online }); }
  if (url.pathname === '/api/drivers/location') return reply({});
  if (url.pathname === '/api/drivers/jobs/current') return reply({ job: state.job });
  if (url.pathname === '/api/drivers/jobs/available' || url.pathname === '/api/driver/earnings/history') return reply({ jobs: [], total: 0, page: 1, pages: 1 });
  if (url.pathname.endsWith('/cancel-preview')) return reply({ allowed: true, cancellation_fee: state.cancellationFee, refund_amount: 200 - state.cancellationFee, requires_confirmation: true, message: 'Review your cancellation fee and refund before confirming.' });
  if (url.pathname.endsWith('/cancel')) { state.job.status = 'cancelled'; return reply({ job: state.job, cancellation_fee: state.cancellationFee }); }
  if (url.pathname.endsWith('/status') && req.method === 'PUT') {
    state.job = { ...state.job, ...data, version: state.job.version + 1 };
    if (state.loseStatus) { state.loseStatus = false; return reply({ error: 'Simulated lost status response. Retry the saved update.' }, 503); }
    return reply({ job: state.job });
  }
  if (url.pathname === '/api/drivers/jobs/draft-job' || url.pathname === '/api/jobs/draft-job') return reply({ job: state.job });
  if (url.pathname.includes('/notifications')) return reply({ notifications: [], unread_count: 0 });
  if (url.pathname === '/api/auth/me') return reply({ id: 'customer-draft', name: 'Local Customer', email: 'customer@example.test', role: 'customer' });
  if (url.pathname === '/api/booking/abandoned' || url.pathname.includes('/analytics')) return reply({});
  if (url.pathname === '/') { res.writeHead(200, { 'Content-Type': 'text/html' }); return res.end('<h1>Umuve local test fixture</h1>'); }
  reply({ error: `Fixture has no route: ${url.pathname}` }, 404);
}).listen(3108, '127.0.0.1', () => console.log('Local fixture: http://127.0.0.1:3108'));
