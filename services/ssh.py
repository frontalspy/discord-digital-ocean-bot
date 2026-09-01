from __future__ import annotations

import os
import time
from typing import Callable

import paramiko


def _startup_commands() -> list[str]:
    raw = os.environ.get("SSH_STARTUP_COMMANDS", "")
    return [cmd.strip() for cmd in raw.split("|") if cmd.strip()]


def _load_private_key(key_path: str, passphrase: str | None) -> paramiko.PKey:
    key_classes = (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey, paramiko.DSSKey)
    last_exc: Exception = RuntimeError("no key classes tried")
    for key_class in key_classes:
        try:
            return key_class.from_private_key_file(key_path, password=passphrase)
        except paramiko.SSHException as exc:
            last_exc = exc
    raise RuntimeError(
        f"Could not load SSH private key at {key_path!r} as any known key type "
        f"(Ed25519/RSA/ECDSA/DSS): {last_exc}"
    )


def run_startup_commands(host: str, on_output: Callable[[str], None]) -> None:
    key_path = os.environ["SSH_PRIVATE_KEY_PATH"]
    username = os.environ.get("SSH_USERNAME", "root")
    passphrase = os.environ.get("SSH_PASSPHRASE") or None
    commands = _startup_commands()

    if not commands:
        on_output("No SSH_STARTUP_COMMANDS configured — skipping.")
        return

    # Fail fast on a bad/unreadable key file — this is never a "not ready
    # yet" condition, so retrying it 12 times would just waste ~2 minutes.
    pkey = _load_private_key(key_path, passphrase)

    # Give the SSH daemon time to start after the droplet boots
    time.sleep(15)

    for command in commands:
        on_output(f"$ {command}")
        _exec(host, username, pkey, command, on_output)


def _exec(
    host: str,
    username: str,
    pkey: paramiko.PKey,
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
                pkey=pkey,
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
