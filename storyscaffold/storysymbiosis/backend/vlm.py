"""
vlm.py
Converts a base64 PNG screenshot of a Figma canvas into a concise
descriptive state string using a vision-capable LLM (Claude or GPT-4V).

The descriptive state is a structured prose summary covering:
  - What elements/frames are visible
  - Apparent narrative or thematic content
  - Any recent changes visible vs the prior state hint
"""

import os
import base64
import httpx

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
VLM_MODEL = "claude-opus-4-6"

VLM_SYSTEM_PROMPT = """You are a precise visual analyst observing a designer's Figma canvas.
Given a screenshot, produce a concise descriptive state in 3-5 sentences covering:
1. What frames or elements are visible and their apparent purpose
2. The overall narrative or thematic direction you can infer
3. Any notable design choices (layout, color, typography, imagery)
4. What appears to be the focus of current work

Be specific and observational. Do not give design advice. Do not use bullet points.
Output plain prose only."""


async def screenshot_to_state(image_b64: str, prior_state: str | None = None) -> str:
    """
    Sends image to Claude vision API, returns descriptive state string.
    prior_state is included as context so the model can note changes.
    """
    user_content: list = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": image_b64,
            },
        },
        {
            "type": "text",
            "text": (
                f"Prior state for reference:\n{prior_state}\n\n"
                if prior_state
                else ""
            ) + "Describe the current state of this Figma canvas.",
        },
    ]

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": VLM_MODEL,
                "max_tokens": 300,
                "system": VLM_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_content}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()
