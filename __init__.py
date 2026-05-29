#Github.com/Vasusen-code

from pyrogram import Client

from telethon.sessions import StringSession
from telethon.sync import TelegramClient

from decouple import config
import logging, time, sys

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                    level=logging.WARNING)

# variables
API_ID = config("API_ID", default=None, cast=int)
API_HASH = config("API_HASH", default=None)
BOT_TOKEN = config("BOT_TOKEN", default=None)
SESSION = config("SESSION", default=None)
AUTH = config("AUTH", default=None, cast=int)

bot = TelegramClient('bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# FIX: added workers=16 so Pyrogram opens multiple parallel upload connections
# to Telegram's DC. Default is 1 worker which serialises all chunk uploads.
# 16 workers allows concurrent chunk dispatch, saturating the link at 20+ Mbps.
userbot = Client(
    "saverestricted",
    session_string=SESSION,
    api_hash=API_HASH,
    api_id=API_ID,
    workers=16,          # parallel upload/download workers
    max_concurrent_transmissions=4,  # concurrent file transfers
)

try:
    userbot.start()
except BaseException:
    print("Userbot Error ! Have you added SESSION while deploying??")
    sys.exit(1)

Bot = Client(
    "SaveRestricted",
    bot_token=BOT_TOKEN,
    api_id=int(API_ID),
    api_hash=API_HASH,
    workers=16,          # parallel upload/download workers
    max_concurrent_transmissions=4,
)

try:
    Bot.start()
except Exception as e:
    print(e)
    sys.exit(1)
