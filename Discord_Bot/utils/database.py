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
        """Initialize database connection and create tables if needed."""
        try:
            logger.info("Initializing database connection to '%s'", self._db_path)
            self._conn = await aiosqlite.connect(self._db_path)
            await self._create_tables()
            logger.info("Database initialized successfully")
        except aiosqlite.Error as e:
            logger.error("Failed to initialize database: %s", e)
            raise DatabaseError(f"Failed to initialize database: {e}") from e

    async def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    token TEXT NOT NULL UNIQUE
                )
            """)

            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS leaderboards (
                    track TEXT PRIMARY KEY NOT NULL,
                    discord_channel INTEGER NOT NULL,
                    weather TEXT NOT NULL,
                    classes INTEGER DEFAULT 1,
                    show_technical BOOLEAN DEFAULT 0,
                    tod INTEGER DEFAULT 0,
                    fixed_setup BOOLEAN DEFAULT 0
                )
            """)

            await self._conn.execute("""
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

            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    reason TEXT,
                    blacklisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY NOT NULL,
                    value TEXT NOT NULL
                )
            """)

            await self._conn.commit()
            logger.debug("Database schema initialized")
        except aiosqlite.Error as e:
            logger.error("Failed to create database tables: %s", e)
            raise DatabaseError(f"Failed to create database tables: {e}") from e

    # ==================== Admin Controls ====================

    async def add_leaderboard(
        self,
        track: str,
        discord_channel: int,
        weather: dict[str, Any],
        classes: list[int],
        show_technical: bool = False,
        tod: int = 0,
        fixed_setup: bool = False
    ) -> None:
        """Add or update a leaderboard entry."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.info("Adding leaderboard for track '%s'", track)
            await self._conn.execute(
                """
                INSERT INTO leaderboards (track, discord_channel, weather, classes, show_technical, tod, fixed_setup) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(track) DO UPDATE SET 
                    discord_channel = excluded.discord_channel,
                    weather = excluded.weather,
                    classes = excluded.classes,
                    show_technical = excluded.show_technical,
                    tod = excluded.tod,
                    fixed_setup = excluded.fixed_setup
                """,
                (track, discord_channel, str(weather), str(classes), show_technical, tod, fixed_setup)
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
        
    # ==================== Settings ====================
    async def get_event_admin_roles(self) -> list[int]:
        """Retrieve the event administrator role ID."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.debug("Fetching event administrator role ID")
            async with self._conn.execute(
                "SELECT value FROM settings WHERE key = 'event_admin_roles'"
            ) as cursor:
                result = await cursor.fetchall()
                if result:
                    role_ids = [int(row[0]) for row in result]
                    logger.debug("Found event administrator role IDs: %s", role_ids)
                    return role_ids
                else:
                    logger.debug("No event administrator role ID set")
                    return []
        except aiosqlite.Error as e:
            logger.error("Error fetching event administrator role ID: %s", e)
            raise DatabaseError(f"Error fetching settings: {e}") from e

    async def add_event_admin_role(self, role_id: int) -> None:
        """Add an event administrator role ID."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.debug("Adding event administrator role ID %s", role_id)
            await self._conn.execute(
                "INSERT INTO settings (key, value) VALUES ('event_admin_roles', ?)",
                (str(role_id),)
            )
            await self._conn.commit()
            logger.debug("Event administrator role ID set to %s", role_id)
        except aiosqlite.Error as e:
            logger.error("Error setting event administrator role ID: %s", e)
            raise DatabaseError(f"Error setting settings: {e}") from e
        
    async def remove_event_admin_role(self, role_id: int) -> bool:
        """Remove an event administrator role ID."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.debug("Removing event administrator role ID %s", role_id)
            cursor = await self._conn.execute(
                "DELETE FROM settings WHERE key = 'event_admin_roles' AND value = ?",
                (str(role_id),)
            )
            await self._conn.commit()

            if cursor.rowcount > 0:
                logger.debug("Event administrator role ID %s removed", role_id)
                return True
            else:
                logger.debug("Event administrator role ID %s not found", role_id)
                return False
        except aiosqlite.Error as e:
            logger.error("Error removing event administrator role ID: %s", e)
            raise DatabaseError(f"Error removing settings: {e}") from e

    # ==================== Leaderboard Data ====================
    async def get_lap_times(self, track: str) -> list[dict[str, Any]]:
        """Retrieve all lap times for a track, sorted by fastest."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.debug("Fetching lap times for track '%s'", track)
            async with self._conn.execute(
                """
                SELECT driver_name, car, class, lap_time, sector1, sector2
                FROM lap_times 
                WHERE track = ? AND lap_time IS NOT NULL
                ORDER BY lap_time ASC
                """,
                (track,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "driver_name": row[0],
                        "car": row[1],
                        "car_class": row[2],
                        "lap_time": row[3],
                        "sector1": row[4],
                        "sector2": row[5],
                    }
                    for row in rows
                ]
        except aiosqlite.Error as e:
            logger.error("Error fetching lap times for track '%s': %s", track, e)
            raise DatabaseError(f"Error fetching lap times: {e}") from e
        
    async def get_active_track_by_channel(self, channel_id: int) -> tuple[str]:
        """Get the active track for a given Discord channel."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.debug("Fetching active track for channel ID '%d'", channel_id)
            async with self._conn.execute(
                "SELECT track, show_technical FROM leaderboards WHERE discord_channel = ?", (channel_id,)
            ) as cursor:
                result = await cursor.fetchone()
                if result:
                    logger.debug("Found active track '%s' for channel ID '%d'", result[0], channel_id)
                    return result
                else:
                    logger.debug("No active track found for channel ID '%d'", channel_id)
                    return ("", "")
        except aiosqlite.Error as e:
            logger.error("Error fetching active track for channel ID '%d': %s", channel_id, e)
            raise DatabaseError(f"Error fetching active track: {e}") from e
        
    async def update_entry_username(self, old_username: str, new_username: str) -> int:
        """Update driver names in lap times when a user changes their username."""
        if not self._conn:
            raise DatabaseError("Database connection not established")

        try:
            logger.info("Updating driver name from '%s' to '%s'", old_username, new_username)
            cursor = await self._conn.execute(
                "UPDATE lap_times SET driver_name = ? WHERE driver_name = ?",
                (new_username, old_username)
            )
            await self._conn.commit()
            logger.info("Updated %d entries from '%s' to '%s'", cursor.rowcount, old_username, new_username)
            return cursor.rowcount
        except aiosqlite.Error as e:
            logger.error("Error updating driver name from '%s' to '%s': %s", old_username, new_username, e)
            raise DatabaseError(f"Error updating driver name: {e}") from e


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
