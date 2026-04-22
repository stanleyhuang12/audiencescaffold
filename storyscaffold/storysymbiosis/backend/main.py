"""
main.py — StorySymbiosis FastAPI backend

Routes:
  POST /session/new           — create session
  POST /process               — screenshot → VLM → stochastic agent roll
  GET  /stream/{sid}          — SSE stream for the floating panel
  POST /comment               — user clicked agent; generate comment
  POST /artifact              — user requested artifact from agent
  POST /comment/feedback      — user responded to a comment (three-button widget)
  POST /comment/dismiss       — user dismissed a comment
  POST /slider                — update global speak probability multiplier

  Export:
  GET  /export/{sid}          — full JSON audit trail
  GET  /export/{sid}/events   — interaction events as CSV
  GET  /export/{sid}/states   — VLM state snapshots as CSV

Environment variables required:
  GEMINI_API_KEY              — Google Gemini API key
"""

import json, os, asyncio, random
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
from pydantic import BaseModel

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


# ── Request models ────────────────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    session_id: str
    image_b64: str
    manual: bool = False        # true when triggered by user hotkey / button

class CommentRequest(BaseModel):
    session_id: str
    agent_id: str
    trigger: str = "user_click"  # 'user_click' | 'passive_cue'

class ArtifactRequest(BaseModel):
    session_id: str
    agent_id: str

class FeedbackRequest(BaseModel):
    session_id: str
    agent_id: str
    feedback_key: str            # 'explore' | 'different' | 'unsure'
    comment_preview: str = ""

class DismissRequest(BaseModel):
    session_id: str
    agent_id: str

class SliderRequest(BaseModel):
    session_id: str
    value: float                 # 0.0–1.0


# ── Stochastic roll ───────────────────────────────────────────────────────────

def roll_speakers(personas: list[dict], slider: float, state_count: int) -> list[str]:
    winners = []
    for p in personas:
        if state_count < p.get("min_states_required", 1):
            continue
        effective_prob = p["speak_probability"] * (0.3 + 0.7 * slider)
        if random.random() < effective_prob:
            winners.append((p["id"], p["speak_probability"]))
    winners.sort(key=lambda x: x[1], reverse=True)
    return [w[0] for w in winners[:2]]


# ── Session ───────────────────────────────────────────────────────────────────

@app.post("/session/new")
async def new_session():
    sid = sess.new_session_id()
    sess.get_or_create(sid)
    return {"session_id": sid}


# ── Core processing ───────────────────────────────────────────────────────────

@app.post("/process")
async def process(req: ProcessRequest):
    s = sess.get_or_create(req.session_id)
    prior_state = s.states[-1] if s.states else None

    current_state = await screenshot_to_state(req.image_b64, prior_state)
    s.add_state(current_state)

    trigger = "active" if req.manual else "passive"
    hand_raisers = roll_speakers(PERSONAS, s.slider_value, len(s.states))
    s.current_hand_raisers = hand_raisers
    for aid in hand_raisers:
        s.log_hand_raise(aid, trigger=trigger)

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


# ── Agent interaction ─────────────────────────────────────────────────────────

@app.post("/comment")
async def get_comment(req: CommentRequest):
    s = sess.get(req.session_id)
    if not s or not s.states:
        return JSONResponse({"error": "session not found"}, status_code=404)
    persona = PERSONA_MAP.get(req.agent_id)
    if not persona:
        return JSONResponse({"error": "unknown agent"}, status_code=400)
    comment = await generate_comment(persona, s.states[-1], s.states)
    s.log_comment_shown(req.agent_id, comment, trigger=req.trigger)
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


@app.post("/comment/feedback")
async def submit_feedback(req: FeedbackRequest):
    valid_keys = {"explore", "different", "unsure"}
    if req.feedback_key not in valid_keys:
        return JSONResponse(
            {"error": f"feedback_key must be one of {valid_keys}"},
            status_code=400,
        )
    s = sess.get(req.session_id)
    if not s:
        return JSONResponse({"error": "session not found"}, status_code=404)
    s.log_feedback(req.agent_id, req.feedback_key, req.comment_preview)
    return {"status": "ok"}


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


# ── Export ────────────────────────────────────────────────────────────────────

def _get_session_or_404(session_id: str):
    s = sess.get(session_id)
    if not s:
        return None, JSONResponse({"error": "session not found"}, status_code=404)
    return s, None


@app.get("/export/{session_id}")
async def export_json(session_id: str):
    """Full nested JSON audit trail."""
    s, err = _get_session_or_404(session_id)
    if err:
        return err
    return JSONResponse(s.export_json())


@app.get("/export/{session_id}/events")
async def export_events_csv(session_id: str):
    """
    Flat CSV of all interaction events — one row per event.
    Excludes state snapshots (those are in /export/{sid}/states).

    Columns: session_id, ts, event_type, agent_id, state_index,
             trigger, feedback_key, feedback_label,
             comment_preview, comment_full, artifact_title
    """
    s, err = _get_session_or_404(session_id)
    if err:
        return err
    csv_text = s.export_events_csv()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="events_{session_id[:8]}.csv"'},
    )


@app.get("/export/{session_id}/states")
async def export_states_csv(session_id: str):
    """
    Flat CSV of VLM state snapshots — one row per screen capture cycle.
    Joins to events.csv on (session_id, state_index).

    Columns: session_id, state_index, ts, state_preview, state_full
    """
    s, err = _get_session_or_404(session_id)
    if err:
        return err
    csv_text = s.export_states_csv()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="states_{session_id[:8]}.csv"'},
    )
