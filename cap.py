import logging
from pyrogram import Client, filters
from pyrogram.enums import ParseMode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

API_ID = 35292658
API_HASH = "a14fdc9ed8e1456c9570381024954d0b"
BOT_TOKEN = "8257600572:AAFVmlwEDiEy-AFzXN94XpUmsSRe6aXMxhw"

app = Client(
    "multi_channel_recorder",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# {channel_id: {"type": content_type, "posts": []}}
recording_sessions = {}


def make_link(chat_id, msg_id):
    if str(chat_id).startswith("-100"):
        return f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}"
    return f"(private) msg_id={msg_id}"


# ---------------------- /rec ----------------------
@app.on_message(filters.private & filters.command("rec"))
async def rec_start(client, message):
    args = message.text.split()

    if len(args) < 3:
        return await message.reply(
            "Usage:\n`/rec <channel_id> <video/pdf/text/file/image> <limit>`"
        )

    channel_id = int(args[1])
    content_type = args[2].lower()
    limit = int(args[3]) if len(args) >= 4 else 100

    if content_type not in ["video", "pdf", "text", "file", "image"]:
        return await message.reply("❌ Invalid type.\nUse: video / pdf / text / file / image")

    recording_sessions[channel_id] = {"type": content_type, "posts": []}

    await message.reply(
        f"📡 Recording started for `{channel_id}`.\n"
        f"Type: **{content_type}**\n"
        f"Fetching last **{limit}** messages..."
    )

    # ---------------- Fetch History ----------------
    try:
        async for msg in client.get_chat_history(channel_id, limit=limit):
            capture = False

            if content_type == "video" and msg.video:
                capture = True
            elif content_type == "pdf" and msg.document and msg.document.file_name.endswith(".pdf"):
                capture = True
            elif content_type == "image" and msg.photo:
                capture = True
            elif content_type == "file" and msg.document:
                capture = True
            elif content_type == "text" and msg.text:
                capture = True

            if capture:
                caption = msg.caption or msg.text or "(no caption)"
                link = make_link(channel_id, msg.id)
                recording_sessions[channel_id]["posts"].append((caption, link))

        await message.reply(
            f"✅ History fetched. Now monitoring new posts in `{channel_id}`.\n"
            f"Use `/done {channel_id}` when finished."
        )

    except Exception as e:
        await message.reply(f"❌ Error fetching history:\n`{e}`")


# ---------------------- Live Capture ----------------------
@app.on_message(filters.channel)
async def capture_live(client, message):
    cid = message.chat.id
    if cid not in recording_sessions:
        return

    ctype = recording_sessions[cid]["type"]
    capture = False

    if ctype == "video" and message.video:
        capture = True
    elif ctype == "pdf" and message.document and message.document.file_name.endswith(".pdf"):
        capture = True
    elif ctype == "image" and message.photo:
        capture = True
    elif ctype == "file" and message.document:
        capture = True
    elif ctype == "text" and message.text:
        capture = True

    if capture:
        caption = message.caption or message.text or "(no caption)"
        link = make_link(cid, message.id)
        recording_sessions[cid]["posts"].append((caption, link))


# ---------------------- /done ----------------------
@app.on_message(filters.private & filters.command("done"))
async def finish(client, message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("Usage: /done <channel_id>")

    channel_id = int(args[1])

    if channel_id not in recording_sessions:
        return await message.reply("❌ No active recording for that channel.")

    posts = recording_sessions[channel_id]["posts"]
    content_type = recording_sessions[channel_id]["type"]

    if not posts:
        return await message.reply("No posts recorded.")

    lines = [f"📌 **Recorded {content_type} posts:**", ""]

    for caption, link in posts:
        short = caption.replace("\n", " ")[:100]
        lines.append(f"- [{short}]({link})")

    lines.append(f"\n**Total: {len(posts)}**")
    lines.append("Extracted by: @PUTINxINDIA 🇮🇳")

    final_text = "\n".join(lines)

    await client.send_message(
        chat_id=message.chat.id,
        text=final_text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

    del recording_sessions[channel_id]


# ---------------------- Run Bot ----------------------
if __name__ == "__main__":
    app.run()