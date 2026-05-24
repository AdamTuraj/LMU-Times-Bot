# MIT License
#
# Copyright (c) 2026 Adam Turaj
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import json
import ast
import logging
import os
import secrets
import sys
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

from aiohttp import ClientSession, BasicAuth
from dotenv import load_dotenv
from nexios import NexiosApp, MakeConfig
from nexios.http import Request, Response

from utils.database import Database, DatabaseError
from utils.middleware import rate_limit_middleware, auth_middleware

load_dotenv()

# Logging setup
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _log_file_path():
    path_string = Path(__file__).resolve().parent / "logs" / "backend.log"

    path = Path(path_string).expanduser()
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    return path


def configure_logging():
    level = logging.DEBUG if DEBUG else logging.INFO
    log_file = _log_file_path()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d - "
        "%(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=_env_int("LOG_MAX_BYTES", 10 * 1024 * 1024),
        backupCount=_env_int("LOG_BACKUP_COUNT", 5),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(level)

    return log_file


LOG_FILE = configure_logging()
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Config from environment
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "localhost")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_CALLBACK_URL = os.getenv("DISCORD_CALLBACK_URL", "")
HOME_GUILD_ID = os.getenv("HOME_GUILD_ID", "")
APPLICATION_CALLBACK = os.getenv("APPLICATION_CALLBACK", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "../database.db")

DISCORD_API = "https://discord.com/api/v10"

# Initialize app
app = NexiosApp(
    config=MakeConfig(
        debug=DEBUG,
        port=PORT,
        host=HOST,
        discord_client_id=DISCORD_CLIENT_ID,
        discord_client_secret=DISCORD_CLIENT_SECRET,
        discord_callback_url=DISCORD_CALLBACK_URL,
        home_guild_id=HOME_GUILD_ID,
        application_callback=APPLICATION_CALLBACK,
    ),
    title="LMU Times Bot Backend",
    version="0.1.0"
)

database = Database()

# Register middleware
app.add_middleware(lambda req, res, next: auth_middleware(req, res, next, database, logger))
app.add_middleware(lambda req, res, next: rate_limit_middleware(req, res, next, logger))


# Discord OAuth helpers
async def exchange_code_for_token(code):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": app.config.discord_callback_url,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    auth = BasicAuth(app.config.discord_client_id, app.config.discord_client_secret)

    async with ClientSession() as session:
        async with session.post(f"{DISCORD_API}/oauth2/token", data=data, headers=headers, auth=auth) as resp:
            result = await resp.json()
            if resp.status != 200:
                logger.error("Token exchange failed: %s", result)
                return None
            return result


