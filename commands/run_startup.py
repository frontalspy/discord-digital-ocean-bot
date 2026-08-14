from __future__ import annotations

import asyncio
import os

import discord

from discord_utils import send_chunked
from services import digitalocean as do
from services.ssh import run_startup_commands
from state import ServerState


async def handle_run_startup(ctx: discord.ApplicationContext, state: ServerState) -> None:
    reserved_ip = os.environ.get("DO_RESERVED_IP")
    if not reserved_ip:
        await ctx.respond("`DO_RESERVED_IP` is not configured.", ephemeral=True)
        return

    droplet_name = do.get_droplet_name()

    if state.lock.locked():
        await ctx.respond(
            "⚠️ Another start/stop request is already in progress — try again once it finishes.",
            ephemeral=True,
        )
        return

    await ctx.respond(f"🔍 Checking status of **{droplet_name}**...")
    ch = ctx.channel

    async with state.lock:
        droplet = await asyncio.to_thread(do.get_droplet)
        if not droplet:
            await ch.send(f"⚠️ No running `{droplet_name}` droplet found.")
            return
        if droplet["status"] != "active":
            await ch.send(
                f"⚠️ Droplet exists but isn't active yet (status: `{droplet['status']}`) — "
                "wait for it to finish booting first."
            )
            return

        await ch.send(f"📡 Re-running startup commands against `{reserved_ip}`...")

        output_lines: list[str] = []
        try:
            await asyncio.to_thread(run_startup_commands, reserved_ip, output_lines.append)
            await send_chunked(ch, output_lines)
            await ch.send("✅ Startup commands completed successfully.")
        except Exception as exc:
            await send_chunked(ch, output_lines)
            await ch.send(f"⚠️ Startup commands failed: {exc}")
