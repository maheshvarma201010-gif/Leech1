import os
import re
import json
from natsort import natsorted
from asyncio import create_subprocess_exec, create_subprocess_shell, Event, wait_for
from asyncio.subprocess import PIPE
from bot import LOGGER, cores, threads
from bot.core.config_manager import BinConfig
from os import path as ospath
from aioshutil import move
from aiofiles.os import makedirs, remove, path as aiopath
from pyrogram.filters import user, reply, regex, photo, audio, video, document, text as pyro_text, chat
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from contextlib import suppress

async def get_streams_info(file_path):
    cmd = [
        "ffprobe", "-hide_banner", "-loglevel", "error",
        "-print_format", "json", "-show_streams", file_path
    ]
    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        return None
    return json.loads(stdout).get("streams", [])

async def merge_videos(video_list, output_path):
    concat_file = f"{output_path}.txt"
    with open(concat_file, "w") as f:
        for v in video_list:
            f.write(f"file '{os.path.abspath(v)}'\n")

    cmd = [
        BinConfig.FFMPEG_NAME, "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", concat_file,
        "-c", "copy", "-threads", f"{threads}", output_path
    ]
    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    await process.wait()
    if os.path.exists(concat_file):
        os.remove(concat_file)
    return process.returncode == 0

async def mux_audio_subtitle(video_path, source_path, output_path, stream_type="audio"):
    cmd = [
        BinConfig.FFMPEG_NAME, "-hide_banner", "-loglevel", "error",
        "-i", video_path, "-i", source_path,
        "-map", "0:v", "-map", "0:a?", "-map", "0:s?",
    ]

    if stream_type == "audio":
        cmd.extend(["-map", "1:a:0"])
    else:
        cmd.extend(["-map", "1:s:0"])

    cmd.extend(["-c", "copy", "-threads", f"{threads}", output_path])

    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    await process.wait()
    return process.returncode == 0

