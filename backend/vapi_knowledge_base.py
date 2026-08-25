"""
Umuve (You-Move) Knowledge Base for Vapi AI Phone Agent.

Contains comprehensive FAQ and company information that gets injected
into the assistant's system prompt.

Usage:
    python vapi_knowledge_base.py          # Patch assistant with knowledge base
    python -c "from vapi_knowledge_base import KNOWLEDGE_BASE; print(KNOWLEDGE_BASE)"
"""

import os
import sys
import requests
import json

VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "")
ASSISTANT_ID = "91198234-25c8-450a-9075-854509e9e59d"

KNOWLEDGE_BASE = {
    "what_we_take": {
        "question": "What items do you take?",
        "answer": (
            "We take almost everything! Furniture, appliances, electronics, mattresses, "
            "yard waste, construction debris, office equipment, hot tubs, pool tables, "
            "pianos, and general household junk. The only things we cannot take are "
            "hazardous waste, chemicals, asbestos, medical waste, and biohazardous materials. "
            "If you're unsure about a specific item, just ask and we'll let you know."
        ),
    },
    "pricing": {
        "question": "How does pricing work?",
        "answer": (
            "We price by item. Each item has a set price (for example, a sofa is $119, "
            "a mattress is $99 plus a $20 recycling fee, a refrigerator is $129 plus a $10 refrigerant fee). There's an 8% service fee on top. "
            "Volume discounts apply: 10% off for 4-7 items, 15% off for 8-15 items, "
            "20% off for 16+ items. Surge pricing may apply: same-day is +25%, "
            "next-day is +10%, weekends are +15%. Minimum job is $119."
        ),
    },
    "service_area": {
        "question": "What areas do you serve?",
        "answer": (
            "We serve Miami-Dade County, Broward County, and Palm Beach County — "
            "all of South Florida's tri-county area. This includes Miami, Fort Lauderdale, "
            "West Palm Beach, Boca Raton, Hollywood, Coral Springs, Pembroke Pines, "
            "Hialeah, Homestead, and all surrounding cities."
        ),
    },
    "payment": {
        "question": "How do I pay?",
        "answer": (
            "You can pay online at app.goumuve.com. We accept all major credit and debit cards "
            "through Stripe, as well as Apple Pay. Payment is collected when you book. "
            "No cash needed — everything is handled digitally for your convenience."
        ),
    },
    "recycling": {
        "question": "Do you recycle?",
        "answer": (
            "Yes! We are committed to responsible disposal. We recycle and donate items "
            "whenever possible. Usable furniture and appliances are donated to organizations "
            "like Habitat for Humanity and Goodwill. Electronics are taken to certified "
            "e-waste recyclers. We aim to divert as much as possible from landfills."
        ),
    },
    "pickup_time": {
        "question": "How long does a pickup take?",
        "answer": (
            "A typical pickup takes 30 to 60 minutes depending on the number and size "
            "of items. Larger jobs like full house cleanouts may take longer. "
            "We'll give you a 2-hour arrival window and the team works quickly."
        ),
    },
    "presence": {
        "question": "Do I need to be there? Can I watch?",
        "answer": (
            "You can be present during the pickup if you'd like, but it's not required. "
            "Just make sure the items are accessible — leave them outside, in the garage, "
            "or let us know how to access them. Many customers leave items on the curb "
            "or in the driveway for contactless pickup."
        ),
    },
    "cancellation": {
        "question": "What if I need to cancel?",
        "answer": (
            "Free cancellation up to 2 hours before your scheduled pickup time. "
            "You can cancel or reschedule through the app at app.goumuve.com or by calling us. "
            "Cancellations within 2 hours of the scheduled time may be subject to a fee."
        ),
    },
    "commercial": {
        "question": "Do you do commercial jobs?",
        "answer": (
            "Yes! We handle commercial junk removal for offices, retail stores, warehouses, "
            "and construction sites. This includes office furniture, electronics, "
            "construction debris, and general commercial waste. Contact us for a custom quote "
            "on large commercial jobs."
        ),
    },
    "insurance": {
        "question": "Are you licensed and insured?",
        "answer": (
            "Yes, Umuve is fully licensed and insured in the state of Florida. "
            "Our team is covered by general liability insurance, so you can have peace of mind "
            "that your property is protected during the removal process."
        ),
    },
    "item_destination": {
        "question": "What happens to my stuff?",
        "answer": (
            "We sort everything we pick up. Items in good condition are donated to "
            "Habitat for Humanity, Goodwill, and other local charities. Recyclable materials "
            "like metals, electronics, and cardboard go to certified recycling facilities. "
            "Everything else is responsibly disposed of at licensed waste facilities. "
            "We provide disposal receipts on request."
        ),
    },
    "minimum_charge": {
        "question": "Is there a minimum charge?",
        "answer": (
            "Yes, our minimum job charge is $119 plus the 8% service fee. This covers a single small item pickup. "
            "Most jobs end up being more than the minimum since customers typically have "
            "multiple items."
        ),
    },
    "get_quote": {
        "question": "How do I get a quote?",
        "answer": (
            "There are three easy ways to get a quote: "
            "1) Call us and Maya (that's me!) can give you an instant estimate over the phone. "
            "2) Use our app at app.goumuve.com to see prices and book online. "
            "3) Just describe your items right now and I'll calculate a quote for you instantly."
        ),
    },
}


