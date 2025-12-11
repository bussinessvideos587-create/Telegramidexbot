import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
import asyncio

# --- Logging setup ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# *** Update your credentials here ***
API_ID = 35292658
API_HASH = "a14fdc9ed8e1456c9570381024954d0b"
BOT_TOKEN = "8257600572:AAFVmlwEDiEy-AFzXN94XpUmsSRe6aXMxhw"

app = Client(
    "caption_recorder",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

channel_posts = {}
VALID_TYPES = {"video", "pdf", "text", "all"}

def make_tg_link(chat_id: int, message_id: int) -> str:
    if str(chat_id).startswith("-100"):
        suf = str(chat_id).replace("-100", "")
        return f"https://t.me/c/{suf}/{message_id}"
    return f"(private chat) msg_id={message_id}"

def message_matches_type(message, content_type):
    if content_type == "video":
        return message.video is not None
    if content_type == "pdf":
        if message.document:
            if message.document.mime_type == "application/pdf" or message.document.file_name.lower().endswith(".pdf"):
                return True
        return False
    if content_type == "text":
        # Accept only messages with text and no media
        return (not message.video) and (not message.document) and (message.text is not None)
    if content_type == "all":
        # Accept video, pdf, or text
        return (
            message.video is not None
            or (message.document is not None and
                (message.document.mime_type == "application/pdf" or message.document.file_name.lower().endswith(".pdf")))
            or (message.text is not None)
        )
    return False

@app.on_message(filters.command("rec") & filters.private)
async def start_recording(client, message):
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text(
            "Usage: /rec <channel_id> <content_type> [limit]\n"
            "Content types: video, pdf, text, all\n"
            "Limit is optional, default is 500."
        )
        return

    try:
        channel_id = int(args[1])
    except ValueError:
        await message.reply_text("Invalid channel ID.")
        return

    content_type = args[2].lower()
    if content_type not in VALID_TYPES:
        await message.reply_text(
            f"Invalid content type. Choose one of: {', '.join(VALID_TYPES)}"
        )
        return

    # Parse limit if provided
    if len(args) >= 4:
        try:
            limit = int(args[3])
            if limit <= 0:
                raise ValueError()
        except ValueError:
            await message.reply_text("Limit must be a positive integer.")
            return
    else:
        limit = 500  # default

    channel_posts[channel_id] = {"type": content_type, "posts": []}

    try:
        await client.send_message(
            chat_id=channel_id,
            text=f"🟢 **Recording started for {content_type} posts (including past messages).**\n"
                 "Send matching media or messages to begin capturing new posts.",
        )
    except Exception as e:
        await message.reply_text(f"Failed to send message to channel: {e}")

    await message.reply_text(
        f"Recording started for channel `{channel_id}` with content type `{content_type}`.\n"
        f"Fetching and processing last {limit} messages..."
    )

    count = 0
    try:
        async for msg in client.iter_history(channel_id, limit=limit):
            if message_matches_type(msg, content_type):
                caption = msg.caption if msg.caption else msg.text
                if not caption:
                    continue
                link = make_tg_link(msg.chat.id, msg.id)
                channel_posts[channel_id]["posts"].append((caption, link))
                count += 1
        await message.reply_text(f"Recorded {count} existing posts from history.")
        logging.info(f"[{channel_id}] Recorded {count} existing posts from history.")
    except FloodWait as e:
        await message.reply_text(f"Flood wait: sleep for {e.x} seconds. Try again later.")
    except Exception as e:
        await message.reply_text(f"Error fetching history: {e}")

@app.on_message(filters.channel & (filters.text | filters.video | filters.document))
async def handle_channel_post(client, message):
    if message.chat.id not in channel_posts:
        return

    content_type = channel_posts[message.chat.id]["type"]

    if content_type == "video" and not message.video:
        return

    if content_type == "pdf":
        if not message.document:
            return
        if (
            message.document.mime_type != "application/pdf"
            and not message.document.file_name.lower().endswith(".pdf")
        ):
            return

    if content_type == "text":
        if message.video or message.document:
            return

    caption = message.caption if message.caption else message.text
    if not caption:
        return

    link = make_tg_link(message.chat.id, message.id)
    channel_posts[message.chat.id]["posts"].append((caption, link))
    logging.info(f"[{message.chat.id}] Recorded Post: {link} | Caption Length: {len(caption)}")

@app.on_message(filters.command("done") & filters.private)
async def finish_recording(client, message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("Usage: /done <channel_id>")
        return

    try:
        channel_id = int(args[1])
    except ValueError:
        await message.reply_text("Invalid channel ID.")
        return

    data = channel_posts.get(channel_id)
    if not data or not data["posts"]:
        await message.reply_text("No posts recorded for that channel.")
        return

    posts_data = data["posts"]

    lines = ["📝 **Recorded Posts (Caption and Link)** 🔗", ""]

    for caption, link in posts_data:
        display_caption = caption.strip().replace('\n', ' ')
        display_caption = display_caption[:100] + ('...' if len(display_caption) > 100 else '')
        lines.append(f"• [{display_caption}]({link})")

    lines.append("")
    lines.append(f"**Total Posts Recorded:** {len(posts_data)}")
    lines.append("Extracted by : @PUTINxINDIA 🇮🇳")

    text = "\n".join(lines)

    await client.send_message(
        chat_id=channel_id,
        text=text,
        disable_web_page_preview=True,
        parse_mode=ParseMode.MARKDOWN,
    )
    await message.reply_text(f"Summary of {len(posts_data)} posts posted to channel `{channel_id}`.")

    del channel_posts[channel_id]

if __name__ == "__main__":
    logging.info("Bot ready for /rec and /done commands via DM.")
    app.run()