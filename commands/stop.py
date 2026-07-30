from __future__ import annotations

import asyncio

import discord

from scheduler import cancel_shutdown, run_shutdown_sequence
from services import digitalocean as do
from state import ServerState


async def handle_stop(ctx: discord.ApplicationContext, state: ServerState) -> None:
    droplet_name = do.get_droplet_name()

    # Ack the interaction immediately — the lock below may be held for
    # minutes by a concurrent start/stop/auto-shutdown.
    await ctx.respond(f"🔍 Checking status of **{droplet_name}**...")
    ch = ctx.channel

    async with state.lock:
        droplet = await asyncio.to_thread(do.get_droplet)
        if not droplet:
            await ch.send(f"⚠️ No running `{droplet_name}` droplet found.")
            return

        cancel_shutdown(state)
        await ch.send("🛑 Stopping server manually...")
        await run_shutdown_sequence(state, ch)
