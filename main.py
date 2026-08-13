import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from bot import create_bot  # noqa: E402 — must load env before importing bot


def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set in environment / .env")

    # py-cord's Client.__init__ fetches an event loop via asyncio.get_event_loop()
    # before bot.run() ever starts one. Python 3.13 no longer auto-creates a loop
    # in that situation, so one has to be set explicitly first.
    asyncio.set_event_loop(asyncio.new_event_loop())

    bot = create_bot()
    bot.run(token)


if __name__ == "__main__":
    main()