async def process_vt(self, up_path, up_dir, gid):
    from .bot_utils import sync_to_async
    from .files_utils import is_archive, is_archive_split, get_document_type, get_path_size
    from .links_utils import is_url
    from ..telegram_helper.message_utils import send_message, edit_message, delete_message
    from ..telegram_helper.button_build import ButtonMaker
    from bot.core.tg_client import TgClient
    from pyrogram.enums import ButtonStyle

    # Auto-Extraction logic for Video+Video
    if self.vt_data.get("video_video") and not self.extract:
        if self.is_file and (is_archive(up_path) or is_archive_split(up_path)):
            up_path = await self.proceed_extract(up_path, self.mid)
            if self.is_cancelled: return up_path
            self.is_file = await aiopath.isfile(up_path)
            up_dir = self.dir

    # Step 1: Video + Video Merge
    if self.vt_data.get("video_video") and not self.is_file:
        video_files = []
        for r, d, f in await sync_to_async(os.walk, up_path):
            for file in f:
                f_path = ospath.join(r, file)
                if (await get_document_type(f_path))[0]:
                    video_files.append(f_path)
        video_files = natsorted(video_files)
        if video_files:
            # Logic for output name if -m not provided
            if self.vt_data.get("rename"):
                output_name = self.vt_data["rename"]
                if not output_name.endswith(ospath.splitext(video_files[0])[1]):
                    output_name += ospath.splitext(video_files[0])[1]
            else:
                output_name = f"merged_{ospath.basename(video_files[0])}"

            output_merge = ospath.join(up_dir, output_name)
            if await merge_videos(video_files, output_merge):
                for v in video_files:
                    with suppress(Exception): await remove(v)
                up_path = output_merge
                self.is_file = True
                self.name = ospath.basename(up_path)

    # Step 2: Muxing (Audio/Subtitle)
    for mux_type in ["video_audio", "video_subtitle"]:
        if self.vt_data.get(mux_type):
            label = "audio" if mux_type == "video_audio" else "subtitle"
            msg = await send_message(self.message, f"{self.tag} <b>Please send or reply with the {label} file, link, or video containing the {label}.</b>")
            source_event = Event()
            source_data = {}

            async def _reply_cb(client, message):
                if message.audio or message.video or message.document:
                    source_data["msg"] = message
                elif message.text and is_url(message.text):
                    source_data["link"] = message.text
                source_event.set()

            handler = TgClient.bot.add_handler(MessageHandler(_reply_cb, filters=chat(self.message.chat.id) & user(self.user_id) & (reply | photo | audio | video | document | pyro_text)), group=-1)
            try:
                await wait_for(source_event.wait(), timeout=180)
            except:
                await send_message(self.message, f"{self.tag} {label} muxing timed out!")
            finally:
                TgClient.bot.remove_handler(handler, group=-1)
                await delete_message(msg)

            if source_data:
                src_path = ospath.join(self.dir, f"{label}_source")
                if "msg" in source_data:
                    src_path = await source_data["msg"].download(file_name=src_path)
                elif "link" in source_data:
                    import aiohttp
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(source_data["link"]) as resp:
                                if resp.status == 200:
                                    with open(src_path, 'wb') as f:
                                        f.write(await resp.read())
                    except Exception as e: LOGGER.error(f"Download failed: {e}")

                output_mux = ospath.join(up_dir, f"muxed_{label}.mp4")
                if await mux_audio_subtitle(up_path, src_path, output_mux, label):
                    with suppress(Exception): await remove(up_path)
                    with suppress(Exception): await remove(src_path)
                    up_path = output_mux
                    self.is_file = True

    # Step 3: Remove Stream
    if self.vt_data.get("remove_stream"):
        streams = await get_streams_info(up_path)
        if streams:
            def _build_rs_kb(removed):
                btns = ButtonMaker()
                for s in streams:
                    s_idx = s.get("index")
                    s_type = s.get("codec_type")
                    s_lang = s.get("tags", {}).get("language", "und")
                    state = "❌ " if s_idx in removed else ""
                    btns.data_button(f"{state}{s_type} [{s_idx}] ({s_lang})", f"vtrs {self.mid} {s_idx}")
                btns.data_button("✅ Done", f"vtrs {self.mid} done", style=ButtonStyle.SUCCESS)
                return btns.build_menu(2)

            remove_list = []
            rs_event = Event()
            rs_msg = await send_message(self.message, "<b>Select streams to REMOVE (Checkmarked ❌ ones will be removed):</b>", _build_rs_kb(remove_list))

            async def _rs_cb(client, query):
                data = query.data.split()
                if data[2] == "done":
                    rs_event.set()
                elif data[2] == "cancel":
                    rs_event.set()
                    remove_list.clear() # effectively cancel by keeping everything or failing
                else:
                    idx = int(data[2])
                    if idx in remove_list: remove_list.remove(idx)
                    else: remove_list.append(idx)
                    await edit_message(rs_msg, rs_msg.text, _build_rs_kb(remove_list))
                    await query.answer()

            rs_handler = TgClient.bot.add_handler(CallbackQueryHandler(_rs_cb, filters=chat(self.message.chat.id) & regex(f"^vtrs {self.mid}")), group=-1)
            try:
                await wait_for(rs_event.wait(), timeout=300)
            except:
                pass
            finally:
                TgClient.bot.remove_handler(rs_handler, group=-1)
            await delete_message(rs_msg)

            if remove_list:
                map_args = ["-map", "0"]
                for idx in remove_list: map_args.extend(["-map", f"-0:{idx}"])
                output_rs = ospath.join(up_dir, "stream_removed.mp4")
                if await remove_streams(up_path, output_rs, map_args):
                    with suppress(Exception): await remove(up_path)
                    up_path = output_rs

    # Step 4: Convert
    if self.vt_data.get("convert"):
        output_conv = ospath.join(up_dir, "converted_video.mp4")
        if await convert_video(up_path, output_conv):
            with suppress(Exception): await remove(up_path)
            up_path = output_conv
            self.is_file = True

    # Step 5: Trim
    if self.vt_data.get("trim"):
        msg = await send_message(self.message, f"{self.tag} <b>Please reply with start and end time (format: HH:MM:SS-HH:MM:SS or SS-SS).</b>")
        trim_event = Event()
        trim_data = []

        async def _trim_reply(client, message):
            if message.text:
                trim_data.extend(message.text.split("-"))
            trim_event.set()

        handler = TgClient.bot.add_handler(MessageHandler(_trim_reply, filters=chat(self.message.chat.id) & user(self.user_id) & reply), group=-1)
        try:
            await wait_for(trim_event.wait(), timeout=180)
        except:
            pass
        finally:
            TgClient.bot.remove_handler(handler, group=-1)
            await delete_message(msg)

        if len(trim_data) == 2:
            output_trim = ospath.join(up_dir, "trimmed_video.mp4")
            if await trim_video(up_path, output_trim, trim_data[0], trim_data[1]):
                with suppress(Exception): await remove(up_path)
                up_path = output_trim

    # Step 6: Compress
    if self.vt_data.get("compress"):
        compressed_files = []
        for res in self.vt_data["compress"]:
            output_comp = ospath.join(up_dir, f"{ospath.splitext(self.name)[0]}_{res}.mp4")
            if await compress_video(up_path, output_comp, res):
                compressed_files.append(output_comp)
        if compressed_files:
            if self.is_file:
                new_folder = ospath.join(up_dir, ospath.splitext(self.name)[0])
                await makedirs(new_folder, exist_ok=True)
                for cf in compressed_files: await move(cf, ospath.join(new_folder, ospath.basename(cf)))
                with suppress(Exception): await remove(up_path)
                up_path = new_folder
                self.is_file = False
            else:
                for cf in compressed_files: await move(cf, ospath.join(up_path, ospath.basename(cf)))

    # Step 7: Extract tracks
    if self.vt_data.get("extract"):
        ext_dir = ospath.join(up_dir, "extracted_tracks")
        await makedirs(ext_dir, exist_ok=True)
        if await extract_streams(up_path, ext_dir):
            if self.is_file:
                new_folder = ospath.join(up_dir, ospath.splitext(self.name)[0])
                await makedirs(new_folder, exist_ok=True)
                await move(up_path, ospath.join(new_folder, ospath.basename(up_path)))
                await move(ext_dir, new_folder)
                up_path = new_folder
                self.is_file = False
            else:
                await move(ext_dir, up_path)

    # Name Swap Integration
    if self.name_swap:
        def _do_swap(path):
            dir_, name = ospath.split(path)
            new_name = name
            for swap in self.name_swap:
                pattern, res = swap[0], swap[1]
                new_name = re.sub(rf"{pattern}", res, new_name)
            return ospath.join(dir_, new_name)

        if self.is_file:
            new_path = _do_swap(up_path)
            await move(up_path, new_path)
            up_path = new_path
        else:
            for r, d, f in await sync_to_async(os.walk, up_path):
                for file in f:
                    old = ospath.join(r, file)
                    await move(old, _do_swap(old))

    # Metadata Integration
    metadata = getattr(self, "default_metadata_dict", {})
    if metadata:
        if self.is_file:
            output_meta = ospath.join(up_dir, "meta_" + ospath.basename(up_path))
            if await apply_vt_metadata(up_path, output_meta, metadata):
                with suppress(Exception): await remove(up_path)
                up_path = output_meta
                self.is_file = True
        else:
            for r, d, f in await sync_to_async(os.walk, up_path):
                for file in f:
                    f_path = ospath.join(r, file)
                    if (await get_document_type(f_path))[0]:
                        out = ospath.join(r, "meta_" + file)
                        if await apply_vt_metadata(f_path, out, metadata):
                            with suppress(Exception): await remove(f_path)
                            os.rename(out, f_path)

    # Final Rename
    if self.vt_data.get("rename"):
        new_name = self.vt_data["rename"]
        if not new_name.endswith(ospath.splitext(up_path)[1]):
            new_name += ospath.splitext(up_path)[1]
        new_path = ospath.join(ospath.dirname(up_path), new_name)
        await move(up_path, new_path)
        up_path = new_path
        self.name = new_name

    self.size = await get_path_size(up_path)
    return up_path

