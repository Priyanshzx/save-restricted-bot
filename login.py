# login.py — Per-user phone number login
#
# Only authorized users (added by admin via /adduser) can use /login.
# Each user gets their own Pyrogram session stored on disk.
# get_user_client(uid) returns their client, or the global userbot as fallback.

import asyncio
import os
import json

from .. import bot as Drone, API_ID, API_HASH, userbot as _global_userbot
from telethon import events, Button

from pyrogram import Client
from pyrogram.errors import (
    PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired,
    SessionPasswordNeeded, PasswordHashInvalid, FloodWait
)
from main.plugins.auth import is_authorized

SESSION_DIR = "user_sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# uid -> live pyrogram Client
_USER_CLIENTS: dict = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session_path(uid: int) -> str:
    return os.path.join(SESSION_DIR, str(uid))

def _meta_path(uid: int) -> str:
    return os.path.join(SESSION_DIR, f"{uid}_meta.json")

def _save_meta(uid: int, phone: str, name: str):
    with open(_meta_path(uid), "w") as f:
        json.dump({"phone": phone, "name": name}, f)

def _load_meta(uid: int) -> dict:
    try:
        with open(_meta_path(uid)) as f:
            return json.load(f)
    except Exception:
        return {}

def _del_meta(uid: int):
    p = _meta_path(uid)
    if os.path.exists(p):
        os.remove(p)


# ── Public API ────────────────────────────────────────────────────────────────

def get_user_client(uid: int):
    """Return this user's own Pyrogram client, or the global userbot."""
    return _USER_CLIENTS.get(uid, _global_userbot)

def get_session_info(uid: int) -> dict:
    """Return login metadata for display in /myplan."""
    if uid in _USER_CLIENTS or os.path.exists(_session_path(uid) + ".session"):
        meta = _load_meta(uid)
        return {"logged_in": True, "name": meta.get("name","?"), "phone": meta.get("phone","?")}
    return {"logged_in": False}


# ── Auto-restore sessions on startup ─────────────────────────────────────────

async def _restore_sessions():
    if not os.path.isdir(SESSION_DIR):
        return
    for fname in os.listdir(SESSION_DIR):
        if not fname.endswith(".session"):
            continue
        try:
            uid = int(fname.replace(".session", ""))
        except ValueError:
            continue
        if uid in _USER_CLIENTS:
            continue
        try:
            client = Client(
                _session_path(uid),
                api_id=API_ID,
                api_hash=API_HASH,
                no_updates=True,
            )
            await client.start()
            _USER_CLIENTS[uid] = client
            meta = _load_meta(uid)
            print(f"[login] Restored session uid={uid} name={meta.get('name','?')}")
        except Exception as e:
            print(f"[login] Could not restore session uid={uid}: {e}")
            sess = _session_path(uid) + ".session"
            if os.path.exists(sess):
                os.remove(sess)

asyncio.get_event_loop().run_until_complete(_restore_sessions())


