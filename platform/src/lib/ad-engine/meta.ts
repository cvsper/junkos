/**
 * The thin Meta Marketing API layer for the ad engine. Reads are cheap;
 * writes are spaced 31s apart because this account allows about one a
 * minute-and-a-half before it starts refusing.
 */
import type { AdStats, QueuedCreative } from "./rules";

const GRAPH = "https://graph.facebook.com/v21.0";
const WRITE_GAP_MS = 31_000;

export interface MetaConfig {
  token: string;
  account: string;      // act_...
  testAdset: string;
  scaleAdset: string;
  page: string;
  homepage: string;     // where every ad lands
  callNumber: string;   // tel:+1...
}

export function configFromEnv(): MetaConfig {
  return {
    token: process.env.META_ADS_TOKEN || "",
    account: process.env.META_AD_ACCOUNT_ID || "act_961234110160786",
    testAdset: process.env.META_ENGINE_TEST_ADSET || "120250612710800262",
    scaleAdset: process.env.META_ENGINE_SCALE_ADSET || "120250509718640262",
    page: process.env.META_PAGE_ID || "999029583304217",
    homepage: process.env.META_ENGINE_LANDING || "https://goumuve.com/",
    callNumber: process.env.META_ENGINE_CALL || "tel:+15617815686",
  };
}

type Json = Record<string, unknown>;

async function get(cfg: MetaConfig, path: string, params: Record<string, string>): Promise<Json> {
  const q = new URLSearchParams({ ...params, access_token: cfg.token });
  const r = await fetch(`${GRAPH}/${path}?${q}`, { cache: "no-store" });
  const j = (await r.json()) as Json;
  if (j.error) throw new Error(`Meta GET ${path}: ${(j.error as Json).message}`);
  return j;
}

let lastWrite = 0;
async function post(cfg: MetaConfig, path: string, params: Record<string, string>): Promise<Json> {
  const wait = lastWrite + WRITE_GAP_MS - Date.now();
  if (wait > 0) await new Promise((res) => setTimeout(res, wait));
  const body = new URLSearchParams({ ...params, access_token: cfg.token });
  const r = await fetch(`${GRAPH}/${path}`, { method: "POST", body });
  lastWrite = Date.now();
  const j = (await r.json()) as Json;
  if (j.error) throw new Error(`Meta POST ${path}: ${(j.error as Json).message}`);
  return j;
}

function actionCount(actions: unknown, ...types: string[]): number {
  if (!Array.isArray(actions)) return 0;
  let best = 0;
  for (const t of types) {
    const a = actions.find((x) => (x as Json).action_type === t) as Json | undefined;
    if (a) best = Math.max(best, parseInt(String(a.value), 10) || 0);
  }
  return best;
}

/** Every ad in an ad set with its numbers over `preset` (e.g. maximum, last_14d). */
export async function adsIn(cfg: MetaConfig, adsetId: string, preset: string): Promise<AdStats[]> {
  const j = await get(cfg, `${adsetId}/ads`, {
    fields: `name,effective_status,created_time,creative{id},insights.date_preset(${preset}){impressions,inline_link_clicks,spend,actions}`,
    limit: "50",
  });
  return ((j.data as Json[]) || []).map((a) => {
    const ins = (((a.insights as Json | undefined)?.data as Json[] | undefined) || [])[0] || {};
    return {
      id: String(a.id),
      name: String(a.name),
      creativeId: String((a.creative as Json)?.id || ""),
      createdAt: String(a.created_time),
      active: a.effective_status === "ACTIVE",
      impressions: parseInt(String(ins.impressions || 0), 10),
      clicks: parseInt(String(ins.inline_link_clicks || 0), 10),
      spend: parseFloat(String(ins.spend || 0)),
      lpv: actionCount(ins.actions, "landing_page_view"),
      calls: actionCount(ins.actions, "click_to_call_call_confirm", "click_to_call_native_call_placed"),
    };
  });
}

/** Creatives waiting their turn: named "queue|<slug>", oldest first. */
export async function queuedCreatives(cfg: MetaConfig): Promise<QueuedCreative[]> {
  const j = await get(cfg, `${cfg.account}/adcreatives`, { fields: "id,name", limit: "200" });
  return ((j.data as Json[]) || [])
    .map((c) => ({ id: String(c.id), name: String(c.name) }))
    .filter((c) => c.name.startsWith("queue|"))
    .reverse();
}

/** Creative ids that are spoken for: used by any live ad, or ever tested in
 *  the test lane. A creative behind a paused, never-tested ad can still be
 *  queued for a fair round. */
export async function usedCreativeIds(cfg: MetaConfig): Promise<Set<string>> {
  const j = await get(cfg, `${cfg.account}/ads`, { fields: "creative{id},effective_status,adset_id", limit: "500" });
  const used = new Set<string>();
  for (const a of (j.data as Json[]) || []) {
    const id = String((a.creative as Json)?.id || "");
    if (a.effective_status === "ACTIVE" || String(a.adset_id) === cfg.testAdset) used.add(id);
  }
  return used;
}

export async function createAd(cfg: MetaConfig, adsetId: string, name: string, creativeId: string): Promise<string> {
  const j = await post(cfg, `${cfg.account}/ads`, {
    name, adset_id: adsetId, status: "ACTIVE", creative: JSON.stringify({ creative_id: creativeId }),
  });
  return String(j.id);
}

export async function pauseAd(cfg: MetaConfig, adId: string): Promise<void> {
  await post(cfg, adId, { status: "PAUSED" });
}
