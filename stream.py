import asyncio
import random
import string
import time
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import InputAudioStream, InputStream
from config import API_ID, API_HASH, BOT_TOKEN, DURATION_LIMIT
from youtubesearchpython import VideosSearch
import lyricsgenius

# Initialize the bot client
bot = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Initialize Lyrics Genius API
genius = lyricsgenius.Genius("your_genius_api_key")

# Helper function to prompt for phone number and code
#async def get_userbot_session():
async def get_userbot_session():
    userbot = Client(":memory:", api_id=API_ID, api_hash=API_HASH)
    await userbot.connect()
    phone_number = input("Enter your phone number: ")
    sent_code = await userbot.send_code(phone_number)
    code = input("Enter the code you received: ")
    await userbot.sign_in(phone_number, sent_code.phone_code_hash, code)
    session_string = await userbot.export_session_string()
    await userbot.disconnect()
    return session_string

async def main():
    # Get userbot session string
    USERBOT_SESSION = await get_userbot_session()

    # Initialize userbot client and pytgcalls
    userbot = Client("userbot", api_id=API_ID, api_hash=API_HASH, session_string=USERBOT_SESSION)
    pytgcalls = PyTgCalls(userbot)

    await userbot.start()
    await pytgcalls.start()
    print("Userbot and PyTgCalls started successfully!")
    
# Initialize userbot client and pytgcalls


# Global variables to manage state
queues = {}
last_activity = {}
CALLS = {}
vote_skip = {}

# Helper functions
def generate_queue_markup(chat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Skip", callback_data=f"skip_{chat_id}")],
        [InlineKeyboardButton("Show Lyrics", callback_data=f"lyrics_{chat_id}")]
    ])

async def auto_leave():
    while True:
        for chat_id in list(CALLS.keys()):
            if time.time() - last_activity.get(chat_id, 0) > 1800:  # 30 minutes
                await pytgcalls.leave_group_call(chat_id)
                del CALLS[chat_id]
                del queues[chat_id]
        await asyncio.sleep(60)

async def send_player_panel(chat_id, details):
    await bot.send_message(
        chat_id,
        f"**Currently Playing**\n\n"
        f"**Title:** {details['title']}\n"
        f"**Duration:** {details['duration']}\n"
        f"**Requested by:** {details['requested_by']}\n"
        f"[YouTube Link]({details['link']})",
        reply_markup=generate_queue_markup(chat_id)
    )

@bot.on_message(filters.command("play") & filters.group)
async def play_command(client, message):
    chat_id = message.chat.id
    user = message.from_user
    query = message.text.split(maxsplit=1)[1]
    videos_search = VideosSearch(query, limit=5)
    results = videos_search.result()["result"]
    buttons = [
        [InlineKeyboardButton(f"{i + 1}. {result['title']}", callback_data=f"select_{chat_id}_{i}")]
        for i, result in enumerate(results)
    ]
    await bot.send_message(chat_id, "Select a song:", reply_markup=InlineKeyboardMarkup(buttons))
    last_activity[chat_id] = time.time()

@bot.on_callback_query(filters.regex(r"^select_"))
async def select_callback(client, callback_query):
    data = callback_query.data.split("_")
    chat_id = int(data[1])
    index = int(data[2])
    user = callback_query.from_user
    query = callback_query.message.reply_markup.inline_keyboard[index][0].text.split('. ')[1]
    videos_search = VideosSearch(query, limit=1)
    result = videos_search.result()["result"][0]
    details = {
        "title": result["title"],
        "duration": result["duration"],
        "requested_by": user.first_name,
        "link": result["link"]
    }
    if chat_id not in CALLS:
        await pytgcalls.join_group_call(chat_id, InputAudioStream(InputStream()))
        CALLS[chat_id] = True
    queues[chat_id] = queues.get(chat_id, []) + [details]
    last_activity[chat_id] = time.time()
    await send_player_panel(chat_id, details)

@bot.on_callback_query(filters.regex(r"^skip_"))
async def skip_callback(client, callback_query):
    chat_id = int(callback_query.data.split("_")[1])
    if chat_id in queues and queues[chat_id]:
        queues[chat_id].pop(0)
        if queues[chat_id]:
            await send_player_panel(chat_id, queues[chat_id][0])
        else:
            await callback_query.message.edit_text("The queue is now empty.")
    last_activity[chat_id] = time.time()

@bot.on_callback_query(filters.regex(r"^lyrics_"))
async def lyrics_callback(client, callback_query):
    chat_id = int(callback_query.data.split("_")[1])
    if chat_id in queues and queues[chat_id]:
        title = queues[chat_id][0]["title"]
        song = genius.search_song(title)
        if song:
            await bot.send_message(chat_id, f"**Lyrics for {title}**\n\n{song.lyrics}")
        else:
            await bot.send_message(chat_id, "Lyrics not found.")
    last_activity[chat_id] = time.time()

# Start bot and userbot clients
bot.start()
userbot.start()
pytgcalls.start()

# Start auto leave task
bot.loop.create_task(auto_leave())

# Run the bot
bot.run()
