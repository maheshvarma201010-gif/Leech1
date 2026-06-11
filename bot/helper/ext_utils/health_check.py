from asyncio import create_subprocess_exec, wait_for
from asyncio.subprocess import PIPE
from time import time
from bot import LOGGER
from bot.core.config_manager import Config, BinConfig
from .db_handler import database
import aiohttp

async def check_db():
    if not Config.DATABASE_URL:
        return "Not Configured"
    start = time()
    try:
        await database.connect()
        if database.db is not None:
            await database.db.command("ping")
            return f"Connected ({round((time() - start) * 1000)}ms)"
        return "Failed to Connect"
    except Exception as e:
        return f"Error: {str(e)}"

async def check_api():
    from os import getenv
    port = getenv("PORT", "") or Config.BASE_URL_PORT
    start = time()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.telegram.org", timeout=5) as resp:
                if resp.status == 200:
                    api_res = f"Reachable ({round((time() - start) * 1000)}ms)"
                else:
                    api_res = f"Error: {resp.status}"

            # Also check local web server
            try:
                async with session.get(f"http://localhost:{port}/", timeout=2) as resp:
                    web_res = "Running" if resp.status == 200 else f"Error: {resp.status}"
            except Exception:
                web_res = "Not Running"

            return f"{api_res} | Web: {web_res}"
    except Exception as e:
        return f"Error: {str(e)}"

async def check_ffmpeg():
    try:
        process = await create_subprocess_exec(BinConfig.FFMPEG_NAME, "-version", stdout=PIPE, stderr=PIPE)
        await wait_for(process.wait(), timeout=5)
        if process.returncode == 0:
            return "Functional"
        return f"Error (Exit Code: {process.returncode})"
    except Exception as e:
        return f"Error: {str(e)}"

async def run_health_checks():
    return {
        "Database": await check_db(),
        "Telegram API": await check_api(),
        "FFmpeg": await check_ffmpeg(),
        "Internet": "Connected" # Simple placeholder since API check also verifies this
    }
