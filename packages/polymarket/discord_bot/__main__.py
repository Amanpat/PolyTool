"""Run the Vera bot as a long-lived service: ``python -m packages.polymarket.discord_bot``.

This is the command the Docker ``vera-bot`` compose service invokes.
"""

from packages.polymarket.discord_bot.bot import run

if __name__ == "__main__":
    run()
