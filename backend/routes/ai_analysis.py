"""
AI Photo Analysis — GPT-4o-mini Vision
Analyzes uploaded photos to detect items, estimate volume, and suggest truck size.
"""

import base64
import json
import logging
import os

from flask import Blueprint, request, jsonify
from extensions import limiter

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_PHOTOS = 5

VALID_CATEGORIES = {
    "furniture", "appliances", "electronics", "yard_waste",
    "construction", "general", "mattress", "hot_tub", "other",
}
VALID_SIZES = {"small", "medium", "large"}

ANALYSIS_PROMPT = """Analyze these photos of items that need junk removal. Return a JSON object with:

{
  "items": [{"category": "<category>", "size": "<size>", "quantity": <int>, "description": "<brief description>"}],
  "estimatedVolume": <cubic feet as float>,
  "truckSize": "<truck size>",
  "confidence": <0.0-1.0>,
  "notes": "<brief summary>"
}

Rules:
- category must be one of: furniture, appliances, electronics, yard_waste, construction, general, mattress, hot_tub, other
- size must be one of: small, medium, large
- truckSize must be one of: Pickup Truck, Standard Truck, Large Truck
- Estimate volume in cubic feet based on visible items
- Set confidence based on photo clarity and item visibility
- Return ONLY valid JSON, no markdown or extra text"""


@ai_bp.route("/analyze-photos", methods=["POST"])
@limiter.limit("10 per minute")
def analyze_photos():
    """Analyze uploaded photos with GPT-4o-mini Vision."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not configured — skipping AI analysis")
        return jsonify({"success": False, "error": "AI analysis not configured"}), 503

    # --- Validate uploaded files ---
    if "photos" not in request.files:
        return jsonify({"success": False, "error": "No photos provided"}), 400

    files = request.files.getlist("photos")
    if not files or len(files) == 0:
        return jsonify({"success": False, "error": "No photos provided"}), 400
    if len(files) > MAX_PHOTOS:
        return jsonify({"success": False, "error": f"Maximum {MAX_PHOTOS} photos allowed"}), 400

    image_contents = []
    for f in files:
        if not f.filename:
            continue
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({"success": False, "error": f"Invalid file type: .{ext}"}), 400

        data = f.read()
        if len(data) > MAX_FILE_SIZE:
            return jsonify({"success": False, "error": f"{f.filename} exceeds 10MB limit"}), 400

        mime = f.content_type or "image/jpeg"
        if mime not in ALLOWED_MIME_TYPES:
            mime = "image/jpeg"  # fallback

        b64 = base64.b64encode(data).decode("utf-8")
        image_contents.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "low"},
        })

    if not image_contents:
        return jsonify({"success": False, "error": "No valid photos provided"}), 400

    # --- Call OpenAI GPT-4o-mini Vision ---
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ANALYSIS_PROMPT},
                    *image_contents,
                ],
            }
        ]

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
        )

        raw_text = response.choices[0].message.content or ""
        # Strip markdown code fences if present
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        analysis = json.loads(cleaned)

        # Validate and sanitize the response
        items = []
        for item in analysis.get("items", []):
            cat = item.get("category", "other")
            if cat not in VALID_CATEGORIES:
                cat = "other"
            sz = item.get("size", "medium")
            if sz not in VALID_SIZES:
                sz = "medium"
            items.append({
                "category": cat,
                "size": sz,
                "quantity": max(1, int(item.get("quantity", 1))),
                "description": str(item.get("description", ""))[:200],
            })

        truck_size = analysis.get("truckSize", "Standard Truck")
        if truck_size not in {"Pickup Truck", "Standard Truck", "Large Truck"}:
            truck_size = "Standard Truck"

        confidence = analysis.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            confidence = 0.5

        result = {
            "items": items,
            "estimatedVolume": float(analysis.get("estimatedVolume", 0)),
            "truckSize": truck_size,
            "confidence": round(float(confidence), 2),
            "notes": str(analysis.get("notes", ""))[:500],
        }

        return jsonify({"success": True, "analysis": result}), 200

    except json.JSONDecodeError:
        logger.error("AI returned invalid JSON: %s", raw_text[:200] if 'raw_text' in dir() else "unknown")
        return jsonify({"success": False, "error": "AI returned invalid response"}), 502
    except Exception as exc:
        logger.error("AI analysis failed: %s", str(exc))
        return jsonify({"success": False, "error": "AI analysis temporarily unavailable"}), 502
