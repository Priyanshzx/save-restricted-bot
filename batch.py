# batch.py — One-click batch downloader for all authorized users
#
# /batch <link>           → save 100 files from that message
# /batch <link> <count>   → save up to 100 files
# /cancel                 → stop your running batch

import asyncio

from .. import bot as Drone
from .. import Bot
from main.plugins.pyroplug import get_bulk_msg
from main.plugins.helpers import get_link
from main.plugins.login import get_user_client
from main.plugins.auth import is_authorized

from telethon import events
from pyrogram.errors import FloodWait

# uid -> True when batch is running
_active_batches: set = set()


# ── /cancel ───────────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, pattern=r'^/cancel$'))
async def cancel(event):
    if not event.is_private:
        return
    if not is_authorized(event.sender_id):
        return await event.reply("⛔ You are not authorized.")
    if event.sender_id not in _active_batches:
        return await event.reply("⚠️ No batch is currently running.")
    _active_batches.discard(event.sender_id)
    await event.reply("❌ Batch cancelled.")


# ── /batch ────────────────────────────────────────────────────────────────────

@Drone.on(events.NewMessage(incoming=True, pattern=r'^/batch(.*)'))
async def _batch(event):
    if not event.is_private:
        return

    # Authorization check
    if not is_authorized(event.sender_id):
        return await event.reply(
            "⛔ **You are not authorized.**\n\n"
            "Ask the admin to add you with `/adduser`."
        )

    # Duplicate batch check
    if event.sender_id in _active_batches:
        return await event.reply(
            "⚡ A batch is already running!\n"
            "Send /cancel to stop it first."
        )

    # ── Parse args ─────────────────────────────────────────────────────────
    args = event.pattern_match.group(1).strip().split()

    if not args:
        return await event.reply(
            "⚡ **Batch Downloader**\n\n"
            "**Usage:**\n"
            "`/batch <link>` — save **100** files\n"
            "`/batch <link> <count>` — save up to **100** files\n\n"
            "**Examples:**\n"
            "`/batch https://t.me/c/1234567890/55`\n"
            "`/batch https://t.me/c/1234567890/55 50`\n\n"
            "The link should point to the **first** message of the range.\n"
            "Send /cancel anytime to stop."
        )

    _link = get_link(args[0])
    if not _link:
        return await event.reply(
            "❌ No valid link found.\n\n"
            "Usage: `/batch <t.me link> [count]`"
        )

    count = 100
    if len(args) >= 2:
        try:
            count = int(args[1])
            if count < 1:
                return await event.reply("❌ Count must be at least 1.")
            if count > 100:
                return await event.reply("❌ Maximum is **100** files per batch.")
        except ValueError:
            return await event.reply(f"❌ `{args[1]}` is not a valid number.")

    # ── Start batch ─────────────────────────────────────────────────────────
    _active_batches.add(event.sender_id)
    confirm = await event.reply(
        f"✅ **Batch started!**\n\n"
        f"📎 Link: `{_link}`\n"
        f"📦 Files: **{count}**\n"
        f"👤 Using: {'your account' if event.sender_id in __import__('main.plugins.login', fromlist=['_USER_CLIENTS'])._USER_CLIENTS else 'shared account'}\n\n"
        "Send /cancel anytime to stop."
    )

    try:
        completed = await run_batch(
            get_user_client(event.sender_id),
            Bot, event.sender_id, _link, count
        )
    finally:
        _active_batches.discard(event.sender_id)

    try:
        await confirm.delete()
    except Exception:
        pass

    if completed >= count:
        await Bot.send_message(
            event.sender_id,
            f"🎉 **Batch complete!** Saved **{completed}/{count}** files."
        )
    else:
        await Bot.send_message(
            event.sender_id,
            f"🏁 **Batch stopped.** Saved **{completed}/{count}** files."
        )


# ── Core batch runner ─────────────────────────────────────────────────────────

async def run_batch(ub, client, sender, link, total: int) -> int:
    """
    Downloads `total` consecutive messages starting at `link`.
    Returns number of files successfully processed.

    Delay schedule:
      files  1-25  → 5s  private / 2s  public
      files 26-50  → 10s private / 3s  public
      files 51-100 → 15s private / 3s  public
    """
    is_private = 't.me/c/' in link
    completed = 0

    for i in range(total):
        if sender not in _active_batches:
            break

        # Sleep timer
        if is_private:
            timer = 5 if i < 25 else (10 if i < 50 else 15)
        else:
            timer = 2 if i < 25 else 3

        # Download + upload
        try:
            await get_bulk_msg(ub, client, sender, link, i)
            completed += 1
        except FloodWait as fw:
            wait = fw.value
            if wait > 299:
                await client.send_message(
                    sender,
                    f"⚠️ FloodWait **{wait}s** (>5 min). Stopping to protect your account."
                )
                break
            flood_msg = await client.send_message(
                sender, f"⏳ FloodWait — sleeping **{wait + 5}s**..."
            )
            await asyncio.sleep(wait + 5)
            try:
                await flood_msg.delete()
            except Exception:
                pass
            try:
                await get_bulk_msg(ub, client, sender, link, i)
                completed += 1
            except Exception as e:
                await client.send_message(sender, f"⚠️ Skipped file {i+1}: `{e}`")
        except Exception as e:
            await client.send_message(sender, f"⚠️ Skipped file {i+1}: `{e}`")
            completed += 1

        if sender not in _active_batches:
            break

        # Progress update every 10 files
        if (i + 1) % 10 == 0:
            prog = await client.send_message(
                sender, f"📊 Progress: **{i+1}/{total}** files done..."
            )
            await asyncio.sleep(2)
            try:
                await prog.delete()
            except Exception:
                pass

        # Anti-flood sleep
        sleep_msg = await client.send_message(
            sender,
            f"⏱ Sleeping **{timer}s** to avoid FloodWait... `({i+1}/{total})`"
        )
        await asyncio.sleep(timer)
        try:
            await sleep_msg.delete()
        except Exception:
            pass

    return completed
