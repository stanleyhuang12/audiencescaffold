from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass
class Session:
    session_id: str
    states: list[str] = field(default_factory=list)
    audit: list[dict] = field(default_factory=list)
    slider_value: float = 0.5
    current_hand_raisers: list[str] = field(default_factory=list)

    def add_state(self, state: str):
        self.states.append(state)
        self._log("state_update", None, {"preview": state[:80]})

    def log_hand_raise(self, agent_id: str):
        self._log("hand_raised", agent_id, {})

    def log_comment_shown(self, agent_id: str, comment: str):
        self._log("comment_shown", agent_id, {"comment": comment})

    def log_artifact_shown(self, agent_id: str, artifact: dict):
        self._log("artifact_shown", agent_id, {"artifact": artifact})

    def log_comment_dismissed(self, agent_id: str):
        self._log("comment_dismissed", agent_id, {})

    def _log(self, event_type: str, agent_id, payload: dict):
        self.audit.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "agent": agent_id,
            "state_index": len(self.states) - 1,
            **payload,
        })

    def export(self) -> dict:
        return {
            "session_id": self.session_id,
            "state_count": len(self.states),
            "states": self.states,
            "audit": self.audit,
        }


_store: dict[str, Session] = {}

def get_or_create(sid: str) -> Session:
    if sid not in _store:
        _store[sid] = Session(session_id=sid)
    return _store[sid]

def get(sid: str) -> Session | None:
    return _store.get(sid)

def new_session_id() -> str:
    return str(uuid.uuid4())
