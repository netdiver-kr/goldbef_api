"""
EODHD Economic Events Client

Fetches today's economic events from EODHD Economic Events API.
Polls every 30 minutes. Caches in memory (refreshes daily).
"""
import asyncio
import aiohttp
from datetime import datetime, timezone, timedelta, date
from typing import Dict, Optional
from app.config import get_settings
from app.utils.logger import app_logger as logger


class EodhdEventsClient:
    API_URL = "https://eodhd.com/api/economic-events"
    POLL_INTERVAL = 1800  # 30 minutes
    COUNTRIES = ["US", "KR", "JP", "CN", "EU"]

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.EODHD_API_KEY
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict = {'events': [], 'date': None, 'last_updated': None}

    @property
    def cached_data(self) -> Dict:
        return dict(self._cache)

    async def start(self):
        self.running = True
        self.session = aiohttp.ClientSession()
        logger.info("[EodhdEvents] Starting economic events client")

        try:
            await self._fetch()
            while self.running:
                await asyncio.sleep(self.POLL_INTERVAL)
                if not self.running:
                    break
                await self._fetch()
        except asyncio.CancelledError:
            pass
        finally:
            if self.session:
                await self.session.close()

    async def stop(self):
        self.running = False

    async def _fetch(self):
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        all_events = []
        for country in self.COUNTRIES:
            try:
                params = {
                    'api_token': self.api_key,
                    'from': today,
                    'to': tomorrow,
                    'country': country,
                    'fmt': 'json',
                }
                async with self.session.get(
                    self.API_URL, params=params,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"[EodhdEvents] HTTP {resp.status} for {country}")
                        continue
                    data = await resp.json()
                    if isinstance(data, list):
                        for event in data:
                            all_events.append({
                                'date': event.get('date', ''),
                                'country': event.get('country', country),
                                'event': event.get('event', ''),
                                'actual': event.get('actual'),
                                'forecast': event.get('estimate') or event.get('forecast'),
                                'previous': event.get('previous'),
                                'impact': event.get('impact', ''),
                            })
            except Exception as e:
                logger.warning(f"[EodhdEvents] Failed for {country}: {e}")

        # Sort by date/time
        all_events.sort(key=lambda x: x.get('date', ''))

        self._cache = {
            'events': all_events,
            'date': today,
            'last_updated': datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"[EodhdEvents] Fetched {len(all_events)} events for {today}")


# Singleton
_events_client: Optional[EodhdEventsClient] = None


def get_eodhd_events_client() -> EodhdEventsClient:
    global _events_client
    if _events_client is None:
        _events_client = EodhdEventsClient()
    return _events_client
