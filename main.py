from bot.bot import bot
from utils.config import get_discord_bot_token

if __name__ == "__main__":
    bot.run(get_discord_bot_token())