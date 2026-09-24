"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Phone, FileText, Loader2 } from "lucide-react";
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

const WHATS = ["Furniture", "Appliances", "Unit cleanout", "Mattresses", "Construction debris", "Something else"];
const WHENS = ["Today", "Tomorrow", "This week", "Next week"];

function PartnerStart() {
  const params = useSearchParams();
  const p = params.get("p") || "";
  const s = params.get("s") || "";
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
    fetch(`${resolveApiBaseUrl()}/api/partners/offer?p=${encodeURIComponent(p)}&s=${encodeURIComponent(s)}`)
      .then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.error || "This link isn't valid."); setOffer(j); if (j.first_name) setName(j.first_name); })
      .catch((e) => setBad(e instanceof Error ? e.message : String(e)));
  }, [p, s]);

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
        body: JSON.stringify({ p, s, what: whatLine, address: address.trim(), when, name: name.trim(), phone: phone.trim(), email: email.trim() }),
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
  const field = "w-full rounded-lg border border-border bg-card px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent";
  const chip = (on: boolean) => `rounded-full border px-3.5 py-2 text-sm transition-colors ${on ? "border-primary bg-primary text-primary-foreground" : "border-border bg-card hover:border-primary/40"}`;

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
      <div className="max-w-xl mx-auto px-4 py-16">
        <h1 className="font-display text-3xl font-bold tracking-tight">Got it.</h1>
        <p className="mt-3 text-foreground">{done.va} will text you a price and a time within the hour, during business hours. Nothing is charged until you say yes.</p>
        {done.desk && (
          <p className="mt-6 text-sm text-muted-foreground">Rather talk now? <a href={`tel:${offer.desk_tel}`} className="text-primary hover:underline">{done.desk}</a></p>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto px-4 py-10 sm:py-14">
      <p className="text-sm text-muted-foreground">{offer.company}{offer.city ? `, ${offer.city}` : ""}</p>
      <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mt-1">
        {offer.first_name ? `${offer.first_name}, put a pickup on the books.` : "Put a pickup on the books."}
      </h1>
      <p className="mt-3 text-muted-foreground">
        Tell {offer.va_name} what, where and when. You get a price and a confirmed slot back by text, usually within the hour. No card, no account.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-7">
        <fieldset>
          <legend className="text-sm font-medium mb-2">What needs to go?</legend>
          <div className="flex flex-wrap gap-2">
            {WHATS.map((w) => (
              <button key={w} type="button" onClick={() => toggle(w)} aria-pressed={what.includes(w)} className={chip(what.includes(w))}>{w}</button>
            ))}
          </div>
          <input value={detail} onChange={(e) => setDetail(e.target.value)} placeholder="Anything specific: unit 4B, two sofas, a fridge on the third floor" className={`${field} mt-3`} maxLength={300} />
        </fieldset>

        <div>
          <label htmlFor="address" className="block text-sm font-medium mb-1.5">Where</label>
          <input id="address" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Property address, gate code if there is one" className={field} maxLength={300} />
        </div>

        <fieldset>
          <legend className="text-sm font-medium mb-2">When</legend>
          <div className="flex flex-wrap gap-2">
            {WHENS.map((w) => (
              <button key={w} type="button" onClick={() => setWhen(when === w ? "" : w)} aria-pressed={when === w} className={chip(when === w)}>{w}</button>
            ))}
          </div>
        </fieldset>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label htmlFor="name" className="block text-sm font-medium mb-1.5">Your name</label>
            <input id="name" value={name} onChange={(e) => setName(e.target.value)} className={field} maxLength={120} />
          </div>
          <div>
            <label htmlFor="phone" className="block text-sm font-medium mb-1.5">Cell to confirm on</label>
            <input id="phone" type="tel" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="(561) 555-0100" required className={field} />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="email" className="block text-sm font-medium mb-1.5">Email for the invoice <span className="text-muted-foreground font-normal">(optional)</span></label>
            <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={field} maxLength={254} />
          </div>
        </div>

        <div aria-live="polite">{error && <p role="alert" className="text-sm text-red-700">{error}</p>}</div>

        <button type="submit" disabled={busy} className="w-full sm:w-auto rounded-lg bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 inline-flex items-center justify-center gap-2">
          {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {busy ? "Sending…" : "Send it to " + offer.va_name}
        </button>
      </form>

      <div className="mt-10 flex flex-wrap gap-x-6 gap-y-2 text-sm">
        <a href={offer.rate_card_url} className="inline-flex items-center gap-2 text-primary hover:underline"><FileText className="h-4 w-4" aria-hidden="true" /> Your rate card</a>
        {offer.desk_tel && <a href={`tel:${offer.desk_tel}`} className="inline-flex items-center gap-2 text-primary hover:underline"><Phone className="h-4 w-4" aria-hidden="true" /> {offer.desk_number}</a>}
      </div>
    </div>
  );
}

export default function PartnerStartPage() {
  return <Suspense fallback={null}><PartnerStart /></Suspense>;
}