async def fetch_discord_user(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    user_data = {}

    async with ClientSession() as session:
        async with session.get(f"{DISCORD_API}/users/@me", headers=headers) as resp:
            user_data["user"] = await resp.json()

        async with session.get(f"{DISCORD_API}/users/@me/guilds", headers=headers) as resp:
            user_data["guilds"] = await resp.json()

    return user_data


async def get_discord_user_data(code):
    token_data = await exchange_code_for_token(code)
    if not token_data:
        return {"error": "Token exchange failed"}

    try:
        return await fetch_discord_user(token_data["access_token"])
    except Exception as e:
        logger.exception("Error fetching Discord user")
        return {"error": str(e)}
    
@app.get("/version")
async def get_version(req: Request, res: Response):
    try:
        with open("../VERSION", "r") as f:
            version = f.read().strip()
    except Exception as e:
        logger.error("Error reading version file: %s", e)
        return res.status(500).json({"error": "Internal server error"})

    return res.json({"version": version})

_car_models_path = Path(__file__).parent / "car_models.json"
try:
    with open(_car_models_path, "r", encoding="utf-8") as _f:
        CAR_MODELS = json.load(_f)
    logger.info("Loaded %d car models", len(CAR_MODELS))
except Exception as e:
    logger.error("Failed to load car_models.json: %s", e)
    CAR_MODELS = {}


@app.get("/car-models")
async def get_car_models(req: Request, res: Response):
    return res.json(CAR_MODELS)


def leaderboard_to_response(leaderboard):
    try:
        weather = ast.literal_eval(leaderboard[2])
    except:
        weather = {}

    try:
        classes = ast.literal_eval(leaderboard[3])
    except:
        classes = []

    return {
        "track": leaderboard[0],
        "discord_channel": leaderboard[1],
        "weather": weather,
        "classes": classes,
        "tod": leaderboard[5],
        "fixed_setup": leaderboard[6]
    }

# Routes - Leaderboard
@app.get("/leaderboards")
async def get_leaderboards(req: Request, res: Response):
    try:
        leaderboards = await database.get_all_leaderboards()
    except DatabaseError as e:
        logger.error("Database error: %s", e)
        return res.status(500).json({"error": "Internal server error"})

    return res.json([leaderboard_to_response(lb) for lb in leaderboards])


@app.get("/leaderboard/{track}")
async def get_leaderboard(req: Request, res: Response):
    track = req.path_params.get("track")
    if not track:
        return res.status(400).json({"error": "Track parameter required"})

    try:
        leaderboard = await database.get_leaderboard(track)
    except DatabaseError as e:
        logger.error("Database error: %s", e)
        return res.status(500).json({"error": "Internal server error"})

    if not leaderboard:
        return res.status(404).json({"error": "Leaderboard not found"})

    return res.json(leaderboard_to_response(leaderboard))


@app.post("/leaderboard/{track}/submit")
async def submit_time(req: Request, res: Response):
    request_id = uuid.uuid4().hex[:12]
    track = req.path_params.get("track")
    if not track:
        logger.warning("[%s] Rejected submit with missing track", request_id)
        return res.status(400).json({"error": "Track parameter required"})

    user = req.state.user
    logger.info(
        "[%s] Lap submit received: track='%s' user_id='%s' user_name='%s'",
        request_id,
        track,
        user[1],
        user[2],
    )

    try:
        if await database.is_blacklisted(user[1]):
            logger.warning(
                "[%s] Rejected blacklisted user: track='%s' user_id='%s' user_name='%s'",
                request_id,
                track,
                user[1],
                user[2],
            )
            return res.status(403).json({"error": "You are blacklisted"})
    except DatabaseError as e:
        logger.error("[%s] Database error checking blacklist: %s", request_id, e)
        return res.status(500).json({"error": "Internal server error"})

    try:
        body = await req.json
    except Exception:
        logger.warning("[%s] Rejected submit with invalid JSON body", request_id)
        return res.status(400).json({"error": "Invalid JSON body"})

    time_data = body.get("time_data")
    car = body.get("car")
    driver_name = body.get("driver_name")
    car_class = body.get("class")
    logger.debug(
        "[%s] Raw submit payload: track='%s' driver_name=%r car=%r class=%r time_data=%r",
        request_id,
        track,
        driver_name,
        car,
        car_class,
        time_data,
    )

    # Validate required fields
    if not time_data or not isinstance(time_data, dict):
        logger.warning("[%s] Rejected submit with invalid time_data: %r", request_id, time_data)
        return res.status(400).json({"error": "time_data is required and must be an object"})
    if not car or not isinstance(car, str) or not car.strip():
        logger.warning("[%s] Rejected submit with invalid car: %r", request_id, car)
        return res.status(400).json({"error": "car is required and must be a non-empty string"})
    if not driver_name or not isinstance(driver_name, str) or not driver_name.strip():
        logger.warning("[%s] Rejected submit with invalid driver_name: %r", request_id, driver_name)
        return res.status(400).json({"error": "driver_name is required and must be a non-empty string"})
    if not car_class or not isinstance(car_class, str) or not car_class.strip():
        logger.warning("[%s] Rejected submit with invalid class: %r", request_id, car_class)
        return res.status(400).json({"error": "class is required and must be a non-empty string"})

    # Validate time_data structure
    lap_time = time_data.get("lap")
    sector1 = time_data.get("sector1")
    sector2 = time_data.get("sector2")

    if lap_time is None:
        logger.warning("[%s] Rejected submit with missing lap time", request_id)
        return res.status(400).json({"error": "time_data.lap is required"})
    if sector1 is None:
        logger.warning("[%s] Rejected submit with missing sector1", request_id)
        return res.status(400).json({"error": "time_data.sector1 is required"})
    if sector2 is None:
        logger.warning("[%s] Rejected submit with missing sector2", request_id)
        return res.status(400).json({"error": "time_data.sector2 is required"})

    # Validate time values are numbers
    try:
        lap_time = float(lap_time)
        sector1 = float(sector1)
        sector2 = float(sector2)
    except (ValueError, TypeError):
        logger.warning(
            "[%s] Rejected submit with non-numeric times: lap=%r sector1=%r sector2=%r",
            request_id,
            lap_time,
            sector1,
            sector2,
        )
        return res.status(400).json({"error": "All time values must be numbers"})

    # Validate lap_time is positive
    if lap_time <= 0:
        logger.warning("[%s] Rejected submit with non-positive lap: %.3f", request_id, lap_time)
        return res.status(400).json({"error": "lap_time must be greater than 0"})

    # Validate sector times are either -1 or positive
    if sector1 != -1 and sector1 <= 0:
        logger.warning("[%s] Rejected submit with invalid sector1: %.3f", request_id, sector1)
        return res.status(400).json({"error": "sector1 must be -1 or greater than 0"})
    if sector2 != -1 and sector2 <= 0:
        logger.warning("[%s] Rejected submit with invalid sector2: %.3f", request_id, sector2)
        return res.status(400).json({"error": "sector2 must be -1 or greater than 0"})

    # Validate string lengths
    if len(driver_name) > 100:
        logger.warning(
            "[%s] Rejected submit with driver_name too long: length=%d",
            request_id,
            len(driver_name),
        )
        return res.status(400).json({"error": "driver_name must not exceed 100 characters"})
    if len(car) > 100:
        logger.warning("[%s] Rejected submit with car too long: length=%d", request_id, len(car))
        return res.status(400).json({"error": "car must not exceed 100 characters"})
    if len(car_class) > 50:
        logger.warning(
            "[%s] Rejected submit with class too long: length=%d",
            request_id,
            len(car_class),
        )
        return res.status(400).json({"error": "class must not exceed 50 characters"})

    if sector1 != -1 and sector2 != -1:
        sector3 = lap_time - sector1 - sector2
        if sector3 <= 0:
            logger.warning(
                "[%s] Suspicious time data: lap=%.3f sector1=%.3f sector2=%.3f derived_sector3=%.3f",
                request_id,
                lap_time,
                sector1,
                sector2,
                sector3,
            )
        else:
            logger.debug(
                "[%s] Normalized time data: lap=%.3f sector1=%.3f sector2=%.3f derived_sector3=%.3f",
                request_id,
                lap_time,
                sector1,
                sector2,
                sector3,
            )

    try:
        leaderboard = await database.get_leaderboard(track)
    except DatabaseError as e:
        logger.error("[%s] Database error fetching leaderboard: %s", request_id, e)
        return res.status(500).json({"error": "Internal server error"})

    if not leaderboard:
        logger.warning("[%s] Rejected submit for missing leaderboard: track='%s'", request_id, track)
        return res.status(404).json({"error": "Leaderboard not found"})

    time_data = {
        "lap": lap_time,
        "sector1": sector1,
        "sector2": sector2
    }

    try:
        result = await database.submit_lap_time(
            track,
            user[1],
            driver_name.strip(),
            car.strip(),
            car_class.strip(),
            time_data,
            request_id=request_id,
        )
    except DatabaseError as e:
        logger.error("[%s] Database error submitting lap time: %s", request_id, e)
        return res.status(500).json({"error": "Internal server error"})

    logger.info(
        "[%s] Lap submit finished: action='%s' saved=%s track='%s' user_id='%s' "
        "driver_name='%s' car='%s' class='%s' lap=%.3f",
        request_id,
        result.get("action"),
        result.get("saved"),
        track,
        user[1],
        driver_name.strip(),
        car.strip(),
        car_class.strip(),
        lap_time,
    )
    return res.json({
        "message": "Time submitted successfully",
        "saved": result.get("saved"),
        "action": result.get("action"),
    })


# Routes - User
@app.get("/user")
async def get_user(req: Request, res: Response):
    user = req.state.user
    return res.json({"name": user[2]})


@app.post("/user/logout")
async def user_logout(req: Request, res: Response):
    user = req.state.user
    token = req.state.token

    try:
        await database.remove_user_by_token(token)
        logger.info("User '%s' logged out", user[2])
    except DatabaseError as e:
        logger.error("Database error: %s", e)
        return res.status(500).json({"error": "Internal server error"})

    return res.json({"message": "Logged out successfully"})


# Routes - Discord OAuth
@app.get("/discord")
async def discord_oauth(req: Request, res: Response):
    state = req.query_params.get("state", "default")
    oauth_url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={app.config.discord_client_id}"
        f"&response_type=code"
        f"&redirect_uri={app.config.discord_callback_url}"
        f"&scope=identify+guilds"
        f"&state={state}"
    )
    return res.json({"url": oauth_url})


