from pyrogram.handlers import CallbackQueryHandler
from pyrogram.filters import regex, user
from asyncio import sleep, create_task
from time import time

from bot import bot, LOGGER, user_data
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage, deleteMessage
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.bot_utils import new_task

vt_sessions = {}

VT_OPTIONS = [
    "Rename",
    "Video + Video", "Video + Audio",
    "Video + Subtitle", "SubSync",
    "Compress", "Convert",
    "Watermark", "Extract",
    "Trim", "Remove Stream",
    "Reorder Streams", "Speed"
]

async def _timeout_handler(user_id, message_id):
    await sleep(180)
    if message_id in vt_sessions:
        menu_msg = vt_sessions[message_id].get('menu_msg')
        del vt_sessions[message_id]
        if menu_msg:
            try:
                await editMessage(menu_msg, "<b>Video Tools menu expired!</b>")
            except:
                pass

def _get_vt_buttons(user_id, message_id):
    buttons = ButtonMaker()
    options = vt_sessions[message_id]['options']

    # Row 1: Rename (Full Width)
    name = f"✅ Rename" if "Rename" in options else "Rename"
    buttons.ibutton(name, f"vt {user_id} {message_id} Rename")

    # Row 2 to 7 (2 columns)
    for i in range(1, 13, 2):
        opt1 = VT_OPTIONS[i]
        opt2 = VT_OPTIONS[i+1]
        name1 = f"✅ {opt1}" if opt1 in options else opt1
        name2 = f"✅ {opt2}" if opt2 in options else opt2
        buttons.ibutton(name1, f"vt {user_id} {message_id} {opt1}")
        buttons.ibutton(name2, f"vt {user_id} {message_id} {opt2}")

    # Row 8: Done (Full Width)
    done_name = "Done / Start Process"
    if options:
        done_name = f"🟢 {done_name} ({len(options)})"
    buttons.ibutton(done_name, f"vt {user_id} {message_id} done")

    # Row 9: Cancel (Full Width)
    buttons.ibutton("Cancel", f"vt {user_id} {message_id} cancel")

    return buttons.build_menu(2)

async def video_tools_menu(client, message, isQbit, isLeech, sameDir, bulk):
    user_id = message.from_user.id
    message_id = message.id

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

from pyrogram.handlers import MessageHandler

async def _rename_handler(client, message, message_id, handler):
    user_id = message.from_user.id
    if message_id in vt_sessions and vt_sessions[message_id]['user_id'] == user_id:
        bot.remove_handler(*handler) if isinstance(handler, tuple) else bot.remove_handler(handler)
        vt_sessions[message_id]['new_name'] = message.text
        await deleteMessage(message)
        await editMessage(vt_sessions[message_id]['menu_msg'], "<b>Advanced Video Tools Pipeline</b>\nSelect the tools you want to apply:\n\n<b>New Name:</b> <code>" + message.text + "</code>", _get_vt_buttons(user_id, message_id))

@new_task
async def vt_callback(client, query):
    user_id = query.from_user.id
    data = query.data.split()
    owner_id = int(data[1])
    message_id = int(data[2])
    option = " ".join(data[3:])

    if user_id != owner_id:
        return await query.answer("This is not your task session!", show_alert=True)

    if message_id not in vt_sessions:
        return await query.answer("Session expired or invalid!", show_alert=True)

    session = vt_sessions[message_id]

    if option == "cancel":
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

        from bot.modules.mirror_leech import _mirror_leech
        await deleteMessage(session['menu_msg'])

        orig_message = session['menu_msg'].reply_to_message
        isQbit = session['isQbit']
        isLeech = session['isLeech']
        bulk = session['bulk']

        del vt_sessions[message_id]
        await _mirror_leech(client, orig_message, isQbit, isLeech, sameDir, bulk)
    else:
        if option in session['options']:
            session['options'].remove(option)
            if option == "Rename" and 'new_name' in session:
                del session['new_name']
        else:
            session['options'].add(option)
            if option == "Rename":
                await query.answer("Send the new name now...", show_alert=True)
                handler = []
                h = bot.add_handler(MessageHandler(
                    lambda c, m: _rename_handler(c, m, message_id, handler[0]),
                    filters=user(user_id)
                ), group=-1)
                handler.append(h)
                create_task(sleep(30)).add_done_callback(lambda _: bot.remove_handler(*h) if isinstance(h, tuple) else bot.remove_handler(h))
                return

        msg = "<b>Advanced Video Tools Pipeline</b>\nSelect the tools you want to apply:"
        if session.get('new_name'):
            msg += f"\n\n<b>New Name:</b> <code>{session['new_name']}</code>"
        await editMessage(session['menu_msg'], msg, _get_vt_buttons(user_id, message_id))
        await query.answer()

bot.add_handler(CallbackQueryHandler(vt_callback, filters=regex(r"^vt")))
