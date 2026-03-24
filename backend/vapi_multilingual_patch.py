"""
Patch Vapi assistant for full multilingual support.

Replaces the Spanish-only patch with comprehensive multilingual capabilities.
Updates system prompt + transcriber to handle English, Spanish, French,
Portuguese, Haitian Creole, and any other language callers use.

Usage:
    export VAPI_API_KEY=your-key-here
    python vapi_multilingual_patch.py
"""

import os
import sys
import requests
import json

VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "")
ASSISTANT_ID = "91198234-25c8-450a-9075-854509e9e59d"

if not VAPI_API_KEY:
    print("Error: VAPI_API_KEY environment variable is required")
    print("  export VAPI_API_KEY=your-key-here")
    sys.exit(1)

HEADERS = {
    "Authorization": "Bearer {}".format(VAPI_API_KEY),
    "Content-Type": "application/json",
}

MULTILINGUAL_INSTRUCTIONS = """
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
- For Haitian Creole: "Mèsi paske ou rele Umuve" / "Kijan mwen ka ede ou jodi a?"
- For Portuguese: "Obrigado por ligar para a Umuve" / "Como posso ajudar?"
- For French: "Merci d'avoir appele Umuve" / "Comment puis-je vous aider?"
- For Spanish: "Gracias por llamar a Umuve" / "Como puedo ayudarle?"
"""


def patch_for_multilingual():
    """Patch the Vapi assistant with full multilingual support."""
    # Get current assistant config
    print("Fetching current assistant config...")
    get_resp = requests.get(
        "https://api.vapi.ai/assistant/{}".format(ASSISTANT_ID),
        headers=HEADERS,
    )

    if get_resp.status_code != 200:
        print("Error fetching assistant: {}".format(get_resp.status_code))
        print(get_resp.text)
        sys.exit(1)

    current = get_resp.json()
    current_prompt = current.get("model", {}).get("messages", [{}])[0].get("content", "")

    # Strip old bilingual section if present (from Spanish-only patch)
    if "Bilingual Support (English / Spanish)" in current_prompt:
        print("Removing old Spanish-only bilingual section...")
        idx = current_prompt.find("\n## Bilingual Support (English / Spanish)")
        rest = current_prompt[idx + 1:]
        next_section = -1
        for marker in ["\n## Frequently Asked Questions", "\n## "]:
            pos = rest.find(marker, len("## Bilingual Support"))
            if pos > 0 and (next_section < 0 or pos < next_section):
                next_section = pos
                break
        if next_section > 0:
            current_prompt = current_prompt[:idx] + rest[next_section:]
        else:
            current_prompt = current_prompt[:idx]

    # Strip old multilingual section if present (idempotent re-runs)
    if "## Multilingual Support" in current_prompt:
        print("Replacing existing multilingual section...")
        idx = current_prompt.find("\n## Multilingual Support")
        rest = current_prompt[idx + 1:]
        next_section = -1
        for marker in ["\n## Frequently Asked Questions"]:
            pos = rest.find(marker, len("## Multilingual Support"))
            if pos > 0:
                next_section = pos
                break
        if next_section > 0:
            current_prompt = current_prompt[:idx] + rest[next_section:]
        else:
            current_prompt = current_prompt[:idx]

    # Insert multilingual instructions before FAQ section if present,
    # otherwise append at the end
    faq_marker = "\n## Frequently Asked Questions (Knowledge Base)"
    if faq_marker in current_prompt:
        faq_idx = current_prompt.find(faq_marker)
        updated_prompt = current_prompt[:faq_idx] + MULTILINGUAL_INSTRUCTIONS + current_prompt[faq_idx:]
    else:
        updated_prompt = current_prompt + MULTILINGUAL_INSTRUCTIONS

    # Patch the assistant
    print("Patching assistant with multilingual support...")
    patch_data = {
        "model": {
            **current.get("model", {}),
            "messages": [
                {
                    "role": "system",
                    "content": updated_prompt,
                }
            ],
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "multi",
        },
    }

    patch_resp = requests.patch(
        "https://api.vapi.ai/assistant/{}".format(ASSISTANT_ID),
        headers=HEADERS,
        json=patch_data,
    )

    if patch_resp.status_code == 200:
        data = patch_resp.json()
        print("Multilingual support added successfully!")
        print()
        print("Changes applied:")
        print("  - System prompt: multilingual instructions added")
        print("    (English, Spanish, French, Portuguese, Haitian Creole, + auto-detect)")
        print("  - Transcriber: Deepgram Nova-2 multi-language mode")
        print("  - Old Spanish-only patch replaced with full multilingual support")
        print()
        print("Transcriber config: {}".format(
            json.dumps(data.get("transcriber", {}), indent=2)
        ))
        print()
        print("Updated system prompt length: {} chars".format(
            len(data.get("model", {}).get("messages", [{}])[0].get("content", ""))
        ))
    else:
        print("Error patching assistant: {}".format(patch_resp.status_code))
        print(patch_resp.text)

    return patch_resp


if __name__ == "__main__":
    patch_for_multilingual()
