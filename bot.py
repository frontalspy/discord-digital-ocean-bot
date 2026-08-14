from __future__ import annotations

import os
import traceback

import discord

from commands.run_startup import handle_run_startup
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

    @pewpew.command(
        name="run-startup",
        description="Re-run the startup commands against the already-running droplet",
    )
    async def run_startup(ctx: discord.ApplicationContext) -> None:
        await handle_run_startup(ctx, state)

    @bot.event
    async def on_application_command_error(
        ctx: discord.ApplicationContext, error: discord.DiscordException
    ) -> None:
        # Any exception a command handler didn't already catch lands here —
        # log the full traceback for us, but don't leave the user staring at
        # a dead interaction.
        original = getattr(error, "original", error)
        traceback.print_exception(type(original), original, original.__traceback__)

        if isinstance(original, discord.Forbidden):
            message = "❌ I don't have permission to post in this channel — check my role/channel permissions."
        else:
            message = f"❌ Something went wrong: {original}"

        try:
            if ctx.interaction.response.is_done():
                await ctx.followup.send(message, ephemeral=True)
            else:
                await ctx.respond(message, ephemeral=True)
        except discord.DiscordException:
            pass  # can't reach this channel/interaction at all — already logged above

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
