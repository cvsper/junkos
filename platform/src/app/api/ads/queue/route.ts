import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/ad-engine/auth";
import { configFromEnv, queueCreative, slugify } from "@/lib/ad-engine/meta";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

/** Add a creative to the queue: multipart with image, headline, copy, optional slug. */
export async function POST(req: Request) {
  const who = await requireAdmin(req);
  if (!who.ok) return NextResponse.json({ error: who.error }, { status: who.status });
  const form = await req.formData();
  const image = form.get("image");
  const headline = String(form.get("headline") || "").trim();
  const copy = String(form.get("copy") || "").trim();
  if (!(image instanceof Blob) || !image.size) return NextResponse.json({ error: "Add the image first." }, { status: 400 });
  if (image.size > 8 * 1024 * 1024) return NextResponse.json({ error: "Keep the image under 8 MB." }, { status: 400 });
  if (!headline) return NextResponse.json({ error: "Give it a headline." }, { status: 400 });
  if (!copy) return NextResponse.json({ error: "Write the one line of copy people see above the image." }, { status: 400 });
  const filename = (image as File).name || "creative.png";
  const slug = slugify(String(form.get("slug") || "") || filename.replace(/\.[a-z0-9]+$/i, "") || headline);
  try {
    const out = await queueCreative(configFromEnv(), image, filename, slug, headline, copy);
    return NextResponse.json({ ok: true, ...out });
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : String(e) }, { status: 502 });
  }
}