# ── /login ────────────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, pattern=r'^/login$'))
async def login_cmd(event):
    if not event.is_private:
        return

    uid = event.sender_id

    # Authorization gate
    if not is_authorized(uid):
        return await event.reply(
            "⛔ **You are not authorized.**\n\n"
            "Ask the admin to add you with `/adduser`."
        )

    # Already live
    if uid in _USER_CLIENTS:
        meta = _load_meta(uid)
        return await event.reply(
            f"✅ Already logged in as **{meta.get('name','?')}** "
            f"(`{meta.get('phone','?')}`).\n\n"
            "Use /logout to sign out."
        )

    # Saved session on disk — try to resume
    sess_file = _session_path(uid) + ".session"
    if os.path.exists(sess_file):
        try:
            client = Client(
                _session_path(uid),
                api_id=API_ID,
                api_hash=API_HASH,
                no_updates=True,
            )
            await client.start()
            _USER_CLIENTS[uid] = client
            me = await client.get_me()
            name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            _save_meta(uid, me.phone_number or "?", name)
            return await event.reply(
                f"✅ Session resumed for **{name}** (`{me.phone_number}`).\n\n"
                "Use /logout to sign out."
            )
        except Exception:
            if os.path.exists(sess_file):
                os.remove(sess_file)

    # Fresh login
    await event.reply(
        "📱 **Login with your Phone Number**\n\n"
        "Reply with your number in international format.\n"
        "Example: `+919876543210`\n\n"
        "⚠️ Your session is stored on this server and used "
        "only to download restricted content on your behalf.",
        buttons=Button.force_reply()
    )

    async def do_login():
        async with Drone.conversation(event.chat_id) as conv:
            try:
                # Step 1: phone
                phone_msg = await conv.get_reply(timeout=60)
                phone = phone_msg.text.strip()
                if not phone.startswith("+"):
                    return await conv.send_message(
                        "❌ Must start with `+`. Try /login again."
                    )

                wait_msg = await conv.send_message("⏳ Sending OTP...")

                client = Client(
                    _session_path(uid),
                    api_id=API_ID,
                    api_hash=API_HASH,
                    no_updates=True,
                )
                await client.connect()

                try:
                    sent = await client.send_code(phone)
                except PhoneNumberInvalid:
                    await wait_msg.edit("❌ Invalid phone number. Try /login again.")
                    await client.disconnect()
                    return
                except FloodWait as fw:
                    await wait_msg.edit(f"⏳ Too many requests. Retry after {fw.value}s.")
                    await client.disconnect()
                    return

                await wait_msg.edit(
                    "📩 OTP sent!\n\n"
                    "Reply with the code — no spaces.\n"
                    "If you got `1 2 3 4 5`, send `12345`.",
                    buttons=Button.force_reply()
                )

                # Step 2: OTP
                code_msg = await conv.get_reply(timeout=120)
                code = code_msg.text.strip().replace(" ", "")

                try:
                    me = await client.sign_in(phone, sent.phone_code_hash, code)
                except SessionPasswordNeeded:
                    await conv.send_message(
                        "🔐 **Two-Step Verification enabled.**\n\n"
                        "Reply with your 2FA password:",
                        buttons=Button.force_reply()
                    )
                    pw_msg = await conv.get_reply(timeout=120)
                    try:
                        me = await client.check_password(pw_msg.text.strip())
                    except PasswordHashInvalid:
                        await conv.send_message("❌ Wrong password. Try /login again.")
                        await client.disconnect()
                        return
                except (PhoneCodeInvalid, PhoneCodeExpired):
                    await conv.send_message("❌ Wrong or expired OTP. Try /login again.")
                    await client.disconnect()
                    return

                name = f"{me.first_name or ''} {me.last_name or ''}".strip()
                _save_meta(uid, phone, name)
                _USER_CLIENTS[uid] = client

                await conv.send_message(
                    f"✅ **Logged in successfully!**\n\n"
                    f"👤 Name: **{name}**\n"
                    f"📱 Phone: `{phone}`\n\n"
                    "Your session is saved. All your downloads now use your account.\n"
                    "Use /logout to sign out anytime."
                )

            except asyncio.TimeoutError:
                await conv.send_message("⏰ Timed out. Send /login to try again.")
            except Exception as e:
                await conv.send_message(f"❌ Login failed: `{e}`\n\nTry /login again.")

    asyncio.create_task(do_login())


# ── /logout ───────────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, pattern=r'^/logout$'))
async def logout_cmd(event):
    if not event.is_private:
        return

    uid = event.sender_id
    if not is_authorized(uid):
        return await event.reply("⛔ You are not authorized.")

    sess_file = _session_path(uid) + ".session"
    if uid not in _USER_CLIENTS and not os.path.exists(sess_file):
        return await event.reply("⚠️ You are not logged in.")

    meta = _load_meta(uid)
    name  = meta.get("name", "Unknown")
    phone = meta.get("phone", "?")

    if uid in _USER_CLIENTS:
        try:
            await _USER_CLIENTS[uid].log_out()
        except Exception:
            try:
                await _USER_CLIENTS[uid].disconnect()
            except Exception:
                pass
        del _USER_CLIENTS[uid]

    if os.path.exists(sess_file):
        os.remove(sess_file)
    _del_meta(uid)

    await event.reply(
        f"✅ **Logged out.**\n\n"
        f"Session for **{name}** (`{phone}`) removed.\n"
        "Your downloads will now use the shared bot account."
    )
