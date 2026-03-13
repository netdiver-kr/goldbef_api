"""
EODHD News Client

Fetches commodity/forex news headlines from EODHD News API.
Polls every 10 minutes. Caches last 20 headlines in memory.
"""
import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import Dict, Optional
from app.config import get_settings
from app.utils.logger import app_logger as logger


class EodhdNewsClient:
    API_URL = "https://eodhd.com/api/news"
    POLL_INTERVAL = 600  # 10 minutes
    TAGS = ['gold', 'commodity', 'forex', 'precious metals']
    MAX_HEADLINES = 20

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.EODHD_API_KEY
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict = {'headlines': [], 'last_updated': None}

    @property
    def cached_data(self) -> Dict:
        return dict(self._cache)

    async def start(self):
        self.running = True
        self.session = aiohttp.ClientSession()
        logger.info("[EodhdNews] Starting news client")

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
        seen_titles = set()
        all_articles = []

        for tag in self.TAGS:
            try:
                params = {
                    'api_token': self.api_key,
                    't': tag,
                    'limit': 10,
                    'fmt': 'json',
                }
                async with self.session.get(
                    self.API_URL, params=params,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"[EodhdNews] HTTP {resp.status} for tag '{tag}'")
                        continue
                    data = await resp.json()
                    if isinstance(data, list):
                        for article in data:
                            title = article.get('title', '')
                            if title and title not in seen_titles:
                                seen_titles.add(title)
                                sentiment = article.get('sentiment', {})
                                all_articles.append({
                                    'title': title,
                                    'date': article.get('date', ''),
                                    'link': article.get('link', ''),
                                    'sentiment': sentiment.get('polarity', 0) if isinstance(sentiment, dict) else 0,
                                })
            except Exception as e:
                logger.warning(f"[EodhdNews] Failed for tag '{tag}': {e}")

        # Sort by date descending, keep top N
        all_articles.sort(key=lambda x: x.get('date', ''), reverse=True)
        all_articles = all_articles[:self.MAX_HEADLINES]

        self._cache = {
            'headlines': all_articles,
            'last_updated': datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"[EodhdNews] Fetched {len(all_articles)} headlines")


# Singleton
_news_client: Optional[EodhdNewsClient] = None


def get_eodhd_news_client() -> EodhdNewsClient:
    global _news_client
    if _news_client is None:
        _news_client = EodhdNewsClient()
    return _news_client
