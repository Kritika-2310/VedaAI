"""
Simple in-memory store. No DB needed per assignment spec.
Data is lost on server restart - that's fine for this scope.
"""

_sessions: dict[str, dict] = {}


def create_session(session_id: str, data: dict) -> None:
    _sessions[session_id] = data


def get_session(session_id: str) -> dict | None:
    return _sessions.get(session_id)


def update_session(session_id: str, patch: dict) -> None:
    if session_id in _sessions:
        _sessions[session_id].update(patch)


def delete_session(session_id: str) -> None:
    _sessions.pop(session_id, None)
