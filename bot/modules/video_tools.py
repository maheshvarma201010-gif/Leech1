from pyrogram.handlers import CallbackQueryHandler, MessageHandler
from pyrogram.filters import regex, user
from asyncio import sleep, create_task, Event
from time import time
import os

from bot import bot, LOGGER, user_data
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage, deleteMessage
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.bot_utils import new_task

vt_sessions = {}

VT_OPTIONS = [
    "Rename",
    "Video + Video", "Video + Audio",
    "Video + Subtitle", "Compress",
    "Convert", "Extract",
    "Trim", "Remove Stream"
]

RESOLUTIONS = ["144p", "240p", "360p", "480p", "540p", "720p", "1080p"]

async def _timeout_handler(user_id, message_id):
    await sleep(180)
    message_id = str(message_id)
    if message_id in vt_sessions:
        session = vt_sessions[message_id]
        menu_msg = session.get('menu_msg')
        if 'event' in session:
            session['event'].set()
        del vt_sessions[message_id]
        if menu_msg:
            try:
                await editMessage(menu_msg, "<b>Video Tools menu expired!</b>")
            except:
                pass

def _get_vt_buttons(user_id, message_id):
    buttons = ButtonMaker()
    message_id = str(message_id)
    session = vt_sessions[message_id]
    options = session['options']

    # Row 1: Rename (Full Width)
    name = f"✅ Rename" if "Rename" in options else "Rename"
    buttons.ibutton(name, f"vt {user_id} {message_id} Rename")

    # Other options (2 columns)
    for i in range(1, len(VT_OPTIONS), 2):
        opt1 = VT_OPTIONS[i]
        name1 = f"✅ {opt1}" if opt1 in options else opt1
        buttons.ibutton(name1, f"vt {user_id} {message_id} {opt1}")
        if i + 1 < len(VT_OPTIONS):
            opt2 = VT_OPTIONS[i+1]
            name2 = f"✅ {opt2}" if opt2 in options else opt2
            buttons.ibutton(name2, f"vt {user_id} {message_id} {opt2}")

    # Done (Full Width)
    done_name = "🟩 Done / Start Process"
    if options:
        done_name = f"🟩 Done / Start Process ({len(options)})"
    buttons.ibutton(done_name, f"vt {user_id} {message_id} done")

    # Cancel (Full Width)
    buttons.ibutton("❌ Cancel", f"vt {user_id} {message_id} cancel")

    return buttons.build_menu(2)

def _get_compress_buttons(user_id, message_id):
    buttons = ButtonMaker()
    message_id = str(message_id)
    selected = vt_sessions[message_id].get('resolutions', [])
    for res in RESOLUTIONS:
        name = f"✅ {res}" if res in selected else res
        buttons.ibutton(name, f"vt {user_id} {message_id} res {res}")
    buttons.ibutton("💾 Save", f"vt {user_id} {message_id} main", position="footer")
    return buttons.build_menu(3)

def _get_track_buttons(user_id, message_id):
    buttons = ButtonMaker()
    message_id = str(message_id)
    session = vt_sessions[message_id]
    tracks = session.get('available_tracks', [])
    selected = session.get('remove_tracks', [])
    for track in tracks:
        name = f"❌ {track['name']}" if track['id'] in selected else track['name']
        buttons.ibutton(name, f"vt {user_id} {message_id} trm {track['id']}")
    buttons.ibutton("🟩 Done", f"vt {user_id} {message_id} track_done", position="footer")
    return buttons.build_menu(1)

async def video_tools_menu(client, message, isQbit, isLeech, sameDir, bulk):
    user_id = message.from_user.id
    message_id = str(message.id)

    vt_sessions[message_id] = {
        'user_id': user_id,
        'isQbit': isQbit,
        'isLeech': isLeech,
        'sameDir': sameDir,
        'bulk': bulk,
        'options': set(),
        'time': time()
    }

    menu_msg = await sendMessage(message, "<b>Advanced Video Tools Pipeline</b>\nSelect the tools you want to apply:", _get_vt_buttons(user_id, message_id))
    vt_sessions[message_id]['menu_msg'] = menu_msg
    create_task(_timeout_handler(user_id, message_id))

async def _vt_input_handler(client, message, message_id, handler, mode):
    user_id = message.from_user.id
    message_id = str(message_id)
    if message_id in vt_sessions and vt_sessions[message_id]['user_id'] == user_id:
        if handler:
            bot.remove_handler(*handler, group=-1) if isinstance(handler, tuple) else bot.remove_handler(handler, group=-1)
        if mode == 'rename':
            vt_sessions[message_id]['new_name'] = message.text
            await deleteMessage(message)
            msg = f"<b>Advanced Video Tools Pipeline</b>\nSelect the tools you want to apply:\n\n<b>New Name:</b> <code>{message.text}</code>"
            await editMessage(vt_sessions[message_id]['menu_msg'], msg, _get_vt_buttons(user_id, message_id))
        elif mode == 'audio':
            link = message.text or (message.reply_to_message.link if message.reply_to_message else message.link if message.media else None)
            vt_sessions[message_id]['audio_source'] = link
            await deleteMessage(message)
            msg = f"<b>Advanced Video Tools Pipeline</b>\nSelect the tools you want to apply:\n\n<b>Audio Source Set!</b>"
            await editMessage(vt_sessions[message_id]['menu_msg'], msg, _get_vt_buttons(user_id, message_id))
        elif mode == 'trim':
            vt_sessions[message_id]['trim_duration'] = message.text
            await deleteMessage(message)
            msg = f"<b>Advanced Video Tools Pipeline</b>\nSelect the tools you want to apply:\n\n<b>Trim Duration:</b> <code>{message.text}</code>"
            await editMessage(vt_sessions[message_id]['menu_msg'], msg, _get_vt_buttons(user_id, message_id))

