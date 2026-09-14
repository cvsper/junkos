// Run against web-continuity-fixture.mjs and the local Next.js preview only.
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { writeFileSync } from 'node:fs';
const cli = process.env.AGENT_BROWSER_CLI;
if (!cli) throw new Error('Set AGENT_BROWSER_CLI to the installed agent-browser.js path.');
const base = 'http://127.0.0.1:3107';
const env = { ...process.env, AGENT_BROWSER_INIT_SCRIPTS: fileURLToPath(new URL('./web-continuity-browser-init.js', import.meta.url)) };
const run = (...args) => execFileSync(process.execPath, [cli, '--session', 'umuve-web-checks', '--allowed-domains', '127.0.0.1,localhost', ...args], { env, encoding: 'utf8', timeout: 60000 });
const evaluate = code => run('eval', code);
const wait = text => run('wait', '--fn', `document.body.innerText.includes(${JSON.stringify(text)})`);
const check = (condition, label) => { evaluate(`if (!(${condition})) throw new Error(${JSON.stringify(label)}); true`); console.log('PASS ' + label); };
const control = async data => fetch('http://127.0.0.1:3108/__control', { method: 'POST', body: JSON.stringify(data) });
const state = async () => (await fetch('http://127.0.0.1:3108/__state')).json();
const png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=';
async function seed(step = 4) {
  evaluate(`(async () => {
    const r = indexedDB.open('umuve-browser-work',1);
    r.onupgradeneeded = () => r.result.createObjectStore('drafts');
    const db = await new Promise((resolve,reject)=>{r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)});
    const photo = new File([Uint8Array.from(atob('${png}'), c=>c.charCodeAt(0))], 'pickup.png', {type:'image/png'});
    const date = document.querySelector('input[type=date]')?.min || new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York'}).format(new Date());
    const data = {step:${step}, address:{street:'123 Test Ave',city:'Boca Raton',state:'FL',zip:'33432',lat:26.3683,lng:-80.1289}, photos:[photo],items:[{id:'sofa',name:'Sofa',category:'sofa',quantity:1,size:'medium'}],scheduledDate:date,scheduledTimeSlot:'10-12',notes:'Keep the lamp',dispositionPreference:'best',estimatedPrice:200,priceVersion:'local-price',quoteId:null,quoteBinding:false,quoteToken:null,promoCode:'',promoDiscount:0,promoApplied:false,leadSource:'',contact:{name:'Local Customer',email:'customer@example.test',phone:'(561) 555-0100'},checkout:null};
    await new Promise((resolve,reject)=>{const tx=db.transaction('drafts','readwrite');tx.objectStore('drafts').put({version:1,updatedAt:Date.now(),data},'booking:guest');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error)});db.close();
  })()`);
  run('reload');
}
const stage = process.argv[2] || 'initial';
if (stage === 'initial') {
  console.log(run('open', base + '/book'));
  wait('Where');
  console.log(run('snapshot', '-i'));
  check('!document.querySelector("[data-nextjs-dialog]") && document.body.innerText.length > 100', 'Booking renders without an error overlay');
  console.log(run('screenshot', '/private/tmp/umuve-web-initial.png'));
  console.log('Page errors: ' + run('errors'));
}
if (stage === 'booking') {
  evaluate("localStorage.removeItem('umuve-auth')");
  run('open', base+'/book');
  await seed();
  wait('Available');
  check('document.querySelectorAll("button[aria-pressed][disabled]").length === 3', 'Unavailable windows are disabled');
  check('document.querySelector("button[aria-pressed=true]")?.innerText.includes("10 AM")', 'Saved schedule restored');
  run('reload'); wait('Available');
  check('document.querySelector("button[aria-pressed=true]") !== null', 'Selected schedule survives reload');
  evaluate(`document.querySelector('button[aria-pressed=true]').click()`);
  console.log(run('screenshot', '/private/tmp/umuve-web-schedule.png'));
  await seed(6); run('wait', '[aria-label="Local test card"]');
  console.log(run('snapshot', '-i'));
  check('document.querySelector("input[type=email]")?.value === "customer@example.test"', 'Contact restored at checkout');
  await control({ loseBooking: true, failConfirm: true, booking: null, requests: [] });
  run('fill', '[aria-label="Local test card"]', '4242');
  run('find', 'role', 'button', 'click', '--name', 'Pay $200.00');
  wait('Simulated lost booking response');
  run('reload'); run('wait', '[aria-label="Local test card"]');
  run('fill', '[aria-label="Local test card"]', '4242');
  run('find', 'role', 'button', 'click', '--name', 'Pay $200.00');
  wait('Simulated lost payment response');
  const s = await state();
  const creates = s.requests.filter(r => r.path === '/api/booking');
  assert.equal(creates.length, 2); assert.equal(creates[0].data.booking_request_id, creates[1].data.booking_request_id);
  assert.deepEqual(creates[0].data, creates[1].data);
  console.log('PASS Lost booking response retries the original saved request');
  assert(s.requests.some(r => r.path === '/api/booking/saved-booking/photos' && r.filesField));
  console.log('PASS Restored booking photo uses authenticated files upload contract');
  run('reload'); wait('Check saved payment');
  await control({ failConfirm: false });
  run('find', 'role', 'button', 'click', '--name', 'Check saved payment');
  wait('Booking Confirmed!');
  const after = await state();
  assert.equal(after.requests.filter(r => r.path === '/api/payments/create-intent-simple').length, 1);
  console.log('PASS Payment recovery confirms saved intent without another card submission');
  console.log(run('screenshot', '/private/tmp/umuve-web-checkout.png'));
}
if (stage === 'driver') {
  evaluate(`(async()=>{const r=indexedDB.open('umuve-browser-work',1);const db=await new Promise(resolve=>r.onsuccess=()=>resolve(r.result));await new Promise(resolve=>{const tx=db.transaction('drafts','readwrite');tx.objectStore('drafts').delete('proof:driver-draft:draft-job');tx.oncomplete=resolve});db.close()})()`);
  evaluate(`localStorage.setItem('umuve-auth',JSON.stringify({version:0,state:{token:'local-driver',user:{id:'driver-draft',name:'Local Driver',email:'driver@example.test',role:'driver'}}}))`);
  const previous = await state();
  await control({ job: { ...previous.job, status: 'arrived', before_photos: [], after_photos: [], version: 1 }, failUpload: true, loseStatus: true, requests: [] });
  console.log(run('open', base + '/driver/jobs/draft-job/active'));
  wait('Before Photos');
  writeFileSync('/private/tmp/umuve-proof-fixture.png', Buffer.from(png,'base64'));
  run('upload', 'input[type=file]', '/private/tmp/umuve-proof-fixture.png');
  wait('Retry saved before photos');
  run('reload'); wait('Retry saved before photos');
  check('Array.from(document.images).some(img=>img.alt==="Preview 1")', 'Failed Pro photo remains available after reload');
  await control({ failUpload: false });
  run('find','role','button','click','--name','Retry saved before photos');
  run('wait', 'img[alt="Before Photos 1"]');
  run('reload'); wait('Before Photos');
  check('Array.from(document.images).some(img=>img.alt==="Before Photos 1")', 'Uploaded Pro proof restores without uploading again');
  run('find','role','button','click','--name','Start Job');
  wait('Simulated lost status response');
  run('reload'); wait('Retry saved update');
  run('find','role','button','click','--name','Retry saved update');
  wait('Saved update confirmed');
  const retried = await state();
  assert.equal(retried.requests.filter(r=>r.path.endsWith('/status') && r.method==='PUT').length,1);
  assert.equal(retried.requests.filter(r=>r.path==='/api/upload/photos').length,2);
  assert.equal(retried.job.before_photos.length,1);
  console.log('PASS Lost Pro status response reconciles without sending the transition twice');
  run('upload', 'input[type=file]', '/private/tmp/umuve-proof-fixture.png'); wait('After photos saved');
  run('find','role','button','click','--name','Complete Job','--exact');
  wait('Yes, Complete Job');
  run('find','role','button','click','--name','Yes, Complete Job');
  wait('Job Complete!');
  check('document.body.innerText.includes("144.00") && document.body.innerText.includes("Finish payout setup")', 'Pro completion shows driver pay and payout readiness');
  const completed = await state(); assert.equal(completed.job.after_photos.length,1);
  console.log(run('screenshot','/private/tmp/umuve-web-pro.png'));
}
if (stage === 'driver' || stage === 'presence') {
  evaluate(`localStorage.setItem('umuve-auth',JSON.stringify({version:0,state:{token:'local-driver',user:{id:'driver-draft',name:'Local Driver',email:'driver@example.test',role:'driver'}}}))`);
  await control({ is_online: false });
  run('set','geo','26.3683','-80.1289');
  run('open',base+'/driver'); wait("You're Offline");
  // Headless geolocation stand-in: verify browser callbacks/API flow, not device GPS.
  evaluate(`navigator.geolocation.getCurrentPosition = success => queueMicrotask(()=>success({coords:{latitude:26.3683,longitude:-80.1289,accuracy:5}}))`);
  run('find','role','button','click','--name',"You're Offline Tap to go online",'--exact');
  wait("You're Online");
  run('find','role','link','click','--name','Jobs','--exact');
  evaluate('window.dispatchEvent(new Event("online"))');
  run('wait','--fn',"document.body.innerText.includes('Keep this browser open')");
  assert((await state()).requests.some(r=>r.path==='/api/drivers/location' && r.data.lat===26.3683));
  console.log('PASS Online status and location sharing persist across Pro navigation');
}
if (stage === 'cancel') {
  evaluate(`localStorage.setItem('umuve-auth',JSON.stringify({version:0,state:{token:'local-customer',user:{id:'customer-draft',name:'Local Customer',email:'customer@example.test',role:'customer'}}}))`);
  const previous = await state();
  await control({ job: { ...previous.job, status: 'assigned' }, cancellationFee: 0, requests: [] });
  run('open', base+'/jobs/draft-job'); wait('Cancel Job');
  run('find','role','button','click','--name','Cancel Job','--exact');
  wait('Cancellation fee:');
  check('document.body.innerText.includes("Refund: $200.00")', 'Cancellation preview shows the server refund');
  await control({ cancellationFee: 25 });
  run('find','role','button','click','--name','Yes, Cancel Job');
  wait('Refund: $175.00');
  assert.equal((await state()).requests.filter(r=>r.path.endsWith('/cancel')).length,0);
  console.log('PASS Changed cancellation fee is disclosed again before applying');
  run('find','role','button','click','--name','Yes, Cancel Job');
  wait('Cancelled');
  assert.equal((await state()).requests.find(r=>r.path.endsWith('/cancel')).data.confirm,true);
  console.log('PASS Cancellation sends explicit confirmation after review');
  console.log(run('screenshot','/private/tmp/umuve-web-cancellation.png'));
}

