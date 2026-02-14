import ast
import logging
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.Database import DatabaseError
from utils.Types import Classes, Tracks, WeatherConditions, GripLevel

logger = logging.getLogger(__name__)


class ConfirmView(discord.ui.View):
    """A confirmation view with Confirm/Cancel buttons."""

    def __init__(self, timeout: float = 60.0) -> None:
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.interaction: Optional[discord.Interaction] = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle confirm button click."""
        await interaction.response.defer()
        self.value = True
        self.interaction = interaction
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Handle cancel button click."""
        await interaction.response.defer()
        self.value = False
        self.interaction = interaction
        self.stop()

    async def on_timeout(self) -> None:
        """Handle view timeout."""
        self.value = None

class Admin(commands.Cog):
    """Admin cog for managing leaderboards and users."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        logger.info("Admin cog initialized")

    group = app_commands.Group(
        name="admin",
        description="Admin commands to manage leaderboards and users.",
        default_permissions=discord.Permissions(manage_roles=True), # A general permission most event admins would have. Main purpose is to hide admin commands from normal users
    )

    # ==================== Helper Methods ====================

    async def is_event_admin(self, interaction: discord.Interaction) -> bool:
        """Check if the user is an event administrator."""

        owner_id = os.getenv("OWNER_ID")
        event_admin_role_ids = await self.bot.database.get_event_admin_roles()

        if any(role.id in event_admin_role_ids for role in interaction.user.roles):
            return True

        if interaction.user.guild_permissions.administrator or str(interaction.user.id) == owner_id:
            return True
        else:
            await interaction.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )
            return False
        
    @staticmethod
    def parse_classes(classes_str: str) -> tuple[list[str], list[int], Optional[str]]:
        """Parse and validate class string input.
        
        Args:
            classes_str: Comma-separated class names.
            
        Returns:
            Tuple of (class_names, class_ids, error_message).
            error_message is None if parsing succeeded.
        """
        class_names = [cls.strip().upper() for cls in classes_str.split(",")]
        class_ids = []
        
        for cls in class_names:
            if cls in Classes.__members__:
                class_ids.append(Classes[cls].value)
            else:
                valid = ", ".join(Classes.__members__.keys())
                return [], [], f"Invalid class '{cls}'. Valid classes are: {valid}."
        
        return class_names, class_ids, None

    @staticmethod
    def format_condition_name(condition: WeatherConditions | int | str) -> str:
        """Format weather condition for display."""
        if isinstance(condition, WeatherConditions):
            return condition.name.replace("_", " ").title()
        elif isinstance(condition, int):
            return WeatherConditions(condition).name.replace("_", " ").title()
        else:
            return str(condition).replace("_", " ").title()

    # ==================== Leaderboard Management ====================

    @group.command(name="add_leaderboard")
    async def add_leaderboard(
        self,
        interaction: discord.Interaction,
        track: Tracks,
        classes: str,
        channel: discord.TextChannel,
        show_technical: bool = False,
        temperature: float = 25.0,
        rain: float = 0.0,
        condition: WeatherConditions = WeatherConditions.CLEAR,
        grip: GripLevel = GripLevel.SATURATED_GRIP,
    ) -> None:
        """Add or update a leaderboard for a track.

        Parameters
        -----------
        track: Tracks
            The track for the leaderboard.
        classes: str
            Comma-separated list of class names (LMGT3, GTE, LMP3, LMP2, LMP2_UNRESTRICTED, HYPERCAR).
        channel: discord.TextChannel
            The Discord channel to post the leaderboard in.
        show_technical: bool
            Whether to show technical lap times (default: False).
        temperature: float
            Temperature setting (default: 25.0).
        rain: float
            Rain intensity (default: 0.0).
        condition: WeatherConditions
            Weather condition (default: CLEAR).
        grip: GripLevel
            Grip level (default: SATURATED_GRIP).
        """
        if not await self.is_event_admin(interaction):
            return

        logger.info(
            "User %s attempting to add leaderboard for track %s",
            interaction.user.id,
            track.name,
        )

        existing_leaderboards = await self.bot.database.get_all_leaderboards()

        for lb in existing_leaderboards:
            if lb[0] == track.value:
                await interaction.response.send_message(
                    f"A leaderboard for **{track.name}** already exists. "
                    "You must remove it before adding a new one.",
                    ephemeral=True,
                )
                return

        for lb in existing_leaderboards:
            if lb[1] == channel.id:
                await interaction.response.send_message(
                    f"The channel {channel.mention} is already assigned to another leaderboard. "
                    "Please choose a different channel.",
                    ephemeral=True,
                )
                return

        class_names, class_ids, error = self.parse_classes(classes)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        weather = {
            "temperature": temperature,
            "rain": rain,
            "condition": condition.value,
            "grip_level": grip.value,
        }

        embed = discord.Embed(
            title="Add Leaderboard",
            description=f"Are you sure you want to add the leaderboard for **{track.name}**?",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Track", value=track.name, inline=True)
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Classes", value=", ".join(class_names), inline=False)
        embed.add_field(
            name="Weather",
            value=f"Temp: {temperature}°C, Rain: {rain}%, Condition: {self.format_condition_name(condition)}, Grip: {grip.name.replace('_', ' ').title()}",
            inline=False,
        )
        embed.add_field(
            name="Show Technical",
            value="True" if show_technical else "False",
            inline=False,
        )

        view = ConfirmView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if view.value is None:
            await interaction.edit_original_response(
                content="Timed out.", embed=None, view=None
            )
        elif view.value:
            await self.bot.database.add_leaderboard(
                track.value, channel.id, weather, class_ids, show_technical
            )
            logger.info(
                "Leaderboard for track %s added by user %s",
                track.value,
                interaction.user.id,
            )
            await view.interaction.followup.send(
                f"Leaderboard for **{track.name}** has been added!",
                ephemeral=True,
            )
        else:
            await view.interaction.followup.send("Cancelled.", ephemeral=True)

    @group.command(name="remove_leaderboard")
    async def remove_leaderboard(
        self, interaction: discord.Interaction, track: Tracks
    ) -> None:
        """Remove a leaderboard and all associated lap times.

        Parameters
        -----------
        track: Tracks
            The track leaderboard to remove.
        """
        if not await self.is_event_admin(interaction):
            return

        logger.info(
            "User %s attempting to remove leaderboard for track %s",
            interaction.user.id,
            track.name,
        )

        embed = discord.Embed(
            title="Remove Leaderboard",
            description=(
                f"Are you sure you want to remove the leaderboard for **{track.name}**?\n\n"
                "**This will delete all lap times for this track!**"
            ),
            color=discord.Color.red(),
        )

        view = ConfirmView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if view.value is None:
            await interaction.edit_original_response(
                content="Timed out.", embed=None, view=None
            )
        elif view.value:
            removed = await self.bot.database.remove_leaderboard(track.value)
            if removed:
                logger.info(
                    "Leaderboard for track %s removed by user %s",
                    track.name,
                    interaction.user.id,
                )
                await view.interaction.followup.send(
                    f"Leaderboard for **{track.name}** has been removed!",
                    ephemeral=True,
                )
            else:
                await view.interaction.followup.send(
                    f"No leaderboard found for **{track.name}**.",
                    ephemeral=True,
                )
        else:
            await view.interaction.followup.send("Cancelled.", ephemeral=True)

    @group.command(name="edit_leaderboard")
    async def edit_leaderboard(
        self,
        interaction: discord.Interaction,
        track: Tracks,
        classes: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None,
        show_technical: Optional[bool] = None,
        temperature: Optional[float] = None,
        rain: Optional[float] = None,
        condition: Optional[WeatherConditions] = None,
        grip: Optional[GripLevel] = None,
    ) -> None:
        """Edit an existing leaderboard for a track.

        Parameters
        -----------
        track: Tracks
            The track leaderboard to edit.
        classes: str
            Comma-separated list of class names (LMGT3, GTE, LMP3, LMP2, LMP2_UNRESTRICTED, HYPERCAR).
        channel: discord.TextChannel
            The Discord channel for the leaderboard.
        show_technical: Optional[bool] = None,
            Whether to show technical lap times.
        temperature: float
            Temperature setting.
        rain: float
            Rain intensity.
        condition: WeatherConditions
            Weather condition.
        grip: GripLevel
            Grip level.
        """

        if not await self.is_event_admin(interaction):
            return

        logger.info(
            "User %s attempting to edit leaderboard for track %s",
            interaction.user.id,
            track.name,
        )

        existing_leaderboards = await self.bot.database.get_all_leaderboards()
        leaderboard = next(
            (lb for lb in existing_leaderboards if lb[0] == track.value), None
        )

        if not leaderboard:
            await interaction.response.send_message(
                f"No leaderboard found for **{track.value}**.",
                ephemeral=True,
            )
            return

        _track_name, current_channel_id, weather_str, classes_str, current_show_technical = leaderboard
        try:
            current_weather = ast.literal_eval(weather_str)
            current_class_ids = ast.literal_eval(classes_str)
        except (ValueError, SyntaxError) as e:
            logger.error("Failed to parse leaderboard data: %s", e)
            await interaction.response.send_message(
                "Error parsing existing leaderboard data.",
                ephemeral=True,
            )
            return

        new_channel_id = channel.id if channel else current_channel_id
        new_class_ids = current_class_ids
        new_show_technical = show_technical if show_technical is not None else current_show_technical

        if classes is not None:
            _class_names, new_class_ids, error = self.parse_classes(classes)
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return

        if channel:
            for lb in existing_leaderboards:
                if lb[0] != track.value and lb[1] == channel.id:
                    await interaction.response.send_message(
                        f"The channel {channel.mention} is already assigned to another leaderboard. "
                        "Please choose a different channel.",
                        ephemeral=True,
                    )
                    return

        new_temperature = temperature if temperature is not None else current_weather.get('temperature', 25.0)
        new_rain = rain if rain is not None else current_weather.get('rain', 0.0)
        new_condition = condition if condition is not None else WeatherConditions(current_weather.get('condition', 0))
        new_grip = grip if grip is not None else GripLevel(current_weather.get('grip_level', 5))

        new_weather = {
            'temperature': new_temperature,
            'rain': new_rain,
            'condition': new_condition.value,
            'grip_level': new_grip.value,
        }

        embed = discord.Embed(
            title="Edit Leaderboard",
            description=f"Confirm changes for **{track.name}**",
            color=discord.Color.blue(),
        )

        embed.add_field(name="Track", value=track.name, inline=False)
        if channel:
            embed.add_field(name="Channel", value=channel.mention, inline=False)

        if classes is not None:
            class_display = ", ".join(
                c.name for c in Classes if c.value in new_class_ids
            )
            embed.add_field(name="Classes", value=class_display or "None", inline=False)

        embed.add_field(
            name="Weather",
            value=f"Temp: {new_temperature}°C, Rain: {new_rain}%, Condition: {self.format_condition_name(new_condition)}, Grip: {new_grip.name.replace('_', ' ').title()}",
            inline=False,
        )

        embed.add_field(
            name="Show Technical",
            value="True" if new_show_technical else "False",
            inline=False,
        )

        view = ConfirmView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if view.value is None:
            await interaction.edit_original_response(
                content="Timed out.", embed=None, view=None
            )
        elif view.value:
            await self.bot.database.add_leaderboard(
                track.value, new_channel_id, new_weather, new_class_ids, new_show_technical
            )
            logger.info(
                "Leaderboard for track %s edited by user %s",
                track.name,
                interaction.user.id,
            )
            await view.interaction.followup.send(
                f"Leaderboard for **{track.name}** has been updated!",
                ephemeral=True,
            )
        else:
            await view.interaction.followup.send("Cancelled.", ephemeral=True)

    @group.command(name="edit_entry_username")
    async def edit_entry_username(
        self,
        interaction: discord.Interaction,
        old_username: str,
        new_username: str,
    ) -> None:
        """Edit the username associated with lap time entries.

        Parameters
        -----------
        old_username: str
            The current username to change.
        new_username: str
            The new username to set.
        """
        if not await self.is_event_admin(interaction):
            return

        logger.info(
            "User %s attempting to change username from %s to %s",
            interaction.user.id,
            old_username,
            new_username,
        )

        count = await self.bot.database.update_entry_username(
            old_username, new_username
        )

        if count > 0:
            logger.info(
                "Changed username from %s to %s for %d entries by user %s",
                old_username,
                new_username,
                count,
                interaction.user.id,
            )
            await interaction.response.send_message(
                f"Updated username from **{old_username}** to **{new_username}** for **{count}** entries.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"No entries found for username **{old_username}**.",
                ephemeral=True,
            )

    @group.command(name="list_leaderboards")
    async def list_leaderboards(self, interaction: discord.Interaction) -> None:
        """List all configured leaderboards."""
        if not await self.is_event_admin(interaction):
            return

        leaderboards = await self.bot.database.get_all_leaderboards()

        if not leaderboards:
            await interaction.response.send_message(
                "No leaderboards configured.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Configured Leaderboards",
            color=discord.Color.blue(),
        )

        for lb in leaderboards:
            track, channel_id, weather_str, classes_str, show_technical = lb
            track_display = (
                Tracks[track].value if track in Tracks.__members__ else track
            )
            channel = self.bot.get_channel(channel_id)
            channel_str = channel.mention if channel else f"ID: {channel_id}"
            show_technical_display = "True" if show_technical else "False"
            
            try:
                weather = ast.literal_eval(weather_str)
                grip_level = GripLevel(weather.get('grip_level', 5)).name.replace('_', ' ').title()
                weather_display = (
                    f"Temp: {weather.get('temperature', 'N/A')}°C, "
                    f"Rain: {weather.get('rain', 'N/A')}, "
                    f"Condition: {self.format_condition_name(weather.get('condition', 'N/A'))}, "
                    f"Grip: {grip_level}"
                )
            except (ValueError, SyntaxError):
                weather_display = str(weather_str)

            try:
                class_ids = ast.literal_eval(classes_str)
                class_names = [
                    cls.name for cls in Classes if cls.value in class_ids
                ]
                classes_display = ", ".join(class_names) or "None"
            except (ValueError, SyntaxError):
                classes_display = str(classes_str)

            embed.add_field(
                name=track_display,
                value=(
                    f"Channel: {channel_str}\n"
                    f"Weather: {weather_display}\n"
                    f"Classes: {classes_display}\n"
                    f"Show Technical: {show_technical_display}"
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @group.command(name="server_info")
    async def server_info(
        self,
        interaction: discord.Interaction,
        track: Tracks,
        title: Optional[str] = None,
    ) -> None:
        """Display server settings for a configured leaderboard.

        Parameters
        -----------
        track: Tracks
            The track to display settings for.
        title: str
            Optional custom title for the embed.
        """
        leaderboards = await self.bot.database.get_all_leaderboards()
        leaderboard = next(
            (lb for lb in leaderboards if lb[0] == track.value), None
        )

        if not leaderboard:
            await interaction.response.send_message(
                f"No leaderboard configured for **{track.name}**.",
                ephemeral=True,
            )
            return

        _track_name, _channel_id, weather_str, classes_str, _show_technical = leaderboard

        try:
            weather = ast.literal_eval(weather_str)
            class_ids = ast.literal_eval(classes_str)
        except (ValueError, SyntaxError) as e:
            logger.error("Failed to parse leaderboard data: %s", e)
            await interaction.response.send_message(
                "Error parsing leaderboard data.", ephemeral=True
            )
            return

        class_names = [cls.name for cls in Classes if cls.value in class_ids]
        condition_name = self.format_condition_name(weather.get("condition", 0))

        if not title:
            title = f"Server Info: {track.name.replace('_', ' ').title()}"

        embed = discord.Embed(
            title=title,
            description="Configure your session with these settings for valid lap time submissions.",
            color=discord.Color.blue(),
        )

        embed.add_field(name="Track", value="- " + track.name.replace('_', ' ').title(), inline=False)

        classes_text = "- " + "\n- ".join(
            cls.replace('_', ' ') for cls in class_names
        )
        embed.add_field(
            name="Classes", value=classes_text or "None", inline=False
        )

        grip_level = GripLevel(weather.get('grip_level', 5)).name.replace('_', ' ').title()
        weather_text = (
            f"- Temperature: {round(weather.get('temperature', 'N/A'))}°C\n"
            f"- Rain: {round(weather.get('rain', 'N/A'))}%\n"
            f"- Condition: {condition_name}\n"
            f"- Grip Level: {grip_level}"
        )
        embed.add_field(name="Weather", value=weather_text, inline=False)

        embed.add_field(
            name="Important",
            value=(
                "- All weather slots must be set to the values above\n"
                "- You must be alone in a practice server"
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @group.command(name="clear_times")
    async def clear_times(
        self, interaction: discord.Interaction, track: Tracks
    ) -> None:
        """Clear all lap times for a track.

        Parameters
        -----------
        track: Tracks
            The track to clear lap times for.
        """
        if not await self.is_event_admin(interaction):
            return

        logger.info(
            "User %s attempting to clear lap times for track %s",
            interaction.user.id,
            track.name,
        )

        embed = discord.Embed(
            title="Clear Lap Times",
            description=(
                f"Are you sure you want to clear all lap times for **{track.value}**?\n\n"
                "**This action cannot be undone!**"
            ),
            color=discord.Color.orange(),
        )

        view = ConfirmView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if view.value is None:
            await interaction.edit_original_response(
                content="Timed out.", embed=None, view=None
            )
        elif view.value:
            count = await self.bot.database.clear_lap_times(track.value)
            logger.info(
                "Cleared %d lap times for track %s by user %s",
                count,
                track.name,
                interaction.user.id,
            )
            await view.interaction.followup.send(
                f"Cleared **{count}** lap times for **{track.value}**!",
                ephemeral=True,
            )
        else:
            await view.interaction.followup.send("Cancelled.", ephemeral=True)

    # ==================== Blacklist Management ====================

    @group.command(name="blacklist")
    async def blacklist_user(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: Optional[str] = None,
    ) -> None:
        """Add a user to the blacklist.

        Parameters
        -----------
        user: discord.User
            The user to blacklist.
        reason: str
            Optional reason for blacklisting.
        """
        if not await self.is_event_admin(interaction):
            return

        logger.info(
            "User %s attempting to blacklist user %s (reason: %s)",
            interaction.user.id,
            user.id,
            reason,
        )

        embed = discord.Embed(
            title="Blacklist User",
            description=(
                f"Are you sure you want to blacklist **{user.display_name}** ({user.id})?"
            ),
            color=discord.Color.red(),
        )
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)

        view = ConfirmView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if view.value is None:
            await interaction.edit_original_response(
                content="Timed out.", embed=None, view=None
            )
        elif view.value:
            await self.bot.database.blacklist_user(str(user.id), reason)
            logger.info(
                "User %s blacklisted user %s",
                interaction.user.id,
                user.id,
            )
            await view.interaction.followup.send(
                f"**{user.display_name}** has been blacklisted!",
                ephemeral=True,
            )
        else:
            await view.interaction.followup.send("Cancelled.", ephemeral=True)

    @group.command(name="unblacklist")
    async def unblacklist_user(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        """Remove a user from the blacklist.

        Parameters
        -----------
        user: discord.User
            The user to remove from the blacklist.
        """
        if not await self.is_event_admin(interaction):
            return

        logger.info(
            "User %s attempting to unblacklist user %s",
            interaction.user.id,
            user.id,
        )

        embed = discord.Embed(
            title="Unblacklist User",
            description=(
                f"Are you sure you want to remove **{user.display_name}** "
                f"({user.id}) from the blacklist?"
            ),
            color=discord.Color.green(),
        )

        view = ConfirmView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()

        if view.value is None:
            await interaction.edit_original_response(
                content="Timed out.", embed=None, view=None
            )
        elif view.value:
            removed = await self.bot.database.unblacklist_user(str(user.id))
            if removed:
                logger.info(
                    "User %s unblacklisted user %s",
                    interaction.user.id,
                    user.id,
                )
                await view.interaction.followup.send(
                    f"**{user.display_name}** has been removed from the blacklist!",
                    ephemeral=True,
                )
            else:
                await view.interaction.followup.send(
                    f"**{user.display_name}** was not in the blacklist.",
                    ephemeral=True,
                )
        else:
            await view.interaction.followup.send("Cancelled.", ephemeral=True)

    @group.command(name="check_blacklist")
    async def check_blacklist(
        self, interaction: discord.Interaction, user: discord.User
    ) -> None:
        """Check if a user is blacklisted.

        Parameters
        -----------
        user: discord.User
            The user to check.
        """
        if not await self.is_event_admin(interaction):
            return

        is_blacklisted = await self.bot.database.is_blacklisted(str(user.id))

        if is_blacklisted:
            embed = discord.Embed(
                title="User Blacklisted",
                description=(
                    f"**{user.display_name}** ({user.id}) is currently blacklisted."
                ),
                color=discord.Color.red(),
            )
        else:
            embed = discord.Embed(
                title="User Not Blacklisted",
                description=(
                    f"**{user.display_name}** ({user.id}) is not blacklisted."
                ),
                color=discord.Color.green(),
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== Settings ====================
    @group.command(name="add_event_admin_role")
    @discord.app_commands.default_permissions(administrator=True)
    async def add_event_admin_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        """Add an event administrator role.

        Parameters
        -----------
        role: discord.Role
            The role to assign as event administrator.
        """
        await self.bot.database.add_event_admin_role(role.id)
        logger.info(
            "User %s added event admin role %s",
            interaction.user.id,
            role.id,
        )
        await interaction.response.send_message(
            f"Event administrator role added: {role.name}.", ephemeral=True
        )

    @group.command(name="remove_event_admin_role")
    @discord.app_commands.default_permissions(administrator=True)
    async def remove_event_admin_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ) -> None:
        """Remove an event administrator role.

        Parameters
        -----------
        role: discord.Role
            The role to remove from event administrators.
        """
        removed = await self.bot.database.remove_event_admin_role(role.id)
        if removed:
            logger.info(
                "User %s removed event admin role %s",
                interaction.user.id,
                role.id,
            )
            await interaction.response.send_message(
                f"Event administrator role removed: {role.name}.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Role {role.name} was not in the event administrator list.", ephemeral=True
            )

    @group.command(name="view_event_admin_roles")
    @discord.app_commands.default_permissions(administrator=True)
    async def view_event_admin_roles(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """View the current event administrator role."""
        role_ids = await self.bot.database.get_event_admin_roles()
        if role_ids:
            roles = [interaction.guild.get_role(role_id) for role_id in role_ids]
            role_names = [role.name if role else f"Role ID: {role_id} (not found)" for role, role_id in zip(roles, role_ids)]
            await interaction.response.send_message(
                f"Current event administrator roles: {', '.join(role_names)}.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "No event administrator role is set.", ephemeral=True
            )

    # ==================== Error Handler ====================
    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Handle errors from app commands in this cog."""
        if isinstance(error, app_commands.CheckFailure):
            logger.warning(
                "Permission denied for user %s on command",
                interaction.user.id,
            )
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True,
            )
        elif isinstance(error.__cause__, DatabaseError):
            logger.error("Database error in admin command: %s", error)
            await interaction.response.send_message(
                "A database error occurred. Please try again later.",
                ephemeral=True,
            )
        else:
            logger.exception("Unexpected error in admin command: %s", error)
            await interaction.response.send_message(
                f"An error occurred: {error}",
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    """Load the Admin cog."""
    await bot.add_cog(Admin(bot))
