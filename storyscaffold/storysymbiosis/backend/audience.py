"""
audience.py — comment and artifact generation per agent.
Both are lazy: only called when the user clicks.
"""

import os, json, httpx

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-6"


def _history_block(history: list[str], n: int = 5) -> str:
    recent = history[-n:]
    return "\n".join(f"{i+1}. {s}" for i, s in enumerate(recent))


async def _call(system: str, user: str, max_tokens: int = 150) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"].strip()


async def generate_comment(persona: dict, current_state: str, history: list[str]) -> str:
    user = f"""Session history:\n{_history_block(history)}\n\nCurrent state:\n{current_state}\n\nSpeak as {persona['name']}."""
    return await _call(persona["system_prompt"], user, max_tokens=120)


async def generate_artifact(persona: dict, current_state: str, history: list[str]) -> dict:
    """Returns a dict with title, creator, year, caption, image_query."""
    user = f"""Session history:\n{_history_block(history)}\n\nCurrent state:\n{current_state}"""
    raw = await _call(persona["system_prompt"], 
                      user + "\n\n" + persona["artifact_prompt"], 
                      max_tokens=200)
    try:
        # Strip markdown fences if present
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
