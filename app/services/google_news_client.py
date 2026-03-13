"""
Google News RSS Client (Korean)

Fetches Korean-language financial news headlines from Google News RSS.
Polls every 10 minutes using rotating queries for diverse coverage.
Merges results across queries, deduplicates by title, caches up to 40 headlines.
"""
import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from html import unescape
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.utils.logger import app_logger as logger


class GoogleNewsClient:
    RSS_URL = "https://news.google.com/rss/search"
    POLL_INTERVAL = 600  # 10 minutes
    QUERIES = [
        "금값 OR 금시세 OR 금 가격",
        "환율 OR 원달러 OR 달러 환율",
        "귀금속 OR 은값 OR 백금",
        "원자재 OR 유가 OR 국제유가",
        "코스피 OR 코스닥 OR 주식시장",
    ]
    MAX_HEADLINES = 40

    def __init__(self):
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict = {'headlines': [], 'last_updated': None}
        self._query_index = 0

    @property
    def cached_data(self) -> Dict:
        return dict(self._cache)

    async def start(self):
        self.running = True
        self.session = aiohttp.ClientSession()
        logger.info("[GoogleNews] Starting Korean news RSS client")

        try:
            # Initial fetch: all queries
            await self._fetch_all()
            while self.running:
                await asyncio.sleep(self.POLL_INTERVAL)
                if not self.running:
                    break
                # Rotate: fetch 2 queries per cycle
                await self._fetch_rotating()
        except asyncio.CancelledError:
            pass
        finally:
            if self.session:
                await self.session.close()

    async def stop(self):
        self.running = False

    async def _fetch_all(self):
        """Fetch all queries at startup for maximum coverage."""
        all_articles = []
        seen_titles = set()
        for query in self.QUERIES:
            articles = await self._fetch_query(query)
            for a in articles:
                if a['title'] not in seen_titles:
                    seen_titles.add(a['title'])
                    all_articles.append(a)
        self._update_cache(all_articles)

    async def _fetch_rotating(self):
        """Fetch 2 queries per cycle, rotating through all queries."""
        new_articles = []
        seen_titles = set()
        for _ in range(2):
            query = self.QUERIES[self._query_index % len(self.QUERIES)]
            self._query_index += 1
            articles = await self._fetch_query(query)
            for a in articles:
                if a['title'] not in seen_titles:
                    seen_titles.add(a['title'])
                    new_articles.append(a)

        # Merge with existing cache, deduplicate
        existing = {a['title']: a for a in self._cache.get('headlines', [])}
        for a in new_articles:
            existing[a['title']] = a  # New articles override old ones

        merged = list(existing.values())
        self._update_cache(merged)

    async def _fetch_query(self, query: str) -> List[Dict]:
        """Fetch a single RSS query and return parsed articles."""
        try:
            params = {
                'q': query,
                'hl': 'ko',
                'gl': 'KR',
                'ceid': 'KR:ko',
            }
            async with self.session.get(
                self.RSS_URL, params=params,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"[GoogleNews] HTTP {resp.status} for query '{query}'")
                    return []
                text = await resp.text()

            root = ET.fromstring(text)
            channel = root.find('channel')
            if channel is None:
                return []

            articles = []
            for item in channel.findall('item'):
                title_el = item.find('title')
                link_el = item.find('link')
                pubdate_el = item.find('pubDate')
                source_el = item.find('source')

                if title_el is None or not title_el.text:
                    continue

                title = unescape(title_el.text.strip())
                source = source_el.text.strip() if source_el is not None and source_el.text else ''

                articles.append({
                    'title': title,
                    'source': source,
                    'date': pubdate_el.text.strip() if pubdate_el is not None and pubdate_el.text else '',
                    'link': link_el.text.strip() if link_el is not None and link_el.text else '',
                })

            return articles

        except Exception as e:
            logger.warning(f"[GoogleNews] Failed for query '{query}': {e}")
            return []

    def _update_cache(self, articles: List[Dict]):
        """Sort by date descending, trim to max, update cache."""
        # Sort by date descending (RFC 2822 format sorts correctly as strings)
        articles.sort(key=lambda x: x.get('date', ''), reverse=True)
        articles = articles[:self.MAX_HEADLINES]

        # Don't replace good cache with fewer results
        if len(articles) < 5 and len(self._cache.get('headlines', [])) >= 5:
            logger.warning(f"[GoogleNews] Only {len(articles)} results, keeping previous cache")
            return

        self._cache = {
            'headlines': articles,
            'last_updated': datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"[GoogleNews] Cache updated: {len(articles)} headlines")


# Singleton
_news_client: Optional[GoogleNewsClient] = None


def get_google_news_client() -> GoogleNewsClient:
    global _news_client
    if _news_client is None:
        _news_client = GoogleNewsClient()
    return _news_client
