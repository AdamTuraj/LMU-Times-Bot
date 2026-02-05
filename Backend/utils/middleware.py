import time
from collections import defaultdict

from utils.database import DatabaseError

# Rate limit stores
requests = defaultdict(list)
submit_requests = defaultdict(list)
auth_requests = defaultdict(list)

# Route config
ROUTES = {
    "/leaderboard/{track}": {"limiter": "general", "auth": False},
    "/leaderboard/{track}/submit": {"limiter": "submit", "auth": True},
    "/user": {"limiter": "general", "auth": True},
    "/user/logout": {"limiter": "auth", "auth": True},
    "/discord": {"limiter": "auth", "auth": False},
    "/discord/callback": {"limiter": "auth", "auth": False},
}

LIMITS = {
    "general": (60, 60),   # 60 requests per 60 seconds
    "submit": (10, 60),    # 10 requests per 60 seconds
    "auth": (10, 60),      # 10 requests per 60 seconds
}


def get_limiter_store(limiter_type):
    if limiter_type == "submit":
        return submit_requests
    elif limiter_type == "auth":
        return auth_requests
    return requests


def check_rate_limit(identifier, limiter_type):
    store = get_limiter_store(limiter_type)
    max_requests, window = LIMITS[limiter_type]
    now = time.time()
    cutoff = now - window

    # Clean old requests
    store[identifier] = [t for t in store[identifier] if t > cutoff]

    if len(store[identifier]) >= max_requests:
        oldest = min(store[identifier])
        reset_time = int(oldest + window - now)
        return True, max(0, reset_time)

    store[identifier].append(now)
    return False, 0


def match_route(path):
    if path in ROUTES:
        return path

    for pattern in ROUTES:
        if "{" not in pattern:
            continue

        parts = pattern.split("/")
        path_parts = path.split("/")

        if len(parts) != len(path_parts):
            continue

        match = True
        for p, pp in zip(parts, path_parts):
            if p.startswith("{") and p.endswith("}"):
                continue
            if p != pp:
                match = False
                break

        if match:
            return pattern

    return None


def get_client_id(req):
    forwarded = req.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()

    auth = req.headers.get("Authorization", "")

    if not auth:
        return req.headers.get("X-Real-IP", "unknown")

    if auth.startswith("Bearer "):
        return f"token:{auth[7:23]}"

    return req.headers.get("X-Real-IP", "unknown")


def get_token(req):
    auth = req.headers.get("Authorization", "")
    if not auth:
        return None
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


async def rate_limit_middleware(req, res, call_next, logger):
    path = req.url.path
    route = match_route(path)

    if route and route in ROUTES:
        limiter_type = ROUTES[route].get("limiter", "general")
        client_id = get_client_id(req)

        is_limited, reset_time = check_rate_limit(client_id, limiter_type)
        if is_limited:
            logger.warning("Rate limit exceeded for %s on %s", client_id, path)
            return res.status(429).json({
                "error": "Rate limit exceeded",
                "retry_after": reset_time
            })

    return await call_next()


async def auth_middleware(req, res, call_next, database, logger):
    path = req.url.path
    route = match_route(path)

    if route and ROUTES.get(route, {}).get("auth", False):
        token = get_token(req)

        if not token:
            logger.warning("Missing auth token for %s", path)
            return res.status(401).json({"error": "Missing Authorization header"})

        try:
            user = await database.get_user_by_token(token)
        except DatabaseError as e:
            logger.error("Database error: %s", e)
            return res.status(500).json({"error": "Internal server error"})

        if not user:
            logger.warning("Invalid token for %s", path)
            return res.status(401).json({"error": "Invalid token"})

        req.state.user = user
        req.state.token = token

    return await call_next()
