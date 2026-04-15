"""
main.py — StorySymbiosis FastAPI backend (simplified)

Routes:
  POST /process          — screenshot → VLM → stochastic agent roll → SSE
  GET  /stream/{sid}     — SSE stream for the floating panel
  POST /comment          — user clicked agent; generate comment
  POST /artifact         — user requested artifact from agent
  POST /slider           — update global speak probability multiplier
  GET  /export/{sid}     — download audit trail
  POST /session/new      — create session
"""

import json, os, asyncio, random
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import httpx

import session as sess
from vlm import screenshot_to_state
from audience import generate_comment, generate_artifact

with open(os.path.join(os.path.dirname(__file__), "personas.json")) as f:
    PERSONAS: list[dict] = json.load(f)
PERSONA_MAP = {p["id"]: p for p in PERSONAS}

_sse_queues: dict[str, asyncio.Queue] = {}

def get_queue(sid: str) -> asyncio.Queue:
    if sid not in _sse_queues:
        _sse_queues[sid] = asyncio.Queue()
    return _sse_queues[sid]

app = FastAPI(title="StorySymbiosis")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Models ────────────────────────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    session_id: str
    image_b64: str

class CommentRequest(BaseModel):
    session_id: str
    agent_id: str

class ArtifactRequest(BaseModel):
    session_id: str
    agent_id: str

class SliderRequest(BaseModel):
    session_id: str
    value: float   # 0.0–1.0 multiplier on all speak_probabilities

class DismissRequest(BaseModel):
    session_id: str
    agent_id: str


# ── Stochastic roll ───────────────────────────────────────────────────────────

def roll_speakers(personas: list[dict], slider: float, state_count: int) -> list[str]:
    """
    Each agent independently rolls against its speak_probability * slider.
    Returns at most 2 agents that won the roll, in descending probability order.
    Agents below min_states_required are excluded.
    """
    winners = []
    for p in personas:
        if state_count < p.get("min_states_required", 1):
            continue
        effective_prob = p["speak_probability"] * (0.3 + 0.7 * slider)
        if random.random() < effective_prob:
            winners.append((p["id"], p["speak_probability"]))
    # Sort by base probability descending, cap at 2
    winners.sort(key=lambda x: x[1], reverse=True)
    return [w[0] for w in winners[:2]]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/session/new")
async def new_session():
    sid = sess.new_session_id()
    sess.get_or_create(sid)
    return {"session_id": sid}


@app.post("/process")
async def process(req: ProcessRequest):
    s = sess.get_or_create(req.session_id)
    prior_state = s.states[-1] if s.states else None

    # VLM: image → descriptive state
    current_state = await screenshot_to_state(req.image_b64, prior_state)
    s.add_state(current_state)

    # Stochastic roll — who speaks this cycle?
    hand_raisers = roll_speakers(PERSONAS, s.slider_value, len(s.states))
    s.current_hand_raisers = hand_raisers
    for aid in hand_raisers:
        s.log_hand_raise(aid)

    event = {
        "type": "cycle_complete",
        "state_index": len(s.states) - 1,
        "hand_raisers": hand_raisers,
    }
    await get_queue(req.session_id).put(event)
    return {"status": "ok", "hand_raisers": hand_raisers}


@app.get("/stream/{session_id}")
async def sse_stream(session_id: str):
    q = get_queue(session_id)
    async def gen():
        yield 'data: {"type":"connected"}\n\n'
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield 'data: {"type":"ping"}\n\n'
    return StreamingResponse(gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/comment")
async def get_comment(req: CommentRequest):
    s = sess.get(req.session_id)
    if not s or not s.states:
        return JSONResponse({"error": "session not found"}, status_code=404)
    persona = PERSONA_MAP.get(req.agent_id)
    if not persona:
        return JSONResponse({"error": "unknown agent"}, status_code=400)
    comment = await generate_comment(persona, s.states[-1], s.states)
    s.log_comment_shown(req.agent_id, comment)
    return {"agent_id": req.agent_id, "comment": comment}


@app.post("/artifact")
async def get_artifact(req: ArtifactRequest):
    s = sess.get(req.session_id)
    if not s or not s.states:
        return JSONResponse({"error": "session not found"}, status_code=404)
    persona = PERSONA_MAP.get(req.agent_id)
    if not persona:
        return JSONResponse({"error": "unknown agent"}, status_code=400)
    artifact = await generate_artifact(persona, s.states[-1], s.states)
    s.log_artifact_shown(req.agent_id, artifact)
    return {"agent_id": req.agent_id, "artifact": artifact}


@app.post("/comment/dismiss")
async def dismiss(req: DismissRequest):
    s = sess.get(req.session_id)
    if s:
        s.log_comment_dismissed(req.agent_id)
    return {"status": "ok"}


@app.post("/slider")
async def update_slider(req: SliderRequest):
    s = sess.get_or_create(req.session_id)
    s.slider_value = max(0.0, min(1.0, req.value))
    return {"status": "ok"}


@app.get("/export/{session_id}")
async def export_session(session_id: str):
    s = sess.get(session_id)
    if not s:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(s.export())
