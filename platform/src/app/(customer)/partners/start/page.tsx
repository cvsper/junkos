"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Phone, FileText, Loader2, Sofa, Refrigerator, DoorOpen, BedDouble, HardHat, Package, type LucideIcon } from "lucide-react";
import { resolveApiBaseUrl } from "@/lib/api-base-url";

/**
 * The partner request page: where an interested business's booking link
 * lands. Not the consumer checkout. A property manager tells us what, where
 * and when in under a minute, and a person confirms the price and the slot.
 */

type Offer = {
  prospect_id: string; company: string; first_name: string; city: string | null;
  va_name: string; desk_number: string | null; desk_tel: string | null; rate_card_url: string; already_booked: boolean;
};

const WHATS: { label: string; Icon: LucideIcon }[] = [
  { label: "Furniture", Icon: Sofa },
  { label: "Appliances", Icon: Refrigerator },
  { label: "Unit cleanout", Icon: DoorOpen },
  { label: "Mattresses", Icon: BedDouble },
  { label: "Construction debris", Icon: HardHat },
  { label: "Something else", Icon: Package },
];
const WHENS = ["Today", "Tomorrow", "This week", "Next week"];

function sentence(what: string[], detail: string, address: string, when: string): string {
  const things = [...what.map((w) => w.toLowerCase()), detail.trim()].filter(Boolean);
  if (!things.length && !address.trim() && !when) return "";
  const list = things.length > 2 ? things.slice(0, -1).join(", ") + " and " + things[things.length - 1] : things.join(" and ");
  let out = list ? `Pick up ${list}` : "Pick up";
  if (address.trim()) out += ` from ${address.trim()}`;
  if (when) out += `, ${when.toLowerCase()}`;
  return out + ".";
}

