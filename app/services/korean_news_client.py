"""
Korean Financial News Client

Scrapes headlines from:
  1. 연합인포맥스 (news.einfomax.co.kr) - professional financial news
  2. 네이버 경제뉴스 (news.naver.com/section/101) - general economy headlines

Polls every 10 minutes, caches up to 40 headlines.
Same interface as GoogleNewsClient for drop-in replacement.
"""
import asyncio
import aiohttp
import re
from html import unescape
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.utils.logger import app_logger as logger


class KoreanNewsClient:
    EINFOMAX_URL = "https://news.einfomax.co.kr/news/articleList.html?view_type=sm"
    NAVER_ECON_URL = "https://news.naver.com/section/101"
    POLL_INTERVAL = 600  # 10 minutes
    MAX_HEADLINES = 40

    def __init__(self):
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict = {'headlines': [], 'last_updated': None}

    @property
    def cached_data(self) -> Dict:
        return dict(self._cache)

    async def start(self):
        self.running = True
        self.session = aiohttp.ClientSession(
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        logger.info("[KoreanNews] Starting news scraper (einfomax + naver)")

        try:
            await self._fetch_all()
            while self.running:
                await asyncio.sleep(self.POLL_INTERVAL)
                if not self.running:
                    break
                await self._fetch_all()
        except asyncio.CancelledError:
            pass
        finally:
            if self.session:
                await self.session.close()

    async def stop(self):
        self.running = False

    async def _fetch_all(self):
        """Fetch from both sources concurrently."""
        results = await asyncio.gather(
            self._fetch_einfomax(),
            self._fetch_naver(),
            return_exceptions=True,
        )

        all_articles = []
        seen_titles = set()

        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"[KoreanNews] Source fetch error: {result}")
                continue
            for article in result:
                # Deduplicate by normalized title
                key = re.sub(r'\s+', '', article['title'])
                if key not in seen_titles:
                    seen_titles.add(key)
                    all_articles.append(article)

        self._update_cache(all_articles)

    async def _fetch_einfomax(self) -> List[Dict]:
        """Scrape einfomax article list page."""
        try:
            async with self.session.get(
                self.EINFOMAX_URL,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"[KoreanNews] einfomax HTTP {resp.status}")
                    return []
                html = await resp.text()

            articles = []
            # Pattern: <h4 class="titles"><a href="/news/articleView.html?idxno=XXXXX">TITLE</a></h4>
            pattern = re.compile(
                r'<h4\s+class="titles">\s*<a\s+href="(/news/articleView\.html\?idxno=\d+)"[^>]*>([^<]+)</a>',
                re.DOTALL
            )
            for match in pattern.finditer(html):
                path, title = match.group(1), match.group(2)
                title = unescape(title.strip())
                if not title:
                    continue
                articles.append({
                    'title': title,
                    'source': '연합인포맥스',
                    'link': f'https://news.einfomax.co.kr{path}',
                    'date': '',
                })

            logger.info(f"[KoreanNews] einfomax: {len(articles)} headlines")
            return articles

        except Exception as e:
            logger.warning(f"[KoreanNews] einfomax fetch failed: {e}")
            return []

    async def _fetch_naver(self) -> List[Dict]:
        """Scrape Naver economy news section."""
        try:
            async with self.session.get(
                self.NAVER_ECON_URL,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"[KoreanNews] naver HTTP {resp.status}")
                    return []
                html = await resp.text()

            articles = []
            # Pattern: <a href="URL" class="sa_text_title ...">...<strong class="sa_text_strong">TITLE</strong>
            pattern = re.compile(
                r'<a\s+href="(https://n\.news\.naver\.com/mnews/article/[^"]+)"\s+class="sa_text_title[^"]*"[^>]*>'
                r'[^<]*<strong\s+class="sa_text_strong">([^<]+)</strong>',
                re.DOTALL
            )
            for match in pattern.finditer(html):
                link, title = match.group(1), match.group(2)
                title = unescape(title.strip())
                if not title:
                    continue
                articles.append({
                    'title': title,
                    'source': '네이버경제',
                    'link': link,
                    'date': '',
                })

            logger.info(f"[KoreanNews] naver: {len(articles)} headlines")
            return articles

        except Exception as e:
            logger.warning(f"[KoreanNews] naver fetch failed: {e}")
            return []

    def _update_cache(self, articles: List[Dict]):
        """Update cache, keeping existing if new results are too few."""
        articles = articles[:self.MAX_HEADLINES]

        if len(articles) < 3 and len(self._cache.get('headlines', [])) >= 3:
            logger.warning(f"[KoreanNews] Only {len(articles)} results, keeping previous cache")
            return

        self._cache = {
            'headlines': articles,
            'last_updated': datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"[KoreanNews] Cache updated: {len(articles)} headlines")


# Singleton
_news_client: Optional[KoreanNewsClient] = None


def get_korean_news_client() -> KoreanNewsClient:
    global _news_client
    if _news_client is None:
        _news_client = KoreanNewsClient()
    return _news_client
