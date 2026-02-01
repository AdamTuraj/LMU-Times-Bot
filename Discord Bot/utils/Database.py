import logging
from typing import Any, Optional

import aiosqlite

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database-related errors."""
    pass


class Database:
    """Async SQLite database handler for the Discord bot."""

    def __init__(self, db_path: str) -> None:
        self._conn: Optional[aiosqlite.Connection] = None
        self._db_path = db_path

    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    async def init(self) -> None:
        """Initialize database connection."""
        try:
            logger.info("Initializing database connection to '%s'", self._db_path)
            self._conn = await aiosqlite.connect(self._db_path)
            logger.info("Database initialized successfully")
        except aiosqlite.Error as e:
            logger.error("Failed to initialize database: %s", e)
            raise DatabaseError(f"Failed to initialize database: {e}") from e

    # ==================== Admin Controls ====================

    async def add_leaderboard(
        self,
        track: str,
        discord_channel: int,
        weather: dict[str, Any],
        classes: list[int]
    ) -> None:
        """Add or update a leaderboard entry."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.info("Adding leaderboard for track '%s'", track)
            await self._conn.execute(
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
            await self._conn.commit()
            logger.info("Leaderboard for track '%s' saved successfully", track)
        except aiosqlite.Error as e:
            logger.error("Error saving leaderboard for track '%s': %s", track, e)
            raise DatabaseError(f"Error saving leaderboard: {e}") from e

    async def remove_leaderboard(self, track: str) -> bool:
        """Remove a leaderboard and all associated lap times."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.info("Removing leaderboard for track '%s'", track)

            await self._conn.execute(
                "DELETE FROM lap_times WHERE track = ?", (track,)
            )
            cursor = await self._conn.execute(
                "DELETE FROM leaderboards WHERE track = ?", (track,)
            )
            await self._conn.commit()

            if cursor.rowcount > 0:
                logger.info("Leaderboard for track '%s' removed successfully", track)
                return True
            else:
                logger.warning("No leaderboard found to remove for track '%s'", track)
                return False
        except aiosqlite.Error as e:
            logger.error("Error removing leaderboard for track '%s': %s", track, e)
            raise DatabaseError(f"Error removing leaderboard: {e}") from e

    async def get_all_leaderboards(self) -> list[tuple[Any, ...]]:
        """Retrieve all leaderboard entries."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.debug("Fetching all leaderboards")
            async with self._conn.execute("SELECT * FROM leaderboards") as cursor:
                results = await cursor.fetchall()
                logger.debug("Found %d leaderboards", len(results))
                return results
        except aiosqlite.Error as e:
            logger.error("Error fetching all leaderboards: %s", e)
            raise DatabaseError(f"Error fetching leaderboards: {e}") from e

    async def blacklist_user(self, user_id: str, reason: Optional[str] = None) -> bool:
        """Add a user to the blacklist."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.info("Blacklisting user '%s' with reason: %s", user_id, reason)
            await self._conn.execute(
                """
                INSERT INTO blacklist (user_id, reason) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET reason = excluded.reason
                """,
                (user_id, reason)
            )
            await self._conn.commit()
            logger.info("User '%s' blacklisted successfully", user_id)
            return True
        except aiosqlite.Error as e:
            logger.error("Error blacklisting user '%s': %s", user_id, e)
            raise DatabaseError(f"Error blacklisting user: {e}") from e

    async def unblacklist_user(self, user_id: str) -> bool:
        """Remove a user from the blacklist."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.info("Removing user '%s' from blacklist", user_id)
            cursor = await self._conn.execute(
                "DELETE FROM blacklist WHERE user_id = ?", (user_id,)
            )
            await self._conn.commit()

            if cursor.rowcount > 0:
                logger.info("User '%s' removed from blacklist", user_id)
                return True
            else:
                logger.warning("User '%s' was not in the blacklist", user_id)
                return False
        except aiosqlite.Error as e:
            logger.error("Error removing user '%s' from blacklist: %s", user_id, e)
            raise DatabaseError(f"Error removing from blacklist: {e}") from e

    async def is_blacklisted(self, user_id: str) -> bool:
        """Check if a user is blacklisted."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            async with self._conn.execute(
                "SELECT 1 FROM blacklist WHERE user_id = ?", (user_id,)
            ) as cursor:
                result = await cursor.fetchone()
                return result is not None
        except aiosqlite.Error as e:
            logger.error("Error checking blacklist status: %s", e)
            raise DatabaseError(f"Error checking blacklist: {e}") from e

    async def clear_lap_times(self, track: str) -> int:
        """Clear all lap times for a specific track."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.info("Clearing lap times for track '%s'", track)
            cursor = await self._conn.execute(
                "DELETE FROM lap_times WHERE track = ?", (track,)
            )
            await self._conn.commit()
            logger.info("Cleared %d lap times for track '%s'", cursor.rowcount, track)
            return cursor.rowcount
        except aiosqlite.Error as e:
            logger.error("Error clearing lap times for track '%s': %s", track, e)
            raise DatabaseError(f"Error clearing lap times: {e}") from e

    # ==================== Leaderboard Data ====================
    async def get_lap_times(self, track: str) -> list[dict[str, Any]]:
        """Retrieve all lap times for a track, sorted by fastest."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.debug("Fetching lap times for track '%s'", track)
            async with self._conn.execute(
                """
                SELECT user_id, driver_name, car, lap_time, sector1, sector2
                FROM lap_times 
                WHERE track = ? AND lap_time IS NOT NULL
                ORDER BY lap_time ASC
                """,
                (track,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "driver_name": row[1],
                        "car": row[2],
                        "lap_time": row[3],
                        "sector1": row[4],
                        "sector2": row[5] - row[4] if row[4] and row[5] else row[5],
                        "sector3": row[3] - row[5] if row[5] else None,
                    }
                    for row in rows
                ]
        except aiosqlite.Error as e:
            logger.error("Error fetching lap times for track '%s': %s", track, e)
            raise DatabaseError(f"Error fetching lap times: {e}") from e
        
    async def get_active_track_by_channel(self, channel_id: int) -> Optional[str]:
        """Get the active track for a given Discord channel."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.debug("Fetching active track for channel ID '%d'", channel_id)
            async with self._conn.execute(
                "SELECT track FROM leaderboards WHERE discord_channel = ?", (channel_id,)
            ) as cursor:
                result = await cursor.fetchone()
                if result:
                    logger.debug("Found active track '%s' for channel ID '%d'", result[0], channel_id)
                    return result[0]
                else:
                    logger.debug("No active track found for channel ID '%d'", channel_id)
                    return None
        except aiosqlite.Error as e:
            logger.error("Error fetching active track for channel ID '%d': %s", channel_id, e)
            raise DatabaseError(f"Error fetching active track: {e}") from e

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            logger.info("Closing database connection")
            try:
                await self._conn.close()
                self._conn = None
                logger.info("Database connection closed")
            except aiosqlite.Error as e:
                logger.error("Error closing database connection: %s", e)
                raise DatabaseError(f"Error closing database: {e}") from e
