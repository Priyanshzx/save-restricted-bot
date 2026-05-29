# auth.py — Admin-controlled user authorization
#
# Admin commands (AUTH user only):
#   /adduser <user_id>     — authorize a user
#   /removeuser <user_id>  — revoke authorization
#   /users                 — list all authorized users
#
# Authorized users get access to:
#   /login, /logout, /batch, /setthumb, /remthumb,
#   /caption, /setchat, /remchat, /myplan, /free
#
# Public API used by all other plugins:
#   is_authorized(uid)  -> bool

import json
import os

from .. import bot as Drone, AUTH
from telethon import events

AUTH_FILE = "authorized_users.json"


# ── Storage ───────────────────────────────────────────────────────────────────

def _load_auth() -> list:
    if os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save_auth(users: list):
    with open(AUTH_FILE, "w") as f:
        json.dump(users, f)


# ── Public API ────────────────────────────────────────────────────────────────

def is_authorized(uid: int) -> bool:
    """Returns True if user is admin OR has been authorized by admin."""
    if uid == AUTH:
        return True
    return uid in _load_auth()

def get_authorized_users() -> list:
    return _load_auth()


# ── /adduser ──────────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, from_users=AUTH, pattern=r'^/adduser(.*)'))
async def adduser_cmd(event):
    if not event.is_private:
        return
    arg = event.pattern_match.group(1).strip()
    if not arg:
        return await event.reply(
            "❌ Usage: `/adduser <user_id>`\n"
            "Example: `/adduser 123456789`"
        )
    try:
        uid = int(arg)
    except ValueError:
        return await event.reply("❌ User ID must be a number.")

    users = _load_auth()
    if uid == AUTH:
        return await event.reply("👑 That's you (the admin). Already has full access.")
    if uid in users:
        return await event.reply(f"⚠️ User `{uid}` is already authorized.")

    users.append(uid)
    _save_auth(users)

    # Notify the newly authorized user
    try:
        await Drone.send_message(
            uid,
            "✅ **You have been authorized to use this bot!**\n\n"
            "You can now:\n"
            "📱 `/login` — connect your Telegram account\n"
            "⚡ `/batch` — bulk download up to 100 files\n"
            "🖼 `/setthumb` — set custom thumbnail\n"
            "💬 `/caption` — manage captions\n"
            "📌 `/setchat` — set upload target\n"
            "📋 `/myplan` — view your settings\n\n"
            "Send /login to get started!"
        )
    except Exception:
        pass  # User may not have started the bot yet

    await event.reply(f"✅ User `{uid}` has been authorized.")


# ── /removeuser ───────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, from_users=AUTH, pattern=r'^/removeuser(.*)'))
async def removeuser_cmd(event):
    if not event.is_private:
        return
    arg = event.pattern_match.group(1).strip()
    if not arg:
        return await event.reply(
            "❌ Usage: `/removeuser <user_id>`\n"
            "Example: `/removeuser 123456789`"
        )
    try:
        uid = int(arg)
    except ValueError:
        return await event.reply("❌ User ID must be a number.")

    if uid == AUTH:
        return await event.reply("👑 Cannot remove yourself (admin).")

    users = _load_auth()
    if uid not in users:
        return await event.reply(f"⚠️ User `{uid}` is not in the authorized list.")

    users.remove(uid)
    _save_auth(users)

    # Notify the removed user
    try:
        await Drone.send_message(
            uid,
            "⛔ **Your access to this bot has been revoked.**\n"
            "Contact the admin if you think this is a mistake."
        )
    except Exception:
        pass

    await event.reply(f"✅ User `{uid}` has been removed.")


# ── /users ────────────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, from_users=AUTH, pattern=r'^/users$'))
async def users_cmd(event):
    if not event.is_private:
        return
    users = _load_auth()
    if not users:
        return await event.reply(
            "📋 **Authorized Users**\n\n"
            "No users authorized yet.\n"
            "Use `/adduser <user_id>` to add one."
        )
    lines = "\n".join(f"• `{uid}`" for uid in users)
    await event.reply(
        f"📋 **Authorized Users** ({len(users)} total)\n\n"
        f"{lines}\n\n"
        f"👑 Admin: `{AUTH}` (always authorized)"
    )
