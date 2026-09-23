import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/ad-engine/auth";
import { runEngine } from "@/lib/ad-engine/turn";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

/** Take today's turn now instead of waiting for the morning. */
export async function POST(req: Request) {
  const who = await requireAdmin(req);
  if (!who.ok) return NextResponse.json({ error: who.error }, { status: who.status });
  return NextResponse.json(await runEngine(false));
}
