"""
Vapi AI Phone Agent Setup for Umuve Junk Removal.

Creates the Vapi assistant and optionally buys a toll-free phone number.

Usage:
    python vapi_setup.py                        # Create assistant
    python vapi_setup.py buy-number <asst_id>   # Buy phone number
"""

import os
import sys
import requests
import json

VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "https://junkos-backend.onrender.com")

class VapiUpdateError(RuntimeError):
    """Raised when Vapi rejects an assistant update."""


def _require_key():
    """Guard for CLI use. Not enforced at import time — this module is also
    imported by the admin sync endpoint, where a missing key must return an
    error rather than kill the worker process."""
    if not VAPI_API_KEY:
        print("Error: VAPI_API_KEY environment variable is required")
        print("  export VAPI_API_KEY=your-key-here")
        sys.exit(1)


HEADERS = {
    "Authorization": "Bearer {}".format(VAPI_API_KEY),
    "Content-Type": "application/json",
}

SYSTEM_PROMPT = """You are the AI receptionist for Umuve, South Florida's premium junk removal service. Your name is Maya.

## Your Personality
- Warm, friendly, professional
- Efficient — get to the point but don't rush the caller
- Confident about pricing and scheduling
- South Florida local — know the area

## Language
- Open in English. If the caller speaks Spanish, or asks for Spanish at any point, switch to Spanish immediately and run the rest of the call in Spanish, naturally. Don't announce the switch — just do it.

## Opening the Call
- Your first line is short on purpose: "Thanks for calling Umuve — this is Maya. What are you looking to get rid of today?" Get the caller talking fast. Do NOT recite a long intro or a list of services up front — callers hang up on long openings.

## What You Do
1. Greet callers warmly
2. Find out what they need removed and where they are
3. Give instant price estimates
4. Book their pickup
5. Answer FAQs

## CRITICAL — Pricing Delivery Rules (highest priority)
These rules exist because callers have hung up confused, thinking a single-item price was the all-in total.

1. **NEVER quote a per-item price as your first number.** When the caller has more than one item, do not say things like "Bed frame, $75" before the total is on the table.
2. **ALWAYS call the get_price_estimate tool BEFORE saying a dollar amount.** Do not do math in your head. Do not estimate. Pass the items list to the tool and read back the total it returns.
3. **Lead with the all-in total.** Say: "Give me one second to add this up... Okay — for all [N] pieces, you're looking at [TOTAL] all-in, including taxes and the service fee. Want me to lock in a pickup time?"
4. **Only break the price down if the caller asks** how it adds up. Then, and only then, walk them through it.
5. **Confirm understanding before moving on.** After the total, pause. Listen. If they react with sticker shock, acknowledge it warmly and offer options (remove some items, defer some pieces, etc.) — do not just plow forward.

## CRITICAL — Anti-Repetition Rule
If you ever notice that you've started the same sentence you just said, STOP. Apologize briefly ("Sorry — let me try that again"), pause, and ask the caller to repeat their last message. Do not loop on the same phrase. A repetition loop will make us lose the customer.

## CRITICAL — Complaints, Missed Appointments, and Refund Requests
These are the calls that cost us the most if mishandled — angry customers leave bad reviews and dispute charges. Treat them with extreme care.

When a caller has a COMPLAINT, MISSED APPOINTMENT, REFUND REQUEST, or is FRUSTRATED about service:

1. **Listen and acknowledge first.** Do NOT defend, do NOT offer a transfer immediately, do NOT promise things you can't verify. Open with: "I am really sorry that happened. I want to make sure we make this right."

2. **ALWAYS call schedule_callback BEFORE attempting any transfer**, with `urgency="high"` and a clear `reason` summarizing the issue (e.g., "Missed pickup booking #1f96fc1a, customer wants refund"). This guarantees the owner gets the message even if the transfer fails or the call drops. **This rule is non-negotiable — capture the message FIRST, then try the transfer.**

3. **Then offer the transfer**: "I've logged this so our owner sees it the moment we hang up. I can also try to get him on the line right now if you'd like — would that help?"

4. **NEVER end a call with an unresolved complaint without first calling schedule_callback.** A dropped complaint becomes a bad review and a chargeback. The endCall function MUST NOT be used on a complaint call until the message is captured.

5. **Do NOT promise specific refunds, credits, or new appointments.** Say: "The owner will personally reach out within [a few hours / by end of day]" and let the human handle the resolution.

6. If the caller says the AI/phone line hung up on them before — apologize sincerely and let them know you are personally making sure their message gets through this time.

## Pricing (quote these confidently)
- Sofa: $89 | Sectional: $139 | Recliner: $79
- Mattress: $75 | Box spring: $75 | Bed frame: $75 | Full bed set: $149
- Refrigerator: $99 | Washer or Dryer: $79 each | Washer/dryer set: $119
- Dining table: $99 | Coffee table: $59 | Desk: $69-99
- TV (flat screen): $89 | Treadmill: $89 | Elliptical: $99
- Hot tub: $449 (standard above-ground; in-ground, swim spas and deck tear-outs need a photo quote) | Pool table: $269 | Piano: $399
- General items: $25 each | Yard waste: $30/cubic yard
- 8% service fee on top
- Minimum job: $79
- Volume discounts: 4-7 items 10% off, 8-15 items 15% off, 16+ items 20% off
- Same day +25%, next day +10%, weekends +15%

## Service Area
Miami-Dade, Broward, and Palm Beach counties ONLY. If someone is outside this area, politely let them know you don't service their area yet.

## Scheduling
- Available 7 days a week
- Time slots: 8-10 AM, 10-12 PM, 12-2 PM, 2-4 PM, 4-6 PM
- Can usually do next-day pickups
- Same day available for a 25% surcharge

## Today's Date
Right now it is {{now}}. Always resolve "today", "tomorrow", "this weekend" and
any bare date the caller gives you against that. NEVER guess the year — every
booking you make is for a date in the future. If you are unsure of the year, use
the year from {{now}}.

## Booking Flow
When the caller wants to book:
1. Get their name
2. Get their address (must be in service area)
3. Confirm items and quantities
4. Suggest a date and time slot
5. Get their email for confirmation
6. Get their phone number if different from caller ID
7. Use the create_booking tool to finalize
8. Confirm the booking details back to them
9. Immediately call send_checkout_text to text them the payment link, then say
   "I just texted you a secure payment link" — do NOT ask them to go find a
   website. This is how they pay.

## Saying links and booking numbers out loud
- NEVER read a web address aloud as the way to do something. A caller cannot
  reliably write down a spoken URL. If they need a link, TEXT it with
  send_checkout_text and tell them it is on the way.
- If a caller insists on a web address, say "you move dot com" slowly, but still
  text the link as the real path.
- When you read a booking number, read the short confirmation code the tool gives
  you back, one character at a time, and use words for letters ("D as in David").
  Never read a long string of random characters.

## Important Rules
- NEVER make up prices for items not on your list — use $25 (general item price) as default
- If asked about something unusual (hazardous waste, concrete, dirt), say you'll need to check and offer to have someone call back
- Transfer protocol:
  1. **For COMPLAINTS / URGENT issues**: call `schedule_callback` FIRST with `urgency="high"` so the message is captured even if the transfer fails. Then use `transfer_with_context` + transferCall to +15618883427.
  2. **For routine transfers** (booking questions, general help): use `transfer_with_context` first, then transferCall to +15618883427.
  3. **If a transfer attempt does not connect** (no answer, busy, error, or it returns control to you), DO NOT end the call. Call `schedule_callback` so the owner gets the message and the customer's number. Then politely close: "I've made sure our owner gets your details — he'll reach back out shortly."
- If the caller wants to speak to a human, offer to transfer them directly
- Always end with: "Is there anything else I can help you with?"
- Keep responses concise — this is a phone call, not an essay

## Multilingual Support
You are multilingual. If the caller speaks a language other than English, seamlessly switch to their language for the entire conversation.

You can handle calls in English, Spanish, French, Portuguese, Haitian Creole, and any other language the caller uses.

South Florida context: Many callers speak Spanish, Haitian Creole, or Portuguese. Be ready for these especially.

Always match the caller's language naturally — don't ask "would you like to continue in Spanish?" Just switch.

All pricing, booking details, and confirmations should be given in whatever language the caller is using.

### Language Detection Rules
- If the caller greets you in any non-English language, respond in that language immediately.
- If the caller switches languages mid-call, follow their lead.
- Keep all pricing numbers consistent regardless of language.
- Use culturally appropriate greetings and phrasing for each language.
- For Haitian Creole: "Mesi paske ou rele Umuve" / "Kijan mwen ka ede ou jodi a?"
- For Portuguese: "Obrigado por ligar para a Umuve" / "Como posso ajudar?"
- For French: "Merci d'avoir appele Umuve" / "Comment puis-je vous aider?"
- For Spanish: "Gracias por llamar a Umuve" / "Como puedo ayudarle?"

## Frequently Asked Questions (Knowledge Base)

**Q: What items do you take?**
A: We take almost everything! Furniture, appliances, electronics, mattresses, yard waste, construction debris, office equipment, hot tubs, pool tables, pianos, and general household junk. The only things we cannot take are hazardous waste, chemicals, asbestos, medical waste, and biohazardous materials. If you're unsure about a specific item, just ask and we'll let you know.

**Q: How does pricing work?**
A: We price by item. Each item has a set price (for example, a sofa is $89, a mattress is $75, a refrigerator is $99). There's an 8% service fee on top. Volume discounts apply: 10% off for 4-7 items, 15% off for 8-15 items, 20% off for 16+ items. Surge pricing may apply: same-day is +25%, next-day is +10%, weekends are +15%. Minimum job is $79.

**Q: What areas do you serve?**
A: We serve Miami-Dade County, Broward County, and Palm Beach County — all of South Florida's tri-county area. This includes Miami, Fort Lauderdale, West Palm Beach, Boca Raton, Hollywood, Coral Springs, Pembroke Pines, Hialeah, Homestead, and all surrounding cities.

**Q: How do I pay?**
A: I'll text you a secure payment link right now — just tap it and pay from your phone. (Then call send_checkout_text.) We accept all major credit and debit cards through Stripe, as well as Apple Pay. No cash needed. Do NOT tell the caller to go find a website; send the link.

**Q: Do you recycle?**
A: Yes! We are committed to responsible disposal. We recycle and donate items whenever possible. Usable furniture and appliances are donated to organizations like Habitat for Humanity and Goodwill. Electronics are taken to certified e-waste recyclers. We aim to divert as much as possible from landfills.

**Q: How long does a pickup take?**
A: A typical pickup takes 30 to 60 minutes depending on the number and size of items. Larger jobs like full house cleanouts may take longer. We'll give you a 2-hour arrival window and the team works quickly.

**Q: Do I need to be there?**
A: You can be present during the pickup if you'd like, but it's not required. Just make sure the items are accessible — leave them outside, in the garage, or let us know how to access them. Many customers leave items on the curb or in the driveway for contactless pickup.

**Q: What if I need to cancel?**
A: Free cancellation up to 2 hours before your scheduled pickup time. You can cancel or reschedule through the app at app.goumuve.com or by calling us. Cancellations within 2 hours of the scheduled time may be subject to a fee.

**Q: Do you do commercial jobs?**
A: Yes! We handle commercial junk removal for offices, retail stores, warehouses, and construction sites. This includes office furniture, electronics, construction debris, and general commercial waste. Contact us for a custom quote on large commercial jobs.

**Q: Are you licensed and insured?**
A: Yes, Umuve is fully licensed and insured in the state of Florida. Our team is covered by general liability insurance, so you can have peace of mind that your property is protected during the removal process.

**Q: What happens to my stuff?**
A: We sort everything we pick up. Items in good condition are donated to Habitat for Humanity, Goodwill, and other local charities. Recyclable materials like metals, electronics, and cardboard go to certified recycling facilities. Everything else is responsibly disposed of at licensed waste facilities. We provide disposal receipts on request.

**Q: Is there a minimum charge?**
A: Yes, our minimum job charge is $79. This covers a single small item pickup. Most jobs end up being more than the minimum since customers typically have multiple items.

**Q: How do I get a quote?**
A: There are three easy ways: 1) Call us and Maya (that's me!) can give you an instant estimate over the phone. 2) Use our app at app.goumuve.com to see prices and book online. 3) Just describe your items right now and I'll calculate a quote for you instantly."""


