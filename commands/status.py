from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta

import discord

from scheduler import get_lifetime_hours
from services import digitalocean as do
from state import ServerState


async def handle_status(ctx: discord.ApplicationContext, state: ServerState) -> None:
    droplet = await asyncio.to_thread(do.get_droplet)
    reserved_ip = os.environ.get("DO_RESERVED_IP", "not configured")
    droplet_name = do.get_droplet_name()

    if not droplet:
        await ctx.respond(f"🔴 Server is **offline**. No `{droplet_name}` droplet exists.")
        return

    power_status = droplet["status"]
    if power_status == "active":
        header = "🟢 Server is **on**"
    elif power_status == "off":
        header = "🟡 Droplet exists but is **powered off**"
    else:
        header = f"🟠 Droplet exists in state `{power_status}`"

    now = datetime.now()
    uptime = _fmt(now - state.started_at) if state.started_at else "unknown"
    hours = get_lifetime_hours()
    shutdown_in = (
        _fmt(state.started_at + timedelta(hours=hours) - now) if state.started_at else "unknown"
    )

    await ctx.respond(
        f"{header}\n"
        f"• Droplet ID: `{droplet['id']}`\n"
        f"• Status: `{power_status}`\n"
        f"• Reserved IP: `{reserved_ip}`\n"
        f"• Uptime: `{uptime}`\n"
        f"• Auto-shutdown in: `{shutdown_in}`\n"
        f"• Started by: `{state.started_by or 'unknown'}`"
    )


def _fmt(delta: timedelta) -> str:
    total = max(0, int(delta.total_seconds()))
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    return f"{h}h {m}m {s}s"
