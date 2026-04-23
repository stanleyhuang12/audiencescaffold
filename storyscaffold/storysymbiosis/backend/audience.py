"""
audience.py — comment and artifact generation per agent.
Both are lazy: only called when the user clicks.
Uses OpenAI via AsyncOpenAI client.
Comments use gpt-4o-mini; artifacts use gpt-4o with web search (Responses API).
"""

import os
import json
from openai import AsyncOpenAI

_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
COMMENT_MODEL  = "gpt-4o-mini"
ARTIFACT_MODEL = "gpt-4o"


def _history_block(history: list[str], n: int | None = 5) -> str:
    recent = history if n is None else history[-n:]
    return "\n".join(f"{i+1}. {s}" for i, s in enumerate(recent))


async def _call(system_prompt: str, user_text: str, max_tokens: int = 150) -> str:
    response = await _client.chat.completions.create(
        model=COMMENT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_text},
        ],
        max_tokens=max_tokens,
        temperature=0.8,
    )
    return response.choices[0].message.content.strip()


async def generate_comment(
    persona: dict,
    current_state: str,
    history: list[str],
    prior_comments: list[str] | None = None,
) -> tuple[str, str]:
    n = None if persona["id"] in ("reviewability", "recombinability") else 5

    prior_block = ""
    if prior_comments:
        lines = "\n".join(f"- {c[:120]}" for c in prior_comments[-5:])
        prior_block = f"\n\nYour previous observations this session (do not repeat these ideas):\n{lines}"

    delta_instruction = ""
    if len(history) >= 2:
        delta_instruction = (
            "\n\nBegin your response with this exact format:\n"
            "NOTICED: <one brief sentence about what changed in the creative work since last observation>\n"
            "Then your observation from your persona's perspective."
        )

    user = (
        f"Session history:\n{_history_block(history, n)}\n\n"
        f"Current state:\n{current_state}"
        f"{prior_block}"
        f"{delta_instruction}\n\n"
        f"Speak as {persona['name']}."
    )
    raw = await _call(persona["system_prompt"], user, max_tokens=160)

    noticed = ""
    comment = raw
    if raw.startswith("NOTICED:"):
        parts = raw.split("\n", 1)
        noticed = parts[0][len("NOTICED:"):].strip()
        comment = parts[1].strip() if len(parts) > 1 else raw

    return comment, noticed


async def generate_artifact(persona: dict, current_state: str, history: list[str]) -> dict:
    """Use gpt-4o with web search to find a real cultural artifact.

    Returns a dict with: title, creator, year, caption, link.
    """
    instructions = (
        "You are a cultural research assistant. "
        "Find ONE specific, real-world cultural artifact (film, book, artwork, "
        "design piece, installation, or research publication) that is relevant "
        "and inspirational given the creative work described. "
        "Search the web to verify the artifact is real and find its official or authoritative page. "
        "Reply with ONLY a JSON object — no markdown fences, no extra text — with these exact fields: "
        '{"title": "exact title", "creator": "author/director/artist name", '
        '"year": "year as string", '
        '"caption": "1-2 sentences on why this artifact is relevant to the work described", '
        '"link": "direct URL to the official or authoritative page"}'
    )
    input_text = (
        f"Session history:\n{_history_block(history)}\n\n"
        f"Current state:\n{current_state}\n\n"
        f"Persona angle: {persona['artifact_prompt']}\n\n"
        "Find a real artifact that fits. Return only the JSON."
    )

    try:
        response = await _client.responses.create(
            model=ARTIFACT_MODEL,
            tools=[{"type": "web_search_preview"}],
            instructions=instructions,
            input=input_text,
        )
        raw_text = response.output_text.strip()

        # Extract the first cited URL from web search annotations
        link = ""
        for item in response.output:
            annotations = getattr(item, "annotations", None) or []
            for ann in annotations:
                url = getattr(ann, "url", "")
                if url.startswith("http"):
                    link = url
                    break
            if link:
                break

        clean = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        artifact = json.loads(clean)
        return {
            "title":   artifact.get("title", ""),
            "creator": artifact.get("creator", ""),
            "year":    artifact.get("year", ""),
            "caption": artifact.get("caption", "")[:200],
            "link":    artifact.get("link", "") or link,
        }

    except Exception as exc:
        print(f"[SS] artifact error: {exc}")
        return {"title": "Reference", "creator": "", "year": "", "caption": str(exc)[:120], "link": ""}
