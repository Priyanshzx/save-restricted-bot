import math
import asyncio
import time
import json

import aiofiles
import os

FINISHED_PROGRESS_STR = "█"
UN_FINISHED_PROGRESS_STR = "░"
DOWNLOAD_LOCATION = "/app"

# Throttle: only update the progress message every N seconds
# Previously used `round(diff % 10.00) == 0` which fires erratically
# (floating point rarely equals exactly 0, so updates were unpredictable).
# A simple time-gate is both reliable and keeps the event loop free.
_PROGRESS_UPDATE_INTERVAL = 3  # seconds


async def progress_for_pyrogram(
    current,
    total,
    bot,
    ud_type,
    message,
    start
):
    now = time.time()
    diff = now - start
    if diff == 0:
        return

    # Only update every _PROGRESS_UPDATE_INTERVAL seconds (or on completion)
    # Use an attribute stored on the message object to track last update time
    last_update = getattr(message, "_last_progress_update", 0)
    if current != total and (now - last_update) < _PROGRESS_UPDATE_INTERVAL:
        return
    try:
        message._last_progress_update = now
    except Exception:
        pass

    # Check stop flag using async file I/O — no longer blocks the event loop
    status_path = DOWNLOAD_LOCATION + "/status.json"
    try:
        if os.path.exists(status_path):
            async with aiofiles.open(status_path, 'r') as f:
                content = await f.read()
                statusMsg = json.loads(content)
                if not statusMsg.get("running", True):
                    bot.stop_transmission()
    except Exception:
        pass  # Don't let status check crash a transfer

    percentage = current * 100 / total
    speed = current / diff
    elapsed_time = round(diff) * 1000
    time_to_completion = round((total - current) / speed) * 1000
    estimated_total_time = elapsed_time + time_to_completion

    elapsed_str = TimeFormatter(milliseconds=elapsed_time)
    eta_str = TimeFormatter(milliseconds=estimated_total_time)

    filled = math.floor(percentage / 10)
    bar = "".join([FINISHED_PROGRESS_STR] * filled) + \
          "".join([UN_FINISHED_PROGRESS_STR] * (10 - filled))

    progress = f"**[{bar}]** `| {round(percentage, 2)}%`\n\n"
    tmp = progress + (
        f"**Done:** {humanbytes(current)} of {humanbytes(total)}\n\n"
        f"**Speed:** {humanbytes(speed)}/s\n\n"
        f"**ETA:** {eta_str if eta_str else '0 s'}\n"
    )

    try:
        if not message.photo:
            await message.edit_text(
                text=f"{ud_type}\n {tmp}"
            )
        else:
            await message.edit_caption(
                caption=f"{ud_type}\n {tmp}"
            )
    except Exception:
        pass


def humanbytes(size):
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'


def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
        ((str(hours) + "h, ") if hours else "") + \
        ((str(minutes) + "m, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "")
    return tmp[:-2]