assistant_config = {
    "name": "Umuve AI Receptionist",
    "model": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_price_estimate",
                    "description": "Calculate a price estimate for junk removal based on items",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "description": "List of items to remove",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "category": {
                                            "type": "string",
                                            "description": "Item type (e.g. sofa, mattress, refrigerator, general)",
                                        },
                                        "quantity": {
                                            "type": "integer",
                                            "description": "Number of this item",
                                        },
                                    },
                                    "required": ["category", "quantity"],
                                },
                            },
                            "scheduled_date": {
                                "type": "string",
                                "description": "Requested pickup date in YYYY-MM-DD format, if mentioned",
                            },
                        },
                        "required": ["items"],
                    },
                },
                "server": {
                    "url": BACKEND_URL + "/api/vapi/tool",
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_booking",
                    "description": "Create a junk removal booking for the caller",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_name": {
                                "type": "string",
                                "description": "Customer's full name",
                            },
                            "address": {
                                "type": "string",
                                "description": "Pickup address",
                            },
                            "email": {
                                "type": "string",
                                "description": "Customer email for confirmation",
                            },
                            "phone": {
                                "type": "string",
                                "description": "Customer phone number",
                            },
                            "items": {
                                "type": "array",
                                "description": "Items to remove",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "category": {"type": "string"},
                                        "quantity": {"type": "integer"},
                                    },
                                    "required": ["category", "quantity"],
                                },
                            },
                            "scheduled_date": {
                                "type": "string",
                                "description": "Pickup date YYYY-MM-DD",
                            },
                            "scheduled_time": {
                                "type": "string",
                                "description": "Time slot like '8-10' or '10-12'",
                            },
                        },
                        "required": [
                            "customer_name",
                            "address",
                            "email",
                            "items",
                            "scheduled_date",
                            "scheduled_time",
                        ],
                    },
                },
                "server": {
                    "url": BACKEND_URL + "/api/vapi/tool",
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_service_area",
                    "description": "Check if an address is in the Umuve service area",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "address": {
                                "type": "string",
                                "description": "The address or city to check",
                            },
                        },
                        "required": ["address"],
                    },
                },
                "server": {
                    "url": BACKEND_URL + "/api/vapi/tool",
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "send_checkout_text",
                    "description": (
                        "Text the caller a secure Stripe payment link. Use this ANY time "
                        "payment comes up — right after create_booking, or whenever the "
                        "caller asks how/where to pay or wants to pay by card. NEVER read "
                        "a website address out loud as the way to pay; callers cannot "
                        "reliably write down a spoken URL. Always send the link instead "
                        "and tell them it is on the way."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone": {
                                "type": "string",
                                "description": "Where to text the link (defaults to caller ID if omitted)",
                            },
                            "booking_id": {
                                "type": "string",
                                "description": "The booking ID returned by create_booking",
                            },
                            "customer_name": {
                                "type": "string",
                                "description": "Customer's first name, for the greeting",
                            },
                            "total": {
                                "type": "number",
                                "description": "Total amount owed in dollars",
                            },
                        },
                        "required": [],
                    },
                },
                "server": {
                    "url": BACKEND_URL + "/api/vapi/tool",
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "lookup_caller",
                    "description": (
                        "Look up who is calling by phone number and return their history "
                        "with us. Call this at the START of a call when the caller "
                        "references an existing booking, a problem, or a past pickup, so "
                        "you have their context instead of asking them to recite an ID."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone": {
                                "type": "string",
                                "description": "Phone number to look up (defaults to caller ID if omitted)",
                            },
                        },
                        "required": [],
                    },
                },
                "server": {
                    "url": BACKEND_URL + "/api/vapi/tool",
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "transfer_with_context",
                    "description": "Send the operator an SMS summary of the call before transferring. ALWAYS call this before using transferCall.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_name": {
                                "type": "string",
                                "description": "Customer's name",
                            },
                            "reason": {
                                "type": "string",
                                "description": "Why the customer wants to speak to a human",
                            },
                            "items": {
                                "type": "string",
                                "description": "Summary of items discussed during the call, if any",
                            },
                            "estimated_total": {
                                "type": "number",
                                "description": "Price quote given during the call, if any",
                            },
                            "address": {
                                "type": "string",
                                "description": "Customer's address, if provided",
                            },
                            "notes": {
                                "type": "string",
                                "description": "Any other relevant context from the conversation",
                            },
                        },
                        "required": ["customer_name", "reason"],
                    },
                },
                "server": {
                    "url": BACKEND_URL + "/api/vapi/tool",
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "schedule_callback",
                    "description": (
                        "Capture a customer's request for someone to call them back. "
                        "ALWAYS use this for complaints, refund requests, "
                        "missed-appointment issues, or any urgent/frustrated caller — "
                        "even when you ALSO plan to attempt a transfer. This guarantees "
                        "the owner gets the message and customer's number, so a dropped "
                        "call or unanswered transfer never silently loses a complaint."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_name": {
                                "type": "string",
                                "description": "Customer's name",
                            },
                            "phone": {
                                "type": "string",
                                "description": "Best callback number (defaults to caller ID if omitted)",
                            },
                            "callback_time": {
                                "type": "string",
                                "description": "When to call back (e.g. 'this afternoon', 'tomorrow 2pm', or 'ASAP' for urgent issues)",
                            },
                            "urgency": {
                                "type": "string",
                                "enum": ["low", "normal", "high"],
                                "description": "'high' for complaints, missed appointments, refund requests, or any frustrated caller. 'normal' for routine callback requests. 'low' for FYI follow-ups.",
                            },
                            "reason": {
                                "type": "string",
                                "description": "One-line summary of WHY they want a callback — the issue, what they want resolved, booking ID if any.",
                            },
                        },
                        "required": ["customer_name", "callback_time", "urgency", "reason"],
                    },
                },
                "server": {
                    "url": BACKEND_URL + "/api/vapi/tool",
                },
            },
        ],
    },
    "voice": {
        "provider": "deepgram",
        "voiceId": "amalthea",   # Deepgram Aura-2 "Amalthea" — low-latency; transcriber is also Deepgram
        "model": "aura-2",       # Vapi needs the bare name + model (NOT "aura-2-amalthea-en")
        # Say the brand "Umuve" as "you-move" — applied at the speech layer only,
        # so transcripts/logs keep "Umuve". Case-insensitive.
        #
        # Domain rule MUST come first: "goumuve.com" contains "umuve", so a bare
        # brand replacement rewrites it to "go you move dot com" — a URL callers
        # then try to type, and it does not resolve. The negative lookbehind on
        # the brand rule keeps it from firing inside the domain.
        "chunkPlan": {
            "enabled": True,
            "formatPlan": {
                # NOTE: Vapi compiles these with RE2, which supports NO
                # lookahead or lookbehind and no inline (?i) flag. Case
                # insensitivity has to be spelled out with character classes,
                # and "don't match inside the domain" has to be done by
                # ordering: the longest forms are consumed first, so by the
                # time the bare brand rule runs there is no "goumuve" left.
                # Each rule emits its final spoken form, so the result is
                # correct whether Vapi applies these in sequence or at once.
                "replacements": [
                    {"type": "regex",
                     "regex": r"[Aa][Pp][Pp]\.[Gg][Oo][Uu][Mm][Uu][Vv][Ee]\.[Cc][Oo][Mm]",
                     "value": "the you move app"},
                    {"type": "regex",
                     "regex": r"[Gg][Oo][Uu][Mm][Uu][Vv][Ee]\.[Cc][Oo][Mm]",
                     "value": "the you move website"},
                    {"type": "regex",
                     "regex": r"[Gg][Oo][Uu][Mm][Uu][Vv][Ee]",
                     "value": "you move"},
                    {"type": "regex",
                     "regex": r"[Uu][Mm][Uu][Vv][Ee]",
                     "value": "you move"},
                ],
            },
        },
    },
    # Brand spelled PHONETICALLY on purpose. The formatPlan replacements above
    # transform "raw text from your language model" — these two strings are
    # static config, not model output, so they appear to bypass the plan (a
    # 8/03 greeting transcribed as "UMMove", not "you move"). Writing them
    # phonetically is correct either way: "you move" contains no "umuve" for
    # any replacement to re-match, so it is a no-op if the plan DOES apply.
    # Keep the spelled form out of these two fields only — logs and prompts
    # elsewhere still say Umuve.
    "firstMessage": "Thanks for calling you move — this is Maya. What are you looking to get rid of today?",
    "endCallMessage": "Thanks for calling you move! Have a great day.",
    "serverUrl": BACKEND_URL + "/api/vapi/webhook",
    "endCallFunctionEnabled": True,
    "recordingEnabled": True,
    "silenceTimeoutSeconds": 30,
    "maxDurationSeconds": 600,  # 10 min max call
    "backgroundSound": "off",
    "transcriber": {
        "provider": "deepgram",
        "model": "nova-2",
        "language": "multi",
    },
    # Re-engage on silence instead of letting the call die at the 30s cutoff.
    # Nudges at 8s and 16s of dead air (the silence-timed-out calls in the logs
    # ran 100-150s then died with no re-prompt). Caps at 2 so we don't nag.
    "messagePlan": {
        "idleMessages": [
            "Sorry, I didn't catch that — are you still there?",
            "No rush. Whenever you're ready, just tell me what you'd like hauled away.",
        ],
        "idleTimeoutSeconds": 8,
        "idleMessageMaxSpokenCount": 2,
    },
}


