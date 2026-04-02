"""
Paginated view for displaying multi-page embeds.

Provides a reusable PaginatedView class for navigating through
lists of embeds with Previous/Next buttons and page indicators.
"""

from typing import List, Optional, Callable
import discord
from discord import ui


class PaginatedView(ui.View):
    """
    Reusable paginated view for displaying multiple embeds.

    Includes Previous/Next buttons, page indicator, and optional
    "Jump to My Rank" callback for leaderboards.
    """

    def __init__(
        self,
        embeds: List[discord.Embed],
        on_jump_to_rank: Optional[Callable] = None,
        timeout: float = 60.0,
    ):
        """
        Initialize paginated view.

        Args:
            embeds: List of discord.Embed objects (one per page)
            on_jump_to_rank: Optional async callback(interaction) for jump button
            timeout: Button timeout in seconds (default 60)
        """
        super().__init__(timeout=timeout)

        if not embeds:
            raise ValueError("At least one embed is required")

        self.embeds = embeds
        self.current_page = 0
        self.on_jump_to_rank = on_jump_to_rank

        self._update_buttons()

    def _update_buttons(self) -> None:
        """Update button states based on current page."""
        # Disable previous button on first page
        self.previous_button.disabled = self.current_page == 0

        # Disable next button on last page
        self.next_button.disabled = self.current_page == len(self.embeds) - 1

        # Disable jump button if no callback
        self.jump_to_rank_button.disabled = self.on_jump_to_rank is None

    @ui.button(
        label="Previous",
        emoji="◀️",
        style=discord.ButtonStyle.secondary,
    )
    async def previous_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ) -> None:
        """Navigate to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self._update_buttons()
            await interaction.response.edit_message(
                embed=self.embeds[self.current_page],
                view=self,
            )
        else:
            await interaction.response.defer()

    @ui.button(
        label="1 / 1",
        emoji="📄",
        style=discord.ButtonStyle.secondary,
        disabled=True,
    )
    async def page_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ) -> None:
        """
        Page indicator button (non-interactive).

        This button is disabled and only shows the current page.
        """
        await interaction.response.defer()

    @ui.button(
        label="Next",
        emoji="▶️",
        style=discord.ButtonStyle.secondary,
    )
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ) -> None:
        """Navigate to next page."""
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            self._update_buttons()
            await interaction.response.edit_message(
                embed=self.embeds[self.current_page],
                view=self,
            )
        else:
            await interaction.response.defer()

    @ui.button(
        label="Jump to My Rank",
        emoji="📍",
        style=discord.ButtonStyle.primary,
        disabled=True,
    )
    async def jump_to_rank_button(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ) -> None:
        """Jump to user's rank on the leaderboard."""
        if self.on_jump_to_rank:
            await self.on_jump_to_rank(interaction)
        else:
            await interaction.response.defer()

    async def on_timeout(self) -> None:
        """Disable all buttons on timeout."""
        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True

    def get_current_embed(self) -> discord.Embed:
        """Get the current embed."""
        return self.embeds[self.current_page]

    def update_page_indicator(self) -> None:
        """
        Update the page indicator button label.

        Call this after changing embeds or current_page.
        """
        total = len(self.embeds)
        current = self.current_page + 1

        # Find the page button
        for item in self.children:
            if isinstance(item, ui.Button) and item.label and "of" in item.label:
                item.label = f"{current} / {total}"
                break
