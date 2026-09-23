#!/usr/bin/env node
/**
 * Feed the ad engine.
 *
 *   node scripts/ad-queue.mjs add <image.png> --headline "Time to let go." --copy "Old couch, old boxes…" [--slug time-to-let-go-v3]
 *   node scripts/ad-queue.mjs list          # what's waiting, what's been used
 *   node scripts/ad-queue.mjs plan          # ask the live engine what it would do today (no changes)
 *   node scripts/ad-queue.mjs run           # take today's turn now instead of waiting for the cron
 *
 * `add` uploads the image and creates a creative named "queue|<slug>" with
 * the homepage link (tracked) and the Call Now button. The engine loads it
 * into the next test round. Token: ~/.config/umuve-meta-token.
 */
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { homedir } from "node:os";

const GRAPH = "https://graph.facebook.com/v21.0";
const ACCOUNT = "act_961234110160786";
const PAGE = "999029583304217";
const CALL = "tel:+15617815686";
const token = readFileSync(`${homedir()}/.config/umuve-meta-token`, "utf8").trim();
const cronSecret = () => { try { return readFileSync(`${homedir()}/.config/umuve-vercel-cron-secret`, "utf8").trim(); } catch { return ""; } };

const [cmd, ...rest] = process.argv.slice(2);
const opt = (k) => { const i = rest.indexOf(`--${k}`); return i >= 0 ? rest[i + 1] : undefined; };

async function graph(path, { method = "GET", params = {}, form } = {}) {
  const q = new URLSearchParams({ ...params, access_token: token });
  const url = method === "GET" ? `${GRAPH}/${path}?${q}` : `${GRAPH}/${path}`;
  const init = { method };
  if (method === "POST") { const f = form || new FormData(); for (const [k, v] of Object.entries(params)) f.set(k, v); f.set("access_token", token); init.body = f; }
  const j = await (await fetch(url, init)).json();
  if (j.error) throw new Error(j.error.message);
  return j;
}

if (cmd === "add") {
  const file = rest[0];
  const headline = opt("headline"), copy = opt("copy");
  if (!file || !headline || !copy) { console.error("usage: add <image> --headline \"…\" --copy \"…\" [--slug s]"); process.exit(1); }
  const slug = (opt("slug") || basename(file).replace(/\.[a-z0-9]+$/i, "")).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const form = new FormData();
  form.set("filename", new Blob([readFileSync(file)]), basename(file));
  const up = await graph(`${ACCOUNT}/adimages`, { method: "POST", form });
  const hash = Object.values(up.images)[0].hash;
  const spec = { page_id: PAGE, link_data: {
    link: `https://goumuve.com/?utm_source=meta&utm_campaign=pbc_launch&utm_content=${slug}`,
    message: copy, name: headline, caption: "goumuve.com", description: "Same-day junk removal. Book in 60 seconds.",
    image_hash: hash, call_to_action: { type: "CALL_NOW", value: { link: CALL } } } };
  const cr = await graph(`${ACCOUNT}/adcreatives`, { method: "POST", params: { name: `queue|${slug}`, object_story_spec: JSON.stringify(spec) } });
  console.log(`queued  ${slug}  (creative ${cr.id}). The engine loads it into the next test round.`);
} else if (cmd === "list") {
  const [cr, ads] = await Promise.all([
    graph(`${ACCOUNT}/adcreatives`, { params: { fields: "id,name", limit: "200" } }),
    graph(`${ACCOUNT}/ads`, { params: { fields: "name,effective_status,adset_id,creative{id}", limit: "500" } }),
  ]);
  // Same rule as the engine: a creative is spoken for when a live ad uses it
  // or it has been through the test lane; a paused, never-tested ad's creative still waits.
  const TEST = "120250612710800262";
  const spoken = new Map();
  for (const a of ads.data) if (a.effective_status === "ACTIVE" || a.adset_id === TEST) spoken.set(a.creative?.id, a);
  const queued = cr.data.filter((c) => c.name.startsWith("queue|")).reverse();
  if (!queued.length) console.log("queue is empty");
  for (const c of queued) {
    const a = spoken.get(c.id);
    const state = !a ? "waiting " : a.effective_status === "ACTIVE" ? (a.adset_id === TEST ? "testing " : "live    ") : "tested  ";
    console.log(`${state} ${c.name.slice(6)}${a ? `  → ${a.name}` : ""}`);
  }
} else if (cmd === "plan" || cmd === "run") {
  const s = cronSecret();
  if (!s) { console.error("no ~/.config/umuve-vercel-cron-secret"); process.exit(1); }
  const r = await fetch(`https://app.goumuve.com/api/cron/ad-engine${cmd === "plan" ? "?dry=1" : ""}`, { headers: { Authorization: `Bearer ${s}` } });
  const j = await r.json();
  if (j.queue) j.queue = j.queue.map((q) => (typeof q === "string" ? q : q.ad));
  for (const lane of ["test", "scale"]) if (j[lane]) j[lane] = j[lane].map(({ thumb, copy, headline, ...rest }) => rest);
  console.log(JSON.stringify(j, null, 2));
} else {
  console.log("commands: add | list | plan | run");
}