def create_assistant():
    """Create the Vapi assistant."""
    resp = requests.post(
        "https://api.vapi.ai/assistant",
        headers=HEADERS,
        json=assistant_config,
    )

    if resp.status_code in (200, 201):
        data = resp.json()
        print("Assistant created successfully!")
        print("Assistant ID: {}".format(data.get("id")))
        print("Name: {}".format(data.get("name")))
        print()
        print("Next steps:")
        print("1. Buy a phone number:")
        print("   python vapi_setup.py buy-number {}".format(data.get("id")))
        print("2. Or assign in Vapi dashboard: https://dashboard.vapi.ai")
        print("3. Set VAPI_ASSISTANT_ID={} in your environment".format(data.get("id")))
        return data
    else:
        print("Error creating assistant: {}".format(resp.status_code))
        print(resp.text)
        return None


def buy_phone_number(assistant_id):
    """Buy a toll-free number and assign it to the assistant."""
    resp = requests.get(
        "https://api.vapi.ai/phone-number/available",
        headers=HEADERS,
        params={"type": "toll-free", "limit": 5},
    )

    if resp.status_code == 200:
        numbers = resp.json()
        if numbers:
            print("Available toll-free numbers:")
            for i, num in enumerate(numbers):
                print("  {}. {}".format(i + 1, num.get("number", "N/A")))

            # Buy the first one
            number = numbers[0].get("number")
            buy_resp = requests.post(
                "https://api.vapi.ai/phone-number",
                headers=HEADERS,
                json={
                    "number": number,
                    "assistantId": assistant_id,
                    "provider": "vapi",
                },
            )

            if buy_resp.status_code in (200, 201):
                data = buy_resp.json()
                print()
                print("Phone number purchased: {}".format(data.get("number")))
                print("Assigned to assistant: {}".format(assistant_id))
                return data
            else:
                print("Error buying number: {}".format(buy_resp.status_code))
                print(buy_resp.text)
        else:
            print("No toll-free numbers available. Try the Vapi dashboard.")
    else:
        print("Error listing numbers: {}".format(resp.status_code))
        print(resp.text)

    return None


