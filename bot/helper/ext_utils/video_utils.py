import os
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from aiofiles.os import path as aiopath, listdir, remove as aioremove
from bot import LOGGER, user_data, bot
import json

async def get_track_info(input_path):
    cmd = [
        "ffprobe", "-hide_banner", "-loglevel", "error",
        "-print_format", "json", "-show_streams", input_path
    ]
    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        LOGGER.error(f"ffprobe error: {stderr.decode()}")
        return []

    data = json.loads(stdout.decode())
    tracks = []
    for stream in data.get('streams', []):
        s_type = stream.get('codec_type')
        if s_type not in ['audio', 'subtitle']:
            continue
        idx = stream.get('index')
        lang = stream.get('tags', {}).get('language', 'und')
        title = stream.get('tags', {}).get('title', '')
        t_id = f"{s_type[0]}{idx}" # a1, s2 etc
        name = f"{s_type.capitalize()} {idx} ({lang})"
        if title: name += f" - {title}"
        tracks.append({'id': t_id, 'name': name})
    return tracks

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

async def ffmpeg_process(input_path, output_dir, options, listener, resolutions=None, audio_source=None, trim_duration=None, remove_tracks=None):
    LOGGER.info(f"Processing video {input_path} with options: {options}")

    base_name = os.path.basename(input_path)
    final_outputs = []

    async def run_ffmpeg(input_file, output_file, res=None):
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", input_file]

        v_codec = "copy"
        a_codec = "copy"
        s_codec = "copy"
        vf = []
        af = []
        maps = ["-map", "0:v:0?", "-map", "0:a:?", "-map", "0:s?"]
        input_idx = 1

        if res:
            v_codec = "libx264"
            cmd.extend(["-crf", "24", "-preset", "medium"])
            width = res.replace("p", "")
            vf.append(f"scale=-2:{width}")
            a_codec = "aac"
        elif "Compress" in options:
            v_codec = "libx264"
            cmd.extend(["-crf", "24", "-preset", "medium"])
            a_codec = "aac"

        if "Convert" in options:
            if not output_file.lower().endswith(".mp4"):
                output_file = os.path.splitext(output_file)[0] + ".mp4"

        if "Extract" in options:
            maps = ["-map", "0:a:0"]
            output_file = os.path.splitext(output_file)[0] + ".m4a"
            v_codec = None

        if "Trim" in options and trim_duration:
            cmd.extend(["-t", str(trim_duration)])

        if "Remove Stream" in options and remove_tracks:
            new_maps = []
            # Extract types and indices from maps, filtered by user selection
            for i in range(0, len(maps), 2):
                # map format: '0:v:0?', '0:a:?', '1:a:0', etc.
                parts = maps[i+1].split(':')
                m_type = parts[-2] if len(parts) > 2 else parts[-1][0]
                m_idx = parts[-1].replace('?', '')
                track_id = f"{m_type}{m_idx}"
                if track_id not in remove_tracks:
                    new_maps.extend([maps[i], maps[i+1]])
            maps = new_maps

        if audio_source:
            cmd.extend(["-i", audio_source])
            maps = ["-map", "0:v:0", "-map", f"{input_idx}:a:0"]
            input_idx += 1

        if "Video + Subtitle" in options:
            input_dir = os.path.dirname(input_file)
            other_files = [f for f in await listdir(input_dir) if os.path.join(input_dir, f) != input_file]
            for f in other_files:
                f_path = os.path.join(input_dir, f)
                if f.lower().endswith(('.srt', '.vtt', '.ass')):
                    cmd.extend(["-i", f_path])
                    maps.extend(["-map", f"{input_idx}:s:0"])
                    s_codec = "srt" if f.lower().endswith(".srt") else "ass"
                    input_idx += 1
                    break

        cmd.extend(maps)

        # Metadata injection
        user_id = listener.message.from_user.id
        metadata = user_data.get(user_id, {}).get("lmeta") or listener.user_dict.get("lmeta")
        if metadata:
            cmd.extend(["-metadata", f"title={metadata}", "-metadata:s:v", f"title={metadata}", "-metadata:s:a", f"title={metadata}"])
            cmd.extend(["-map_metadata", "-1"])

        if vf: cmd.extend(["-vf", ",".join(vf)])
        if af: cmd.extend(["-af", ",".join(af)])

        if v_codec: cmd.extend(["-c:v", v_codec])
        if a_codec: cmd.extend(["-c:a", a_codec])
        if s_codec: cmd.extend(["-c:s", s_codec])

        cmd.extend([output_file, "-y"])

        listener.suproc = await create_subprocess_exec(*cmd, stderr=PIPE)
        code = await listener.suproc.wait()
        return output_file if code == 0 else None

    if "Compress" in options and resolutions:
        for res in resolutions:
            out_name = f"{os.path.splitext(base_name)[0]}_{res}.mp4"
            out_path = os.path.join(output_dir, out_name)
            res_out = await run_ffmpeg(input_path, out_path, res)
            if res_out: final_outputs.append(res_out)
    else:
        out_name = f"processed_{os.path.splitext(base_name)[0]}.mp4"
        out_path = os.path.join(output_dir, out_name)
        res_out = await run_ffmpeg(input_path, out_path)
        if res_out: final_outputs.append(res_out)

    if final_outputs:
        await aioremove(input_path)
        return final_outputs
    return None
