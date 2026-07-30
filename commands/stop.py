from __future__ import annotations

import asyncio

import discord

from scheduler import cancel_shutdown, run_shutdown_sequence
from services import digitalocean as do
from state import ServerState


async def handle_stop(ctx: discord.ApplicationContext, state: ServerState) -> None:
    droplet = await asyncio.to_thread(do.get_droplet)
    if not droplet:
        await ctx.respond(
            f"⚠️ No running `{do.get_droplet_name()}` droplet found.", ephemeral=True
        )
        return

    cancel_shutdown(state)
    await ctx.respond("🛑 Stopping server manually...")
    await run_shutdown_sequence(state, ctx.channel)