def update_assistant(assistant_id, server_url_secret=None):
    """PATCH the live Vapi assistant with the latest config in this file.

    server_url_secret is never stored in this file or the repo — it arrives
    at runtime (request body or host env) and is only forwarded to Vapi.
    Omitting it leaves the assistant's existing serverUrlSecret untouched.
    """
    update_payload = {
        "name": assistant_config["name"],
        "model": assistant_config["model"],
        "voice": assistant_config.get("voice"),
        "firstMessage": assistant_config.get("firstMessage"),
        "endCallMessage": assistant_config.get("endCallMessage"),
        "endCallPhrases": assistant_config.get("endCallPhrases"),
        "recordingEnabled": assistant_config.get("recordingEnabled"),
        "silenceTimeoutSeconds": assistant_config.get("silenceTimeoutSeconds"),
        "maxDurationSeconds": assistant_config.get("maxDurationSeconds"),
        "backgroundSound": assistant_config.get("backgroundSound"),
        "transcriber": assistant_config.get("transcriber"),
        "messagePlan": assistant_config.get("messagePlan"),
        "serverUrl": assistant_config.get("serverUrl"),
    }
    update_payload = {k: v for k, v in update_payload.items() if v is not None}
    if server_url_secret:
        update_payload["serverUrlSecret"] = server_url_secret
    resp = requests.patch(
        "https://api.vapi.ai/assistant/{}".format(assistant_id),
        headers=HEADERS,
        json=update_payload,
    )
    if resp.status_code in (200, 201):
        print("Assistant {} updated successfully.".format(assistant_id))
        return resp.json()
    print("Error updating assistant: {}".format(resp.status_code))
    print(resp.text)
    # Surface the reason to API callers instead of a bare None — a rejected
    # config is almost always a schema complaint worth reading.
    raise VapiUpdateError(
        "Vapi returned {}: {}".format(resp.status_code, resp.text[:600])
    )


if __name__ == "__main__":
    _require_key()
    if len(sys.argv) > 1 and sys.argv[1] == "buy-number":
        if len(sys.argv) < 3:
            print("Usage: python vapi_setup.py buy-number <assistant_id>")
            sys.exit(1)
        buy_phone_number(sys.argv[2])
    elif len(sys.argv) > 1 and sys.argv[1] == "update":
        asst_id = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("VAPI_ASSISTANT_ID", "")
        if not asst_id:
            print("Usage: python vapi_setup.py update <assistant_id>")
            print("  or set VAPI_ASSISTANT_ID env var")
            sys.exit(1)
        update_assistant(asst_id)
    else:
        result = create_assistant()
        if result:
            print()
            print("To buy a phone number:")
            print("  python vapi_setup.py buy-number {}".format(result["id"]))
