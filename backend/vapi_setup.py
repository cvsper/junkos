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

## What You Do
1. Greet callers warmly
2. Find out what they need removed and where they are
3. Give instant price estimates
4. Book their pickup
5. Answer FAQs

## Pricing (quote these confidently)
- Sofa: $89 | Sectional: $139 | Recliner: $79
- Mattress: $75 | Box spring: $75 | Bed frame: $75 | Full bed set: $149
- Refrigerator: $99 | Washer or Dryer: $79 each | Washer/dryer set: $119
- Dining table: $99 | Coffee table: $59 | Desk: $69-99
- TV (flat screen): $89 | Treadmill: $89 | Elliptical: $99
- Hot tub: $299 | Pool table: $199 | Piano: $199
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

## Important Rules
- NEVER make up prices for items not on your list — use $25 (general item price) as default
- If asked about something unusual (hazardous waste, concrete, dirt), say you'll need to check and offer to have someone call back
- If the caller wants to speak to a human, say you can have someone call them back within the hour
- Always end with: "Is there anything else I can help you with?"
- Keep responses concise — this is a phone call, not an essay"""


assistant_config = {
    "name": "Umuve AI Receptionist",
    "model": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
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
        ],
    },
    "voice": {
        "provider": "11labs",
        "voiceId": "21m00Tcm4TlvDq8ikWAM",  # Rachel - warm, professional
    },
    "firstMessage": "Thanks for calling Umuve, South Florida's junk removal service! This is Maya. How can I help you today?",
    "endCallMessage": "Thanks for calling Umuve! Have a great day.",
    "serverUrl": BACKEND_URL + "/api/vapi/webhook",
    "endCallFunctionEnabled": True,
    "recordingEnabled": True,
    "silenceTimeoutSeconds": 30,
    "maxDurationSeconds": 600,  # 10 min max call
    "backgroundSound": "off",
    "transcriber": {
        "provider": "deepgram",
        "model": "nova-2",
        "language": "en",
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


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "buy-number":
        if len(sys.argv) < 3:
            print("Usage: python vapi_setup.py buy-number <assistant_id>")
            sys.exit(1)
        buy_phone_number(sys.argv[2])
    else:
        result = create_assistant()
        if result:
            print()
            print("To buy a phone number:")
            print("  python vapi_setup.py buy-number {}".format(result["id"]))
