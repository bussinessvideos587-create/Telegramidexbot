import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode

# --- Logging setup ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Replace with your actual credentials
API_ID = "35292658"
API_HASH = "a14fdc9ed8e1456c9570381024954dOb"
BOT_TOKEN = "8257600572:AAFVmlwEDiEy-AFzXN94XpUmsSRe6aXMxhw"

app = Client("caption_recorder", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Store recorded captions and links
# { chat_id: [(caption, link), (caption, link), ...] }
channel_posts = {}

# --- Helper: Build tg link ---
def make_tg_link(chat_id: int, message_id: int) -> str:
    """Creates a t.me/c/ link for public/private channels."""
    if str(chat_id).startswith("-100"):
        suf = str(chat_id).replace("-100", "")
        return f"https://t.me/c/{suf}/{message_id}"
    return f"(private chat) msg_id={message_id}" # Fallback for non-channel messages

# --- Start recording command (/rec) ---
@app.on_message(filters.command("rec") & filters.private)
async def start_recording(client, message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("Usage: /rec <channel_id>")
        return

    try:
        channel_id = int(args[1])
    except ValueError:
        await message.reply_text("Invalid channel ID.")
        return

    # Initialize or reset the list for this channel
    channel_posts[channel_id] = []

    # Announce in channel feed (optional)
    await client.send_message(
        chat_id=channel_id,
        text="🟢 **Caption and Link Recording session started!**\nSend media with captions to begin capturing.",
    )
    await message.reply_text(f"Recording started for channel `{channel_id}`. **Every captioned post will be recorded.**")

# --- Handle media in any monitored channel ---
@app.on_message(filters.channel & (filters.media | filters.text)) # Added filters.text to catch text-only posts
async def handle_channel_post(client, message):
    if message.chat.id not in channel_posts:
        return  # skip channels not being recorded

    caption = message.caption if message.caption else message.text # Use text if no media/caption
    if not caption:
        return # Skip posts with no caption/text

    link = make_tg_link(message.chat.id, message.id)

    # Store the full caption and the link
    channel_posts[message.chat.id].append((caption, link))
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

    posts_data = channel_posts.get(channel_id)

    if not posts_data:
        await message.reply_text("No posts recorded for that channel.")
        return

    # --- Generate the Final Message ---
    lines = ["📝 **Recorded Posts (Caption and Link)** 🔗", ""]

    # Iterate through recorded (caption, link) tuples
    for caption, link in posts_data:
        # Use only the first 100 characters of the caption to keep the list clean
        # and create a link using the caption as the text.
        display_caption = caption.strip().replace('\n', ' ')
        display_caption = display_caption[:100] + ('...' if len(display_caption) > 100 else '')
        
        # Format: [First 100 chars of Caption](link)
        lines.append(f"• [{display_caption}]({link})")
        
    lines.append("")
    lines.append(f"**Total Posts Recorded:** {len(posts_data)}")
    lines.append("Extracted by : @PUTINxINDIA 🇮🇳")
    text = "\n".join(lines)

    # Post the summary to the channel
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
