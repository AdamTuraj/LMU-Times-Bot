import ast
import asyncio
import logging
import os
import secrets
import sys

from aiohttp import ClientSession, BasicAuth
from dotenv import load_dotenv
from nexios import NexiosApp, MakeConfig
from nexios.http import Request, Response

from utils.database import Database, DatabaseError
from utils.middleware import rate_limit_middleware, auth_middleware

load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG", "false").lower() == "true" else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Config from environment
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
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

# Routes - Leaderboard
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

    try:
        weather = ast.literal_eval(leaderboard[2])
    except:
        weather = {}

    try:
        classes = ast.literal_eval(leaderboard[3])
    except:
        classes = []

    return res.json({
        "track": leaderboard[0],
        "discord_channel": leaderboard[1],
        "weather": weather,
        "classes": classes
    })


@app.post("/leaderboard/{track}/submit")
async def submit_time(req: Request, res: Response):
    track = req.path_params.get("track")
    if not track:
        return res.status(400).json({"error": "Track parameter required"})

    user = req.state.user

    try:
        if await database.is_blacklisted(user[1]):
            return res.status(403).json({"error": "You are blacklisted"})
    except DatabaseError as e:
        logger.error("Database error: %s", e)
        return res.status(500).json({"error": "Internal server error"})

    try:
        body = await req.json
    except:
        return res.status(400).json({"error": "Invalid JSON body"})

    time_data = body.get("time_data")
    car = body.get("car")
    driver_name = body.get("driver_name")
    car_class = body.get("class")

    # Validate required fields
    if not time_data or not isinstance(time_data, dict):
        return res.status(400).json({"error": "time_data is required and must be an object"})
    if not car or not isinstance(car, str) or not car.strip():
        return res.status(400).json({"error": "car is required and must be a non-empty string"})
    if not driver_name or not isinstance(driver_name, str) or not driver_name.strip():
        return res.status(400).json({"error": "driver_name is required and must be a non-empty string"})
    if not car_class or not isinstance(car_class, str) or not car_class.strip():
        return res.status(400).json({"error": "class is required and must be a non-empty string"})

    # Validate time_data structure
    lap_time = time_data.get("lap")
    sector1 = time_data.get("sector1")
    sector2 = time_data.get("sector2")

    if lap_time is None:
        return res.status(400).json({"error": "time_data.lap is required"})
    if sector1 is None:
        return res.status(400).json({"error": "time_data.sector1 is required"})
    if sector2 is None:
        return res.status(400).json({"error": "time_data.sector2 is required"})

    # Validate time values are numbers
    try:
        lap_time = float(lap_time)
        sector1 = float(sector1)
        sector2 = float(sector2)
    except (ValueError, TypeError):
        return res.status(400).json({"error": "All time values must be numbers"})

    # Validate lap_time is positive
    if lap_time <= 0:
        return res.status(400).json({"error": "lap_time must be greater than 0"})

    # Validate sector times are either -1 or positive
    if sector1 != -1 and sector1 <= 0:
        return res.status(400).json({"error": "sector1 must be -1 or greater than 0"})
    if sector2 != -1 and sector2 <= 0:
        return res.status(400).json({"error": "sector2 must be -1 or greater than 0"})

    # Validate string lengths
    if len(driver_name) > 100:
        return res.status(400).json({"error": "driver_name must not exceed 100 characters"})
    if len(car) > 100:
        return res.status(400).json({"error": "car must not exceed 100 characters"})
    if len(car_class) > 50:
        return res.status(400).json({"error": "class must not exceed 50 characters"})

    try:
        leaderboard = await database.get_leaderboard(track)
    except DatabaseError as e:
        logger.error("Database error: %s", e)
        return res.status(500).json({"error": "Internal server error"})

    if not leaderboard:
        return res.status(404).json({"error": "Leaderboard not found"})

    time_data = {
        "lap": lap_time,
        "sector1": sector1,
        "sector2": sector2
    }

    try:
        await database.submit_lap_time(track, user[1], driver_name.strip(), car.strip(), car_class.strip(), time_data)
    except DatabaseError as e:
        logger.error("Database error: %s", e)
        return res.status(500).json({"error": "Internal server error"})

    logger.info("Lap time submitted by '%s' for track '%s'", driver_name, track)
    return res.json({"message": "Time submitted successfully"})


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