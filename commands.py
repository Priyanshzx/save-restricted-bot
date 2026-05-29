# commands.py — Per-user settings commands
# All commands require authorization via /adduser

import os
import json
import asyncio

from .. import bot as Drone, AUTH
from telethon import events, Button
from main.plugins.auth import is_authorized

# ── Persistent user data store ────────────────────────────────────────────────

STORE_FILE = "user_data.json"

def _load() -> dict:
    if os.path.exists(STORE_FILE):
        try:
            with open(STORE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save(data: dict):
    with open(STORE_FILE, "w") as f:
        json.dump(data, f)

def get_user(uid: int) -> dict:
    return _load().get(str(uid), {})

def set_user(uid: int, key: str, value):
    data = _load()
    uid = str(uid)
    if uid not in data:
        data[uid] = {}
    data[uid][key] = value
    _save(data)

def del_user_key(uid: int, key: str):
    data = _load()
    uid = str(uid)
    if uid in data and key in data[uid]:
        del data[uid][key]
        _save(data)


# ── Auth guard helper ─────────────────────────────────────────────────────────

async def _check_auth(event) -> bool:
    if not is_authorized(event.sender_id):
        await event.reply(
            "⛔ **You are not authorized.**\n\n"
            "Ask the admin to add you with `/adduser`."
        )
        return False
    return True


# ── /setthumb ─────────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, pattern=r'^/setthumb$'))
async def setthumb_cmd(event):
    if not event.is_private:
        return
    if not await _check_auth(event):
        return

    await event.reply(
        "📸 **Set Thumbnail**\n\n"
        "Reply to this message with a JPG/PNG image.",
        buttons=Button.force_reply()
    )

    async def wait_for_thumb():
        async with Drone.conversation(event.chat_id) as conv:
            try:
                reply = await conv.get_reply(timeout=60)
                if not reply.media:
                    return await conv.send_message("❌ No media found. Send a photo.")
                mime = reply.file.mime_type if reply.file else ""
                if not any(x in mime for x in ['png', 'jpg', 'jpeg']):
                    return await conv.send_message("❌ Please send a JPG or PNG image.")
                t = await conv.send_message("⏳ Saving thumbnail...")
                path = await reply.download_media()
                dest = f'{event.sender_id}.jpg'
                if os.path.exists(dest):
                    os.remove(dest)
                os.rename(path, dest)
                await t.edit("✅ Thumbnail saved!")
            except asyncio.TimeoutError:
                await conv.send_message("⏰ Timed out. Send /setthumb again.")
            except Exception as e:
                await conv.send_message(f"❌ Error: {e}")

    asyncio.create_task(wait_for_thumb())


# ── /remthumb ─────────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, pattern=r'^/remthumb$'))
async def remthumb_cmd(event):
    if not event.is_private:
        return
    if not await _check_auth(event):
        return
    path = f'{event.sender_id}.jpg'
    if os.path.exists(path):
        os.remove(path)
        await event.reply("✅ Thumbnail removed.")
    else:
        await event.reply("⚠️ No thumbnail is set.")


# ── /caption ──────────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, pattern=r'^/caption(.*)'))
async def caption_cmd(event):
    if not event.is_private:
        return
    if not await _check_auth(event):
        return

    args = event.pattern_match.group(1).strip()
    if not args:
        ud = get_user(event.sender_id)
        rule = ud.get("caption_rule")
        if rule:
            mode = rule.get("mode")
            if mode == "add":
                info = f'**Mode:** Add prefix\n**Text:** `{rule.get("text")}`'
            elif mode == "replace":
                info = f'**Mode:** Replace\n**Find:** `{rule.get("find")}`\n**With:** `{rule.get("replace")}`'
            elif mode == "delete":
                info = "**Mode:** Delete all captions"
            else:
                info = str(rule)
        else:
            info = "None"
        return await event.reply(
            "📝 **Caption Manager**\n\n"
            f"**Current rule:** {info}\n\n"
            "**Usage:**\n"
            "`/caption add <text>` — prepend text\n"
            "`/caption replace <old>|<new>` — find & replace\n"
            "`/caption delete` — remove all captions\n"
            "`/caption clear` — clear saved rule"
        )

    parts = args.split(" ", 1)
    mode = parts[0].lower()

    if mode == "add":
        if len(parts) < 2 or not parts[1].strip():
            return await event.reply("❌ Usage: `/caption add <text>`")
        set_user(event.sender_id, "caption_rule", {"mode": "add", "text": parts[1].strip()})
        await event.reply(f"✅ Will prepend `{parts[1].strip()}` to every caption.")
    elif mode == "replace":
        if len(parts) < 2 or "|" not in parts[1]:
            return await event.reply("❌ Usage: `/caption replace <old>|<new>`")
        old, new = parts[1].split("|", 1)
        set_user(event.sender_id, "caption_rule", {"mode": "replace", "find": old.strip(), "replace": new.strip()})
        await event.reply(f"✅ Will replace `{old.strip()}` → `{new.strip()}`.")
    elif mode == "delete":
        set_user(event.sender_id, "caption_rule", {"mode": "delete"})
        await event.reply("✅ All captions will be removed.")
    elif mode == "clear":
        del_user_key(event.sender_id, "caption_rule")
        await event.reply("✅ Caption rule cleared.")
    else:
        await event.reply("❌ Unknown mode. Use `add`, `replace`, `delete`, or `clear`.")


def apply_caption_rule(uid: int, caption) -> str:
    """Apply saved caption rule. Returns modified caption."""
    ud = get_user(uid)
    rule = ud.get("caption_rule")
    if not rule:
        return caption
    mode = rule.get("mode")
    if mode == "delete":
        return None
    if mode == "add":
        prefix = rule.get("text", "")
        return f"{prefix}\n{caption}" if caption else prefix
    if mode == "replace":
        find = rule.get("find", "")
        replace = rule.get("replace", "")
        return caption.replace(find, replace) if caption else caption
    return caption


# ── /setchat ──────────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, pattern=r'^/setchat(.*)'))
async def setchat_cmd(event):
    if not event.is_private:
        return
    if not await _check_auth(event):
        return
    args = event.pattern_match.group(1).strip()
    if not args:
        ud = get_user(event.sender_id)
        current = ud.get("target_chat")
        if current:
            return await event.reply(
                f"📌 **Current target:** `{current}`\n\n"
                "Use `/remchat` to remove.\n"
                "To change: `/setchat <username or chat_id>`"
            )
        return await event.reply(
            "📌 **Set Target Chat**\n\n"
            "Usage: `/setchat @mychannel` or `/setchat -1001234567890`\n\n"
            "All saved files will be forwarded there."
        )
    set_user(event.sender_id, "target_chat", args.strip())
    await event.reply(f"✅ Target chat set to `{args.strip()}`.")


# ── /remchat ──────────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, pattern=r'^/remchat$'))
async def remchat_cmd(event):
    if not event.is_private:
        return
    if not await _check_auth(event):
        return
    if get_user(event.sender_id).get("target_chat"):
        del_user_key(event.sender_id, "target_chat")
        await event.reply("✅ Target chat removed.")
    else:
        await event.reply("⚠️ No target chat is set.")


# ── /myplan ───────────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, pattern=r'^/myplan$'))
async def myplan_cmd(event):
    if not event.is_private:
        return
    if not await _check_auth(event):
        return

    uid = event.sender_id
    ud = get_user(uid)

    # Login status
    from main.plugins.login import get_session_info
    sess = get_session_info(uid)
    if sess["logged_in"]:
        login_status = f"✅ Logged in as **{sess['name']}** (`{sess['phone']}`)"
    else:
        login_status = "❌ Not logged in (using shared account)\nSend /login to connect your account"

    thumb   = "✅ Set" if os.path.exists(f'{uid}.jpg') else "❌ Not set"
    target  = ud.get("target_chat", "❌ Not set (sends to you)")
    cap_rule = ud.get("caption_rule")
    cap_info = cap_rule.get("mode", "?").capitalize() if cap_rule else "❌ None"

    role = "👑 Admin" if uid == AUTH else "👤 Authorized User"

    await event.reply(
        "📋 **Your Plan Details**\n\n"
        f"{role}\n"
        f"📱 **Login:** {login_status}\n"
        f"🖼 **Thumbnail:** {thumb}\n"
        f"📌 **Target Chat:** `{target}`\n"
        f"📝 **Caption Rule:** {cap_info}\n\n"
        "**Commands:**\n"
        "• `/login` • `/logout`\n"
        "• `/batch` • `/cancel`\n"
        "• `/setthumb` • `/remthumb`\n"
        "• `/caption` • `/setchat` • `/remchat`\n"
        "• `/free`"
    )


# ── /free ─────────────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, pattern=r'^/free$'))
async def free_cmd(event):
    if not event.is_private:
        return
    if not await _check_auth(event):
        return
    status_path = "/app/status.json"
    try:
        os.makedirs(os.path.dirname(status_path), exist_ok=True)
        with open(status_path, "w") as f:
            json.dump({"running": False}, f)
        await event.reply(
            "🔓 **Unstuck signal sent!**\n\n"
            "Any stuck transfer will be cancelled.\n"
            "Wait a moment then try again."
        )
        await asyncio.sleep(3)
        with open(status_path, "w") as f:
            json.dump({"running": True}, f)
    except Exception as e:
        await event.reply(f"❌ Failed: {e}")
