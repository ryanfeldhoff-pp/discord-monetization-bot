"""
OCR Screenshot-to-Entry Cog.

Detects PrizePicks screenshots, performs OCR, matches against projections,
and generates tailable entry links with confidence scoring.
"""

import asyncio
import logging
import os
from typing import Optional

import discord
from discord.ext import commands

from src.services.analytics import AnalyticsService
from src.services.ocr_service import OCRService, OCRProvider
from src.services.prizepicks_api import PrizepicksAPIClient
from src.utils.embeds import info_embed, error_embed, success_embed

logger = logging.getLogger(__name__)

# OCR processing timeout (seconds)
OCR_TIMEOUT = 5


class OCRConfirmationView(discord.ui.View):
    """View for OCR result confirmation."""

    def __init__(
        self,
        entry_link: str,
        confidence: float,
        analytics: Optional[AnalyticsService] = None,
    ):
        """Initialize the view."""
        super().__init__(timeout=300)  # 5 minute timeout
        self.entry_link = entry_link
        self.confidence = confidence
        self.analytics = analytics
        self.confirmed = False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """Handle confirmation."""
        self.confirmed = True

        if self.analytics:
            await self.analytics.emit_event(
                "ocr_match",
                {
                    "discord_user_id": interaction.user.id,
                    "confidence": self.confidence,
                    "action": "confirmed",
                    "channel_id": interaction.channel_id,
                    "guild_id": interaction.guild_id,
                    "timestamp": discord.utils.utcnow().isoformat(),
                },
            )

        embed = success_embed(
            "Entry Confirmed",
            "Click the button to open in PrizePicks",
        )

        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Open Entry",
                url=self.entry_link,
                style=discord.ButtonStyle.link,
            )
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Report Error", style=discord.ButtonStyle.secondary)
    async def report_error_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """Handle error reporting."""
        if self.analytics:
            await self.analytics.emit_event(
                "ocr_match",
                {
                    "discord_user_id": interaction.user.id,
                    "confidence": self.confidence,
                    "action": "reported_error",
                    "channel_id": interaction.channel_id,
                    "guild_id": interaction.guild_id,
                    "timestamp": discord.utils.utcnow().isoformat(),
                },
            )

        embed = info_embed(
            "Error Reported",
            "Thank you for reporting! Our team will review this scan.",
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.red)
    async def dismiss_button(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        """Handle dismissal."""
        if self.analytics:
            await self.analytics.emit_event(
                "ocr_match",
                {
                    "discord_user_id": interaction.user.id,
                    "confidence": self.confidence,
                    "action": "dismissed",
                    "channel_id": interaction.channel_id,
                    "guild_id": interaction.guild_id,
                    "timestamp": discord.utils.utcnow().isoformat(),
                },
            )

        await interaction.response.send_message(
            "Result dismissed.",
            ephemeral=True,
        )


class OCRBotCog(commands.Cog):
    """Cog for OCR-based entry detection."""

    def __init__(self, bot: commands.Bot):
        """Initialize the cog."""
        self.bot = bot
        self.prizepicks_client: PrizepicksAPIClient = bot.prizepicks_client
        self.analytics: Optional[AnalyticsService] = bot.analytics

        # Initialize OCR service
        ocr_provider = os.getenv("OCR_PROVIDER", "google").lower()
        if ocr_provider == "google":
            self.ocr_service = OCRService(OCRProvider.GOOGLE_VISION)
        elif ocr_provider == "aws":
            self.ocr_service = OCRService(OCRProvider.AWS_TEXTRACT)
        else:
            logger.warning(f"Unknown OCR provider: {ocr_provider}, using Google Vision")
            self.ocr_service = OCRService(OCRProvider.GOOGLE_VISION)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Listen for messages with images that might be PrizePicks screenshots.

        Args:
            message: Discord message object
        """
        # Ignore bot messages
        if message.author.bot:
            return

        # Ignore DMs
        if not message.guild:
            return

        try:
            # Check if message has attachments
            if not message.attachments:
                return

            # Process each image attachment
            for attachment in message.attachments:
                if not self._is_image(attachment):
                    continue

                # Check if image looks like PrizePicks screenshot
                if not await self._looks_like_prizepicks_screenshot(attachment):
                    continue

                # Process image
                await self._process_screenshot(
                    attachment,
                    message.channel,
                    message.author.id,
                )

        except Exception as e:
            logger.error(f"Error in on_message: {e}", exc_info=True)

    def _is_image(self, attachment: discord.Attachment) -> bool:
        """
        Check if attachment is an image.

        Args:
            attachment: Discord attachment

        Returns:
            bool: True if image
        """
        return attachment.content_type and attachment.content_type.startswith("image/")

    async def _looks_like_prizepicks_screenshot(
        self,
        attachment: discord.Attachment,
    ) -> bool:
        """
        Use heuristics to determine if image might be PrizePicks screenshot.

        Basic heuristics:
        - Image dimensions (portrait/square, typical app dimensions)
        - File size range (not too large, not too small)
        - Dominant colors matching PrizePicks UI (purples, greens)

        Args:
            attachment: Discord attachment

        Returns:
            bool: True if might be PrizePicks screenshot
        """
        try:
            # Size constraints (images should be reasonable size for a screenshot)
            if attachment.size < 5000 or attachment.size > 10 * 1024 * 1024:
                return False

            # TODO: Implement color analysis for PrizePicks UI colors
            # For now, accept most images and let OCR handle filtering

            return True

        except Exception as e:
            logger.warning(f"Error checking image: {e}")
            return False

    async def _process_screenshot(
        self,
        attachment: discord.Attachment,
        channel: discord.TextChannel,
        user_id: int,
    ) -> None:
        """
        Process a potentially PrizePicks screenshot.

        Args:
            attachment: Discord attachment
            channel: Discord channel
            user_id: Discord user ID
        """
        try:
            # Download image
            image_bytes = await attachment.read()

            # Send "processing" message
            processing_msg = await channel.send("Analyzing screenshot... (this may take a moment)")

            # Emit analytics event
            if self.analytics:
                await self.analytics.emit_event(
                    "ocr_scan",
                    {
                        "discord_user_id": user_id,
                        "channel_id": channel.id,
                        "guild_id": channel.guild.id,
                        "timestamp": discord.utils.utcnow().isoformat(),
                    },
                )

            # Run OCR with timeout
            try:
                ocr_result = await asyncio.wait_for(
                    self.ocr_service.extract_text(image_bytes),
                    timeout=OCR_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning(f"OCR timeout for user {user_id}")
                await processing_msg.delete()
                return

            if not ocr_result or not ocr_result.text:
                logger.debug(f"No text extracted from image for user {user_id}")
                await processing_msg.delete()
                return

            # Match text against projections
            match_result = await self._match_projections(ocr_result.text)

            if not match_result:
                logger.debug(f"No projection matches for user {user_id}")
                await processing_msg.delete()
                return

            # Interpret confidence level
            confidence_pct = match_result['confidence'] * 100
            if confidence_pct >= 95:
                confidence_label = "Very High"
            elif confidence_pct >= 80:
                confidence_label = "High"
            elif confidence_pct >= 70:
                confidence_label = "Medium"
            else:
                confidence_label = "Low"

            # Create embed with match result
            embed = info_embed(
                "Entry Detected",
                f"Confidence: {confidence_label} ({confidence_pct:.0f}%)",
                [
                    ("Matched Props", match_result.get("summary", ""), False),
                ]
            )

            # Create confirmation view
            view = OCRConfirmationView(
                entry_link=match_result["entry_link"],
                confidence=match_result["confidence"],
                analytics=self.analytics,
            )

            # Replace processing message
            await processing_msg.delete()
            await channel.send(embed=embed, view=view)

            logger.info(f"Screenshot processed for user {user_id}")

        except Exception as e:
            logger.error(f"Error processing screenshot: {e}", exc_info=True)
            embed = error_embed(
                "OCR Processing Failed",
                "An error occurred while processing the screenshot",
                recovery_hint="Please try uploading a clearer image",
                error_code="OCR_PROCESS_ERROR"
            )
            try:
                await processing_msg.delete()
                await channel.send(embed=embed, delete_after=30)
            except Exception:
                pass

    async def _match_projections(self, extracted_text: str) -> Optional[dict]:
        """
        Match extracted text against current projections.

        Args:
            extracted_text: Text extracted by OCR

        Returns:
            dict: Match result with entry_link, confidence, summary, or None
        """
        try:
            # TODO: Implement matching algorithm
            # 1. Parse extracted text to identify players and stat types
            # 2. Fetch current projections from /projections API
            # 3. Match extracted players/stats against projections
            # 4. Calculate confidence score
            # 5. Generate entry link with matched selections
            # 6. Return match result

            # Placeholder implementation
            return None

        except Exception as e:
            logger.error(f"Error matching projections: {e}", exc_info=True)
            return None


async def setup(bot: commands.Bot) -> None:
    """Load the cog."""
    await bot.add_cog(OCRBotCog(bot))
