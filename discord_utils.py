from __future__ import annotations

import discord


async def send_chunked(ch: discord.abc.Messageable, lines: list[str]) -> None:
    """Send captured command output in <=1900-char code-block chunks."""
    if not lines:
        return
    chunk: list[str] = []
    length = 0
    for line in lines:
        if length + len(line) + 1 > 1900:
            await ch.send(f"```\n{chr(10).join(chunk)}\n```")
            chunk, length = [], 0
        chunk.append(line)
        length += len(line) + 1
    if chunk:
        await ch.send(f"```\n{chr(10).join(chunk)}\n```")
