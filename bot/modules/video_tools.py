from asyncio import sleep
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import regex, user, reply
from pyrogram.enums import ButtonStyle
from time import time

from .. import LOGGER, bot_loop
from ..core.tg_client import TgClient
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.message_utils import (
    send_message,
    edit_message,
    delete_message,
)
from ..helper.ext_utils.bot_utils import new_task

vt_sessions = {}

async def display_video_tools_menu(mirror_obj):
    user_id = mirror_obj.user_id
    message = mirror_obj.message

    vt_data = {
        "rename": None,
        "video_video": False,
        "video_audio": False,
        "video_subtitle": False,
        "compress": [],
        "convert": False,
        "extract": False,
        "trim": False,
        "remove_stream": False,
        "obj": mirror_obj,
        "user_id": user_id,
        "last_interaction": time()
    }

    vt_sessions[message.id] = vt_data

    text = "<b>Advanced Video Tools Menu</b>\n\n<i>Select the tools you want to apply to your task. These will be processed sequentially after download.</i>"
    buttons = _build_vt_keyboard(vt_data)

    msg = await send_message(message, text, buttons)
    vt_data["menu_msg"] = msg

    # Start timeout task
    bot_loop.create_task(_vt_timeout_task(message.id))

def _build_vt_keyboard(vt_data):
    buttons = ButtonMaker()
    user_id = vt_data["user_id"]

    # Row 1: Rename (Full Width)
    rename_text = f"✅ Rename: {vt_data['rename']}" if vt_data["rename"] else "Rename"
    buttons.data_button(rename_text, f"vt {user_id} rename", position="header")

    # Row 2: Video + Video | Video + Audio
    vv_text = "✅ Video + Video" if vt_data["video_video"] else "Video + Video"
    va_text = "✅ Video + Audio" if vt_data["video_audio"] else "Video + Audio"
    buttons.data_button(vv_text, f"vt {user_id} toggle video_video")
    buttons.data_button(va_text, f"vt {user_id} toggle video_audio")

    # Row 3: Video + Subtitle
    vs_text = "✅ Video + Subtitle" if vt_data["video_subtitle"] else "Video + Subtitle"
    buttons.data_button(vs_text, f"vt {user_id} toggle video_subtitle")

    # Row 4: Compress | Convert
    comp_text = f"✅ Compress ({','.join(vt_data['compress'])})" if vt_data["compress"] else "Compress"
    conv_text = "✅ Convert" if vt_data["convert"] else "Convert"
    buttons.data_button(comp_text, f"vt {user_id} compress_menu")
    buttons.data_button(conv_text, f"vt {user_id} toggle convert")

    # Row 5: Extract
    ext_text = "✅ Extract" if vt_data["extract"] else "Extract"
    buttons.data_button(ext_text, f"vt {user_id} toggle extract")

    # Row 6: Trim | Remove Stream
    trim_text = "✅ Trim" if vt_data["trim"] else "Trim"
    rs_text = "✅ Remove Stream" if vt_data["remove_stream"] else "Remove Stream"
    buttons.data_button(trim_text, f"vt {user_id} toggle trim")
    buttons.data_button(rs_text, f"vt {user_id} toggle remove_stream")

    # Row 7: Done (Full Width)
    buttons.data_button("🟩 Done / Start Process", f"vt {user_id} done", position="footer", style=ButtonStyle.SUCCESS)

    # Row 8: Cancel (Full Width)
    buttons.data_button("❌ Cancel", f"vt {user_id} cancel", position="footer", style=ButtonStyle.DANGER)

    return buttons.build_menu(2)

def _build_compress_keyboard(vt_data):
    buttons = ButtonMaker()
    user_id = vt_data["user_id"]
    qualities = ["144p", "240p", "360p", "480p", "540p", "720p", "1080p"]

    for q in qualities:
        text = f"✅ {q}" if q in vt_data["compress"] else q
        buttons.data_button(text, f"vt {user_id} comp_toggle {q}")

    buttons.data_button("💾 Save", f"vt {user_id} main_menu", position="footer", style=ButtonStyle.SUCCESS)
    return buttons.build_menu(2)

async def _vt_timeout_task(mid):
    await sleep(180)
    if mid in vt_sessions:
        vt_data = vt_sessions.pop(mid)
        msg = vt_data.get("menu_msg")
        # Cleanup any stray handlers
        if "handler" in vt_data:
            TgClient.bot.remove_handler(vt_data["handler"], group=-1)
        if msg:
            await edit_message(msg, "<b>Video Tools Menu Expired!</b>")

@new_task
async def vt_callback(_, query):
    user_id = query.from_user.id
    data = query.data.split()

    # Find session by message id
    session_id = None
    for sid, sdata in vt_sessions.items():
        if sdata["menu_msg"].id == query.message.id:
            session_id = sid
            break

    if not session_id:
        await query.answer("Session expired or invalid!", show_alert=True)
        await delete_message(query.message)
        return

    vt_data = vt_sessions[session_id]

    if user_id != vt_data["user_id"]:
        await query.answer("This is not your task session!", show_alert=True)
        return

    vt_data["last_interaction"] = time()
    action = data[2]

    if action == "toggle":
        key = data[3]
        vt_data[key] = not vt_data[key]
        await edit_message(query.message, query.message.text, _build_vt_keyboard(vt_data))

    elif action == "rename":
        await query.answer()
        msg = await send_message(query.message, "<b>Please reply with your new custom output name.</b>")

        async def _rename_reply(client, message):
            vt_data["rename"] = message.text
            vt_data.pop("handler", None)
            await delete_message(message)
            await delete_message(msg)
            await edit_message(vt_data["menu_msg"], vt_data["menu_msg"].text, _build_vt_keyboard(vt_data))
            client.remove_handler(handler, group=-1)

        handler = TgClient.bot.add_handler(MessageHandler(_rename_reply, filters=user(user_id) & reply), group=-1)
        vt_data["handler"] = handler

    elif action == "compress_menu":
        await edit_message(query.message, "<b>Select Compression Qualities:</b>", _build_compress_keyboard(vt_data))

    elif action == "comp_toggle":
        q = data[3]
        if q in vt_data["compress"]:
            vt_data["compress"].remove(q)
        else:
            vt_data["compress"].append(q)
        await edit_message(query.message, "<b>Select Compression Qualities:</b>", _build_compress_keyboard(vt_data))

    elif action == "main_menu":
        await edit_message(query.message, "<b>Advanced Video Tools Menu</b>", _build_vt_keyboard(vt_data))

    elif action == "done":
        await query.answer("Starting task...", show_alert=True)
        mirror_obj = vt_data["obj"]
        mirror_obj.vt_data = vt_data
        vt_sessions.pop(session_id)
        await delete_message(query.message)
        await mirror_obj.new_event()

    elif action == "cancel":
        vt_sessions.pop(session_id)
        await query.answer("Task Cancelled!")
        await delete_message(query.message)

TgClient.bot.add_handler(CallbackQueryHandler(vt_callback, filters=regex("^vt")))
