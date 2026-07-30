from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ServerState:
    droplet_id: Optional[int] = None
    shutdown_task: Optional[asyncio.Task] = field(default=None, repr=False, compare=False)
    started_at: Optional[datetime] = None
    started_by: Optional[str] = None
    # Serializes start/stop so two concurrent commands can't both pass the
    # "no droplet running" check before either finishes creating one.
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)
