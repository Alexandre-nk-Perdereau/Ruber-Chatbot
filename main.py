import argparse
import logging
from bot.bot import bot
from utils.config import get_discord_bot_token

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    args = parser.parse_args()

    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {args.log_level}')
    logging.basicConfig(level=numeric_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    bot.run(get_discord_bot_token())