# frontend.py — handles single-message link cloning for all authorized users

import time, os

from .. import bot as Drone
from .. import Bot
from main.plugins.pyroplug import get_msg
from main.plugins.helpers import get_link, join
from main.plugins.login import get_user_client
from main.plugins.auth import is_authorized

from telethon import events
from pyrogram.errors import FloodWait

message = "Send me the message link you want to start saving from, as a reply to this message."

@Drone.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def clone(event):
    if event.is_reply:
        reply = await event.get_reply_message()
        if reply.text == message:
            return

    try:
        link = get_link(event.text)
        if not link:
            return
    except TypeError:
        return

    # Authorization check
    if not is_authorized(event.sender_id):
        return await event.reply(
            "⛔ **You are not authorized to use this bot.**\n\n"
            "Ask the admin to add you with `/adduser`."
        )

    edit = await event.reply("Processing!")
    try:
        if 't.me/+' in link:
            q = await join(get_user_client(event.sender_id), link)
            return await edit.edit(q)
        if 't.me/' in link:
            await get_msg(
                get_user_client(event.sender_id),
                Bot, Drone,
                event.sender_id, edit.id, link, 0
            )
    except FloodWait as fw:
        await Drone.send_message(
            event.sender_id,
            f'⏳ FloodWait: try again after {fw.value} seconds.'
        )
    except Exception as e:
        print(e)
        await Drone.send_message(
            event.sender_id,
            f"❌ Error cloning `{link}`\n\n**Error:** {str(e)}"
        )
