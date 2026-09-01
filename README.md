# DigitalOcean Discord Bot

A Discord bot that spins up a DigitalOcean game server on demand, runs setup commands over SSH, and automatically snapshots and destroys it after 6 hours.

## How it works

1. `/server start` — creates a droplet from your snapshot using the cheapest available size, assigns a reserved IP, and runs your startup commands over SSH.
2. After the configured lifetime (default **6 hours**) the bot powers off the droplet, creates a fresh snapshot (replacing the old one), releases the reserved IP, and destroys the droplet.
3. `/server stop` — triggers the same shutdown sequence immediately.
4. `/server status` — queries DigitalOcean directly and reports whether the droplet exists and its actual power state (on / off / other), plus uptime and time until auto-shutdown.

Only one droplet can run at a time. The reserved IP is never deleted — it persists between sessions.

## Requirements

- Python 3.11+
- A [DigitalOcean](https://www.digitalocean.com/) account with:
  - A personal access token
  - A reserved IP
  - An existing snapshot to boot from (must match `DO_DROPLET_NAME`)
- A [Discord application](https://discord.com/developers/applications) with a bot token
- An SSH key authorised on your droplets

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in .env, then:
python main.py
```

## Configuration

All configuration is via environment variables (or a `.env` file).

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Bot token from the Discord Developer Portal |
| `DISCORD_GUILD_ID` | No | Server ID — if set, slash commands register instantly for that guild instead of globally |
| `DO_API_TOKEN` | Yes | DigitalOcean personal access token |
| `DO_RESERVED_IP` | Yes | The reserved IP address to assign to the droplet |
| `DO_DROPLET_NAME` | No | Name used for both the droplet and snapshot (default: `pew-pew`) |
| `DROPLET_LIFETIME_HOURS` | No | How many hours the droplet runs before auto-shutdown (default: `6`) |
| `DO_SSH_KEY_NAME` | No | Name of an SSH key already on your DigitalOcean account, attached to new droplets. Without it, DO generates and emails a random root password instead |
| `DO_CPU_VENDOR` | No | CPU vendor for the auto-selected size: `amd`, `intel`, or `any` (default: `amd`) |
| `SSH_PRIVATE_KEY_PATH` | Yes | Path to the private key authorised on your droplets |
| `SSH_USERNAME` | No | SSH username (default: `root`) |
| `SSH_PASSPHRASE` | No | Passphrase for the SSH private key, if encrypted |
| `SSH_STARTUP_COMMANDS` | No | Commands to run on the droplet after boot, separated by `\|` |

## Discord commands

| Command | Description |
|---|---|
| `/server start` | Boot the server from snapshot |
| `/server stop` | Snapshot, release IP, and destroy the droplet |
| `/server status` | Query DigitalOcean for the droplet's live on/off state |
| `/server run-startup` | Re-run the SSH startup commands against the already-running droplet, without recreating it |

## Project structure

```
main.py           — entry point
bot.py            — Discord bot and slash command registration
scheduler.py      — auto-shutdown timer and restart recovery
state.py          — in-memory server state (droplet id, timers, lock)
persistence.py    — writes/reads server_state.json so a restart can recover
discord_utils.py  — shared Discord helpers (chunked message sending)
commands/
  start.py
  stop.py
  status.py
  run_startup.py
services/
  digitalocean.py — DigitalOcean API wrapper
  ssh.py          — SSH command runner
```
