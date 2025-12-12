import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode

# --- Logging setup ---
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

API_ID = 35292658
API_HASH = "a14fdc9ed8e1456c9570381024954d0b"
BOT_TOKEN = "8257600572:AAFVmlwEDiEy-AFzXN94XpUmsSRe6aXMxhw"

app = Client("caption_recorder", api_id=35292658, api_hash="a14fdc9ed8e1456c9570381024954d0b", bot_token="8257600572:AAFVmlwEDiEy-AFzXN94XpUmsSRe6aXMxhw")

# Store recorded captions and links
channel_posts = {}

# --- Helper: Build tg link ---
def make_tg_link(chat_id: int, message_id: int) -> str:
    if str(chat_id).startswith("-100"):
        suf = str(chat_id).replace("-100", "")
        return f"https://t.me/c/{suf}/{message_id}"
    return f"(private chat) msg_id={message_id}"

# --- Start recording ---
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

    channel_posts[channel_id] = []

    await client.send_message(
        chat_id=channel_id,
        text="🔵 **Recording started!** Send media with caption.",
    )

    await message.reply_text(f"Recording started for `{channel_id}`.")

# --- Handle channel posts (FILTER ADDED HERE) ---
@app.on_message(
    filters.channel              # only channel messages
    & filters.media              # only media posts
    & filters.caption            # only those which contain caption
)
async def handle_channel_post(client, message):
    if message.chat.id not in channel_posts:
        return

    caption = message.caption
    if not caption:
        return

    link = make_tg_link(message.chat.id, message.id)

    channel_posts[message.chat.id].append((caption, link))
    logging.info(f"[{message.chat.id}] Recorded: {link}")

# --- Finish recording ---
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

    lines = ["📝 **Recorded Posts**", ""]
    for caption, link in posts_data:
        display = caption.replace("\n", " ")[:100]
        if len(caption) > 100:
            display += "..."
        lines.append(f"• [{display}]({link})")

    lines.append("")
    lines.append(f"**Total:** {len(posts_data)}")
    lines.append("Extracted by : @PUTINxINDIA 🇮🇳")

    text = "\n".join(lines)

    await client.send_message(
        chat_id=channel_id,
        text=text,
        disable_web_page_preview=True,
        parse_mode=ParseMode.MARKDOWN,
    )
    await message.reply_text("Summary posted.")

    del channel_posts[channel_id]

# --- Run ---
if __name__ == "__main__":
    logging.info("Bot ready.")
    app.run()