def format_knowledge_base():
    """Format the knowledge base as a string for the system prompt."""
    lines = ["\n## Frequently Asked Questions (Knowledge Base)"]
    for key, entry in KNOWLEDGE_BASE.items():
        lines.append("\n**Q: {}**".format(entry["question"]))
        lines.append("A: {}".format(entry["answer"]))
    return "\n".join(lines)


KNOWLEDGE_BASE_PROMPT = format_knowledge_base()


def patch_assistant_with_knowledge():
    """Patch the Vapi assistant to include knowledge base in system prompt."""
    if not VAPI_API_KEY:
        print("Error: VAPI_API_KEY environment variable is required")
        print("  export VAPI_API_KEY=your-key-here")
        sys.exit(1)

    headers = {
        "Authorization": "Bearer {}".format(VAPI_API_KEY),
        "Content-Type": "application/json",
    }

    # First, get the current assistant config
    print("Fetching current assistant config...")
    get_resp = requests.get(
        "https://api.vapi.ai/assistant/{}".format(ASSISTANT_ID),
        headers=headers,
    )

    if get_resp.status_code != 200:
        print("Error fetching assistant: {}".format(get_resp.status_code))
        print(get_resp.text)
        sys.exit(1)

    current = get_resp.json()
    current_prompt = current.get("model", {}).get("messages", [{}])[0].get("content", "")

    # Check if knowledge base is already appended
    if "Frequently Asked Questions (Knowledge Base)" in current_prompt:
        print("Knowledge base already present in system prompt. Replacing...")
        # Strip the old knowledge base section
        idx = current_prompt.find("\n## Frequently Asked Questions (Knowledge Base)")
        if idx > 0:
            current_prompt = current_prompt[:idx]

    updated_prompt = current_prompt + KNOWLEDGE_BASE_PROMPT

    # Patch the assistant
    print("Patching assistant with knowledge base...")
    patch_resp = requests.patch(
        "https://api.vapi.ai/assistant/{}".format(ASSISTANT_ID),
        headers=headers,
        json={
            "model": {
                **current.get("model", {}),
                "messages": [
                    {
                        "role": "system",
                        "content": updated_prompt,
                    }
                ],
            }
        },
    )

    if patch_resp.status_code == 200:
        print("Knowledge base added successfully!")
        print("FAQ topics included: {}".format(len(KNOWLEDGE_BASE)))
        for key in KNOWLEDGE_BASE:
            print("  - {}".format(KNOWLEDGE_BASE[key]["question"]))
    else:
        print("Error patching assistant: {}".format(patch_resp.status_code))
        print(patch_resp.text)

    return patch_resp


if __name__ == "__main__":
    patch_assistant_with_knowledge()
