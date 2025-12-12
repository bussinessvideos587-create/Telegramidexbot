import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, PeerIdInvalid, ChannelPrivate, ChatAdminRequired

logging.basicConfig(level=logging.INFO)

API_ID = 35292658
API_HASH = "a14fdc9ed8e1456c9570381024954d0b"
BOT_TOKEN = "8257600572:AAFVmlwEDiEy-AFzXN94XpUmsSRe6aXMxhw"

app = Client("scraper_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def make_tg_link(chat, message_id: int) -> str:
    if chat.username:
        return f"https://t.me/{chat.username}/{message_id}"
    suf = str(chat.id).replace("-100", "")
    return f"https://t.me/c/{suf}/{message_id}"

def matches_filters(message, selected_filters):
    if "all" in selected_filters: return True
    check_map = {
        "video": bool(message.video or message.animation),
        "document": bool(message.document),
        "pdf": bool(message.document and message.document.file_name.lower().endswith(".pdf")),
        "photo": bool(message.photo),
        "text": bool(message.text and not message.media)
    }
    return any(check_map.get(f) for f in selected_filters)

@app.on_message(filters.command("scrape") & filters.private)
async def scrape_history(client, message):
    args = message.text.split()
    if len(args) < 4:
        await message.reply_text("❌ **Usage:** `/scrape <ID or Username> <limit> <filters>`\nEx: `/scrape -1003330631605 100 all`")
        return

    target = args[1] # Can be ID or @username
    try:
        # Try to convert to int if it's an ID
        if target.startswith("-100") or target.isdigit():
            target = int(target)
    except ValueError:
        pass 

    try:
        limit = int(args[2])
        selected_filters = [f.lower() for f in args[3:]]
        
        # This part forces the bot to "look up" the channel
        chat = await client.get_chat(target)
    except PeerIdInvalid:
        await message.reply_text("❌ **Peer ID Invalid:** The bot doesn't recognize this ID. **Make sure the bot is an ADMIN in the channel and you have sent a message there.**")
        return
    except ChannelPrivate:
        await message.reply_text("❌ **Channel Private:** The bot is not a member of this private channel.")
        return
    except Exception as e:
        await message.reply_text(f"❌ **Error:** {e}")
        return

    status_msg = await message.reply_text(f"🔎 **Searching {chat.title}...**")
    recorded_posts = []

    try:
        async for msg in client.get_chat_history(chat.id, limit=limit):
            if matches_filters(msg, selected_filters):
                content = msg.caption or msg.text
                if content:
                    link = make_tg_link(chat, msg.id)
                    clean_caption = content.strip().split('\n')[0][:70]
                    recorded_posts.append((clean_caption, link))
    except ChatAdminRequired:
        await status_msg.edit("❌ **Error:** Bot needs 'Read Message History' permission.")
        return
    except Exception as e:
        await status_msg.edit(f"❌ **Error during scrape:** {e}")
        return

    if not recorded_posts:
        await status_msg.edit("❌ No matching posts found.")
        return

    await status_msg.edit(f"✅ Found {len(recorded_posts)} posts. Posting to channel...")

    # Build chunks
    header = f"📋 **INDEX: {chat.title}**\n\n"
    footer = f"\n\n**Total:** {len(recorded_posts)}\n@PUTINxINDIA"
    
    chunks = []
    current_chunk = header
    for caption, link in reversed(recorded_posts):
        line = f"• <a href='{link}'>{caption}</a>\n"
        if len(current_chunk) + len(line) + len(footer) > 3900:
            chunks.append(current_chunk)
            current_chunk = ""
        current_chunk += line
    current_chunk += footer
    chunks.append(current_chunk)

    for chunk in chunks:
        await client.send_message(chat.id, chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        await asyncio.sleep(1)

    await message.reply_text("✅ Done.")

app.run()
