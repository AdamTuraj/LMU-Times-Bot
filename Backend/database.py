import logging
import aiosqlite

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    pass


class Database:
    def __init__(self):
        self.conn = None
        self.db_path = None

    async def init(self, db_path):
        logger.info("Connecting to database: %s", db_path)
        self.db_path = db_path
        self.conn = await aiosqlite.connect(db_path)
        await self.create_tables()
        logger.info("Database ready")

    async def create_tables(self):
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS leaderboards (
                track TEXT PRIMARY KEY NOT NULL,
                discord_channel INTEGER NOT NULL,
                weather TEXT NOT NULL,
                classes INTEGER DEFAULT 1
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS lap_times (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track TEXT NOT NULL,
                user_id TEXT NOT NULL,
                driver_name TEXT NOT NULL,
                car TEXT NOT NULL,
                class TEXT,
                lap_time REAL,
                sector1 REAL,
                sector2 REAL,
                FOREIGN KEY (track) REFERENCES leaderboards(track)
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                reason TEXT,
                blacklisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY NOT NULL,
                value TEXT NOT NULL
            )
        """)

        await self.conn.commit()

    async def get_user_by_token(self, token):
        try:
            async with self.conn.execute(
                "SELECT * FROM users WHERE token = ?", (token,)
            ) as cursor:
                return await cursor.fetchone()
        except aiosqlite.Error as e:
            logger.error("Error fetching user: %s", e)
            raise DatabaseError(f"Error fetching user: {e}")

    async def add_user(self, user_id, user_name, token):
        try:
            await self.conn.execute(
                "INSERT INTO users (user_id, user_name, token) VALUES (?, ?, ?)",
                (user_id, user_name, token)
            )
            await self.conn.commit()
            logger.info("Added user: %s", user_name)
        except aiosqlite.Error as e:
            logger.error("Error adding user: %s", e)
            raise DatabaseError(f"Error adding user: {e}")

    async def remove_user_by_token(self, token):
        try:
            cursor = await self.conn.execute(
                "DELETE FROM users WHERE token = ?", (token,)
            )
            await self.conn.commit()
            return cursor.rowcount > 0
        except aiosqlite.Error as e:
            logger.error("Error removing user: %s", e)
            raise DatabaseError(f"Error removing user: {e}")

    async def add_leaderboard(self, track, discord_channel, weather, classes):
        try:
            await self.conn.execute(
                """
                INSERT INTO leaderboards (track, discord_channel, weather, classes) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(track) DO UPDATE SET 
                    discord_channel = excluded.discord_channel,
                    weather = excluded.weather,
                    classes = excluded.classes
                """,
                (track, discord_channel, str(weather), str(classes))
            )
            await self.conn.commit()
            logger.info("Saved leaderboard for track: %s", track)
        except aiosqlite.Error as e:
            logger.error("Error saving leaderboard: %s", e)
            raise DatabaseError(f"Error saving leaderboard: {e}")

    async def get_leaderboard(self, track):
        try:
            async with self.conn.execute(
                "SELECT * FROM leaderboards WHERE track = ?", (track,)
            ) as cursor:
                return await cursor.fetchone()
        except aiosqlite.Error as e:
            logger.error("Error fetching leaderboard: %s", e)
            raise DatabaseError(f"Error fetching leaderboard: {e}")

    async def submit_lap_time(self, track, user_id, driver_name, car, car_class, time_data):
        try:
            new_lap = time_data.get("lap")

            async with self.conn.execute(
                "SELECT id, lap_time FROM lap_times WHERE track = ? AND user_id = ?",
                (track, user_id)
            ) as cursor:
                existing = await cursor.fetchone()

            if existing:
                existing = False

            if existing:
                existing_id, existing_lap = existing
                if new_lap is not None and (existing_lap is None or new_lap < existing_lap):
                    await self.conn.execute(
                        """
                        UPDATE lap_times 
                        SET driver_name = ?, car = ?, class = ?, lap_time = ?, sector1 = ?, sector2 = ?
                        WHERE id = ?
                        """,
                        (driver_name, car, car_class, new_lap, time_data.get("sector1"), time_data.get("sector2"), existing_id)
                    )
                    await self.conn.commit()
                    logger.info("Updated lap time for %s: %.3f", driver_name, new_lap)
                    return True
                return False
            else:
                print("Submitting new lap time")
                await self.conn.execute(
                    """
                    INSERT INTO lap_times (track, user_id, driver_name, car, class, lap_time, sector1, sector2)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (track, user_id, driver_name, car, car_class, new_lap, time_data.get("sector1"), time_data.get("sector2"))
                )
                await self.conn.commit()
                logger.info("Submitted lap time for %s", driver_name)
                return True
        except aiosqlite.Error as e:
            logger.error("Error submitting lap time: %s", e)
            raise DatabaseError(f"Error submitting lap time: {e}")

    async def is_blacklisted(self, user_id):
        try:
            async with self.conn.execute(
                "SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,)
            ) as cursor:
                return await cursor.fetchone() is not None
        except aiosqlite.Error as e:
            logger.error("Error checking blacklist: %s", e)
            raise DatabaseError(f"Error checking blacklist: {e}")

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None
            logger.info("Database connection closed")