import { test } from "node:test";
import assert from "node:assert/strict";
import { plan, score, roundComplete, retireFromScale, pickFromQueue, slugOf } from "../src/lib/ad-engine/rules.ts";
import type { AdStats } from "../src/lib/ad-engine/rules.ts";

const now = new Date("2026-09-30T13:00:00Z");
const daysAgo = (d: number) => new Date(now.getTime() - d * 86_400_000).toISOString();
const ad = (o: Partial<AdStats> & { name: string }): AdStats => ({
  id: "ad_" + o.name, creativeId: "cr_" + o.name, createdAt: daysAgo(5), active: true,
  impressions: 400, clicks: 4, spend: 4, lpv: 2, calls: 0, ...o,
});

test("calls outrank visits outrank clicks", () => {
  const a = score(ad({ name: "a", calls: 1, clicks: 2, lpv: 0 }));
  const b = score(ad({ name: "b", calls: 0, clicks: 40, lpv: 30 }));
  assert.ok(a.score > b.score);
});

test("a round is not judged early or on nothing", () => {
  assert.equal(roundComplete([ad({ name: "young", createdAt: daysAgo(2) })], now), false);
  assert.equal(roundComplete([ad({ name: "starved", createdAt: daysAgo(5), impressions: 40 })], now), false);
  assert.equal(roundComplete([ad({ name: "starved-too-long", createdAt: daysAgo(9), impressions: 40 })], now), true);
  assert.equal(roundComplete([ad({ name: "done" })], now), true);
});

test("a round with no ad over the floor promotes nobody and loads the next three", () => {
  const p = plan(
    [ad({ name: "x [test r1]", clicks: 2, lpv: 1 }), ad({ name: "y [test r1]", clicks: 1, lpv: 0 })],
    [ad({ name: "s1 [feed]" })],
    [{ id: "c1", name: "queue|one" }, { id: "c2", name: "queue|two" }, { id: "c3", name: "queue|three" }, { id: "c4", name: "queue|four" }],
    new Set(), now,
  );
  assert.equal(p.promote, null);
  assert.equal(p.retireTest.length, 2);
  assert.deepEqual(p.load.map((c) => c.name), ["queue|one", "queue|two", "queue|three"]);
  assert.equal(p.nextRound, 2);
  assert.ok(p.notes.some((n) => n.includes("nobody cleared the floor")));
});

test("the winner goes to scale and the weakest old scale ad makes room", () => {
  const scale = [
    ad({ name: "s1 [feed]", createdAt: daysAgo(20), calls: 2 }),
    ad({ name: "s2 [feed]", createdAt: daysAgo(20), clicks: 1, lpv: 0 }),   // weakest
    ad({ name: "s3 [feed]", createdAt: daysAgo(20), lpv: 9 }),
    ad({ name: "s4 [feed]", createdAt: daysAgo(1), clicks: 0, lpv: 0 }),    // too young to retire
    ad({ name: "s5 [feed]", createdAt: daysAgo(20), lpv: 4 }),
  ];
  const p = plan([ad({ name: "w [test r2]", calls: 1 }), ad({ name: "l [test r2]", clicks: 1 })], scale, [], new Set(), now);
  assert.equal(p.promote?.name, "w [test r2]");
  assert.deepEqual(p.retireScale.map((a) => a.name), ["s2 [feed]"]);
  assert.equal(p.load.length, 0);
  assert.ok(p.notes.some((n) => n.includes("queue is empty")));
});

test("a winner already in scale is not duplicated", () => {
  const p = plan([ad({ name: "w [test r3]", calls: 1, creativeId: "cr_same" })], [ad({ name: "w [feed]", creativeId: "cr_same" })], [], new Set(), now);
  assert.equal(p.winner?.name, "w [test r3]");
  assert.equal(p.promote, null);
});

test("queue skips creatives an ad already uses, oldest first", () => {
  const q = [{ id: "c1", name: "queue|a" }, { id: "c2", name: "queue|b" }, { id: "c3", name: "not-queued" }, { id: "c4", name: "queue|d" }];
  assert.deepEqual(pickFromQueue(q, new Set(["c1"]), 3).map((c) => c.id), ["c2", "c4"]);
});

test("nothing retires while the lane has room", () => {
  assert.deepEqual(retireFromScale([ad({ name: "a" }), ad({ name: "b" })], 1, now), []);
  assert.equal(slugOf("room-to-breathe [test r1]"), "room-to-breathe");
  assert.equal(slugOf("queue|price-on-image"), "price-on-image");
  assert.equal(slugOf("gone-square [feed] (home)"), "gone-square");
});

test("an over-full scale lane shrinks two at a time", () => {
  const scale = Array.from({ length: 9 }, (_, i) => ad({ name: `s${i} [feed]`, createdAt: daysAgo(20), clicks: i }));
  assert.equal(retireFromScale(scale, 1, now).length, 2);
});
