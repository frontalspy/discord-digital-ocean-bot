from __future__ import annotations

import asyncio
import os
from datetime import datetime

import discord

from scheduler import get_lifetime_hours, schedule_shutdown
from services import digitalocean as do
from services.ssh import run_startup_commands
from state import ServerState


async def handle_start(ctx: discord.ApplicationContext, state: ServerState) -> None:
    reserved_ip = os.environ.get("DO_RESERVED_IP")
    if not reserved_ip:
        await ctx.respond("`DO_RESERVED_IP` is not configured.", ephemeral=True)
        return

    droplet_name = do.get_droplet_name()

    existing = await asyncio.to_thread(do.get_droplet)
    if existing:
        await ctx.respond(
            f"⚠️ Server `{droplet_name}` is already running "
            f"(droplet `{existing['id']}`, status: `{existing['status']}`).",
            ephemeral=True,
        )
        return

    snapshot = await asyncio.to_thread(do.get_snapshot)
    if not snapshot:
        await ctx.respond(
            f"❌ No snapshot named `{droplet_name}` found. Create one first.", ephemeral=True
        )
        return

    await ctx.respond(f"🚀 Spinning up **{droplet_name}** from snapshot `{snapshot['id']}`...")
    ch = ctx.channel

    try:
        await ch.send("⚙️ Creating droplet from snapshot...")
        droplet = await asyncio.to_thread(do.create_droplet_from_snapshot, snapshot)
        state.droplet_id = droplet["id"]

        await ch.send(
            f"✅ Droplet `{droplet['id']}` created. Waiting for it to become active..."
        )
        active = await asyncio.to_thread(do.wait_for_droplet_active, droplet["id"])

        public_ip = next(
            (n["ip_address"] for n in active["networks"]["v4"] if n["type"] == "public"),
            "unknown",
        )

        await ch.send(f"🟢 Droplet active (internal IP: `{public_ip}`). Assigning reserved IP `{reserved_ip}`...")
        await asyncio.to_thread(do.assign_reserved_ip, active["id"], reserved_ip)

        await ch.send("📡 Reserved IP assigned. Running startup commands...")

        output_lines: list[str] = []
        await asyncio.to_thread(run_startup_commands, reserved_ip, output_lines.append)

        if output_lines:
            # Send output in ≤1900-char chunks to stay within Discord's limit
            chunk: list[str] = []
            length = 0
            for line in output_lines:
                if length + len(line) + 1 > 1900:
                    await ch.send(f"```\n{chr(10).join(chunk)}\n```")
                    chunk, length = [], 0
                chunk.append(line)
                length += len(line) + 1
            if chunk:
                await ch.send(f"```\n{chr(10).join(chunk)}\n```")

        state.started_at = datetime.now()
        state.started_by = str(ctx.author)

        hours = get_lifetime_hours()
        await ch.send(
            f"✅ Server is live at `{reserved_ip}`.\n"
            f"⏰ It will automatically shut down and snapshot in **{hours} hour{'s' if hours != 1 else ''}**."
        )
        await schedule_shutdown(state, ch)

    except Exception as exc:
        await ch.send(f"❌ Start sequence failed: {exc}")
