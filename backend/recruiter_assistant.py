"""
Maya Recruiter — the outbound Vapi assistant that recruits haulers by phone.

This module builds the assistant payload and (optionally) creates it in Vapi.
Run once to provision, then set the returned id as RECRUITER_ASSISTANT_ID on
Render. recruiter_calls.py places the calls; routes/vapi.py handles the
end-of-call outcome.

Provision:
    VAPI_API_KEY=... python3 recruiter_assistant.py --create
Preview only:
    python3 recruiter_assistant.py
"""

import json
import os
import sys

BACKEND_URL = os.environ.get(
    "PUBLIC_API_URL", "https://junkos-backend.onrender.com").rstrip("/")

SYSTEM_PROMPT = (
    "You are Maya, a friendly recruiter for Umuve (pronounced 'you-move'), a "
    "junk-removal marketplace in South Florida. You are calling small "
    "junk-hauling and dump-trailer business owners to offer them paid jobs. "
    "You are an AI assistant and you say so in your first sentence.\n\n"
    "GOAL: find out if they'd take paid junk-removal jobs from us, and if yes, "
    "get their first name and confirm the mobile number to text the signup "
    "link to.\n\n"
    "THE PITCH (keep it short, conversational, one idea at a time):\n"
    "- We send you paid junk-removal jobs in your area by text.\n"
    "- Single-item jobs pay around ninety dollars and up; bigger loads more.\n"
    "- You get paid the same day. No app required to start — you just reply to "
    "a text to grab a job.\n"
    "- It's free to join and there's no obligation; take the jobs that fit.\n\n"
    "RULES:\n"
    "- Disclose you're an AI in your first sentence.\n"
    "- Keep every response under about 30 words. This is a phone call.\n"
    "- Be warm and respectful. If they're busy, offer to text the info instead.\n"
    "- If they're not interested, thank them and end the call politely.\n"
    "- Do not promise a specific job volume or guarantee income.\n"
    "- If they ask something you don't know, say a team member will follow up.\n"
    "- If it's clearly a wrong number or the business is closed, end politely.\n"
    "- When they say yes or seem interested, confirm their first name and that "
    "this mobile number is the best one to text, then let them know the link "
    "is on its way and end the call."
)

ANALYSIS_SUMMARY_PROMPT = (
    "Summarize this recruiting call in 1-2 sentences: were they interested in "
    "receiving paid junk-removal jobs, and what should we do next?"
)

STRUCTURED_SCHEMA = {
    "type": "object",
    "properties": {
        "outcome": {
            "type": "string",
            "enum": ["interested", "callback", "not_interested",
                     "voicemail", "wrong_number"],
            "description": "The single best label for how the call ended.",
        },
        "hauler_name": {
            "type": "string",
            "description": "The owner's first name if given, else empty.",
        },
        "company": {
            "type": "string",
            "description": "Business name if mentioned, else empty.",
        },
        "callback_note": {
            "type": "string",
            "description": "If outcome is callback, when/why to call back.",
        },
    },
    "required": ["outcome"],
}


def build_payload():
    return {
        "name": "Maya Recruiter",
        "firstMessage": (
            "Hi, this is Maya — an AI assistant calling from Umuve, the "
            "junk-removal service. Do you have a quick minute?"
        ),
        "model": {
            "provider": "openai",
            "model": "gpt-4.1",
            "temperature": 0.6,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
        },
        # Match the inbound Maya's brand voice (Deepgram Aura-2 Amalthea) and
        # the "Umuve -> you-move" speech replacement so both lines sound alike.
        "voice": {
            "provider": "deepgram",
            "voiceId": "amalthea",
            "model": "aura-2",
            "chunkPlan": {
                "enabled": True,
                "formatPlan": {
                    "replacements": [
                        {"type": "regex",
                         "regex": "[Uu][Mm][Uu][Vv][Ee]",
                         "value": "you move"},
                    ],
                },
            },
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en",
        },
        "serverUrl": BACKEND_URL + "/api/vapi/webhook",
        "endCallFunctionEnabled": True,
        "endCallMessage": "Thanks for your time — have a great day!",
        "recordingEnabled": True,
        "silenceTimeoutSeconds": 20,
        "maxDurationSeconds": 180,
        "backgroundSound": "off",
        "analysisPlan": {
            "summaryPlan": {
                "enabled": True,
                "messages": [
                    {"role": "system", "content": ANALYSIS_SUMMARY_PROMPT},
                    {"role": "user",
                     "content": "Transcript:\n\n{{transcript}}"},
                ],
            },
            "structuredDataPlan": {
                "enabled": True,
                "schema": STRUCTURED_SCHEMA,
            },
        },
    }


def create():
    import requests
    key = os.environ.get("VAPI_API_KEY")
    if not key:
        sys.exit("VAPI_API_KEY not set.")
    resp = requests.post(
        "https://api.vapi.ai/assistant",
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"},
        json=build_payload(),
        timeout=30,
    )
    if resp.status_code in (200, 201):
        data = resp.json()
        aid = data.get("id")
        print("Created Maya Recruiter assistant.")
        print("RECRUITER_ASSISTANT_ID=" + str(aid))
        print("\nSet that on Render, then set RECRUITER_CALLS_ENABLED=true to "
              "arm outbound calls.")
        return aid
    print("Vapi error {}: {}".format(resp.status_code, resp.text[:500]))
    sys.exit(1)


if __name__ == "__main__":
    if "--create" in sys.argv:
        create()
    else:
        print(json.dumps(build_payload(), indent=2))
