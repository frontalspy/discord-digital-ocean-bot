from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional, TypedDict

_STATE_FILE = "server_state.json"


class PersistedState(TypedDict):
    droplet_id: int
    started_at: str
    started_by: str
    channel_id: int


def save_state(droplet_id: int, started_at: datetime, started_by: str, channel_id: int) -> None:
    with open(_STATE_FILE, "w") as f:
        json.dump(
            {
                "droplet_id": droplet_id,
                "started_at": started_at.isoformat(),
                "started_by": started_by,
                "channel_id": channel_id,
            },
            f,
        )


def load_state() -> Optional[PersistedState]:
    if not os.path.exists(_STATE_FILE):
        return None
    try:
        with open(_STATE_FILE) as f:
            data = json.load(f)
        return {
            "droplet_id": data["droplet_id"],
            "started_at": data["started_at"],
            "started_by": data["started_by"],
            "channel_id": data["channel_id"],
        }
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return None


def clear_state() -> None:
    if os.path.exists(_STATE_FILE):
        os.remove(_STATE_FILE)
