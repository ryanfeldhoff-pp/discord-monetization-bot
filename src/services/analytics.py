"""
Analytics Event Service.

Emits events to analytics pipeline with batching and fallback to file logging.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

# Batch size and flush interval
BATCH_SIZE = 10
FLUSH_INTERVAL = 30  # seconds


class AnalyticsService:
    """Service for emitting analytics events."""

    def __init__(self, config: dict):
        """
        Initialize analytics service.

        Args:
            config: Configuration dict with keys:
                - provider: analytics backend ("webhook", "posthog", "mixpanel")
                - webhook_url: for webhook provider
                - api_key: for PostHog/Mixpanel
        """
        self.provider = config.get("provider", "webhook")
        self.webhook_url = config.get("webhook_url")
        self.api_key = config.get("api_key")
        self.session: Optional[aiohttp.ClientSession] = None
        self.event_queue: list[dict] = []
        self.flush_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the analytics service."""
        if self._running:
            return

        self._running = True
        self.session = aiohttp.ClientSession()
        self.flush_task = asyncio.create_task(self._flush_loop())
        logger.info(f"Analytics service started with provider: {self.provider}")

    async def stop(self) -> None:
        """Stop the analytics service."""
        if not self._running:
            return

        self._running = False

        # Flush remaining events
        await self.flush()

        # Cancel flush task
        if self.flush_task:
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass

        # Close session
        if self.session:
            await self.session.close()

        logger.info("Analytics service stopped")

    async def emit_event(self, event_name: str, properties: dict) -> None:
        """
        Emit an analytics event.

        Args:
            event_name: Name of the event
            properties: Event properties/metadata
        """
        if not self._running:
            await self.start()

        event = {
            "event": event_name,
            "timestamp": datetime.utcnow().isoformat(),
            "properties": properties,
        }

        self.event_queue.append(event)

        # Flush if batch size reached
        if len(self.event_queue) >= BATCH_SIZE:
            await self.flush()

    async def flush(self) -> None:
        """Flush all queued events."""
        if not self.event_queue:
            return

        events = self.event_queue.copy()
        self.event_queue.clear()

        success = await self._send_events(events)

        if not success:
            # Fallback to file logging
            await self._log_to_file(events)

    async def _send_events(self, events: list[dict]) -> bool:
        """
        Send events to analytics backend.

        Args:
            events: List of events to send

        Returns:
            bool: Success status
        """
        try:
            if self.provider == "webhook":
                return await self._send_webhook(events)
            elif self.provider == "posthog":
                return await self._send_posthog(events)
            elif self.provider == "mixpanel":
                return await self._send_mixpanel(events)
            else:
                logger.warning(f"Unknown analytics provider: {self.provider}")
                return False

        except Exception as e:
            logger.error(f"Error sending analytics events: {e}", exc_info=True)
            return False

    async def _send_webhook(self, events: list[dict]) -> bool:
        """
        Send events via webhook.

        Args:
            events: List of events

        Returns:
            bool: Success status
        """
        if not self.webhook_url or not self.session:
            logger.warning("Webhook URL not configured")
            return False

        try:
            payload = {
                "events": events,
                "sent_at": datetime.utcnow().isoformat(),
            }

            async with self.session.post(
                self.webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status >= 400:
                    logger.error(f"Webhook error: HTTP {response.status}")
                    return False

                return True

        except asyncio.TimeoutError:
            logger.warning("Webhook request timeout")
            return False
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return False

    async def _send_posthog(self, events: list[dict]) -> bool:
        """
        Send events to PostHog.

        Args:
            events: List of events

        Returns:
            bool: Success status

        Note:
            TODO: Implement PostHog integration
            - PostHog API endpoint: https://api.posthog.com/batch
            - Requires API key authentication
            - Format: batch payload with event list
        """
        logger.warning("PostHog provider not yet implemented")
        return False

    async def _send_mixpanel(self, events: list[dict]) -> bool:
        """
        Send events to Mixpanel.

        Args:
            events: List of events

        Returns:
            bool: Success status

        Note:
            TODO: Implement Mixpanel integration
            - Mixpanel API endpoint: https://api.mixpanel.com/track
            - Requires token authentication
            - Format: track events with properties
        """
        logger.warning("Mixpanel provider not yet implemented")
        return False

    async def _log_to_file(self, events: list[dict]) -> None:
        """
        Fallback to file logging when analytics service is unavailable.

        Args:
            events: List of events to log
        """
        try:
            # Create logs directory if needed
            log_dir = Path("logs/analytics")
            log_dir.mkdir(parents=True, exist_ok=True)

            # Append events to file
            log_file = log_dir / "events.jsonl"

            with open(log_file, "a") as f:
                for event in events:
                    f.write(json.dumps(event) + "\n")

            logger.info(f"Logged {len(events)} events to file")

        except Exception as e:
            logger.error(f"Error logging to file: {e}")

    async def _flush_loop(self) -> None:
        """Background task that flushes events periodically."""
        while self._running:
            try:
                await asyncio.sleep(FLUSH_INTERVAL)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")

    async def __aenter__(self) -> "AnalyticsService":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()
