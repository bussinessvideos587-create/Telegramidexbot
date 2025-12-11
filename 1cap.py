import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode

# --- Logging setup ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# *** Hardcoded credentials - Replace these with your actual values ***
API_ID = 35292658
API_HASH = "a14fdc9ed8e1456c9570381024954d0b"
BOT_TOKEN = "8257600572:AAFVmlwEDiEy-AFzXN94XpUmsSRe6aXMxhw"

app = Client(
    "caption_recorder",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Structure:
# channel_posts = {
#    channel_id: {
#        "type": "video" / "pdf" / "text" / "all",
#        "posts": [(caption, link), ...]
#    }
# }
channel_posts = {}

VALID_TYPES = {"video", "pdf", "text", "all"}

# --- Helper: Build tg link ---
def make_tg_link(chat_id: int, message_id: int) -> str:
    """Creates a t.me/c/ link for public/private channels."""
    if str(chat_id).startswith("-100"):
        suf = str(chat_id).replace("-100", "")
        return f"https://t.me/c/{suf}/{message_id}"
    return f"(private chat) msg_id={message_id}"  # Fallback for non-channel messages


# --- Start recording command (/rec) ---
@app.on_message(filters.command("rec") & filters.private)
async def start_recording(client, message):
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text(
            "Usage: /rec <channel_id> <content_type>\n"
            "Content types: video, pdf, text, all"
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

    channel_posts[channel_id] = {"type": content_type, "posts": []}

    await client.send_message(
        chat_id=channel_id,
        text=f"🟢 **Recording started for {content_type} posts.**\n"
             "Send matching media or messages to begin capturing.",
    )
    await message.reply_text(
        f"Recording started for channel `{channel_id}` with content type `{content_type}`."
    )


# --- Handle media in any monitored channel ---
@app.on_message(filters.channel & (filters.text | filters.video | filters.document))
async def handle_channel_post(client, message):
    if message.chat.id not in channel_posts:
        return

    content_type = channel_posts[message.chat.id]["type"]

    # Filter based on chosen content type
    if content_type == "video" and not message.video:
        return

    if content_type == "pdf":
        if not message.document:
            return
        # Accept only PDF documents
        if (
            message.document.mime_type != "application/pdf"
            and not message.document.file_name.lower().endswith(".pdf")
        ):
            return

    if content_type == "text":
        # Accept only text messages with no media
        if message.video or message.document:
            return

    # For "all" accept any of the filtered types (text/video/pdf)

    caption = message.caption if message.caption else message.text
    if not caption:
        return

    link = make_tg_link(message.chat.id, message.id)
    channel_posts[message.chat.id]["posts"].append((caption, link))
    logging.info(f"[{message.chat.id}] Recorded Post: {link} | Caption Length: {len(caption)}")


# --- Done command (/done) ---
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

    # --- Generate the Final Message ---
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

    # Reset record
    del channel_posts[channel_id]


# --- Entry point ---
if __name__ == "__main__":
    logging.info("Bot ready for /rec and /done commands via DM.")
    app.run()
