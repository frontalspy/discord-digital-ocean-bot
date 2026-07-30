from __future__ import annotations

import os

import discord

from commands.start import handle_start
from commands.status import handle_status
from commands.stop import handle_stop
from scheduler import recover_state
from state import ServerState


def create_bot() -> discord.Bot:
    guild_id_str = os.environ.get("DISCORD_GUILD_ID")
    debug_guilds = [int(guild_id_str)] if guild_id_str else None

    bot = discord.Bot(debug_guilds=debug_guilds)
    state = ServerState()

    pewpew = bot.create_group("pewpew", "Manage the CS2 pew-pew server")

    @pewpew.command(name="start", description="Spin up the pew-pew server from snapshot")
    async def start(ctx: discord.ApplicationContext) -> None:
        await handle_start(ctx, state)

    @pewpew.command(name="stop", description="Stop the server, snapshot it, and destroy the droplet")
    async def stop(ctx: discord.ApplicationContext) -> None:
        await handle_stop(ctx, state)

    @pewpew.command(name="status", description="Check whether the server is running")
    async def status(ctx: discord.ApplicationContext) -> None:
        await handle_status(ctx, state)

    recovered = False

    @bot.event
    async def on_ready() -> None:
        nonlocal recovered
        print(f"Logged in as {bot.user} — ready.")
        # on_ready can fire again after a gateway reconnect; only recover once.
        if not recovered:
            recovered = True
            await recover_state(state, bot)

    return bot
