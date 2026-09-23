"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Phone, Play, UploadCloud, X } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";

/**
 * Ad Lab — the ad testing engine, from the browser.
 *
 * Three lanes read left to right the way a creative travels: Queue, Testing,
 * Live. The image is the card; the number that matters most (calls) is the
 * one you can read from across the room. The empty slot at the top of the
 * queue is where a new image goes.
 */

type Row = { id?: string; ad: string; impressions: number; clicks: number; visits: number; calls: number; spend: number; since?: string; thumb: string; headline: string; copy: string };
type Queued = { id: string; ad: string; thumb: string; headline: string; copy: string };
type Board = {
  at: string; round: number; complete: boolean;
  test: Row[]; scale: Row[]; queue: Queued[];
  winner: Row | null; actions: string[]; notes: string[];
  budgets: Record<string, { name: string; dailyBudget: number; active: boolean }>;
  lanes: { test: string; scale: string };
  error?: string;
};

function authHeaders(): HeadersInit {
  const token = useAuthStore.getState().token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function daysSince(iso?: string): string {
  if (!iso) return "";
  const d = (Date.now() - new Date(iso).getTime()) / 86_400_000;
  return d < 1 ? "today" : `day ${Math.floor(d) + 1}`;
}

export default function AdLabPage() {
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState<string[] | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/ads/board", { headers: authHeaders(), cache: "no-store" });
      const j = (await r.json()) as Board;
      if (!r.ok || j.error) throw new Error(j.error || `Couldn't load the board (${r.status}).`);
      setBoard(j);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const runNow = async () => {
    setRunning(true);
    setLastRun(null);
    try {
      const r = await fetch("/api/ads/run", { method: "POST", headers: authHeaders() });
      const j = (await r.json()) as Board;
      if (!r.ok || j.error) throw new Error(j.error || "The turn didn't run.");
      setLastRun(j.actions.length ? j.actions : ["Nothing to do yet: " + (j.notes[0] || "the round is still running.")]);
      await load();
    } catch (e) {
      setLastRun([e instanceof Error ? e.message : String(e)]);
    } finally {
      setRunning(false);
    }
  };

  const testBudget = board?.budgets[board.lanes.test]?.dailyBudget;
  const scaleBudget = board?.budgets[board.lanes.scale]?.dailyBudget;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight">Ad Lab</h1>
          <p className="text-muted-foreground mt-1 max-w-xl">
            Drop an image in the queue. Three at a time get four days in front of real people. The ones that make the phone ring move to Live.
          </p>
        </div>
        <button
          type="button"
          onClick={runNow}
          disabled={running || loading}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {running ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Play className="h-4 w-4" aria-hidden="true" />}
          {running ? "Taking the turn…" : "Take today's turn now"}
        </button>
      </div>

      {error && (
        <div role="alert" className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {/* Tomorrow's turn */}
      {board && (
        <section aria-label="Next turn" className="mb-8 rounded-xl border border-border bg-card p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="font-display text-lg font-semibold">
              {board.complete ? `Round ${board.round} is done. Next turn:` : `Round ${board.round} is running`}
            </h2>
            <span className="text-xs text-muted-foreground">runs every morning at 6am with the ads</span>
          </div>
          <ul className="mt-3 space-y-1.5 text-sm">
            {(board.complete ? board.actions : board.notes).map((line, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-primary" aria-hidden="true" />
                <span>{line.replace(/^would /, "")}</span>
              </li>
            ))}
            {board.complete && board.notes.map((n, i) => (
              <li key={"n" + i} className="flex gap-2 text-muted-foreground">
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-border" aria-hidden="true" />
                <span>{n}</span>
              </li>
            ))}
          </ul>
          {lastRun && (
            <div className="mt-4 rounded-lg bg-muted/60 px-4 py-3 text-sm">
              <p className="font-medium mb-1">Just now</p>
              <ul className="space-y-1">{lastRun.map((l, i) => <li key={i}>{l}</li>)}</ul>
            </div>
          )}
        </section>
      )}

      {/* The board */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <Lane title="Queue" sub={board ? `${board.queue.length} waiting` : ""} tone="queue">
          <AddCreative onAdded={load} />
          {board?.queue.map((q) => (
            <Card key={q.id} thumb={q.thumb} headline={q.headline || q.ad} copy={q.copy} footer="waiting for a slot" />
          ))}
          {board && !board.queue.length && (
            <p className="text-sm text-muted-foreground px-1">Nothing waiting. The next round can&apos;t start until something is here.</p>
          )}
        </Lane>

        <Lane title="Testing" sub={board ? `$${testBudget ?? 0}/day · round ${board.round}` : ""} tone="test">
          {board?.test.map((a) => <Card key={a.id} thumb={a.thumb} headline={a.headline || a.ad} copy={a.copy} stats={a} footer={daysSince(a.since) + " of 4"} />)}
          {board && !board.test.length && <p className="text-sm text-muted-foreground px-1">Empty. The next turn loads three from the queue.</p>}
        </Lane>

        <Lane title="Live" sub={board ? `$${scaleBudget ?? 0}/day · ${board.scale.length} of 5` : ""} tone="live">
          {board?.scale
            .slice()
            .sort((a, b) => b.calls - a.calls || b.visits - a.visits || b.clicks - a.clicks)
            .map((a) => <Card key={a.id} thumb={a.thumb} headline={a.headline || a.ad} copy={a.copy} stats={a} footer="last 14 days" />)}
        </Lane>
      </div>

      {loading && !board && (
        <div className="flex items-center justify-center py-24 text-muted-foreground text-sm">
          <Loader2 className="h-5 w-5 animate-spin mr-2" aria-hidden="true" /> Reading the account…
        </div>
      )}
    </div>
  );
}

function Lane({ title, sub, tone, children }: { title: string; sub: string; tone: "queue" | "test" | "live"; children: React.ReactNode }) {
  const rule = tone === "live" ? "bg-green-600" : tone === "test" ? "bg-amber-500" : "bg-muted-foreground/40";
  return (
    <section aria-label={title} className="min-w-0">
      <div className={`h-1 rounded-full ${rule} mb-3`} aria-hidden="true" />
      <div className="flex items-baseline justify-between mb-3 px-1">
        <h2 className="font-display text-xl font-semibold">{title}</h2>
        <span className="text-xs text-muted-foreground">{sub}</span>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Card({ thumb, headline, copy, stats, footer }: { thumb: string; headline: string; copy: string; stats?: Row; footer: string }) {
  return (
    <article className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="flex gap-3 p-3">
        <div className="h-24 w-[4.8rem] shrink-0 overflow-hidden rounded-md bg-muted">
          {thumb ? <img src={thumb} alt="" className="h-full w-full object-cover" /> : null}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="font-display font-semibold leading-tight truncate">{headline}</h3>
          <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{copy}</p>
          {stats && (
            <div className="mt-2 flex flex-wrap items-end gap-x-4 gap-y-1.5">
              <div className={stats.calls ? "text-primary" : "text-foreground"}>
                <div className="flex items-center gap-1">
                  <span className="font-display text-2xl font-bold leading-none">{stats.calls}</span>
                  <Phone className="h-3.5 w-3.5" aria-hidden="true" />
                </div>
                <div className="text-[11px] text-muted-foreground">calls</div>
              </div>
              <Stat n={stats.visits} label="visits" />
              <Stat n={stats.clicks} label="clicks" />
              <Stat n={stats.impressions} label="seen" />
              <Stat n={`$${stats.spend.toFixed(0)}`} label="spent" />
            </div>
          )}
        </div>
      </div>
      <div className="border-t border-border px-3 py-1.5 text-[11px] text-muted-foreground">{footer}</div>
    </article>
  );
}

function Stat({ n, label }: { n: number | string; label: string }) {
  return (
    <div>
      <div className="font-display text-base font-semibold leading-none">{typeof n === "number" ? n.toLocaleString() : n}</div>
      <div className="text-[11px] text-muted-foreground">{label}</div>
    </div>
  );
}

function AddCreative({ onAdded }: { onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string>("");
  const [headline, setHeadline] = useState("");
  const [copy, setCopy] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const pick = (f: File | undefined) => {
    if (!f) return;
    if (!f.type.startsWith("image/")) { setMsg("That isn't an image."); return; }
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setOpen(true);
    setMsg(null);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { setMsg("Add the image first."); return; }
    setBusy(true);
    setMsg(null);
    const fd = new FormData();
    fd.set("image", file);
    fd.set("headline", headline);
    fd.set("copy", copy);
    try {
      const r = await fetch("/api/ads/queue", { method: "POST", headers: authHeaders(), body: fd });
      const j = (await r.json()) as { ok?: boolean; slug?: string; error?: string };
      if (!r.ok || !j.ok) throw new Error(j.error || "Couldn't queue it.");
      setMsg(`Queued as ${j.slug}. It goes into the next round.`);
      setFile(null); setPreview(""); setHeadline(""); setCopy(""); setOpen(false);
      onAdded();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className={`rounded-xl border-2 border-dashed ${drag ? "border-primary bg-primary/5" : "border-border bg-card/60"} transition-colors`}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]); }}
    >
      {!open ? (
        <button type="button" onClick={() => input.current?.click()} className="w-full p-5 text-left">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
              <UploadCloud className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <div className="font-display font-semibold">Add a creative</div>
              <div className="text-xs text-muted-foreground">Drop a 4:5 image here, or tap to choose one</div>
            </div>
          </div>
          {msg && <p className="mt-3 text-xs text-muted-foreground">{msg}</p>}
        </button>
      ) : (
        <form onSubmit={submit} className="p-4 space-y-3">
          <div className="flex items-start gap-3">
            <div className="h-24 w-[4.8rem] shrink-0 overflow-hidden rounded-md bg-muted">
              {preview && <img src={preview} alt="" className="h-full w-full object-cover" />}
            </div>
            <div className="min-w-0 flex-1 space-y-2">
              <input
                value={headline}
                onChange={(e) => setHeadline(e.target.value)}
                placeholder="Headline, like “From $119. Today.”"
                required
                maxLength={60}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <textarea
                value={copy}
                onChange={(e) => setCopy(e.target.value)}
                placeholder="The line above the image. One sentence, plain words, what they get."
                required
                rows={3}
                maxLength={280}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>
          {msg && <p className="text-xs text-red-700">{msg}</p>}
          <div className="flex items-center gap-2">
            <button type="submit" disabled={busy} className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
              {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              {busy ? "Uploading…" : "Add to queue"}
            </button>
            <button type="button" onClick={() => { setOpen(false); setFile(null); setPreview(""); setMsg(null); }} className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" aria-hidden="true" /> Cancel
            </button>
          </div>
        </form>
      )}
      <input ref={input} type="file" accept="image/*" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} />
    </div>
  );
}
