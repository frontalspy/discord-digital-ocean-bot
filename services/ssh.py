from __future__ import annotations

import os
import time
from typing import Callable

import paramiko


def _startup_commands() -> list[str]:
    raw = os.environ.get("SSH_STARTUP_COMMANDS", "")
    return [cmd.strip() for cmd in raw.split("|") if cmd.strip()]


def run_startup_commands(host: str, on_output: Callable[[str], None]) -> None:
    key_path = os.environ["SSH_PRIVATE_KEY_PATH"]
    username = os.environ.get("SSH_USERNAME", "root")
    passphrase = os.environ.get("SSH_PASSPHRASE") or None
    commands = _startup_commands()

    if not commands:
        on_output("No SSH_STARTUP_COMMANDS configured — skipping.")
        return

    # Give the SSH daemon time to start after the droplet boots
    time.sleep(15)

    for command in commands:
        on_output(f"$ {command}")
        _exec(host, username, key_path, passphrase, command, on_output)


def _exec(
    host: str,
    username: str,
    key_path: str,
    passphrase: str | None,
    command: str,
    on_output: Callable[[str], None],
) -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    for attempt in range(12):
        try:
            client.connect(
                host,
                username=username,
                key_filename=key_path,
                passphrase=passphrase,
                timeout=30,
                banner_timeout=30,
                auth_timeout=30,
            )
            break
        except Exception as exc:
            if attempt == 11:
                raise
            on_output(f"SSH not ready (attempt {attempt + 1}/12): {exc} — retrying in 10s")
            time.sleep(10)

    try:
        _, stdout, stderr = client.exec_command(command, timeout=300)
        for line in stdout:
            on_output(line.rstrip())
        for line in stderr:
            on_output(f"[stderr] {line.rstrip()}")
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            raise RuntimeError(f"Command exited {exit_code}: {command}")
    finally:
        client.close()
