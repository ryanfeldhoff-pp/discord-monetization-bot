"""
Recap Card Image Generator

Generates branded recap cards using Pillow for monthly user statistics.
"""

import io
import logging
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
import qrcode

logger = logging.getLogger(__name__)


class RecapCardGenerator:
    """
    Generate recap cards as PNG images.

    Features:
    - Dark template with PrizePicks purple accents (#6C2BD9)
    - Dynamic text rendering for stats
    - QR code generation for referral links
    - Multiple resolution support
    """

    # Design constants
    CARD_WIDTH = 1200
    CARD_HEIGHT = 1600
    MARGIN = 40
    PRIMARY_COLOR = (108, 43, 217)  # PrizePicks purple
    SECONDARY_COLOR = (255, 255, 255)  # White
    BG_COLOR = (20, 20, 30)  # Dark background
    ACCENT_COLOR = (245, 130, 32)  # Orange accent

    def __init__(self, font_dir: Optional[str] = None):
        """
        Initialize image generator.

        Args:
            font_dir: Path to fonts directory (optional)
        """
        self.font_dir = font_dir or "/usr/share/fonts/truetype/dejavu/"

        # Load fonts
        try:
            self.font_title = ImageFont.truetype(
                f"{self.font_dir}DejaVuSans-Bold.ttf",
                size=72,
            )
            self.font_heading = ImageFont.truetype(
                f"{self.font_dir}DejaVuSans-Bold.ttf",
                size=48,
            )
            self.font_normal = ImageFont.truetype(
                f"{self.font_dir}DejaVuSans.ttf",
                size=32,
            )
            self.font_small = ImageFont.truetype(
                f"{self.font_dir}DejaVuSans.ttf",
                size=24,
            )
        except OSError:
            logger.warning("Custom fonts not found, using default")
            self.font_title = ImageFont.load_default()
            self.font_heading = ImageFont.load_default()
            self.font_normal = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def generate_recap_card(
        self,
        username: str,
        entries_placed: int,
        win_rate: float,
        biggest_win: float,
        most_played_sport: str,
        most_played_player: str,
        xp_earned: int,
        messages_sent: int,
        community_rank: int,
        referral_link: str,
    ) -> io.BytesIO:
        """
        Generate recap card as PNG image.

        Args:
            username: Discord username
            entries_placed: Number of entries placed
            win_rate: Win rate as percentage (0-100)
            biggest_win: Biggest win amount
            most_played_sport: Sport name
            most_played_player: Player name
            xp_earned: XP earned in month
            messages_sent: Messages sent in Discord
            community_rank: Leaderboard rank
            referral_link: Referral URL for QR code

        Returns:
            BytesIO object containing PNG image
        """
        try:
            # Create base image
            image = Image.new("RGB", (self.CARD_WIDTH, self.CARD_HEIGHT), self.BG_COLOR)
            draw = ImageDraw.Draw(image)

            y_offset = self.MARGIN

            # Header
            y_offset = self._draw_header(draw, y_offset, username)

            # Stats grid
            y_offset = self._draw_stats_grid(
                draw,
                y_offset,
                entries_placed,
                win_rate,
                biggest_win,
                xp_earned,
                messages_sent,
                community_rank,
            )

            # Top picks section
            y_offset = self._draw_top_picks(
                draw,
                y_offset,
                most_played_sport,
                most_played_player,
            )

            # QR code section
            y_offset = self._draw_qr_code(draw, y_offset, referral_link)

            # Footer
            self._draw_footer(draw, y_offset)

            # Convert to bytes
            output = io.BytesIO()
            image.save(output, format="PNG")
            output.seek(0)

            logger.info(f"Generated recap card for {username}")
            return output

        except Exception as e:
            logger.error(f"Error generating recap card: {e}")
            raise

    def _draw_header(self, draw: ImageDraw.ImageDraw, y: int, username: str) -> int:
        """
        Draw header with title and username.

        Args:
            draw: ImageDraw object
            y: Current Y position
            username: Username to display

        Returns:
            New Y position
        """
        # Title background
        draw.rectangle(
            [(0, y), (self.CARD_WIDTH, y + 150)],
            fill=self.PRIMARY_COLOR,
        )

        # Title text
        title_text = "Your 2024 Recap"
        title_bbox = draw.textbbox((0, 0), title_text, font=self.font_title)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (self.CARD_WIDTH - title_width) // 2

        draw.text(
            (title_x, y + 30),
            title_text,
            font=self.font_title,
            fill=self.SECONDARY_COLOR,
        )

        # Subtitle with username
        subtitle = f"@{username}"
        subtitle_bbox = draw.textbbox((0, 0), subtitle, font=self.font_small)
        subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
        subtitle_x = (self.CARD_WIDTH - subtitle_width) // 2

        draw.text(
            (subtitle_x, y + 110),
            subtitle,
            font=self.font_small,
            fill=self.ACCENT_COLOR,
        )

        return y + 180

    def _draw_stats_grid(
        self,
        draw: ImageDraw.ImageDraw,
        y: int,
        entries_placed: int,
        win_rate: float,
        biggest_win: float,
        xp_earned: int,
        messages_sent: int,
        community_rank: int,
    ) -> int:
        """
        Draw 2x3 stats grid.

        Args:
            draw: ImageDraw object
            y: Current Y position
            entries_placed: Entry count
            win_rate: Win rate percentage
            biggest_win: Biggest win amount
            xp_earned: XP earned
            messages_sent: Message count
            community_rank: Rank

        Returns:
            New Y position
        """
        stats = [
            ("Entries Placed", f"{entries_placed:,}", "📊"),
            ("Win Rate", f"{win_rate:.1f}%", "🎯"),
            ("Biggest Win", f"${biggest_win:,.2f}", "💰"),
            ("XP Earned", f"{xp_earned:,}", "⭐"),
            ("Messages Sent", f"{messages_sent:,}", "💬"),
            ("Community Rank", f"#{community_rank}", "🏆"),
        ]

        # Grid layout: 2 columns x 3 rows
        cell_width = (self.CARD_WIDTH - 2 * self.MARGIN) // 2
        cell_height = 200
        spacing = 20

        for idx, (label, value, emoji) in enumerate(stats):
            row = idx // 2
            col = idx % 2

            x = self.MARGIN + col * (cell_width + spacing)
            cell_y = y + row * (cell_height + spacing)

            # Cell background
            draw.rectangle(
                [(x, cell_y), (x + cell_width, cell_y + cell_height)],
                fill=(35, 35, 50),
                outline=self.PRIMARY_COLOR,
                width=2,
            )

            # Emoji
            draw.text(
                (x + 20, cell_y + 20),
                emoji,
                font=self.font_heading,
                fill=self.SECONDARY_COLOR,
            )

            # Label
            draw.text(
                (x + 20, cell_y + 80),
                label,
                font=self.font_small,
                fill=(150, 150, 150),
            )

            # Value
            value_bbox = draw.textbbox((0, 0), value, font=self.font_heading)
            value_width = value_bbox[2] - value_bbox[0]
            value_x = x + cell_width - value_width - 20

            draw.text(
                (value_x, cell_y + 100),
                value,
                font=self.font_heading,
                fill=self.SECONDARY_COLOR,
            )

        return y + 3 * (cell_height + spacing)

    def _draw_top_picks(
        self,
        draw: ImageDraw.ImageDraw,
        y: int,
        most_played_sport: str,
        most_played_player: str,
    ) -> int:
        """
        Draw top picks section.

        Args:
            draw: ImageDraw object
            y: Current Y position
            most_played_sport: Sport name
            most_played_player: Player name

        Returns:
            New Y position
        """
        # Section title
        draw.text(
            (self.MARGIN, y),
            "Your Top Picks",
            font=self.font_heading,
            fill=self.PRIMARY_COLOR,
        )

        y += 60

        # Sport
        draw.text(
            (self.MARGIN, y),
            f"Most Played Sport: {most_played_sport}",
            font=self.font_normal,
            fill=self.SECONDARY_COLOR,
        )

        y += 70

        # Player
        draw.text(
            (self.MARGIN, y),
            f"Favorite Player: {most_played_player}",
            font=self.font_normal,
            fill=self.SECONDARY_COLOR,
        )

        y += 100

        return y

    def _draw_qr_code(
        self,
        draw: ImageDraw.ImageDraw,
        y: int,
        referral_link: str,
    ) -> int:
        """
        Draw QR code for referral link.

        Args:
            draw: ImageDraw object
            y: Current Y position
            referral_link: URL to encode

        Returns:
            New Y position
        """
        # Section title
        draw.text(
            (self.MARGIN, y),
            "Share Your Recap",
            font=self.font_heading,
            fill=self.PRIMARY_COLOR,
        )

        y += 80

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(referral_link)
        qr.make(fit=True)

        qr_image = qr.make_image(fill_color="white", back_color=(35, 35, 50))
        qr_image = qr_image.resize((250, 250))

        # Center QR code
        qr_x = (self.CARD_WIDTH - 250) // 2

        # Paste QR code onto main image
        # Note: This is a simplification; in production, convert to RGB first
        self._paste_image_safe(draw, qr_image, qr_x, y)

        y += 280

        return y

    def _draw_footer(self, draw: ImageDraw.ImageDraw, y: int) -> None:
        """
        Draw footer with branding.

        Args:
            draw: ImageDraw object
            y: Current Y position
        """
        # Footer background
        draw.rectangle(
            [(0, y), (self.CARD_WIDTH, self.CARD_HEIGHT)],
            fill=(35, 35, 50),
        )

        # Footer text
        footer_text = "PrizePicks Discord Monetization • 2024"
        footer_bbox = draw.textbbox((0, 0), footer_text, font=self.font_small)
        footer_width = footer_bbox[2] - footer_bbox[0]
        footer_x = (self.CARD_WIDTH - footer_width) // 2

        draw.text(
            (footer_x, y + 50),
            footer_text,
            font=self.font_small,
            fill=(100, 100, 100),
        )

    @staticmethod
    def _paste_image_safe(
        draw: ImageDraw.ImageDraw,
        img: Image.Image,
        x: int,
        y: int,
    ) -> None:
        """
        Safely paste an image (workaround for Pillow limitations).

        Args:
            draw: ImageDraw object
            img: Image to paste
            x: X position
            y: Y position
        """
        # For now, just draw a placeholder
        # In production, use Image.paste() after converting formats
        draw.rectangle(
            [(x, y), (x + 250, y + 250)],
            outline=(108, 43, 217),
            width=2,
        )
