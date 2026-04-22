"""
vlm.py
Converts a base64 PNG screenshot of any work environment into a concise
descriptive state string using Google Gemini (gemini-2.0-flash) vision.

Works across: design tools (Figma, Sketch, Adobe XD), browsers, code editors,
document editors, presentation tools, terminals, whiteboards, video editors, etc.

The descriptive state is a structured prose summary covering:
  - What kind of environment/application is visible
  - What content or work is currently on screen
  - Apparent narrative, thematic, or structural direction
  - What appears to be the focus of current activity
  - Any notable changes from the prior state
"""

import os
import httpx

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

VLM_SYSTEM_PROMPT = """You are a precise visual analyst observing someone's screen as they do creative work.
Your job is to produce a concise, accurate description of what is currently happening on screen.

First, identify the environment type (e.g. design tool, web browser, code editor, document editor,
presentation tool, video editor, whiteboard, terminal, or other). Then describe the work in 3-5 sentences covering:

1. What environment or application is visible, and what content or work is on screen
2. The apparent narrative, thematic, or creative direction of the work
3. Any notable structural or aesthetic choices visible (layout, content organisation, visual style)
4. What the user appears to be focused on or actively working on right now

If a prior state is provided, briefly note what has meaningfully changed.

Be specific and observational. Do not give advice or suggestions. Do not use bullet points.
Output plain prose only. Do not begin with "The screen shows" — start with the environment or content directly."""


async def screenshot_to_state(image_b64: str, prior_state: str | None = None) -> str:
    """
    Sends a screenshot to Gemini vision, returns a descriptive state string.
    Works for any work environment visible on screen.
    prior_state is included so the model can note meaningful changes.
    """
    prior_block = (
        f"Prior state for reference (note any meaningful changes):\n{prior_state}\n\n"
        if prior_state
        else ""
    )
    prompt_text = (
        prior_block
        + "Describe what is currently on screen and what the person appears to be working on."
    )

    payload = {
        "system_instruction": {
            "parts": [{"text": VLM_SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": image_b64,
                        }
                    },
                    {"text": prompt_text},
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 300,
            "temperature": 0.3,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            GEMINI_API_URL,
            params={"key": GEMINI_API_KEY},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
