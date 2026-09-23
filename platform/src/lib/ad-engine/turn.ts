import { plan, slugOf } from "./rules";
import { adsIn, configFromEnv, createAd, pauseAd, queuedCreatives, usedCreativeIds } from "./meta";

/**
 * One turn of the ad testing engine. Reads the test lane, the scale lane
 * and the queue from Meta, decides (rules.ts), then acts: promote the
 * round's winner into the scale lane, retire the scale lane's weakest to
 * keep the cap, pause the finished round, load the next creatives.
 * `dry` returns the plan without touching anything.
 */
export async function runEngine(dry: boolean) {
  const cfg = configFromEnv();
  if (!cfg.token) return { error: "META_ADS_TOKEN not set" };
  const now = new Date();
  const [testAds, scaleAds, queue, used] = await Promise.all([
    adsIn(cfg, cfg.testAdset, "maximum"),
    adsIn(cfg, cfg.scaleAdset, "last_14d"),
    queuedCreatives(cfg),
    usedCreativeIds(cfg),
  ]);
  const p = plan(testAds, scaleAds, queue, used, now);
  const report = {
    at: now.toISOString(), dry, round: p.round, complete: p.complete,
    test: testAds.filter((a) => a.active).map(brief),
    scale: scaleAds.filter((a) => a.active).map(brief),
    queue: queue.filter((c) => !used.has(c.id)).map((c) => ({ id: c.id, ad: slugOf(c.name), thumb: c.thumb, headline: c.headline, copy: c.copy })),
    winner: p.winner ? brief(p.winner) : null,
    actions: [] as string[],
    notes: p.notes,
  };
  if (!p.complete) return report;

  const act = async (label: string, fn: () => Promise<unknown>) => {
    if (dry) { report.actions.push(`would ${label}`); return; }
    try { await fn(); report.actions.push(label); }
    catch (e) { report.actions.push(`FAILED ${label}: ${e instanceof Error ? e.message : String(e)}`); }
  };
  if (p.promote) {
    const w = p.promote;
    await act(`promote ${slugOf(w.name)} to scale`, () => createAd(cfg, cfg.scaleAdset, `${slugOf(w.name)} [feed]`, w.creativeId));
  }
  for (const r of p.retireScale) await act(`retire ${slugOf(r.name)} from scale (score ${r.score.toFixed(1)})`, () => pauseAd(cfg, r.id));
  for (const t of p.retireTest) await act(`close round ${p.round}: pause ${slugOf(t.name)}`, () => pauseAd(cfg, t.id));
  for (const c of p.load) await act(`load ${slugOf(c.name)} into round ${p.nextRound}`, () => createAd(cfg, cfg.testAdset, `${slugOf(c.name)} [test r${p.nextRound}]`, c.id));
  return report;
}

function brief(a: { id?: string; name: string; impressions: number; clicks: number; lpv: number; calls: number; spend: number; createdAt?: string; thumb?: string; headline?: string; copy?: string }) {
  return { id: a.id, ad: slugOf(a.name), impressions: a.impressions, clicks: a.clicks, visits: a.lpv, calls: a.calls, spend: a.spend,
           since: a.createdAt, thumb: a.thumb || "", headline: a.headline || "", copy: a.copy || "" };
}
