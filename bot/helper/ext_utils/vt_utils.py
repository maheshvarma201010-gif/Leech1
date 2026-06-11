import os
import json
from natsort import natsorted
from asyncio import create_subprocess_exec, create_subprocess_shell
from asyncio.subprocess import PIPE
from bot import LOGGER, cores, threads
from bot.core.config_manager import BinConfig

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

async def compress_video(input_path, output_path, resolution):
    height = resolution.replace("p", "")
    cmd = [
        BinConfig.FFMPEG_NAME, "-hide_banner", "-loglevel", "error",
        "-i", input_path,
        "-vf", f"scale=-2:{height}",
        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
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
        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
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