@app.get("/discord/callback")
async def discord_callback(req: Request, res: Response):
    code = req.query_params.get("code")
    state = req.query_params.get("state", "default")

    if not code:
        return res.status(400).json({"error": "Missing code parameter"})

    user_data = await get_discord_user_data(code)

    if "error" in user_data:
        return res.status(400).json(user_data)

    # Check guild membership
    is_member = any(g["id"] == app.config.home_guild_id for g in user_data.get("guilds", []))
    if not is_member:
        return res.status(403).json({"error": "You must be a member of the Discord server"})

    # Create token and save user
    token = secrets.token_urlsafe(32)
    discord_id = user_data["user"]["id"]
    username = user_data["user"]["username"]

    await database.add_user(discord_id, username, token)
    logger.info("User '%s' authenticated", username)

    redirect_url = f"{app.config.application_callback}?state={state}&code={token}&name={username}"
    return res.redirect(redirect_url)


# Startup/shutdown
@app.on_startup
async def startup():
    logger.info("Starting LMU Times Bot Backend")
    logger.info("Backend log file: %s", LOG_FILE)
    await database.init(DATABASE_PATH)

@app.on_shutdown
async def shutdown():
    logger.info("Shutting down")
    await database.close()


def main():
    try:
        logger.info("Server starting on %s:%d", HOST, PORT)
        app.run()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