function PartnerStart() {
  const params = useSearchParams();
  const p = params.get("p") || "";
  const s = params.get("s") || "";
  const preview = params.get("preview") === "1";
  const [offer, setOffer] = useState<Offer | null>(null);
  const [bad, setBad] = useState<string | null>(null);
  const [what, setWhat] = useState<string[]>([]);
  const [detail, setDetail] = useState("");
  const [address, setAddress] = useState("");
  const [when, setWhen] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ va: string; desk: string | null } | null>(null);

  useEffect(() => {
    if (!p || !s) { setBad("This link is missing its code. Text the desk and we'll send a fresh one."); return; }
    fetch(`${resolveApiBaseUrl()}/api/partners/offer?p=${encodeURIComponent(p)}&s=${encodeURIComponent(s)}${preview ? "&preview=1" : ""}`)
      .then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.error || "This link isn't valid."); setOffer(j); if (j.first_name) setName(j.first_name); })
      .catch((e) => setBad(e instanceof Error ? e.message : String(e)));
  }, [p, s, preview]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const whatLine = [...what, detail.trim()].filter(Boolean).join(", ");
    if (!whatLine) { setError("Pick what needs to go, or describe it."); return; }
    if (!phone.trim()) { setError("Add the number we should confirm on."); return; }
    setBusy(true);
    try {
      const r = await fetch(`${resolveApiBaseUrl()}/api/partners/request`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ p, s, preview, what: whatLine, address: address.trim(), when, name: name.trim(), phone: phone.trim(), email: email.trim() }),
      });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || "That didn't go through. Call the desk instead.");
      setDone({ va: j.va_name, desk: j.desk_number });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const toggle = (w: string) => setWhat((cur) => (cur.includes(w) ? cur.filter((x) => x !== w) : [...cur, w]));
  const field = "w-full rounded-xl border border-border bg-card px-4 py-3 text-base placeholder:text-muted-foreground/70 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary/50 transition-colors";
  const line = sentence(what, detail, address, when);

  if (bad) {
    return (
      <div className="max-w-xl mx-auto px-4 py-16 text-center">
        <p className="text-foreground">{bad}</p>
        <a href="tel:+15617824350" className="mt-6 inline-flex items-center gap-2 text-primary hover:underline"><Phone className="h-4 w-4" aria-hidden="true" /> (561) 782-4350</a>
      </div>
    );
  }
  if (!offer) {
    return <div className="flex items-center justify-center py-24 text-muted-foreground text-sm"><Loader2 className="h-5 w-5 animate-spin mr-2" aria-hidden="true" /> One moment…</div>;
  }
  if (done) {
    return (
      <div className="max-w-xl mx-auto px-4 py-14 sm:py-20">
        <div className="rounded-3xl bg-[#14213D] text-white p-7 sm:p-10">
          <p className="text-white/60 text-sm">{offer.company}</p>
          <h1 className="font-display text-4xl sm:text-5xl font-bold tracking-tight mt-1">On it.</h1>
          <p className="mt-4 text-white/85 text-lg leading-snug">{line || "Your request is on the desk."}</p>
          <ol className="mt-8 space-y-4 border-l border-white/20 pl-5">
            <li className="relative"><span className="absolute -left-[26px] top-1.5 h-3 w-3 rounded-full bg-primary" aria-hidden="true" /><span className="text-white/90">{done.va} reads it now, during business hours.</span></li>
            <li className="relative"><span className="absolute -left-[26px] top-1.5 h-3 w-3 rounded-full bg-white/30" aria-hidden="true" /><span className="text-white/70">A price and a time come back by text, usually within the hour.</span></li>
            <li className="relative"><span className="absolute -left-[26px] top-1.5 h-3 w-3 rounded-full bg-white/30" aria-hidden="true" /><span className="text-white/70">Nothing is charged until you reply yes.</span></li>
          </ol>
          {done.desk && (
            <a href={`tel:${offer.desk_tel}`} className="mt-8 inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-2.5 text-sm hover:bg-white/15"><Phone className="h-4 w-4" aria-hidden="true" /> Rather talk now? {done.desk}</a>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto px-4 pt-8 pb-40 sm:pt-12">
      {preview && (
        <p className="mb-4 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">Preview. Nothing here counts as an open, and Send does nothing.</p>
      )}

      {/* The work-order header: who this is for, in their name */}
      <div className="rounded-3xl bg-[#14213D] text-white p-6 sm:p-8">
        <p className="text-white/60 text-sm">{offer.company}{offer.city ? `, ${offer.city}` : ""}</p>
        <h1 className="font-display text-[2rem] leading-[1.05] sm:text-5xl font-bold tracking-tight mt-1">
          {offer.first_name ? `${offer.first_name}, put a pickup on the books.` : "Put a pickup on the books."}
        </h1>
        <p className="mt-4 text-white/75 leading-snug">
          Three answers and a number. {offer.va_name} texts back a price and a confirmed slot, usually within the hour. No card, no account.
        </p>
      </div>

      <form onSubmit={submit} className="mt-10 space-y-10">
        <fieldset>
          <legend className="font-display text-2xl font-semibold">What&apos;s going?</legend>
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
            {WHATS.map(({ label, Icon }) => {
              const on = what.includes(label);
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => toggle(label)}
                  aria-pressed={on}
                  className={`flex flex-col items-start gap-3 rounded-2xl border p-4 text-left transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 ${on ? "border-primary bg-primary/[0.06] text-foreground" : "border-border bg-card text-foreground hover:border-foreground/30"}`}
                >
                  <span className={`flex h-9 w-9 items-center justify-center rounded-full ${on ? "bg-primary text-white" : "bg-muted text-foreground/70"}`}>
                    <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
                  </span>
                  <span className="font-medium leading-tight">{label}</span>
                </button>
              );
            })}
          </div>
          <input value={detail} onChange={(e) => setDetail(e.target.value)} placeholder="Anything specific: unit 4B, two sofas, third floor, no elevator" className={`${field} mt-3`} maxLength={300} />
        </fieldset>

        <div>
          <label htmlFor="address" className="font-display text-2xl font-semibold">Where?</label>
          <input id="address" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Property address, and the gate code if there is one" className={`${field} mt-4`} maxLength={300} />
        </div>

        <fieldset>
          <legend className="font-display text-2xl font-semibold">When?</legend>
          <div className="mt-4 flex flex-wrap gap-2.5">
            {WHENS.map((w) => {
              const on = when === w;
              return (
                <button key={w} type="button" onClick={() => setWhen(on ? "" : w)} aria-pressed={on}
                  className={`rounded-full border px-5 py-2.5 text-base transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 ${on ? "border-primary bg-primary text-white" : "border-border bg-card hover:border-foreground/30"}`}>
                  {w}
                </button>
              );
            })}
          </div>
        </fieldset>

        <div>
          <h2 className="font-display text-2xl font-semibold">Who do we confirm with?</h2>
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="name" className="block text-sm text-muted-foreground mb-1.5">Your name</label>
              <input id="name" value={name} onChange={(e) => setName(e.target.value)} className={field} maxLength={120} />
            </div>
            <div>
              <label htmlFor="phone" className="block text-sm text-muted-foreground mb-1.5">Cell</label>
              <input id="phone" type="tel" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="(561) 555-0100" required className={field} />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="email" className="block text-sm text-muted-foreground mb-1.5">Email for the invoice, if you want one</label>
              <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={field} maxLength={254} />
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm pt-2">
          <a href={offer.rate_card_url} className="inline-flex items-center gap-2 text-primary hover:underline"><FileText className="h-4 w-4" aria-hidden="true" /> Your rate card</a>
          {offer.desk_tel && <a href={`tel:${offer.desk_tel}`} className="inline-flex items-center gap-2 text-primary hover:underline"><Phone className="h-4 w-4" aria-hidden="true" /> {offer.desk_number}</a>}
        </div>

        {/* The request, read back in plain words, pinned where the thumb is */}
        <div className="fixed inset-x-0 bottom-0 z-40 px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pointer-events-none">
          <div className="max-w-xl mx-auto pointer-events-auto rounded-2xl bg-[#14213D] text-white shadow-2xl shadow-black/30 p-4 sm:p-5">
            <p className="font-display text-base sm:text-lg leading-snug min-h-[1.5rem]" aria-live="polite">
              {line || <span className="text-white/50">Your request will read back here as you fill it in.</span>}
            </p>
            <div aria-live="polite">{error && <p role="alert" className="mt-2 text-sm text-red-300">{error}</p>}</div>
            <button type="submit" disabled={busy} className="mt-3 w-full rounded-xl bg-primary px-6 py-3.5 text-base font-medium text-white hover:bg-primary/90 disabled:opacity-50 inline-flex items-center justify-center gap-2">
              {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              {busy ? "Sending…" : `Send it to ${offer.va_name}`}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

export default function PartnerStartPage() {
  return <Suspense fallback={null}><PartnerStart /></Suspense>;
}
