import { NextResponse } from "next/server";
import { runEngine } from "@/lib/ad-engine/turn";

/** Manual entry to the ad engine: ?dry=1 shows today's plan, without it
 *  the turn runs now. The scheduled turn rides on the morning daypart cron
 *  (Hobby allows two crons). */
export const dynamic = "force-dynamic";
export const maxDuration = 300;

export async function GET(req: Request) {
  const secret = process.env.CRON_SECRET;
  if (!secret || (req.headers.get("authorization") || "") !== `Bearer ${secret}`) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const dry = new URL(req.url).searchParams.get("dry") === "1";
  return NextResponse.json(await runEngine(dry));
}
