"""
vlm.py
Converts a base64 PNG screenshot into a semantically rich state description
using Claude claude-opus-4-7 vision via the AsyncAnthropic client.
"""

import os
import base64
import io
import anthropic
from PIL import Image

_client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
MODEL = "claude-opus-4-7"

VLM_SYSTEM_PROMPT = """You are a semantic analyst observing someone's screen as they do creative work.
Your job is to produce a rich, interpretive description that helps creative collaborators understand
not just what is visible, but what the person is trying to accomplish and where the work is heading.

First, identify the environment type (e.g. design tool, web browser, code editor, document editor,
presentation tool, video editor, whiteboard, terminal, or other). Then describe the work in 4-6 sentences covering:

1. What is literally present — the content, structure, and materials of the work
2. The inferred goal: what the person appears to be trying to accomplish or the creative direction they are pursuing — be interpretive, not just descriptive
3. The creative decisions already committed to: narrative structure, tone, framing, style, or organisational logic visible in the work
4. What the person appears to be actively working on or wrestling with right now

If a prior state is provided, note what has meaningfully changed — especially shifts in direction, new additions, or anything abandoned.

Read between the lines of what is visible to infer intent and creative logic. Be specific and interpretive.
Do not give advice or suggestions. Do not use bullet points. Output plain prose only.
Do not begin with "The screen shows" — start with the environment or content directly."""


def _compress_image(image_b64: str, max_px: int = 1280, quality: int = 75) -> str:
    """Crop to center 75%, resize, and JPEG-compress a base64 PNG."""
    img = Image.open(io.BytesIO(base64.b64decode(image_b64)))
    w, h = img.size
    crop_w, crop_h = int(w * 0.75), int(h * 0.75)
    left, top = (w - crop_w) // 2, (h - crop_h) // 2
    img = img.crop((left, top, left + crop_w, top + crop_h))
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


async def screenshot_to_state(image_b64: str, prior_state: str | None = None) -> str:
    prior_block = (
        f"Prior state for reference (note any meaningful changes):\n{prior_state}\n\n"
        if prior_state
        else ""
    )
    prompt_text = (
        prior_block
        + "Describe what is on screen, infer what the person is trying to accomplish, "
        + "and identify the creative decisions and direction visible in the work."
    )

    compressed = _compress_image(image_b64)
    response = await _client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=VLM_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": compressed,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt_text,
                    },
                ],
            }
        ],
    )
    return response.content[0].text.strip()