@new_task
async def vt_callback(client, query):
    user_id = query.from_user.id
    data = query.data.split()
    owner_id = int(data[1])
    message_id = str(data[2])
    option = " ".join(data[3:])

    if user_id != owner_id:
        return await query.answer("This is not your task session!", show_alert=True)

    if message_id not in vt_sessions:
        return await query.answer("Session expired or invalid!", show_alert=True)

    session = vt_sessions[message_id]

    if option == "cancel":
        if 'event' in session: session['event'].set()
        del vt_sessions[message_id]
        await deleteMessage(session['menu_msg'])
        await query.answer("Video Tools cancelled.")
    elif option == "done":
        vt_options = list(session['options'])
        sameDir = session['sameDir'] or {}
        if not isinstance(sameDir, dict):
            sameDir = {}
        sameDir['vt_options'] = vt_options
        sameDir['new_name'] = session.get('new_name')
        sameDir['audio_source'] = session.get('audio_source')
        sameDir['resolutions'] = session.get('resolutions')
        sameDir['trim_duration'] = session.get('trim_duration')

        from bot.modules.mirror_leech import _mirror_leech
        await deleteMessage(session['menu_msg'])

        orig_message = session['menu_msg'].reply_to_message
        isQbit = session['isQbit']
        isLeech = session['isLeech']
        bulk = session['bulk']

        del vt_sessions[message_id]
        await _mirror_leech(client, orig_message, isQbit, isLeech, sameDir, bulk)
    elif option == "main":
        msg = "<b>Advanced Video Tools Pipeline</b>\nSelect the tools you want to apply:"
        if session.get('new_name'): msg += f"\n\n<b>New Name:</b> <code>{session['new_name']}</code>"
        if session.get('resolutions'): msg += f"\n<b>Resolutions:</b> {', '.join(session['resolutions'])}"
        await editMessage(session['menu_msg'], msg, _get_vt_buttons(user_id, message_id))
    elif option == "track_done":
        if 'event' in session:
            session['event'].set()
    elif option.startswith("res "):
        res = option.split()[1]
        if 'resolutions' not in session: session['resolutions'] = []
        if res in session['resolutions']: session['resolutions'].remove(res)
        else: session['resolutions'].append(res)
        await editMessage(session['menu_msg'], "<b>Select Resolutions to Compress:</b>", _get_compress_buttons(user_id, message_id))
    elif option.startswith("trm "):
        tr_id = option.split()[1]
        if 'remove_tracks' not in session: session['remove_tracks'] = []
        if tr_id in session['remove_tracks']: session['remove_tracks'].remove(tr_id)
        else: session['remove_tracks'].append(tr_id)
        await editMessage(session['menu_msg'], "<b>Select Tracks to REMOVE:</b>", _get_track_buttons(user_id, message_id))
    else:
        if option in session['options']:
            session['options'].remove(option)
            if option == "Rename" and 'new_name' in session: del session['new_name']
            if option == "Compress" and 'resolutions' in session: del session['resolutions']
            if option == "Video + Audio" and 'audio_source' in session: del session['audio_source']
            if option == "Trim" and 'trim_duration' in session: del session['trim_duration']
        else:
            session['options'].add(option)
            if option == "Rename":
                await query.answer("Please reply with your new custom output name.", show_alert=True)
                handler = []
                h = bot.add_handler(MessageHandler(lambda c, m: _vt_input_handler(c, m, message_id, handler[0], 'rename'), filters=user(user_id)), group=-1)
                handler.append(h)
                create_task(sleep(30)).add_done_callback(lambda _: bot.remove_handler(*h, group=-1) if isinstance(h, tuple) else bot.remove_handler(h, group=-1))
                return
            elif option == "Video + Audio":
                await query.answer("Please send or reply with the audio file, link, or video.", show_alert=True)
                handler = []
                h = bot.add_handler(MessageHandler(lambda c, m: _vt_input_handler(c, m, message_id, handler[0], 'audio'), filters=user(user_id)), group=-1)
                handler.append(h)
                create_task(sleep(60)).add_done_callback(lambda _: bot.remove_handler(*h, group=-1) if isinstance(h, tuple) else bot.remove_handler(h, group=-1))
                return
            elif option == "Trim":
                await query.answer("Please reply with trim duration (e.g., 00:01:00 or 60).", show_alert=True)
                handler = []
                h = bot.add_handler(MessageHandler(lambda c, m: _vt_input_handler(c, m, message_id, handler[0], 'trim'), filters=user(user_id)), group=-1)
                handler.append(h)
                create_task(sleep(30)).add_done_callback(lambda _: bot.remove_handler(*h, group=-1) if isinstance(h, tuple) else bot.remove_handler(h, group=-1))
                return
            elif option == "Compress":
                await editMessage(session['menu_msg'], "<b>Select Resolutions to Compress:</b>", _get_compress_buttons(user_id, message_id))
                return

        msg = "<b>Advanced Video Tools Pipeline</b>\nSelect the tools you want to apply:"
        if session.get('new_name'): msg += f"\n\n<b>New Name:</b> <code>{session['new_name']}</code>"
        if session.get('resolutions'): msg += f"\n<b>Resolutions:</b> {', '.join(session['resolutions'])}"
        await editMessage(session['menu_msg'], msg, _get_vt_buttons(user_id, message_id))
        await query.answer()

bot.add_handler(CallbackQueryHandler(vt_callback, filters=regex(r"^vt")))
