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
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

import discord
from discord.ext import commands

from utils.database import Database

load_dotenv(override=True)

# Constants
DATABASE_PATH = Path(__file__).parent.parent / "database.db"
COGS_DIR = Path(__file__).parent / "cogs"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> logging.Logger:
    """Configure logging for the bot."""
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("time_track_bot.log", encoding="utf-8"),
        ],
    )
    
    # Reduce discord.py verbosity
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)


logger = setup_logging()


class DiscordBot(commands.Bot):
    """Main Discord bot class for LMU Times."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(
            intents=intents,
            help_command=None,
            command_prefix=commands.when_mentioned,
        )
        self.database = Database(str(DATABASE_PATH))
        self._loaded_cogs: list[str] = []

    async def load_cogs(self) -> None:
        """Load all cog extensions from the cogs directory."""
        if not COGS_DIR.exists():
            logger.error("Cogs directory not found: %s", COGS_DIR)
            return

        for file in COGS_DIR.iterdir():
            if file.suffix == ".py" and not file.name.startswith("_"):
                extension = file.stem
                try:
                    await self.load_extension(f"cogs.{extension}")
                    self._loaded_cogs.append(extension)
                    logger.info("Loaded extension: %s", extension)
                except Exception as e:
                    logger.exception("Failed to load extension %s: %s", extension, e)

    async def sync_commands(self) -> None:
        """Sync slash commands to the configured guild."""
        guild_id = os.getenv("GUILD_ID")
        if not guild_id:
            logger.error("GUILD_ID not configured")
            return

        guild = discord.Object(id=int(guild_id))
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        logger.info("Commands synced to guild %s", guild_id)

    async def setup_hook(self) -> None:
        """Initialize bot components before connecting."""
        logger.info("Initializing bot...")
        await self.database.init()
        await self.load_cogs()
        await self.sync_commands()
        logger.info("Bot initialization complete")

    async def on_ready(self) -> None:
        """Handle bot ready event."""
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Le Mans Ultimate",
            )
        )
        logger.info("Bot is ready - Logged in as %s (ID: %s)", self.user, self.user.id)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Leave guilds that aren't the configured guild."""
        allowed_guild_id = os.getenv("GUILD_ID")
        if allowed_guild_id and guild.id != int(allowed_guild_id):
            logger.warning("Leaving unauthorized guild: %s (ID: %s)", guild.name, guild.id)
            await guild.leave()

    async def close(self) -> None:
        """Cleanup resources before shutdown."""
        logger.info("Shutting down bot...")
        await self.database.close()
        await super().close()
        logger.info("Bot shutdown complete")


def validate_environment() -> bool:
    """Validate required environment variables are set."""
    required_vars = ["TOKEN", "GUILD_ID", "OWNER_ID"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        return False
    return True


bot = DiscordBot()


@bot.tree.command(
    name="reload_cogs",
    description="Reloads all cogs (Owner only)",
)
@discord.app_commands.default_permissions(administrator=True)
async def reload_cogs(interaction: discord.Interaction) -> None:
    """Reload all loaded cog extensions."""
    owner_id = os.getenv("OWNER_ID")
    if not owner_id or interaction.user.id != int(owner_id):
        await interaction.response.send_message(
            "You must be the bot owner to use this command.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)
    
    reloaded = []
    failed = []
    
    for cog in bot._loaded_cogs:
        try:
            await bot.reload_extension(f"cogs.{cog}")
            reloaded.append(cog)
            logger.info("Reloaded cog: %s", cog)
        except Exception as e:
            failed.append(f"{cog}: {e}")
            logger.exception("Failed to reload cog %s: %s", cog, e)

    await bot.sync_commands()
    
    response = f"Reloaded: {', '.join(reloaded) or 'None'}"
    if failed:
        response += f"\nFailed: {', '.join(failed)}"
    
    await interaction.followup.send(response, ephemeral=True)


def main() -> None:
    if not validate_environment():
        sys.exit(1)

    token = os.getenv("TOKEN")
    logger.info("Starting bot...")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
