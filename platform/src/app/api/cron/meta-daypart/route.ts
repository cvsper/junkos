import { NextResponse } from "next/server";

/**
 * Dayparting for the Meta ad sets, run by Vercel Cron.
 *
 * Meta only lets an ad set carry a schedule when it has a lifetime budget, and
 * ours are daily, so the platform turns them off and on instead. Two crons
 * call this: one in the morning with ?want=active, one in the evening with
 * ?want=paused. The route is idempotent — it reads each ad set's state and
 * only writes when it differs — so a retry or a manual hit is harmless.
 *
 * Evening traffic (7pm–6am ET) brought 26 booking-page visitors and not one
 * got past the address step; every conversion so far came in the morning.
 */
export const dynamic = "force-dynamic";

const AD_SETS = (process.env.META_DAYPART_ADSETS || "120250509718640262,120250550560920262")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

const GRAPH = "https://graph.facebook.com/v21.0";

export async function GET(req: Request) {
  const secret = process.env.CRON_SECRET;
  const auth = req.headers.get("authorization") || "";
  if (!secret || auth !== `Bearer ${secret}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const token = process.env.META_ADS_TOKEN;
  if (!token) {
    return NextResponse.json({ error: "META_ADS_TOKEN not set" }, { status: 500 });
  }
  const want = new URL(req.url).searchParams.get("want");
  if (want !== "active" && want !== "paused") {
    return NextResponse.json({ error: "want must be active or paused" }, { status: 400 });
  }
  const target = want === "active" ? "ACTIVE" : "PAUSED";

  const results: Record<string, string> = {};
  for (const id of AD_SETS) {
    try {
      const cur = await fetch(`${GRAPH}/${id}?fields=name,status&access_token=${token}`, { cache: "no-store" });
      const j = (await cur.json()) as { name?: string; status?: string; error?: { message: string } };
      if (j.error) {
        results[id] = `read failed: ${j.error.message}`;
        continue;
      }
      if (j.status === target) {
        results[id] = `${j.name}: already ${target}`;
        continue;
      }
      const upd = await fetch(`${GRAPH}/${id}`, {
        method: "POST",
        headers: { "content-type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ status: target, access_token: token }),
      });
      const u = (await upd.json()) as { success?: boolean; error?: { message: string } };
      results[id] = u.success ? `${j.name}: ${j.status} -> ${target}` : `write failed: ${u.error?.message}`;
      // Meta allows roughly one write every 30s on this account.
      await new Promise((r) => setTimeout(r, 31_000));
    } catch (e) {
      results[id] = `error: ${e instanceof Error ? e.message : String(e)}`;
    }
  }
  return NextResponse.json({ want: target, at: new Date().toISOString(), results });
}
