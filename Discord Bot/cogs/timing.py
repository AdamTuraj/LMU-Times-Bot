import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from utils.Database import DatabaseError
from utils.ImageHandler import format_data as format_data_image, gen_image
from utils.Types import Tracks

if TYPE_CHECKING:
    from bot import DiscordBot

logger = logging.getLogger(__name__)


def format_time(time: int) -> str:
    """Format time from milliseconds to MM:SS.mmm format.
    
    Args:
        time: Time in milliseconds.
        
    Returns:
        Formatted time string.
    """
    minutes, seconds = divmod(time, 60000)
    seconds, ms = divmod(seconds, 1000)
    return f"{minutes:02}:{seconds:02}.{ms:03}"


class Timing(commands.Cog):
    """Cog for timing-related commands."""

    def __init__(self, bot: "DiscordBot") -> None:
        self.bot = bot
        logger.info("Timing cog initialized")

    @app_commands.command()
    async def times(self, interaction: discord.Interaction) -> None:
        """Get the best lap times for this channel's configured track."""
        logger.debug(
            "User %s requested times in channel %s",
            interaction.user.id,
            interaction.channel.id,
        )

        try:
            track = await self.bot.database.get_active_track_by_channel(
                interaction.channel.id
            )

            if not track:
                await interaction.response.send_message(
                    "No leaderboard is configured for this channel.",
                    ephemeral=True,
                )
                return

            lap_times = await self.bot.database.get_lap_times(track)

            if not lap_times:
                track_name = Tracks[track].value if track in Tracks.__members__ else track
                await interaction.response.send_message(
                    f"No lap times recorded for **{track_name}** yet.",
                    ephemeral=True,
                )
                return

            data = format_data_image(lap_times)
            image = gen_image(data)

            track_display = Tracks[track].value if track in Tracks.__members__ else track
            logger.info(
                "Displayed %d lap times for track %s to user %s",
                len(lap_times),
                track,
                interaction.user.id,
            )

            await interaction.response.send_message(
                f"Here are the best times for **{track_display}**!",
                file=discord.File(filename=f"{track}.png", fp=image),
            )

        except DatabaseError as e:
            logger.error("Database error fetching times: %s", e)
            await interaction.response.send_message(
                "An error occurred while fetching lap times. Please try again later.",
                ephemeral=True,
            )
        except Exception as e:
            logger.exception("Unexpected error in times command: %s", e)
            await interaction.response.send_message(
                "An unexpected error occurred.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    """Load the Timing cog."""
    await bot.add_cog(Timing(bot))
