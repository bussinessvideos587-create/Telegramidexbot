import logging
import asyncio
from typing import Dict, List, Tuple, Optional
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait, PeerIdInvalid

# ----------------------------
# HARD-CODED CREDENTIALS (edit)
# ----------------------------
API_ID = 35292658
API_HASH = "a14fdc9ed8e1456c9570381024954d0b"
BOT_TOKEN = "8257600572:AAFVmlwEDiEy-AFzXN94XpUmsSRe6aXMxhw"
# ----------------------------

# Defaults
DEFAULT_HISTORY_LIMIT = 500

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Client(
    "caption_recorder_multi",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Data structure:
# channel_data = {
#   chat_identifier (str): {
#       "chat": <chat id or username as passed>,
#       "type": "video"/"pdf"/"text"/"images"/"all",
#       "posts": [(caption, link, msg_id, file_type, timestamp), ...],
#   }
# }
channel_data: Dict[str, Dict] = {}

VALID_TYPES = {"video", "pdf", "text", "images", "all"}


# Helpers
def normalize_chat_arg(arg: str) -> str:
    """Return arg as-is. Accept -100... or @username or numeric strings."""
    return arg.strip()


def make_tg_link_from_chat(chat_identifier: str, chat_id: int, msg_id: int) -> str:
    """Build a t.me link. If username provided, use @username/msg_id; if numeric -100..., use /c/ form."""
    # If user passed a username string like @channelusername -> use that
    if isinstance(chat_identifier, str) and chat_identifier.startswith("@"):
        return f"https://t.me/{chat_identifier.lstrip('@')}/{msg_id}"
    # If chat_id is negative and begins with -100, build /c/ link
    try:
        s = str(chat_id)
        if s.startswith("-100"):
            suf = s.replace("-100", "")
            return f"https://t.me/c/{suf}/{msg_id}"
    except Exception:
        pass
    # Fallback
    return f"(chat {chat_id}) msg_id={msg_id}"


def message_matches_type(msg, desired_type: str) -> bool:
    """Return True if message matches desired_type."""
    if desired_type == "all":
        return bool(msg.video or msg.photo or msg.document or msg.text)
    if desired_type == "video":
        return bool(msg.video)
    if desired_type == "pdf":
        if msg.document:
            # Check mime or filename
            mime = getattr(msg.document, "mime_type", "") or ""
            fname = getattr(msg.document, "file_name", "") or ""
            return mime == "application/pdf" or fname.lower().endswith(".pdf")
        return False
    if desired_type == "text":
        # Only text posts (no photo/video/document)
        return bool(msg.text) and not (msg.video or msg.photo or msg.document)
    if desired_type == "images":
        return bool(msg.photo)
    return False


def detect_file_type(msg) -> str:
    if msg.video:
        return "video"
    if msg.photo:
        return "image"
    if msg.document:
        return "document"
    if msg.text:
        return "text"
    return "other"


# Command: /rec <channel_id_or_username> <type> [limit]
@app.on_message(filters.command("rec") & filters.private)
async def cmd_rec(client, message):
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text(
            "Usage: /rec <channel_id_or_username> <type> [limit]\n"
            "Types: video | pdf | text | images | all\n"
            "Limit (optional): how many past messages to fetch (default 500)\n\n"
            "Example:\n/rec -1001234567890 video 800\n/rec @mychannel pdf 1000"
        )
        return

    chat_arg = normalize_chat_arg(args[1])
    content_type = args[2].lower()
    if content_type not in VALID_TYPES:
        await message.reply_text(f"Invalid type `{content_type}`. Choose one of: {', '.join(VALID_TYPES)}")
        return

    # parse optional limit
    if len(args) >= 4:
        try:
            limit = int(args[3])
            if limit <= 0:
                raise ValueError()
        except ValueError:
            await message.reply_text("Limit must be a positive integer.")
            return
    else:
        limit = DEFAULT_HISTORY_LIMIT

    # Store channel config
    channel_key = chat_arg  # use user's passed string as key so user can call /done same way
    if channel_key in channel_data:
        await message.reply_text(f"Already recording for `{channel_key}`. Use /done to stop or /rec again to re-run history fetch.")
        # still proceed to fetch extra history if requested
    else:
        channel_data[channel_key] = {"chat": chat_arg, "type": content_type, "posts": []}

    # Announce to user and try to announce in channel (may fail if bot cannot post)
    await message.reply_text(f"Recording started for `{channel_key}` with type `{content_type}`. Fetching last {limit} messages...")

    # Attempt to send announcement to the channel (optional)
    try:
        await client.send_message(chat_id=chat_arg, text=f"🟢 Recording started (type: {content_type}). This channel will be scanned for past posts and live ones.")
    except PeerIdInvalid:
        # bot cannot send as that peer might be invalid for sending (but we can still fetch history if allowed)
        logger.warning(f"PeerIdInvalid when trying to send to {chat_arg} — bot may not have send permission.")
    except Exception as e:
        logger.warning(f"Could not send announcement to {chat_arg}: {e}")

    # Fetch history (past messages)
    fetched = 0
    recorded = 0
    try:
        # get_history accepts chat_id as username or numeric id
        messages = await client.get_history(chat_arg, limit=limit)
        fetched = len(messages)
        logger.info(f"Fetched {fetched} messages from {chat_arg}.")
        for msg in messages:
            try:
                if message_matches_type(msg, content_type):
                    caption = msg.caption if getattr(msg, "caption", None) else (msg.text if getattr(msg, "text", None) else "")
                    if not caption:
                        # For images or videos without any text, still record with empty caption if you want; currently skip empty
                        continue
                    link = make_tg_link_from_chat(chat_arg, msg.chat.id, msg.id)
                    ftype = detect_file_type(msg)
                    timestamp = getattr(msg, "date", None)
                    channel_data[channel_key]["posts"].append((caption, link, msg.id, ftype, timestamp))
                    recorded += 1
            except Exception as e:
                logger.exception(f"Error processing historical message: {e}")
        await message.reply_text(f"History processed: fetched {fetched}, recorded {recorded} matching posts.")
    except FloodWait as e:
        await message.reply_text(f"Flood wait from Telegram: sleep {e.x} seconds. Try again later.")
        return
    except PeerIdInvalid:
        await message.reply_text("Peer id invalid. Check that the channel ID / username is correct and that the bot is a member/admin of that channel.")
        # remove channel config if it was newly created
        if channel_key in channel_data and not channel_data[channel_key]["posts"]:
            channel_data.pop(channel_key, None)
        return
    except Exception as e:
        await message.reply_text(f"Error fetching history: {e}")
        logger.exception("Error in get_history")
        # allow live recording even if history failed

    # Confirm live monitoring is active
    await message.reply_text(f"✅ Now monitoring live posts in `{channel_key}` for type `{content_type}`. Use /done {chat_arg} to finish and get summary.")


# Handler for new messages posted in channels: will record if channel is being monitored and message matches chosen type
@app.on_message(filters.channel & (filters.text | filters.video | filters.photo | filters.document))
async def on_channel_message(client, message):
    # find which monitored channels match this chat (user may have used username or id)
    # We'll check by numeric chat id and by any matching channel_data key equal to username
    chat_id = message.chat.id
    username = getattr(message.chat, "username", None)
    keys_to_check = []
    # keys can be username with @ or raw username; standardize both possibilities
    if username:
        keys_to_check.append(f"@{username}")
        keys_to_check.append(username)
    keys_to_check.append(str(chat_id))
    # include -100 form as user may have passed -100... string
    if str(chat_id).startswith("-100"):
        keys_to_check.append(str(chat_id))
    recorded_any = False

    for key in list(channel_data.keys()):
        if key in keys_to_check:
            cfg = channel_data[key]
            desired = cfg["type"]
            if message_matches_type(message, desired):
                caption = message.caption if getattr(message, "caption", None) else (message.text if getattr(message, "text", None) else "")
                if not caption:
                    continue
                link = make_tg_link_from_chat(cfg["chat"], message.chat.id, message.id)
                ftype = detect_file_type(message)
                timestamp = getattr(message, "date", None)
                cfg["posts"].append((caption, link, message.id, ftype, timestamp))
                logger.info(f"[{key}] Recorded live post {message.id} type={ftype} len={len(caption)}")
                recorded_any = True

    # nothing to return; handler just records


# Command: /done <channel_id_or_username>
@app.on_message(filters.command("done") & filters.private)
async def cmd_done(client, message):
    args = message.text.split()
    if len(args) < 2:
        await message.reply_text("Usage: /done <channel_id_or_username>")
        return

    chat_arg = normalize_chat_arg(args[1])
    # same key logic
    channel_key = chat_arg
    if channel_key not in channel_data:
        # try alternative keys (username without @ or numeric)
        alt_keys = []
        if chat_arg.startswith("@"):
            alt_keys.append(chat_arg.lstrip("@"))
        alt_keys.append(str(chat_arg))
        found = None
        for k in alt_keys:
            if k in channel_data:
                found = k
                break
        if not found:
            await message.reply_text(f"No recording found for `{chat_arg}`.")
            return
        channel_key = found

    cfg = channel_data.get(channel_key)
    if not cfg or not cfg.get("posts"):
        await message.reply_text(f"No recorded posts for `{channel_key}`.")
        # remove empty monitoring entry
        channel_data.pop(channel_key, None)
        return

    posts = cfg["posts"]
    # Build summary message (first 200 posts; if more, show top N)
    lines = [f"📝 **Recorded posts for {channel_key}**", ""]
    max_show = 400  # avoid giant messages; adjust as needed
    show = posts[:max_show]
    for caption, link, msgid, ftype, ts in show:
        display = caption.strip().replace("\n", " ")
        display = display[:120] + ("..." if len(display) > 120 else "")
        lines.append(f"• [{display}]({link}) — `{ftype}`")
    lines.append("")
    lines.append(f"**Total recorded:** {len(posts)}")
    text = "\n".join(lines)

    # Try to post summary into the channel if possible
    posted_to_channel = False
    try:
        await client.send_message(chat_id=cfg["chat"], text=text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        posted_to_channel = True
    except PeerIdInvalid:
        await message.reply_text("Cannot post summary to channel: Peer id invalid (bot cannot send there). I'll send summary to you instead.")
    except Exception as e:
        logger.warning(f"Could not post summary to channel {cfg['chat']}: {e}")
        await message.reply_text(f"Could not post summary to channel: {e}")

    # Always send summary to the user (private)
    # If the summary is very large, send as a file
    if len(text) <= 4000:
        await message.reply_text(text, disable_web_page_preview=True, parse_mode=ParseMode.MARKDOWN)
    else:
        # send as txt file
        import io
        bio = io.BytesIO()
        bio.write(text.encode("utf-8"))
        bio.seek(0)
        await message.reply_document(chat_id=message.chat.id, document=bio, file_name=f"summary_{channel_key}.txt")

    # cleanup
    channel_data.pop(channel_key, None)
    await message.reply_text(f"Done. Removed monitoring for `{channel_key}`. Recorded {len(posts)} posts. Posted to channel: {posted_to_channel}")


# Optional: /status to list monitored channels
@app.on_message(filters.command("status") & filters.private)
async def cmd_status(client, message):
    if not channel_data:
        await message.reply_text("No channels are currently being recorded.")
        return
    lines = ["Currently recording:"]
    for k, v in channel_data.items():
        lines.append(f"{k} — type={v['type']} posts={len(v['posts'])}")
    await message.reply_text("\n".join(lines))


# Run
if __name__ == "__main__":
    logger.info("Starting Caption Recorder Multi-channel Bot...")
    app.run()