if (stage === 'review') {
  evaluate("localStorage.removeItem('umuve-auth')");
  run('open',base+'/book'); await seed(4); wait('Available');
  run('set','viewport','390','844');
  check('document.documentElement.scrollWidth <= innerWidth', 'Booking fits a mobile viewport');
  console.log(run('screenshot','/private/tmp/umuve-web-mobile.png'));
  evaluate(`localStorage.setItem('umuve-auth',JSON.stringify({version:0,state:{token:'local-other',user:{id:'other-customer',name:'Other Customer',email:'other@example.test',role:'customer'}}}))`);
  run('reload'); wait('Where should we pick up?');
  check('!document.body.innerText.includes("Keep the lamp") && !document.querySelector("input[type=date]")', 'Account change does not restore another account or guest draft');
  evaluate("localStorage.removeItem('umuve-auth')");
  run('reload'); wait('Available');
  console.log('PASS Returning to guest restores its own saved draft');
  check('!document.querySelector("[data-nextjs-dialog]")', 'No Next.js error overlay after recovery flows');
  console.log('Page errors: '+run('errors'));
  run('set','viewport','1280','900');
}
if (stage === 'earnings') {
  evaluate(`localStorage.setItem('umuve-auth',JSON.stringify({version:0,state:{token:'local-driver',user:{id:'driver-draft',name:'Local Driver',email:'driver@example.test',role:'driver'}}}))`);
  const previous = await state();
  await control({ job: { ...previous.job, status: 'completed' }, is_online: false });
  run('open',base+'/driver/jobs/draft-job/active'); wait('Job Complete!');
  evaluate('document.querySelector("main").scrollTop=0');
  console.log(run('screenshot','/private/tmp/umuve-web-pro.png'));
  run('network','route','**/api/driver/earnings?*','--body',JSON.stringify({success:true,summary:{total:144,jobs_completed:1,avg_per_job:144,period:'week'},records:[{id:'draft-job',job_id:'draft-job',address:'123 Test Ave',amount:144,tip:10,payout_status:'pending_connect',completed_at:'2026-09-12T14:00:00Z'}],weekly_chart:[{day:'Sat',amount:144}]}));
  run('network','route','**/api/payments/payout/eligibility','--body',JSON.stringify({eligible:false,available_amount:0,currency:'usd'}));
  run('open',base+'/driver/earnings'); wait('Earnings History');
  check('Array.from(document.querySelectorAll("td")).some(cell=>cell.textContent==="Finish payout setup") && document.body.innerText.includes("$144.00")', 'Earnings renders actual payout records and setup status');
  check('!document.querySelector("[data-nextjs-dialog]")', 'Earnings has no error overlay');
  console.log(run('screenshot','/private/tmp/umuve-web-earnings.png'));
  run('network','unroute','**/api/driver/earnings?*');
  run('network','unroute','**/api/payments/payout/eligibility');
}
if (stage === 'inspect') {
  console.log(run('snapshot'));
  console.log(run('errors'));
}

