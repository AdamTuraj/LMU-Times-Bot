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
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import DatabaseError
from utils.image_handler import format_data as format_data_image, gen_image
from utils.types import Tracks

if TYPE_CHECKING:
    from bot import DiscordBot

logger = logging.getLogger(__name__)


class Timing(commands.Cog):
    """Cog for timing-related commands."""

    def __init__(self, bot: "DiscordBot") -> None:
        self.bot = bot
        logger.info("Timing cog initialized")

    @app_commands.command()
    async def times(self, interaction: discord.Interaction) -> None:
        """Get the best lap times for this channel's configured track."""
        await interaction.response.defer()
        
        logger.debug(
            "User %s requested times in channel %s",
            interaction.user.id,
            interaction.channel.id,
        )

        try:
            track, show_technical = await self.bot.database.get_active_track_by_channel(
                interaction.channel.id
            )

            if not track:
                await interaction.followup.send(
                    "No leaderboard is configured for this channel.",
                    ephemeral=True,
                )
                return
            
            track_enum = next((t for t in Tracks if t.value == track), None) # Track is the value of enum
            track_name = track_enum.name.replace("_", " ").title() if track_enum else track

            lap_times = await self.bot.database.get_lap_times(track)

            if not lap_times:
                await interaction.followup.send(
                    f"No lap times recorded for **{track_name}** yet.",
                    ephemeral=True,
                )
                return
    
            data = format_data_image(lap_times, show_technical)
            image = gen_image(data, show_technical)

            logger.info(
                "Displayed %d lap times for track %s to user %s",
                len(lap_times),
                track_name,
                interaction.user.id,
            )

            await interaction.followup.send(
                f"Here are the best times for **{track_name}**!",
                file=discord.File(filename=f"{track_name}.png", fp=image),
            )

        except DatabaseError as e:
            logger.error("Database error fetching times: %s", e)
            await interaction.followup.send(
                "An error occurred while fetching lap times. Please try again later.",
                ephemeral=True,
            )
        except Exception as e:
            logger.exception("Unexpected error in times command: %s", e)
            await interaction.followup.send(
                "An unexpected error occurred.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    """Load the Timing cog."""
    await bot.add_cog(Timing(bot))
