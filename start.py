# start.py — /start command + legacy inline thumbnail buttons

import os
from .. import bot as Drone, AUTH
from telethon import events, Button
from main.plugins.auth import is_authorized

S = '/' + 's' + 't' + 'a' + 'r' + 't'

# Legacy inline-button thumbnail handlers
@Drone.on(events.callbackquery.CallbackQuery(data="set"))
async def sett(event):
    Drone = event.client
    await event.delete()
    async with Drone.conversation(event.chat_id) as conv:
        xx = await conv.send_message("Send me any image for thumbnail as a `reply` to this message.")
        x = await conv.get_reply()
        if not x.media:
            return await xx.edit("No media found.")
        mime = x.file.mime_type
        if not any(t in mime for t in ['png', 'jpg', 'jpeg']):
            return await xx.edit("No image found.")
        await xx.delete()
        t = await event.client.send_message(event.chat_id, 'Trying.')
        path = await event.client.download_media(x.media)
        if os.path.exists(f'{event.sender_id}.jpg'):
            os.remove(f'{event.sender_id}.jpg')
        os.rename(path, f'./{event.sender_id}.jpg')
        await t.edit("✅ Thumbnail saved!")

@Drone.on(events.callbackquery.CallbackQuery(data="rem"))
async def remt(event):
    Drone = event.client
    await event.edit('Trying.')
    try:
        os.remove(f'{event.sender_id}.jpg')
        await event.edit('✅ Thumbnail removed!')
    except Exception:
        await event.edit("⚠️ No thumbnail saved.")


@Drone.on(events.NewMessage(incoming=True, pattern=f"{S}"))
async def start(event):
    uid = event.sender_id

    if uid == AUTH:
        # Admin view
        text = (
            "👑 **Admin Panel**\n\n"
            "**User Management:**\n"
            "➕ `/adduser <id>` — authorize a user\n"
            "➖ `/removeuser <id>` — revoke access\n"
            "📋 `/users` — list authorized users\n\n"
            "**Your Commands:**\n"
            "🚀 `/start` • 📱 `/login` • 🚪 `/logout`\n"
            "⚡ `/batch <link> [count]` • ❌ `/cancel`\n"
            "🖼 `/setthumb` • 🙂 `/remthumb`\n"
            "💬 `/caption` • 📌 `/setchat` • 🧹 `/remchat`\n"
            "📋 `/myplan` • 🔓 `/free`\n\n"
            "**SUPPORT:** @TeamDrone"
        )
    elif is_authorized(uid):
        # Authorized user view
        text = (
            "👋 **Welcome!**\n\n"
            "Send me any `t.me/` link to save it.\n"
            "For private channels, send the invite link first.\n\n"
            "**Your Commands:**\n"
            "🚀 `/start` • 📱 `/login` • 🚪 `/logout`\n"
            "⚡ `/batch <link> [count]` • ❌ `/cancel`\n"
            "🖼 `/setthumb` • 🙂 `/remthumb`\n"
            "💬 `/caption` • 📌 `/setchat` • 🧹 `/remchat`\n"
            "📋 `/myplan` • 🔓 `/free`\n\n"
            "**SUPPORT:** @TeamDrone"
        )
    else:
        # Unauthorized user
        text = (
            "👋 **Welcome!**\n\n"
            "⛔ You are not authorized to use this bot.\n\n"
            "Please ask the admin to authorize you.\n"
            "Share your User ID with them: `{}`\n\n"
            "**SUPPORT:** @TeamDrone"
        ).format(uid)

    await event.reply(text)
