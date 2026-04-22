"""
audience.py — comment and artifact generation per agent.
Both are lazy: only called when the user clicks.
Uses Google Gemini (gemini-2.0-flash) for text generation.
"""

import os
import json
import httpx

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def _history_block(history: list[str], n: int = 5) -> str:
    recent = history[-n:]
    return "\n".join(f"{i+1}. {s}" for i, s in enumerate(recent))


async def _call(system_prompt: str, user_text: str, max_tokens: int = 150) -> str:
    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": [
            {
                "parts": [{"text": user_text}]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.8,
        },
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            GEMINI_API_URL,
            params={"key": GEMINI_API_KEY},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


async def generate_comment(persona: dict, current_state: str, history: list[str]) -> str:
    user = (
        f"Session history:\n{_history_block(history)}\n\n"
        f"Current state:\n{current_state}\n\n"
        f"Speak as {persona['name']}."
    )
    return await _call(persona["system_prompt"], user, max_tokens=120)


async def generate_artifact(persona: dict, current_state: str, history: list[str]) -> dict:
    """Returns a dict with title, creator, year, caption, image_query."""
    user = (
        f"Session history:\n{_history_block(history)}\n\n"
        f"Current state:\n{current_state}\n\n"
        + persona["artifact_prompt"]
    )
    raw = await _call(persona["system_prompt"], user, max_tokens=200)
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(clean)
    except Exception:
        return {
            "title": "Reference",
            "creator": "",
            "year": "",
            "caption": raw[:120],
            "image_query": persona.get("artifact_query_hint", ""),
        }
