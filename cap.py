import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait

# --- Logging setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# --- Configuration ---
# Get these from https://my.telegram.org
API_ID = 1234567 
API_HASH = "your_api_hash_here"
BOT_TOKEN = "your_bot_token_here"

app = Client("caption_recorder", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Store recorded captions and links: { chat_id: [(caption, link), ...] }
channel_data = {}

# --- Helper: Build tg link ---
def make_tg_link(chat, message_id: int) -> str:
    """Creates a clickable link for public or private channels."""
    if chat.username:
        return f"https://t.me/{chat.username}/{message_id}"
    else:
        # For private channels, strip the -100 prefix from ID
        suf = str(chat.id).replace("-100", "")
        return f"https://t.me/c/{suf}/{message_id}"

# --- Command: Start recording ---
@app.on_message(filters.command("rec") & filters.private)
async def start_recording(client, message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("❌ **Usage:** `/rec -100123456789` (Replace with your Channel ID)")
        return

    try:
        channel_id = int(args[1])
        # Verify bot is in the channel
        chat = await client.get_chat(channel_id)
    except Exception as e:
        await message.reply_text(f"❌ **Error:** Bot must be an admin in the channel.\n`{e}`")
        return

    channel_data[channel_id] = []
    await message.reply_text(
        f"✅ **Started Recording for:** {chat.title}\n"
        "Every post sent there now will be indexed. Send `/done {channel_id}` to finish."
    )

# --- Handler: Capture posts ---
@app.on_message(filters.channel)
async def handle_channel_post(client, message):
    if message.chat.id not in channel_data:
        return

    # Extract text or caption
    content = message.caption or message.text
    if not content:
        return 

    link = make_tg_link(message.chat, message.id)
    
    # Clean caption for Markdown (remove newlines and truncate)
    clean_caption = content.strip().replace('\n', ' ')
    if len(clean_caption) > 80:
        clean_caption = clean_caption[:77] + "..."

    channel_data[message.chat.id].append((clean_caption, link))
    logging.info(f"Recorded post from {message.chat.id}")

# --- Command: Stop and summarize ---
@app.on_message(filters.command("done") & filters.private)
async def finish_recording(client, message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("❌ **Usage:** `/done -100123456789`")
        return

    try:
        channel_id = int(args[1])
    except ValueError:
        return

    posts = channel_data.get(channel_id)
    if not posts:
        await message.reply_text("No posts found or recording wasn't started.")
        return

    await message.reply_text(f"⌛ Generating index for {len(posts)} posts...")

    # Build the summary
    header = f"📋 **Recorded Posts Index**\n\n"
    footer = f"\n\n**Total Posts:** {len(posts)}\nExtracted by @YourBot"
    
    current_chunk = header
    chunks = []

    for caption, link in posts:
        # Format as HTML for better reliability with special characters
        line = f"• <a href='{link}'>{caption}</a>\n"
        
        # Telegram limit is 4096, keeping buffer at 3900
        if len(current_chunk) + len(line) + len(footer) > 3900:
            chunks.append(current_chunk)
            current_chunk = ""
        current_chunk += line

    current_chunk += footer
    chunks.append(current_chunk)

    # Send the summary (can be multiple messages)
    for chunk in chunks:
        try:
            await client.send_message(
                chat_id=channel_id,
                text=chunk,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            await asyncio.sleep(1) # Avoid flood
        except FloodWait as e:
            await asyncio.sleep(e.value)

    await message.reply_text("✅ Index has been posted to the channel.")
    del channel_data[channel_id]

# --- Command: Stop without posting ---
@app.on_message(filters.command("cancel") & filters.private)
async def cancel_recording(client, message):
    args = message.text.split()
    if len(args) > 1:
        c_id = int(args[1])
        if c_id in channel_data:
            del channel_data[c_id]
            await message.reply_text("Recording cancelled.")

if __name__ == "__main__":
    print("Bot is running...")
    app.run()