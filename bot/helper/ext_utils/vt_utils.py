import os
import json
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
    # Use concat demuxer
    concat_file = f"{output_path}.txt"
    with open(concat_file, "w") as f:
        for v in video_list:
            f.write(f"file '{os.path.abspath(v)}'\n")

    cmd = [
        "taskset", "-c", f"{cores}", BinConfig.FFMPEG_NAME,
        "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", concat_file,
        "-c", "copy", "-threads", f"{threads}", output_path
    ]
    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await process.communicate()
    if os.path.exists(concat_file):
        os.remove(concat_file)
    return process.returncode == 0

async def mux_audio_subtitle(video_path, source_path, output_path, stream_type="audio"):
    # stream_type: "audio" or "subtitle"
    # source_path can be audio file or video file containing the stream
    cmd = [
        "taskset", "-c", f"{cores}", BinConfig.FFMPEG_NAME,
        "-hide_banner", "-loglevel", "error",
        "-i", video_path, "-i", source_path,
        "-map", "0:v", "-map", "0:a?", "-map", "0:s?",
    ]

    if stream_type == "audio":
        cmd.extend(["-map", "1:a:0"]) # Map first audio stream from source
    else:
        cmd.extend(["-map", "1:s:0"]) # Map first subtitle stream from source

    cmd.extend(["-c", "copy", "-threads", f"{threads}", output_path])

    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await process.communicate()
    return process.returncode == 0

async def compress_video(input_path, output_path, resolution):
    # resolution e.g. "720p" -> "720"
    height = resolution.replace("p", "")
    cmd = [
        "taskset", "-c", f"{cores}", BinConfig.FFMPEG_NAME,
        "-hide_banner", "-loglevel", "error",
        "-i", input_path,
        "-vf", f"scale=-2:{height}",
        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
        "-c:a", "aac", "-b:a", "128k",
        "-threads", f"{threads}", output_path
    ]
    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await process.communicate()
    return process.returncode == 0

async def trim_video(input_path, output_path, start_time, end_time):
    cmd = [
        "taskset", "-c", f"{cores}", BinConfig.FFMPEG_NAME,
        "-hide_banner", "-loglevel", "error",
        "-ss", start_time, "-to", end_time,
        "-i", input_path,
        "-c", "copy", "-threads", f"{threads}", output_path
    ]
    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await process.communicate()
    return process.returncode == 0

async def remove_streams(input_path, output_path, map_args):
    # map_args: list of strings like ["-map", "0:v:0", "-map", "0:a:0"]
    cmd = [
        "taskset", "-c", f"{cores}", BinConfig.FFMPEG_NAME,
        "-hide_banner", "-loglevel", "error",
        "-i", input_path
    ]
    cmd.extend(map_args)
    cmd.extend(["-c", "copy", "-threads", f"{threads}", output_path])

    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await process.communicate()
    return process.returncode == 0
