"""
Deeplink Generation Utility.

Generates universal links for iOS, Android, and web fallback URLs.
Includes entry pre-population and referral attribution.
"""

import hashlib
import hmac
import logging
import os
from typing import Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class DeeplinkGenerator:
    """Utility for generating deeplinks and universal links."""

    def __init__(self):
        """Initialize deeplink generator."""
        self.ios_app_id = os.getenv("PRIZEPICKS_IOS_APP_ID", "com.playright.prizepicks")
        self.android_package = os.getenv(
            "PRIZEPICKS_ANDROID_PACKAGE",
            "com.playright.prizepicks",
        )
        self.web_domain = os.getenv("PRIZEPICKS_WEB_DOMAIN", "app.prizepicks.com")
        self.signing_key = os.getenv("DEEPLINK_SIGNING_KEY", "")

    def generate_entry_link(
        self,
        entry_id: str,
        discord_user_id: int,
        source: str = "discord",
    ) -> str:
        """
        Generate deeplink to open/create entry in PrizePicks.

        Args:
            entry_id: PrizePicks entry ID
            discord_user_id: Discord user ID (for attribution)
            source: Traffic source identifier

        Returns:
            str: Universal/deeplink URL
        """
        try:
            # Build parameters
            params = {
                "entry_id": entry_id,
                "source": source,
                "referrer": str(discord_user_id),
            }

            # Generate links
            self._build_deeplink(entry_id, params)
            self._build_web_url(entry_id, params)

            # Return appropriate link based on user agent
            # For Discord, we'll return a universal link that works on all platforms
            return self._build_universal_link(entry_id, params)

        except Exception as e:
            logger.error(f"Error generating deeplink: {e}")
            return f"https://{self.web_domain}/entry/{entry_id}"

    def generate_account_link(self, discord_user_id: int) -> str:
        """
        Generate deeplink to account linking flow.

        Args:
            discord_user_id: Discord user ID

        Returns:
            str: Link to account linking flow
        """
        try:
            params = {
                "discord_user_id": str(discord_user_id),
                "source": "discord",
            }

            return self._build_universal_link("account/link", params)

        except Exception as e:
            logger.error(f"Error generating account link: {e}")
            return f"https://{self.web_domain}/account/link"

    def _build_deeplink(self, path: str, params: dict) -> str:
        """
        Build app deeplink (prizepicks://).

        Args:
            path: Path within app
            params: Query parameters

        Returns:
            str: Deeplink URL
        """
        query_string = urlencode(params)
        return f"prizepicks://{path}?{query_string}"

    def _build_universal_link(self, path: str, params: dict) -> str:
        """
        Build universal link compatible with iOS and Android.

        Universal links:
        - https://app.prizepicks.com/entry/{id}?params
        - Automatically opens in app if installed
        - Falls back to web if not installed

        Args:
            path: Path within app
            params: Query parameters

        Returns:
            str: Universal link URL
        """
        query_string = urlencode(params)
        url = f"https://{self.web_domain}/{path}"

        if query_string:
            url += f"?{query_string}"

        return url

    def _build_web_url(self, path: str, params: dict) -> str:
        """
        Build web fallback URL.

        Args:
            path: Path within app
            params: Query parameters

        Returns:
            str: Web URL
        """
        query_string = urlencode(params)
        url = f"https://{self.web_domain}/{path}"

        if query_string:
            url += f"?{query_string}"

        return url

    def _sign_url(self, url: str) -> str:
        """
        Sign URL for security (optional).

        Args:
            url: URL to sign

        Returns:
            str: Signed URL with signature parameter
        """
        if not self.signing_key:
            return url

        try:
            signature = hmac.new(
                self.signing_key.encode(),
                url.encode(),
                hashlib.sha256,
            ).hexdigest()

            separator = "&" if "?" in url else "?"
            return f"{url}{separator}sig={signature}"

        except Exception as e:
            logger.warning(f"Error signing URL: {e}")
            return url

    # iOS App Links (apple-app-site-association)

    def generate_ios_app_link(
        self,
        entry_id: str,
        discord_user_id: int,
    ) -> str:
        """
        Generate iOS universal link.

        Requires apple-app-site-association file:
        {
            "applinks": {
                "apps": [],
                "details": [{
                    "appID": "{team_id}.{app_id}",
                    "paths": ["/entry/*"]
                }]
            }
        }

        Args:
            entry_id: Entry ID
            discord_user_id: Discord user ID

        Returns:
            str: iOS universal link
        """
        params = {
            "source": "discord",
            "referrer": str(discord_user_id),
        }

        query_string = urlencode(params)
        url = f"https://{self.web_domain}/entry/{entry_id}"

        if query_string:
            url += f"?{query_string}"

        return url

    # Android App Links (assetlinks.json)

    def generate_android_app_link(
        self,
        entry_id: str,
        discord_user_id: int,
    ) -> str:
        """
        Generate Android universal link.

        Requires assetlinks.json:
        [{
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": "com.playright.prizepicks",
                "sha256_cert_fingerprints": ["..."]
            }
        }]

        Args:
            entry_id: Entry ID
            discord_user_id: Discord user ID

        Returns:
            str: Android universal link
        """
        params = {
            "source": "discord",
            "referrer": str(discord_user_id),
        }

        query_string = urlencode(params)
        url = f"https://{self.web_domain}/entry/{entry_id}"

        if query_string:
            url += f"?{query_string}"

        return url


class DeeplinkParser:
    """Utility for parsing deeplinks and extracting parameters."""

    @staticmethod
    def parse_entry_id_from_url(url: str) -> Optional[str]:
        """
        Extract entry ID from PrizePicks URL.

        Args:
            url: PrizePicks URL

        Returns:
            str: Entry ID or None
        """
        import re

        pattern = r"(?:app\.)?prizepicks\.com/entry/([a-zA-Z0-9-_]+)"
        match = re.search(pattern, url)

        return match.group(1) if match else None

    @staticmethod
    def extract_parameters(url: str) -> dict:
        """
        Extract query parameters from deeplink.

        Args:
            url: Deeplink URL

        Returns:
            dict: Query parameters
        """
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Flatten lists (parse_qs returns lists)
        return {k: v[0] if len(v) == 1 else v for k, v in params.items()}
