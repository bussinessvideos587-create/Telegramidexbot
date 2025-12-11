import asyncio
from pyrogram import Client, filters
from pyrogram.enums import MessageMediaType

# ============================
# CONFIG
# ============================
API_ID = 35292658                      # ← YOUR API ID
API_HASH = "a14fdc9ed8e1456c9570381024954d0b"       # ← YOUR API HASH
BOT_TOKEN = "8257600572:AAFVmlwEDiEy-AFzXN94XpUmsSRe6aXMxhw"     # ← YOUR BOT TOKEN

# How many old messages to fetch when recording starts
DEFAULT_LIMIT = 150

# Store active recordings
recording_channels = {}  # {chat_id: {"types": [...]}}


# ============================
# BOT CLIENT
# ============================
bot = Client(
    "recorder-bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ============================
# HELP COMMAND
# ============================
@bot.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply_text(
        "**Recorder Bot Ready**\n\n"
        "Commands:\n"
        "`/record <channel_id> <type> <limit>`\n"
        "`/done <channel_id>`\n\n"
        "Types: video, photo, pdf, text, document, image"
    )


# ============================
# START RECORDING
# ============================
@bot.on_message(filters.command("record"))
async def record_handler(_, msg):
    try:
        parts = msg.text.split()

        if len(parts) < 3:
            return await msg.reply("Usage:\n`/record <channel_id> <type> <limit(optional)>`")

        chat_id = int(parts[1])
        content_type = parts[2].lower()
        limit = int(parts[3]) if len(parts) > 3 else DEFAULT_LIMIT

        # Register
        recording_channels[chat_id] = {"type": content_type}

        await msg.reply(f"🎬 **Recording started for {chat_id}**\n"
                        f"Type: `{content_type}`\n"
                        f"Limit: `{limit}`\n"
                        f"Fetching last `{limit}` messages...")

        # Fetch old messages first
        async for m in bot.iter_history(chat_id, limit=limit):
            await process_message(msg, m, content_type)

        await msg.reply("✅ **Now monitoring live messages...**")

    except Exception as e:
        await msg.reply(f"❌ Error: `{e}`")


# ============================
# STOP RECORDING
# ============================
@bot.on_message(filters.command("done"))
async def done_handler(_, msg):
    try:
        parts = msg.text.split()

        if len(parts) < 2:
            return await msg.reply("Usage:\n`/done <channel_id>`")

        chat_id = int(parts[1])

        if chat_id in recording_channels:
            del recording_channels[chat_id]
            await msg.reply(f"🛑 **Recording stopped for {chat_id}**")
        else:
            await msg.reply("❌ This channel is not being recorded.")

    except Exception as e:
        await msg.reply(f"Error: `{e}`")


# ============================
# PROCESS LIVE CHANNEL MESSAGES
# ============================
@bot.on_message(filters.channel)
async def channel_listener(_, msg):
    chat_id = msg.chat.id

    if chat_id not in recording_channels:
        return

    content_type = recording_channels[chat_id]["type"]
    admin_chat = -1003330631605   # where results will be delivered

    await process_message(admin_chat, msg, content_type)


# ============================
# PROCESS MESSAGE FUNCTION
# ============================
async def process_message(target_chat, msg, content_type):
    """
    Handles video, photo, pdf, document, text.
    """

    # ----- VIDEO -----
    if content_type == "video" and msg.video:
        return await bot.send_video(target_chat, msg.video.file_id)

    # ----- PHOTO / IMAGE -----
    if content_type in ["photo", "image"] and msg.photo:
        return await bot.send_photo(target_chat, msg.photo.file_id)

    # ----- PDF / DOCUMENT -----
    if content_type in ["pdf", "document"] and msg.document:
        return await bot.send_document(target_chat, msg.document.file_id)

    # ----- TEXT -----
    if content_type == "text" and msg.text:
        return await bot.send_message(target_chat, msg.text)


# ============================
# RUN BOT
# ============================
bot.run()
