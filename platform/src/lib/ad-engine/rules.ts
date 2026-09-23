/**
 * Ad testing engine — the rules, with no I/O.
 *
 * Meta picks a winner inside an ad set within hours on almost no data and
 * starves the rest (9 of 12 creatives got under 70 impressions in a week).
 * So testing and scaling are separate lanes:
 *
 *   queue  -> a creative on the ad account named "queue|<slug>", not yet used by any ad
 *   test   -> one ad set, at most ROUND_SIZE ads at a time, each judged after ROUND_DAYS
 *   scale  -> the proven ad set, at most SCALE_CAP live ads; a promoted ad pushes out the weakest
 *
 * The scoreboard, in order: phone calls, then landing-page views per 1,000
 * impressions, then click-through rate. Clicks alone lie.
 */

export const ROUND_SIZE = 3;
export const ROUND_DAYS = 4;
export const ROUND_MAX_DAYS = 8;      // judged even if starved of impressions
export const MIN_IMPRESSIONS = 300;   // below this an ad is not judged, unless the round timed out
export const SCALE_CAP = 5;
export const SCALE_MIN_AGE_DAYS = 4;  // a scale ad younger than this is never retired

export interface AdStats {
  id: string;
  name: string;
  creativeId: string;
  createdAt: string;          // ISO
  active: boolean;
  impressions: number;
  clicks: number;
  spend: number;
  lpv: number;
  calls: number;
}

export interface Scored extends AdStats {
  ctrPct: number;
  lpvPer1k: number;
  score: number;
}

export function score(ad: AdStats): Scored {
  const ctrPct = ad.impressions ? (100 * ad.clicks) / ad.impressions : 0;
  const lpvPer1k = ad.impressions ? (1000 * ad.lpv) / ad.impressions : 0;
  return { ...ad, ctrPct, lpvPer1k, score: ad.calls * 1000 + lpvPer1k * 10 + ctrPct };
}

export function ageDays(iso: string, now: Date): number {
  return (now.getTime() - new Date(iso).getTime()) / 86_400_000;
}

/** A round is over when every live test ad has had its ROUND_DAYS and its
 *  impressions, or has sat there ROUND_MAX_DAYS whatever happened. */
export function roundComplete(testAds: AdStats[], now: Date): boolean {
  const live = testAds.filter((a) => a.active);
  if (!live.length) return true;
  return live.every((a) => {
    const age = ageDays(a.createdAt, now);
    return age >= ROUND_MAX_DAYS || (age >= ROUND_DAYS && a.impressions >= MIN_IMPRESSIONS);
  });
}

/** The floor an ad must clear to be promoted: it made the phone ring, or it
 *  drew real visits at a healthy click rate. Otherwise nobody wins the round. */
export function clearsFloor(s: Scored): boolean {
  return s.calls >= 1 || (s.ctrPct >= 1.0 && s.lpv >= 3);
}

export function pickWinner(testAds: AdStats[]): Scored | null {
  const live = testAds.filter((a) => a.active).map(score).sort((a, b) => b.score - a.score);
  if (!live.length) return null;
  return clearsFloor(live[0]) ? live[0] : null;
}

/** Which live scale ads to retire so the lane stays at SCALE_CAP after
 *  `incoming` new ones arrive. Youngest ads are protected; the lowest score
 *  goes first. */
export function retireFromScale(scaleAds: AdStats[], incoming: number, now: Date): Scored[] {
  const live = scaleAds.filter((a) => a.active);
  const excess = live.length + incoming - SCALE_CAP;
  if (excess <= 0) return [];
  const eligible = live
    .filter((a) => ageDays(a.createdAt, now) >= SCALE_MIN_AGE_DAYS)
    .map(score)
    .sort((a, b) => a.score - b.score);
  return eligible.slice(0, excess);
}

/** Round numbers live in the ad names: "<slug> [test r3]". */
export function roundOf(name: string): number {
  const m = /\[test r(\d+)\]/.exec(name);
  return m ? parseInt(m[1], 10) : 0;
}

export function nextRound(testAds: AdStats[]): number {
  return testAds.reduce((n, a) => Math.max(n, roundOf(a.name)), 0) + 1;
}

export function slugOf(name: string): string {
  return name.replace(/\s*\[[^\]]*\]\s*$/, "").replace(/^queue\|/, "").trim();
}

export interface QueuedCreative {
  id: string;
  name: string;   // "queue|<slug>"
}

/** The next creatives to test: queued, oldest first, never one an ad already uses. */
export function pickFromQueue(queue: QueuedCreative[], usedCreativeIds: Set<string>, n: number): QueuedCreative[] {
  return queue.filter((c) => c.name.startsWith("queue|") && !usedCreativeIds.has(c.id)).slice(0, n);
}

export interface Plan {
  round: number;
  complete: boolean;
  winner: Scored | null;
  promote: Scored | null;        // winner to copy into the scale lane
  retireTest: AdStats[];         // test ads to pause when the round closes
  retireScale: Scored[];         // scale ads that make room
  load: QueuedCreative[];        // next creatives into the test lane
  nextRound: number;
  notes: string[];
}

export function plan(testAds: AdStats[], scaleAds: AdStats[], queue: QueuedCreative[], usedCreativeIds: Set<string>, now: Date): Plan {
  const round = testAds.reduce((n, a) => Math.max(n, roundOf(a.name)), 0);
  const live = testAds.filter((a) => a.active);
  const complete = roundComplete(testAds, now);
  const notes: string[] = [];
  if (!complete) {
    const waiting = live.map((a) => `${slugOf(a.name)}: ${a.impressions} impr, ${ageDays(a.createdAt, now).toFixed(1)}d`);
    notes.push(`round ${round} still running (${waiting.join("; ")})`);
    return { round, complete, winner: null, promote: null, retireTest: [], retireScale: [], load: [], nextRound: round, notes };
  }
  const winner = pickWinner(testAds);
  if (live.length && !winner) notes.push(`round ${round}: nobody cleared the floor (a call, or CTR ≥ 1% with 3+ visits)`);
  const alreadyInScale = winner ? scaleAds.some((a) => a.active && a.creativeId === winner.creativeId) : false;
  const promote = winner && !alreadyInScale ? winner : null;
  if (winner && alreadyInScale) notes.push(`${slugOf(winner.name)} is already live in the scale lane`);
  const retireScale = promote ? retireFromScale(scaleAds, 1, now) : [];
  const load = pickFromQueue(queue, usedCreativeIds, ROUND_SIZE);
  if (!load.length) notes.push("queue is empty — add creatives with scripts/ad-queue.mjs");
  return {
    round, complete, winner, promote, retireTest: live, retireScale, load,
    nextRound: load.length ? round + 1 : round, notes,
  };
}
