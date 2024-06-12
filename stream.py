import asyncio
import random
import string
import time

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import InputAudioStream, InputStream

from config import API_ID, API_HASH, BOT_TOKEN, USERBOT_SESSION, DURATION_LIMIT

# Initialize the bot and userbot clients
bot = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
userbot = Client("userbot", api_id=API_ID, api_hash=API_HASH, session_string=USERBOT_SESSION)
pytgcalls = PyTgCalls(userbot)

# Global variables to manage state
queues = {}
last_activity = {}
CALLS = {}

# Helper functions
def generate_queue_markup(chat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Skip", callback_data=f"skip_{chat_id}")]
    ])

async def auto_leave():
    while True:
        for chat_id in list(CALLS.keys()):
            if time.time() - last_activity.get(chat_id, 0) > 1800:  # 30 minutes
                await pytgcalls.leave_group_call(chat_id)
                del CALLS[chat_id]
                del queues[chat_id]
        await asyncio.sleep(60)

@bot.on_message(filters.command("play") & filters.group)
async def play_command(client, message):
    chat_id = message.chat.id
    user = message.from_user
    if chat_id not in CALLS:
        await pytgcalls.join_group_call(chat_id, InputAudioStream(InputStream()))
        CALLS[chat_id] = True

    query = message.text.split(maxsplit=1)[1]
    queues[chat_id] = queues.get(chat_id, []) + [query]
    last_activity[chat_id] = time.time()

    await message.reply_text(f"Added {query} to the queue.", reply_markup=generate_queue_markup(chat_id))

@bot.on_callback_query(filters.regex(r"^skip_"))
async def skip_callback(client, callback_query):
    chat_id = int(callback_query.data.split("_")[1])
    if chat_id in queues and queues[chat_id]:
        queues[chat_id].pop(0)
        await callback_query.message.edit_text("Skipped to the next song.")
    last_activity[chat_id] = time.time()

# Start bot and userbot clients
bot.start()
userbot.start()
pytgcalls.start()

# Start auto leave task
bot.loop.create_task(auto_leave())

# Run the bot
bot.run()