async def compress_video(input_path, output_path, resolution):
    height = resolution.replace("p", "")
    cmd = [
        BinConfig.FFMPEG_NAME, "-hide_banner", "-loglevel", "error",
        "-i", input_path,
        "-vf", f"scale=-2:{height}",
        "-c:v", "libx264", "-crf", "23", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "128k",
        "-threads", f"{threads}", output_path
    ]
    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    await process.wait()
    return process.returncode == 0

async def convert_video(input_path, output_path):
    cmd = [
        BinConfig.FFMPEG_NAME, "-hide_banner", "-loglevel", "error",
        "-i", input_path,
        "-c:v", "libx264", "-crf", "23", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "128k",
        "-threads", f"{threads}", output_path
    ]
    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    await process.wait()
    return process.returncode == 0

async def trim_video(input_path, output_path, start_time, end_time):
    cmd = [
        BinConfig.FFMPEG_NAME, "-hide_banner", "-loglevel", "error",
        "-ss", start_time, "-to", end_time,
        "-i", input_path,
        "-c", "copy", "-threads", f"{threads}", output_path
    ]
    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    await process.wait()
    return process.returncode == 0

async def remove_streams(input_path, output_path, map_args):
    cmd = [
        BinConfig.FFMPEG_NAME, "-hide_banner", "-loglevel", "error",
        "-i", input_path
    ]
    cmd.extend(map_args)
    cmd.extend(["-c", "copy", "-threads", f"{threads}", output_path])

    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    await process.wait()
    return process.returncode == 0

async def extract_streams(input_path, output_dir):
    streams = await get_streams_info(input_path)
    if not streams: return False

    for s in streams:
        idx = s.get("index")
        codec_type = s.get("codec_type")
        if codec_type not in ["audio", "subtitle"]: continue

        ext = "mka" if codec_type == "audio" else "srt"
        lang = s.get("tags", {}).get("language", "und")
        out_path = os.path.join(output_dir, f"track_{idx}_{lang}.{ext}")

        cmd = [
            BinConfig.FFMPEG_NAME, "-hide_banner", "-loglevel", "error",
            "-i", input_path, "-map", f"0:{idx}", "-c", "copy", out_path
        ]
        process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
        await process.wait()
    return True

async def apply_vt_metadata(input_path, output_path, metadata):
    # metadata: dict of tags
    cmd = [
        BinConfig.FFMPEG_NAME, "-hide_banner", "-loglevel", "error",
        "-i", input_path, "-map_metadata", "-1"
    ]
    for k, v in metadata.items():
        cmd.extend(["-metadata", f"{k}={v}"])

    cmd.extend(["-c", "copy", "-threads", f"{threads}", output_path])
    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    await process.wait()
    return process.returncode == 0
