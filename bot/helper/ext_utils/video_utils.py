import os
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from aiofiles.os import path as aiopath, listdir, remove as aioremove
from bot import LOGGER, user_data

async def ffmpeg_merge(input_dir, output_file, listener):
    LOGGER.info(f"Merging videos in {input_dir}")
    video_files = [f for f in await listdir(input_dir) if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv'))]
    video_files.sort()

    if not video_files:
        return None

    if len(video_files) == 1:
        return os.path.join(input_dir, video_files[0])

    list_file = os.path.join(input_dir, "concat_list.txt")
    with open(list_file, 'w') as f:
        for file in video_files:
            f.write(f"file '{os.path.abspath(os.path.join(input_dir, file))}'\n")

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", list_file,
        "-c", "copy", output_file, "-y"
    ]

    listener.suproc = await create_subprocess_exec(*cmd, stderr=PIPE)
    code = await listener.suproc.wait()

    if code == 0:
        for file in video_files:
            try:
                await aioremove(os.path.join(input_dir, file))
            except:
                pass
        await aioremove(list_file)
        return output_file
    else:
        err = (await listener.suproc.stderr.read()).decode().strip()
        LOGGER.error(f"FFmpeg Merge Error: {err}")
        return None

async def ffmpeg_process(input_path, output_path, options, listener):
    LOGGER.info(f"Processing video {input_path} with options: {options}")

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", input_path]

    v_codec = "copy"
    a_codec = "copy"
    s_codec = "copy"
    vf = []
    af = []
    maps = ["-map", "0:v:0?", "-map", "0:a:?", "-map", "0:s?"]
    input_idx = 1

    if "Compress" in options:
        v_codec = "libx264"
        cmd.extend(["-crf", "24", "-preset", "medium"])
        a_codec = "aac"

    if "Convert" in options:
        if not output_path.lower().endswith(".mp4"):
            output_path = os.path.splitext(output_path)[0] + ".mp4"

    if "Extract" in options:
        maps = ["-map", "0:a:0"]
        output_path = os.path.splitext(output_path)[0] + ".m4a"
        v_codec = None

    if "Watermark" in options:
        from bot import config_dict
        wm_path = config_dict.get('WATERMARK_PATH')
        if wm_path and os.path.exists(wm_path):
            cmd.extend(["-i", wm_path])
            vf.append(f"overlay=main_w-overlay_w-10:10")
            v_codec = "libx264"
            input_idx += 1

    if "Speed" in options:
        vf.append("setpts=0.67*PTS")
        af.append("atempo=1.5")
        v_codec = "libx264"
        a_codec = "aac"

    if "Remove Stream" in options:
        cmd.extend(["-sn"])
        if "-map" in maps:
            new_maps = []
            for i in range(0, len(maps), 2):
                if ":s" not in maps[i+1]:
                    new_maps.extend([maps[i], maps[i+1]])
            maps = new_maps

    if "Trim" in options:
        cmd.extend(["-t", "60"])

    if "SubSync" in options:
        LOGGER.info("SubSync selected. This requires ffsubsync to be installed.")

    if "Reorder Streams" in options:
        maps = ["-map", "0:v:0", "-map", "0:a:1", "-map", "0:a:0", "-map", "0:s?"]

    if "Video + Audio" in options or "Video + Subtitle" in options:
        input_dir = os.path.dirname(input_path)
        other_files = [f for f in await listdir(input_dir) if os.path.join(input_dir, f) != input_path]
        for f in other_files:
            f_path = os.path.join(input_dir, f)
            if "Video + Audio" in options and f.lower().endswith(('.mp3', '.m4a', '.aac', '.wav')):
                cmd.extend(["-i", f_path])
                maps = ["-map", "0:v:0", "-map", f"{input_idx}:a:0"]
                input_idx += 1
                break
            if "Video + Subtitle" in options and f.lower().endswith(('.srt', '.vtt', '.ass')):
                cmd.extend(["-i", f_path])
                maps = ["-map", "0:v:0", "-map", "0:a:?", "-map", f"{input_idx}:s:0"]
                s_codec = "srt" if f.lower().endswith(".srt") else "ass"
                input_idx += 1
                break

    cmd.extend(maps)

    # Metadata injection
    user_id = listener.message.from_user.id
    metadata = user_data.get(user_id, {}).get("lmeta") or listener.user_dict.get("lmeta")
    if metadata:
        cmd.extend(["-metadata", f"title={metadata}", "-metadata:s:v", f"title={metadata}", "-metadata:s:a", f"title={metadata}"])
        cmd.extend(["-map_metadata", "-1"]) # Clear old tags

    if vf:
        cmd.extend(["-vf", ",".join(vf)])
    if af:
        cmd.extend(["-af", ",".join(af)])

    if v_codec: cmd.extend(["-c:v", v_codec])
    if a_codec: cmd.extend(["-c:a", a_codec])
    if s_codec: cmd.extend(["-c:s", s_codec])

    cmd.extend([output_path, "-y"])

    listener.suproc = await create_subprocess_exec(*cmd, stderr=PIPE)
    code = await listener.suproc.wait()

    if code == 0:
        await aioremove(input_path)
        return output_path
    else:
        err = (await listener.suproc.stderr.read()).decode().strip()
        LOGGER.error(f"FFmpeg Process Error: {err}")
        return None
