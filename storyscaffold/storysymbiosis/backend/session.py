"""
session.py — session state and export logic for StorySymbiosis.

Export formats
--------------
JSON  — full nested audit trail (original format)
CSV   — two flat tables designed for analysis in R / Python / Excel:

  events.csv   — one row per logged interaction event
    columns: session_id, ts, event_type, agent_id, state_index,
             trigger, feedback_key, feedback_label,
             comment_preview, comment_full, artifact_title

  states.csv   — one row per VLM state snapshot
    columns: session_id, state_index, ts, state_full, state_preview

The two tables join on (session_id, state_index).
"""

import csv
import io
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.path.dirname(__file__)) / "data"
DATA_DIR.mkdir(exist_ok=True)

FEEDBACK_VALUES = {
    "explore":   "I think this is an interesting idea worth exploring",
    "different": "I think I have a different direction in mind",
    "unsure":    "Not sure at this moment",
}


@dataclass
class Session:
    session_id: str
    states: list[str] = field(default_factory=list)
    audit: list[dict] = field(default_factory=list)
    slider_value: float = 0.5
    current_hand_raisers: list[str] = field(default_factory=list)

    # ── Logging helpers ───────────────────────────────────────────────────────

    def add_state(self, state: str):
        ts = self._now()
        self.states.append(state)
        self._log("state_update", None, {"preview": state[:80], "ts_state": ts})

    def log_hand_raise(self, agent_id: str, trigger: str = "passive"):
        self._log("hand_raised", agent_id, {"trigger": trigger})

    def log_comment_shown(self, agent_id: str, comment: str, trigger: str = "user_click"):
        self._log("comment_shown", agent_id, {
            "trigger": trigger,
            "comment_full": comment,
            "comment_preview": comment[:80],
        })

    def log_artifact_shown(self, agent_id: str, artifact: dict):
        self._log("artifact_shown", agent_id, {
            "artifact_title":   artifact.get("title", ""),
            "artifact_creator": artifact.get("creator", ""),
            "artifact_year":    artifact.get("year", ""),
        })

    def log_comment_dismissed(self, agent_id: str):
        self._log("comment_dismissed", agent_id, {})

    def log_feedback(self, agent_id: str, feedback_key: str, comment_preview: str = ""):
        label = FEEDBACK_VALUES.get(feedback_key, feedback_key)
        self._log("comment_feedback", agent_id, {
            "feedback_key":   feedback_key,
            "feedback_label": label,
            "comment_preview": comment_preview[:80],
        })

    def log_slider_change(self, value: float):
        self._log("slider_changed", None, {"slider_value": value})

    def get_agent_comments(self, agent_id: str) -> list[str]:
        return [
            e["comment_full"] for e in self.audit
            if e.get("event") == "comment_shown" and e.get("agent") == agent_id
            and "comment_full" in e
        ]

    def _log(self, event_type: str, agent_id, payload: dict):
        self.audit.append({
            "ts":          self._now(),
            "event":       event_type,
            "agent":       agent_id,
            "state_index": len(self.states) - 1 if self.states else None,
            **payload,
        })
        self._persist()

    def _persist(self):
        path = DATA_DIR / f"session_{self.session_id}.json"
        path.write_text(json.dumps(self.export_json(), indent=2))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Export ────────────────────────────────────────────────────────────────

    def export_json(self) -> dict:
        return {
            "session_id":  self.session_id,
            "state_count": len(self.states),
            "states":      self.states,
            "audit":       self.audit,
        }

    def export_events_csv(self) -> str:
        fieldnames = [
            "session_id", "ts", "event_type", "agent_id", "state_index",
            "trigger", "feedback_key", "feedback_label",
            "comment_preview", "comment_full", "artifact_title", "slider_value",
        ]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        for entry in self.audit:
            if entry["event"] == "state_update":
                continue
            writer.writerow({
                "session_id":     self.session_id,
                "ts":             entry.get("ts", ""),
                "event_type":     entry.get("event", ""),
                "agent_id":       entry.get("agent") or "",
                "state_index":    entry.get("state_index", ""),
                "trigger":        entry.get("trigger", ""),
                "feedback_key":   entry.get("feedback_key", ""),
                "feedback_label": entry.get("feedback_label", ""),
                "comment_preview": entry.get("comment_preview", ""),
                "comment_full":   entry.get("comment_full", ""),
                "artifact_title": entry.get("artifact_title", ""),
                "slider_value":   entry.get("slider_value", ""),
            })
        return buf.getvalue()

    def export_states_csv(self) -> str:
        fieldnames = ["session_id", "state_index", "ts", "state_preview", "state_full"]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        ts_map: dict[int, str] = {}
        for entry in self.audit:
            if entry["event"] == "state_update":
                idx = entry.get("state_index", 0)
                ts_map[idx] = entry.get("ts", "")
        for i, state_text in enumerate(self.states):
            writer.writerow({
                "session_id":    self.session_id,
                "state_index":   i,
                "ts":            ts_map.get(i, ""),
                "state_preview": state_text[:120],
                "state_full":    state_text,
            })
        return buf.getvalue()


# ── Store ─────────────────────────────────────────────────────────────────────

_store: dict[str, Session] = {}

def get_or_create(sid: str) -> Session:
    if sid not in _store:
        _store[sid] = Session(session_id=sid)
    return _store[sid]

def get(sid: str) -> Session | None:
    return _store.get(sid)

def new_session_id() -> str:
    return str(uuid.uuid4())
