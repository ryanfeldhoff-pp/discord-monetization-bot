"""
Discord ↔ PrizePicks Account Linking Cog.

Handles OAuth 2.0 authentication flow, account linking/unlinking, and role management.
"""

import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import discord
from aiohttp import web
from discord.ext import commands

from src.models.database import AccountLink, Database
from src.services.prizepicks_api import PrizepicksAPIClient
from src.utils.embeds import (
    info_embed,
    success_embed,
    error_embed,
    confirmation_embed,
)
from src.utils.views import ConfirmView

logger = logging.getLogger(__name__)


class LinkState:
    """Represents the state of a link operation."""

    def __init__(self, state: str, discord_user_id: int):
        """Initialize link state."""
        self.state = state
        self.discord_user_id = discord_user_id
        self.created_at = datetime.utcnow()

    def is_expired(self, timeout_minutes: int = 10) -> bool:
        """Check if state has expired (default 10 minutes)."""
        return datetime.utcnow() - self.created_at > timedelta(minutes=timeout_minutes)


class AccountLinkingCog(commands.Cog):
    """Cog for handling account linking between Discord and PrizePicks."""

    def __init__(self, bot: commands.Bot):
        """Initialize the cog."""
        self.bot = bot
        self.prizepicks_client: PrizepicksAPIClient = bot.prizepicks_client
        self.db: Optional[Database] = None
        self.oauth_states: dict[str, LinkState] = {}

        # OAuth configuration
        self.oauth_client_id = os.getenv("PRIZEPICKS_OAUTH_CLIENT_ID")
        self.oauth_client_secret = os.getenv("PRIZEPICKS_OAUTH_CLIENT_SECRET")
        self.oauth_redirect_uri = os.getenv(
            "PRIZEPICKS_OAUTH_REDIRECT_URI",
            "http://localhost:8000/auth/discord/callback",
        )

    async def cog_load(self) -> None:
        """Initialize cog resources."""
        self.db = await Database.create()
        logger.info("AccountLinkingCog loaded")

    async def cog_unload(self) -> None:
        """Clean up cog resources."""
        if self.db:
            await self.db.close()

    def _generate_oauth_url(self, state: str) -> str:
        """
        Generate OAuth 2.0 authorization URL.

        Args:
            state: CSRF protection state parameter

        Returns:
            str: Authorization URL
        """
        # TODO: Confirm OAuth endpoint with PrizePicks backend team
        base_url = os.getenv("PRIZEPICKS_OAUTH_URL", "https://oauth.prizepicks.com/authorize")
        params = {
            "client_id": self.oauth_client_id,
            "redirect_uri": self.oauth_redirect_uri,
            "response_type": "code",
            "scope": "profile:read account:link",
            "state": state,
        }
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{base_url}?{query_string}"

    @commands.slash_command(
        name="link",
        description="Link your Discord account to PrizePicks",
    )
    async def link_account(self, ctx: discord.ApplicationContext) -> None:
        """
        Initiate OAuth 2.0 flow to link Discord account to PrizePicks.

        Args:
            ctx: Discord application context
        """
        try:
            # Check if already linked
            if self.db:
                existing = await self.db.get_account_link(ctx.author.id)
                if existing and existing.status == "linked":
                    embed = info_embed(
                        "Already Linked",
                        "Your account is already linked to PrizePicks!",
                    )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return

            # Generate state for CSRF protection (10-minute timeout)
            state = secrets.token_urlsafe(32)
            self.oauth_states[state] = LinkState(state, ctx.author.id)

            # Generate OAuth URL
            oauth_url = self._generate_oauth_url(state)

            # Send ephemeral message with auth URL
            embed = info_embed(
                "Link Your PrizePicks Account",
                "Click the button below to authorize and link your account.",
                [
                    ("What happens next?", "1. Click the link button\n2. Authorize on PrizePicks\n3. Return to Discord\n4. You'll be assigned the 'Linked' role", False),
                ]
            )

            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label="Link Account",
                    url=oauth_url,
                    style=discord.ButtonStyle.link,
                )
            )
            view.add_item(
                discord.ui.Button(
                    label="Cancel",
                    style=discord.ButtonStyle.secondary,
                    custom_id="cancel_linking",
                )
            )

            await ctx.respond(embed=embed, view=view, ephemeral=True)
            logger.info(f"Link flow initiated for user {ctx.author.id}")

        except Exception as e:
            logger.error(f"Error in link command: {e}", exc_info=True)
            embed = error_embed(
                "Link Initiation Failed",
                "An error occurred while initiating the link process",
                recovery_hint="Please try again in a moment",
                error_code="LINK_INIT_ERROR"
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(
        name="unlink",
        description="Unlink your Discord account from PrizePicks",
    )
    async def unlink_account(self, ctx: discord.ApplicationContext) -> None:
        """
        Unlink Discord account from PrizePicks with confirmation.

        Args:
            ctx: Discord application context
        """
        try:
            if not self.db:
                embed = error_embed(
                    "Database Error",
                    "Database not available",
                    recovery_hint="Please try again",
                    error_code="DB_UNAVAILABLE"
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Check if linked
            account_link = await self.db.get_account_link(ctx.author.id)
            if not account_link or account_link.status != "linked":
                embed = info_embed(
                    "Not Linked",
                    "Your account is not linked to PrizePicks.",
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            # Ask for confirmation
            confirm_view = ConfirmView()
            embed = confirmation_embed(
                "Unlink PrizePicks Account",
                "This will disconnect your PrizePicks account from Discord and remove your 'Linked' role"
            )

            await ctx.respond(embed=embed, view=confirm_view, ephemeral=True)
            await confirm_view.wait()

            if not confirm_view.result:
                await ctx.followup.send("Unlink cancelled", ephemeral=True)
                return

            # Remove link from database
            await self.db.delete_account_link(ctx.author.id)

            # Remove role
            linked_role = discord.utils.get(ctx.guild.roles, name="Linked")
            if linked_role and linked_role in ctx.author.roles:
                await ctx.author.remove_roles(linked_role)

            # Emit analytics event
            if self.bot.analytics:
                await self.bot.analytics.emit_event(
                    "account_unlinked",
                    {
                        "discord_user_id": ctx.author.id,
                        "guild_id": ctx.guild.id,
                        "timestamp": discord.utils.utcnow().isoformat(),
                    },
                )

            embed = success_embed(
                "Account Unlinked",
                "Your account has been successfully disconnected from PrizePicks"
            )
            await ctx.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Account unlinked for user {ctx.author.id}")

        except Exception as e:
            logger.error(f"Error in unlink command: {e}", exc_info=True)
            embed = error_embed(
                "Unlink Failed",
                "An error occurred while unlinking your account",
                recovery_hint="Please try again in a moment",
                error_code="UNLINK_ERROR"
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(
        name="link",
        description="Link your Discord account to PrizePicks",
    )
    @discord.option(
        name="status",
        description="Check your account link status",
        required=False,
    )
    async def link_status(self, ctx: discord.ApplicationContext, status: str = None) -> None:
        """
        Link subcommand to display current link status.

        Args:
            ctx: Discord application context
            status: Subcommand name
        """
        try:
            if status != "status":
                return

            if not self.db:
                embed = error_embed(
                    "Database Error",
                    "Database not available",
                    recovery_hint="Please try again",
                    error_code="DB_UNAVAILABLE"
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return

            account_link = await self.db.get_account_link(ctx.author.id)

            if account_link and account_link.status == "linked":
                # Check token expiry
                if account_link.token_expires_at and datetime.fromisoformat(account_link.token_expires_at) < datetime.utcnow():
                    embed = info_embed(
                        "Link Expired",
                        "Your account link has expired. Use `/link` to reconnect",
                    )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return

                embed = success_embed(
                    "Account Linked",
                    "Your account is linked to PrizePicks!",
                    [
                        ("Linked At", account_link.linked_at.isoformat(), False),
                        ("PrizePicks User ID", account_link.prizepicks_user_id, False),
                    ]
                )
                await ctx.respond(embed=embed, ephemeral=True)
            else:
                embed = info_embed(
                    "Not Linked",
                    "Your account is not linked to PrizePicks.",
                    [
                        ("Next Steps", "Use `/link` to start the linking process.", False),
                    ]
                )
                await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in link status command: {e}", exc_info=True)
            embed = error_embed(
                "Status Check Failed",
                "An error occurred while checking your link status",
                recovery_hint="Please try again in a moment",
                error_code="STATUS_CHECK_ERROR"
            )
            await ctx.respond(embed=embed, ephemeral=True)

    async def handle_oauth_callback(self, request: web.Request) -> web.Response:
        """
        Handle OAuth 2.0 callback from PrizePicks.

        Args:
            request: AIOHTTP request object

        Returns:
            web.Response: HTTP response
        """
        try:
            code = request.query.get("code")
            state = request.query.get("state")
            error = request.query.get("error")

            # Check for errors
            if error:
                logger.warning(f"OAuth error: {error}")
                return web.Response(
                    text=f"Authorization failed: {error}",
                    status=400,
                )

            # Verify state parameter (CSRF protection) - check 10-minute timeout
            if state not in self.oauth_states:
                logger.warning(f"Invalid state parameter: {state}")
                return web.Response(
                    text="Invalid state parameter",
                    status=400,
                )

            link_state = self.oauth_states.get(state)

            # Check if state has expired
            if link_state and link_state.is_expired(timeout_minutes=10):
                self.oauth_states.pop(state, None)
                logger.warning(f"OAuth state expired: {state}")
                return web.Response(
                    text="Authorization request has expired. Please try again.",
                    status=400,
                )

            link_state = self.oauth_states.pop(state)

            try:
                # Exchange code for access token with PrizePicks backend
                access_token = await self._exchange_code_for_token(code)
                prizepicks_user_id = await self._get_prizepicks_user_id(access_token)

                # Store in database with token expiry
                if self.db:
                    token_expires_at = datetime.utcnow() + timedelta(hours=24)
                    await self.db.create_account_link(
                        discord_user_id=link_state.discord_user_id,
                        prizepicks_user_id=prizepicks_user_id,
                        status="linked",
                        token_expires_at=token_expires_at.isoformat(),
                    )

                # Try to assign role if in guild
                guild_id = None
                try:
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        member = guild.get_member(link_state.discord_user_id)
                        if member:
                            linked_role = discord.utils.get(guild.roles, name="Linked")
                            if linked_role:
                                await member.add_roles(linked_role)
                except Exception as e:
                    logger.warning(f"Could not assign role: {e}")

                # Emit analytics event
                if self.bot.analytics:
                    await self.bot.analytics.emit_event(
                        "account_linked",
                        {
                            "discord_user_id": link_state.discord_user_id,
                            "prizepicks_user_id": prizepicks_user_id,
                            "timestamp": discord.utils.utcnow().isoformat(),
                        },
                    )

                logger.info(
                    f"Account linked: discord_user_id={link_state.discord_user_id}, "
                    f"prizepicks_user_id={prizepicks_user_id}"
                )

                return web.Response(
                    text="Account successfully linked! You can now close this window.",
                    status=200,
                )

            except NotImplementedError as e:
                logger.error(f"OAuth feature not yet implemented: {e}")
                return web.Response(
                    text="OAuth linking is not yet fully configured. Please contact support.",
                    status=503,
                )

        except Exception as e:
            logger.error(f"Error in OAuth callback: {e}", exc_info=True)
            return web.Response(
                text="An error occurred during authorization. Please try again.",
                status=500,
            )

    async def _exchange_code_for_token(self, code: str) -> str:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            str: Access token

        Note:
            TODO: Implement token exchange with PrizePicks backend
        """
        # TODO: Confirm token exchange endpoint with PrizePicks backend team
        # Should POST to PrizePicks token endpoint
        # Example structure:
        # POST /auth/token
        # {
        #   "code": code,
        #   "client_id": self.oauth_client_id,
        #   "client_secret": self.oauth_client_secret,
        #   "redirect_uri": self.oauth_redirect_uri,
        #   "grant_type": "authorization_code"
        # }
        raise NotImplementedError("Token exchange not yet implemented")

    async def _get_prizepicks_user_id(self, access_token: str) -> str:
        """
        Get PrizePicks user ID from access token.

        Args:
            access_token: OAuth access token

        Returns:
            str: PrizePicks user ID

        Note:
            TODO: Implement user info retrieval from PrizePicks backend
        """
        # TODO: Confirm user info endpoint with PrizePicks backend team
        # Should GET /auth/me with Bearer token
        raise NotImplementedError("User ID retrieval not yet implemented")


async def setup(bot: commands.Bot) -> None:
    """Load the cog."""
    await bot.add_cog(AccountLinkingCog(bot))
