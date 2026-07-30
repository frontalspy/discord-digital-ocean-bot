import os

from dotenv import load_dotenv

load_dotenv()

from bot import create_bot  # noqa: E402 — must load env before importing bot


def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set in environment / .env")

    bot = create_bot()
    bot.run(token)


if __name__ == "__main__":
    main()
