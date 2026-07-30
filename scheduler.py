from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

import discord

import persistence
from services import digitalocean as do

if TYPE_CHECKING:
    from state import ServerState


def get_lifetime_hours() -> int:
    return int(os.environ.get("DROPLET_LIFETIME_HOURS", "6"))


async def schedule_shutdown(
    state: ServerState,
    channel: discord.TextChannel,
    delay_seconds: Optional[float] = None,
) -> None:
    if state.shutdown_task and not state.shutdown_task.done():
        state.shutdown_task.cancel()
    if delay_seconds is None:
        delay_seconds = get_lifetime_hours() * 60 * 60
    state.shutdown_task = asyncio.create_task(
        _shutdown_after_delay(state, channel, delay_seconds)
    )


def cancel_shutdown(state: ServerState) -> None:
    if state.shutdown_task and not state.shutdown_task.done():
        state.shutdown_task.cancel()
    state.shutdown_task = None


async def _shutdown_after_delay(
    state: ServerState, channel: discord.TextChannel, delay_seconds: float
) -> None:
    await asyncio.sleep(max(delay_seconds, 0))
    # Guard against racing a concurrently-issued /pewpew stop.
    async with state.lock:
        await run_shutdown_sequence(state, channel)


async def run_shutdown_sequence(state: ServerState, channel: discord.TextChannel) -> None:
    reserved_ip = os.environ["DO_RESERVED_IP"]
    droplet_name = do.get_droplet_name()
    hours = get_lifetime_hours()
    await channel.send(
        f"⏰ {hours} hour{'s' if hours != 1 else ''} elapsed — starting shutdown sequence..."
    )

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
    persistence.clear_state()


async def recover_state(state: ServerState, bot: discord.Bot) -> None:
    """Re-arm the auto-shutdown timer after a bot restart, if a droplet is still running.

    In-memory state (and its shutdown timer) doesn't survive a process
    restart. Without this, a droplet that was running when the bot went
    down would keep running — and billing — forever with nothing to shut
    it down.
    """
    droplet = await asyncio.to_thread(do.get_droplet)
    if not droplet:
        persistence.clear_state()
        return

    saved = persistence.load_state()
    channel: Optional[discord.abc.Messageable] = None
    channel_id = saved["channel_id"] if saved else None
    if channel_id:
        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except discord.DiscordException:
                channel = None

    if channel is None:
        print(
            f"Found running droplet {droplet['id']} after restart but could not resolve "
            "the original notification channel — auto-shutdown was NOT re-armed. "
            "Run /pewpew status or /pewpew stop manually."
        )
        return

    if saved and saved["droplet_id"] == droplet["id"]:
        state.droplet_id = droplet["id"]
        state.started_at = datetime.fromisoformat(saved["started_at"])
        state.started_by = saved["started_by"]

        elapsed = datetime.now() - state.started_at
        remaining = (timedelta(hours=get_lifetime_hours()) - elapsed).total_seconds()

        await channel.send(
            f"🔄 Recovered after restart — `{do.get_droplet_name()}` "
            f"(droplet `{droplet['id']}`) was already running. Auto-shutdown re-armed."
        )
        await schedule_shutdown(state, channel, remaining)
        return

    # Droplet exists but there's no usable record of when it started (stale
    # or missing state file). Arm a fresh timer as a safety net rather than
    # leaving it running unbounded.
    state.droplet_id = droplet["id"]
    state.started_at = datetime.now()
    state.started_by = "unknown"

    await channel.send(
        f"⚠️ Found a running `{do.get_droplet_name()}` droplet with no matching saved "
        f"state (bot likely restarted). Arming a fresh {get_lifetime_hours()}-hour auto-shutdown."
    )
    await schedule_shutdown(state, channel)
    persistence.save_state(state.droplet_id, state.started_at, state.started_by, channel.id)
