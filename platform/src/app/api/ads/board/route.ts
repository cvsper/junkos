import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/ad-engine/auth";
import { runEngine } from "@/lib/ad-engine/turn";
import { adsetBudgets, configFromEnv } from "@/lib/ad-engine/meta";

export const dynamic = "force-dynamic";

/** The whole board: every lane with its numbers, the budgets, and what
 *  tomorrow's turn would do. Read-only. */
export async function GET(req: Request) {
  const who = await requireAdmin(req);
  if (!who.ok) return NextResponse.json({ error: who.error }, { status: who.status });
  const cfg = configFromEnv();
  const [report, budgets] = await Promise.all([runEngine(true), adsetBudgets(cfg)]);
  return NextResponse.json({ ...report, budgets, lanes: { test: cfg.testAdset, scale: cfg.scaleAdset } });
}
