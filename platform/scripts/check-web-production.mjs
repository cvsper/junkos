// Reproducible local verification of an already-built frontend. Owns and closes
// its test servers. Run only with no existing listeners on ports 3107 / 3108.
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
const platform = fileURLToPath(new URL('../', import.meta.url));
const root = resolve(platform, '..');
const cli = process.env.AGENT_BROWSER_CLI;
const python = process.env.UMUVE_TEST_PYTHON;
if (!cli || !python) throw new Error('Set AGENT_BROWSER_CLI and UMUVE_TEST_PYTHON to the installed test tools.');
const env = { ...process.env, NEXT_PUBLIC_API_URL: 'http://127.0.0.1:3108', NEXT_PUBLIC_WS_URL: 'http://127.0.0.1:3108', NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY: 'pk_test_local_fixture', NEXT_TELEMETRY_DISABLED: '1' };
const servers = [];
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const start = (command, args, cwd, extra = {}) => spawn(command, args, { cwd, env: { ...env, ...extra }, stdio: 'inherit' });
const run = (command, args, cwd = root, extra = {}) => new Promise((resolve, reject) => {
  const child = start(command, args, cwd, extra);
  const timeout = setTimeout(() => { child.kill('SIGTERM'); reject(new Error('Local check timed out')); }, 240000);
  child.once('error', error => { clearTimeout(timeout); reject(error); });
  child.once('exit', code => { clearTimeout(timeout); code === 0 ? resolve() : reject(new Error(`Local check exited with ${code}`)); });
});
async function ready(child, url) {
  for (let i = 0; i < 80; i++) {
    if (child.exitCode !== null) throw new Error('Local test server failed to start');
    try { if ((await fetch(url, { signal: AbortSignal.timeout(1000) })).ok) return; } catch {}
    await delay(250);
  }
  throw new Error('Local test server did not become ready');
}
try {
  const frontend = start(process.execPath, [resolve(platform, 'node_modules/next/dist/bin/next'), 'start', '--hostname', '127.0.0.1', '--port', '3107'], platform);
  servers.push(frontend);
  await ready(frontend, 'http://127.0.0.1:3107/driver/login');
  await run(process.execPath, [cli, '--session', 'umuve-web-production', '--allowed-domains', '127.0.0.1,localhost', 'batch', '--bail',
    'open http://127.0.0.1:3107/driver/login', 'snapshot -i', 'screenshot /private/tmp/umuve-web-production-login.png']);
  await run(python, ['-m', 'pytest', 'backend/tests/test_web_browser.py', '-q', '-o', 'addopts=', '--tb=short', '--show-capture=no', '-rP'], root, { UMUVE_WEB_BROWSER: '1' });
  if (!process.argv.includes('--backend-only')) {
    const fixture = start(process.execPath, [resolve(platform, 'scripts/web-continuity-fixture.mjs')], root);
    servers.push(fixture);
    await ready(fixture, 'http://127.0.0.1:3108/');
    for (const stage of ['initial', 'booking', 'driver', 'cancel', 'review', 'earnings', 'presence-delayed']) {
      console.log(`Checking ${stage} against the production build`);
      await run(process.execPath, [resolve(platform, 'scripts/check-web-continuity.mjs'), stage]);
    }
  }
} finally {
  for (const session of ['umuve-web-production', 'umuve-web-checks', 'umuve-web-backend']) {
    await run(process.execPath, [cli, '--session', session, 'close']).catch(() => {});
  }
  for (const child of servers.reverse()) {
    if (child.exitCode === null) child.kill('SIGTERM');
  }
}
