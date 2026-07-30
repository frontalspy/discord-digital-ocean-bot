from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import discord

from services import digitalocean as do

if TYPE_CHECKING:
    from state import ServerState


def get_lifetime_hours() -> int:
    return int(os.environ.get("DROPLET_LIFETIME_HOURS", "6"))


async def schedule_shutdown(state: ServerState, channel: discord.TextChannel) -> None:
    if state.shutdown_task and not state.shutdown_task.done():
        state.shutdown_task.cancel()
    state.shutdown_task = asyncio.create_task(_shutdown_after_delay(state, channel))


def cancel_shutdown(state: ServerState) -> None:
    if state.shutdown_task and not state.shutdown_task.done():
        state.shutdown_task.cancel()
    state.shutdown_task = None


async def _shutdown_after_delay(state: ServerState, channel: discord.TextChannel) -> None:
    await asyncio.sleep(get_lifetime_hours() * 60 * 60)
    await run_shutdown_sequence(state, channel)


async def run_shutdown_sequence(state: ServerState, channel: discord.TextChannel) -> None:
    reserved_ip = os.environ["DO_RESERVED_IP"]
    droplet_name = do.get_droplet_name()
    hours = get_lifetime_hours()
    await channel.send(f"⏰ {hours} hour{'s' if hours != 1 else ''} elapsed — starting shutdown sequence...")

    try:
        droplet = await asyncio.to_thread(do.get_droplet)
        if not droplet:
            await channel.send("⚠️ Droplet not found — nothing to shut down.")
            _reset(state)
            return

        droplet_id = droplet["id"]
        old_snapshot = await asyncio.to_thread(do.get_snapshot)

        await channel.send("🔴 Powering off droplet...")
        await asyncio.to_thread(do.power_off_droplet, droplet_id)
        await asyncio.to_thread(do.wait_for_droplet_off, droplet_id)

        await channel.send(f"📸 Creating new snapshot `{droplet_name}`...")
        await asyncio.to_thread(do.create_snapshot, droplet_id, droplet_name)

        if old_snapshot:
            await channel.send(f"🗑️ Deleting old snapshot `{old_snapshot['id']}`...")
            await asyncio.to_thread(do.delete_snapshot, old_snapshot["id"])

        await channel.send("🔌 Unassigning reserved IP...")
        await asyncio.to_thread(do.unassign_reserved_ip, reserved_ip)

        await channel.send("💣 Destroying droplet...")
        await asyncio.to_thread(do.destroy_droplet, droplet_id)

        _reset(state)
        await channel.send(
            "✅ Shutdown complete. Reserved IP is preserved and ready for next session."
        )
    except Exception as exc:
        await channel.send(f"❌ Shutdown sequence failed: {exc}")


def _reset(state: ServerState) -> None:
    state.droplet_id = None
    state.shutdown_task = None
    state.started_at = None
    state.started_by = None
