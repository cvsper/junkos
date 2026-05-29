# PBC Hauler Outreach — Call Sheet
> Generated 2026-05-27 after the Weston booking miss (#1f96fc1a).
> Supply gate is THE blocker. Goal: land 1 truck → unlock coverage → ad spend gets safe.

---

## 🎯 Top 3 to call (warmest first)

These three have **real first names** + **local 561 phone numbers** = highest personal-conversion. Call in this order:

### 1. Ryan — Junk Force South FL
- **📞 (561) 913-2023**
- **📧 ryan@junkforcesouthfl.com**
- **City:** West Palm Beach
- **Hook:** "Hey Ryan, this is Shamar with umuve — followup on the email from last week. Got 60 seconds?"

### 2. Milena — JunkHustle
- **📞 (561) 830-8800**
- **📧 milenabbrandao@gmail.com** (also: junkhustlefl@gmail.com)
- **City:** Palm Beach
- **Hook:** "Hey, is this Milena from JunkHustle? This is Shamar with umuve, got a sec?"

### 3. Owner @ Brooks Moving & Hauling
- **📞 (561) 891-0456**
- **📧 brooksmovingandhauling@gmail.com**
- **City:** Jupiter
- **Hook:** "Hey, this is Shamar with umuve — looking for the owner of Brooks Moving & Hauling?"

**Backup #4 if first 3 don't land:** PBG Junk Removal — (561) 264-7383, Palm Beach Gardens.

---

## 🎙 The 20-second pitch (memorize this)

> "Hey, this is Shamar with umuve. We bring customer demand for junk removal — customer books and pays through us, we route the job to you, you haul it. **No subscription, no upfront cost.** We're onboarding a small number of haulers in **[their city]** before we switch on local ads here. Want one of those spots? 5-min setup."

**If they engage:** "Great — I just need your service area, what trucks you run, and your insurance. I'll text you a setup link."

**If voicemail:** "Hey [name], Shamar with umuve. We bring paying junk removal jobs to local haulers in [their city] — no subscription, no upfront cost. We're picking a small number to onboard before our local ads turn on. If you want a spot, text 'in' to [your cell] or hit me back. Thanks."

---

## ❌ Skipping in this round (and why)

| Skip | Reason |
|------|--------|
| Palm Beach County Junk Removal (Brian) — (610) 883-2577 | 610 is a Pennsylvania area code. Non-local phone is sketchy. |
| Dump Squad (Samson) — (954) 833-0220 | 954 is Broward, not PBC. Saving for Broward phase. |
| All Out Junk Removal — (866) 889-5865 | Toll-free → IVR hell, low conversion. Email only. |
| Junk-IT — (844) 747-3377 | Toll-free → same. Email only. |
| USA Trash Removal — (305) 900-4067 | 305 is Miami-Dade. Out of PBC for round 1. |

→ **9 callable, 13 in the email blast.**

---

## ✉️ After the calls: fire Sequence-D email blast

Sequence-D pitches the **same jobs-first hook** in writing to the whole list. Phone-first then email maximizes touch.

```bash
cd /Users/sevs/Projects/junkos/marketing/outreach

# 1. Safe preview — prints what would send, sends nothing:
python send_sequence_d.py --csv pbc-targets.csv --email 2

# 2. One real test to yourself (se7nz7@gmail.com only):
RESEND_API_KEY=re_xxx python send_sequence_d.py --csv pbc-targets.csv --email 2 --test

# 3. Live send to all eligible rows (throttled 2s, logged, resumable):
RESEND_API_KEY=re_xxx python send_sequence_d.py --csv pbc-targets.csv --email 2 --live

# 4. ~4 days later: breakup email to non-repliers
RESEND_API_KEY=re_xxx python send_sequence_d.py --csv pbc-targets.csv --email 3 --live
```

✅ **No GPU/Ollama dependency** — runs fine with zino down.
⚠️ **Set `replied=yes`** in `pbc-targets.csv` for anyone who responds to a call/email so the breakup skips them.

---

## ✅ Definition of "done" for this round
- [ ] Called all 3 top targets (left voicemail if no answer)
- [ ] Sent Sequence-D email 2 to all 13 rows
- [ ] One hauler committed (replies "in" or verbal yes)
- [ ] First test booking routed through them — proves the loop end-to-end

When 1 hauler lands, **deploy the alert+coverage fixes** (Render env + redeploy) and the airtight system is live.
