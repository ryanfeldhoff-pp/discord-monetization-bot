"""
Reusable UI components (discord.ui.View subclasses).

Provides common interactive components like confirmation dialogs,
retry buttons, and unsubscribe buttons.
"""

from typing import Optional
import discord
from discord import ui


class ConfirmView(ui.View):
    """
    Simple confirmation dialog with Confirm/Cancel buttons.

    Usage:
        view = ConfirmView()
        await ctx.respond("Are you sure?", view=view)
        await view.wait()
        if view.result:
            # User confirmed
    """

    def __init__(self, timeout: float = 60.0):
        """
        Initialize confirmation view.

        Args:
            timeout: Button timeout in seconds (default 60)
        """
        super().__init__(timeout=timeout)
        self.result: Optional[bool] = None

    @ui.button(
        label="Confirm",
        emoji="✅",
        style=discord.ButtonStyle.success,
    )
    async def confirm_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ) -> None:
        """Handle confirm button."""
        self.result = True
        await interaction.response.defer()
        self.stop()

    @ui.button(
        label="Cancel",
        emoji="❌",
        style=discord.ButtonStyle.danger,
    )
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ) -> None:
        """Handle cancel button."""
        self.result = False
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self) -> None:
        """Disable buttons on timeout."""
        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True
        self.result = False


class RetryView(ui.View):
    """
    Simple retry button for transient errors.

    Usage:
        view = RetryView()
        await ctx.respond("Something went wrong", view=view)
        await view.wait()
        if view.should_retry:
            # User clicked retry
    """

    def __init__(self, timeout: float = 60.0):
        """
        Initialize retry view.

        Args:
            timeout: Button timeout in seconds (default 60)
        """
        super().__init__(timeout=timeout)
        self.should_retry: bool = False

    @ui.button(
        label="Retry",
        emoji="🔄",
        style=discord.ButtonStyle.primary,
    )
    async def retry_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ) -> None:
        """Handle retry button."""
        self.should_retry = True
        await interaction.response.defer()
        self.stop()

    @ui.button(
        label="Cancel",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ) -> None:
        """Handle cancel button."""
        self.should_retry = False
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self) -> None:
        """Disable buttons on timeout."""
        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True
        self.should_retry = False


class UnsubscribeView(ui.View):
    """
    Unsubscribe button for DM alerts.

    Usage:
        view = UnsubscribeView(user_id, alert_type)
        embed = discord.Embed(...)
        await user.send(embed=embed, view=view)
    """

    def __init__(
        self,
        user_id: int,
        alert_type: str,
        timeout: float = 3600.0,
    ):
        """
        Initialize unsubscribe view.

        Args:
            user_id: Discord user ID to unsubscribe
            alert_type: Type of alert (e.g., "board_alerts", "referral_alerts")
            timeout: Button timeout in seconds (default 1 hour)
        """
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.alert_type = alert_type
        self.unsubscribed: bool = False

    @ui.button(
        label="Unsubscribe from this alert",
        emoji="🔕",
        style=discord.ButtonStyle.danger,
    )
    async def unsubscribe_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ) -> None:
        """Handle unsubscribe button."""
        # Note: Actual unsubscription logic should be implemented
        # by the calling code. This view just tracks the intent.
        self.unsubscribed = True

        await interaction.response.send_message(
            "✅ You've been unsubscribed from this alert",
            ephemeral=True,
        )
        self.stop()

    async def on_timeout(self) -> None:
        """Disable button on timeout."""
        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True


class DismissView(ui.View):
    """
    Simple dismiss button for temporary messages.

    Usage:
        view = DismissView(timeout=30)
        await ctx.respond("Some info", view=view)
    """

    def __init__(self, timeout: float = 30.0):
        """
        Initialize dismiss view.

        Args:
            timeout: Button timeout in seconds (default 30)
        """
        super().__init__(timeout=timeout)

    @ui.button(
        label="Dismiss",
        emoji="✋",
        style=discord.ButtonStyle.secondary,
    )
    async def dismiss_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ) -> None:
        """Delete the message."""
        await interaction.message.delete()

    async def on_timeout(self) -> None:
        """Disable button on timeout."""
        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True