if (stage === 'presence-delayed') {
  run('open', base + '/driver/login');
  evaluate(`localStorage.setItem('umuve-auth',JSON.stringify({version:0,state:{token:'local-driver',user:{id:'driver-draft',name:'Local Driver',email:'driver@example.test',role:'driver'}}}))`);
  await control({ is_online: false, requests: [] });
  run('open', base + '/driver'); wait("You're Offline");
  evaluate('navigator.geolocation.getCurrentPosition = success => { window.__pendingLocation = success; }');
  run('find', 'role', 'button', 'click', '--name', "You're Offline Tap to go online", '--exact');
  wait("You're Online");
  run('wait', '--fn', 'typeof window.__pendingLocation === "function"');
  evaluate(`(async()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});await window.__pendingLocation({coords:{latitude:26.3683,longitude:-80.1289}});window.__pendingLocation=null})()`);
  assert.equal((await state()).requests.filter(r=>r.path==='/api/drivers/location').length,0);
  console.log('PASS A delayed GPS callback does not send location after the tab is hidden');
  evaluate(`Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'))`);
  run('wait', '--fn', 'typeof window.__pendingLocation === "function"');
  evaluate(`(async()=>{Object.defineProperty(navigator,'onLine',{configurable:true,get:()=>false});await window.__pendingLocation({coords:{latitude:26.3683,longitude:-80.1289}});window.__pendingLocation=null})()`);
  assert.equal((await state()).requests.filter(r=>r.path==='/api/drivers/location').length,0);
  console.log('PASS A delayed GPS callback does not send location after the browser disconnects');
  evaluate(`Object.defineProperty(navigator,'onLine',{configurable:true,get:()=>true});window.dispatchEvent(new Event('online'))`);
  run('wait', '--fn', 'typeof window.__pendingLocation === "function"');
  evaluate(`window.__pendingLocation({coords:{latitude:26.3683,longitude:-80.1289}})`);
  assert.equal((await state()).requests.filter(r=>r.path==='/api/drivers/location').length,1);
  console.log('PASS Location resumes after returning online in a visible tab');
  run('reload');
}
