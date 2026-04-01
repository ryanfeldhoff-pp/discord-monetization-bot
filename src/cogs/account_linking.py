"""
Discord â PrizePicks Account Linking Cog.

Handles OAuth 2.0 authentication flow, account linking/unlinking, and role management.
"""

import logging
import os
import secrets
from typing import Optional

import discord
from aiohttp import web
from discord.ext import commands

from src.models.database import AccountLink, Database
from src.services.prizepicks_api import PrizepicksAPIClient

logger = logging.getLogger(__name__)


class LinkState:
    """Represents the state of a link operation."""

    def __init__(self, state: str, discord_user_id: int):
        """Initialize link state."""
        self.state = state
        self.discord_user_id = discord_user_id


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
                    await ctx.respond(
                        "Your account is already linked to PrizePicks!",
                        ephemeral=True,
                    )
                    return

            # Generate state for CSRF protection
            state = secrets.token_urlsafe(32)
            self.oauth_states[state] = LinkState(state, ctx.author.id)

            # Generate OAuth URL
            oauth_url = self._generate_oauth_url(state)

            # Send ephemeral message with auth URL
            embed = discord.Embed(
                title="Link Your PrizePicks Account",
                description="Click the button below to authorize and link your account.",
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="What happens next?",
                value="1. Click the link button\n2. Authorize on PrizePicks\n3. Return to Discord\n4. You'll be assigned the 'Linked' role",
                inline=False,
            )

            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label="Link Account",
                    url=oauth_url,
                    style=discord.ButtonStyle.link,
                )
            )

            await ctx.respond(embed=embed, view=view, ephemeral=True)
            logger.info(f"Link flow initiated for user {ctx.author.id}")

        except Exception as e:
            logger.error(f"Error in link command: {e}", exc_info=True)
            await ctx.respond(
                "An error occurred while initiating the link process. Please try again.",
                ephemeral=True,
            )

    @commands.slash_command(
        name="unlink",
        description="Unlink your Discord account from PrizePicks",
    )
    async def unlink_account(self, ctx: discord.ApplicationContext) -> None:
        """
        Unlink Discord account from PrizePicks.

        Args:
            ctx: Discord application context
        """
        try:
            if not self.db:
                await ctx.respond(
                    "Database not available. Please try again.",
                    ephemeral=True,
                )
                return

            # Check if linked
            account_link = await self.db.get_account_link(ctx.author.id)
            if not account_link or account_link.status != "linked":
                await ctx.respond(
                    "Your account is not linked to PrizePicks.",
                    ephemeral=True,
                )
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

            await ctx.respond(
                "Your account has been successfully unlinked.",
                ephemeral=True,
            )
            logger.info(f"Account unlinked for user {ctx.author.id}")

        except Exception as e:
            logger.error(f"Error in unlink command: {e}", exc_info=True)
            await ctx.respond(
                "An error occurred while unlinking your account. Please try again.",
                ephemeral=True,
            )

    @commands.slash_command(
        name="linkstatus",
        description="Check your PrizePicks account link status",
    )
    async def link_status(self, ctx: discord.ApplicationContext) -> None:
        """
        Display current link status.

        Args:
            ctx: Discord application context
        """
        try:
            if not self.db:
                await ctx.respond(
                    "Database not available. Please try again.",
                    ephemeral=True,
                )
                return

            account_link = await self.db.get_account_link(ctx.author.id)

            embed = discord.Embed(
                title="Account Link Status",
                color=discord.Color.green() if account_link else discord.Color.red(),
            )

            if account_link and account_link.status == "linked":
                embed.description = "Your account is linked!"
                embed.add_field(
                    name="Linked At",
                    value=account_link.linked_at.isoformat(),
                    inline=False,
                )
                embed.add_field(
                    name="PrizePicks User ID",
                    value=account_link.prizepicks_user_id,
                    inline=False,
                )
                unlink_button = discord.ui.Button(
                    label="Unlink Account",
                    style=discord.ButtonStyle.red,
                    custom_id="unlink_confirm",
                )
                view = discord.ui.View()
                view.add_item(unlink_button)
                await ctx.respond(embed=embed, view=view, ephemeral=True)
            else:
                embed.description = "Your account is not linked to PrizePicks."
                embed.add_field(
                    name="Next Steps",
                    value="Use `/link` to start the linking process.",
                    inline=False,
                )
                await ctx.respond(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in linkstatus command: {e}", exc_info=True)
            await ctx.respond(
                "An error occurred while checking your link status.",
                ephemeral=True,
            )

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

            # Verify state parameter (CSRF protection)
            if state not in self.oauth_states:
                logger.warning(f"Invalid state parameter: {state}")
                return web.Response(
                    text="Invalid state parameter",
                    status=400,
                )

            link_state = self.oauth_states.pop(state)

            # TODO: Exchange code for access token with PrizePicks backend
            # This should call PrizePicks API to exchange code for token
            # and get the user's PrizePicks ID
            access_token = await self._exchange_code_for_token(code)
            prizepicks_user_id = await self._get_prizepicks_user_id(access_token)

            # Store in database
            if self.db:
                await self.db.create_account_link(
                    discord_user_id=link_state.discord_user_id,
                    prizepicks_user_id=prizepicks_user_id,
                    status="linked",
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

        except Exception as e:
            logger.error(f"Error in OAuth callback: {e}", exc_info=True)
            return web.Response(
                text="An error occurred during authorization",
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
        #    "redirect_uri": self.oauth_redirect_uri,
        #    "grant_type": "authorization_code"
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


dync def setup(bot: commands.Bot) -> None:
    """Load the cog."""
    await bot.add_cog(AccountLinkingCog(bot))
