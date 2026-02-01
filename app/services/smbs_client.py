"""
SMBS (Seoul Money Brokerage Services) Exchange Rate Client

Fetches 최초고시환율 (initial announced exchange rate) from smbs.biz.
Updated once daily in the morning.

On weekends/holidays: fetches the most recent business day's rate.
"""

import asyncio
import random
import re
import aiohttp
from typing import Dict, Optional
from datetime import datetime, timezone, timedelta, date
from app.utils.logger import app_logger as logger


KST = timezone(timedelta(hours=9))

# Korean public holidays - update annually
KR_HOLIDAYS = {
    # 2025
    date(2025, 1, 1), date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
    date(2025, 3, 1), date(2025, 5, 5), date(2025, 5, 6), date(2025, 6, 6),
    date(2025, 8, 15), date(2025, 10, 3), date(2025, 10, 6), date(2025, 10, 7),
    date(2025, 10, 8), date(2025, 10, 9), date(2025, 12, 25),
    # 2026
    date(2026, 1, 1), date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),
    date(2026, 3, 2), date(2026, 5, 5), date(2026, 5, 24), date(2026, 6, 6),
    date(2026, 8, 17), date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 26),
    date(2026, 10, 3), date(2026, 10, 9), date(2026, 12, 25),
    # 2027
    date(2027, 1, 1), date(2027, 2, 5), date(2027, 2, 6), date(2027, 2, 7),
    date(2027, 2, 8), date(2027, 3, 1), date(2027, 5, 5), date(2027, 5, 13),
    date(2027, 6, 7), date(2027, 8, 16), date(2027, 10, 3), date(2027, 10, 4),
    date(2027, 10, 14), date(2027, 10, 15), date(2027, 10, 16),
    date(2027, 12, 25),
}


class SMBSClient:
    """
    Fetches USD/KRW exchange rate from Seoul Foreign Exchange Brokerage.

    Endpoint: http://smbs.biz/Flash/TodayExRate_flash.jsp?tr_date=YYYY-MM-DD
    Returns plain text with key=value pairs separated by &
    Example: ...&USD=1,427.00&...

    Schedule:
    - Checks at startup
    - Re-checks every 30 minutes from 08:00~10:00 KST (rate announced ~09:00)
    - Once fetched, stops until next day
    """

    BASE_URL = "http://smbs.biz/Flash/TodayExRate_flash.jsp"

    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    ]

    POLL_INTERVAL = 1800      # 30 minutes
    POLL_START_HOUR = 8
    POLL_END_HOUR = 10
    SLEEP_CHECK_INTERVAL = 60

    def __init__(self):
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict = {
            'rate': None,
            'date': None,
            'last_updated': None
        }
        self._today_fetched: Optional[str] = None

    @staticmethod
    def _is_business_day(d: date) -> bool:
        """Check if a date is a Korean business day (not weekend, not holiday)."""
        return d.weekday() < 5 and d not in KR_HOLIDAYS

    @staticmethod
    def _last_business_day(from_date: date) -> date:
        """Find the most recent business day on or before from_date."""
        d = from_date
        for _ in range(10):  # max 10 days back
            if SMBSClient._is_business_day(d):
                return d
            d -= timedelta(days=1)
        return from_date  # fallback

    @property
    def cached_data(self) -> Dict:
        return dict(self._cache)

    async def start(self):
        """Start the daily fetch loop"""
        self.running = True
        self.session = aiohttp.ClientSession()
        logger.info("[SMBS] Starting SMBS exchange rate client")

        try:
            # Initial fetch (works for weekends too - gets last business day)
            try:
                if await self._fetch_rate():
                    today_str = datetime.now(KST).strftime('%Y-%m-%d')
                    self._today_fetched = today_str
                    logger.info(f"[SMBS] Initial rate: {self._cache['rate']} KRW (date: {self._cache['date']})")
            except Exception as e:
                logger.error(f"[SMBS] Initial fetch error: {e}")

            while self.running:
                now_kst = datetime.now(KST)
                today_str = now_kst.strftime('%Y-%m-%d')

                # Already fetched today
                if self._today_fetched == today_str:
                    tomorrow = now_kst + timedelta(days=1)
                    next_check = tomorrow.replace(hour=self.POLL_START_HOUR, minute=0, second=0, microsecond=0)
                    wait_seconds = (next_check - now_kst).total_seconds()
                    logger.info(f"[SMBS] Rate available. Next check at {next_check.strftime('%Y-%m-%d %H:%M KST')}")
                    await self._sleep_until(wait_seconds)
                    continue

                # Non-business day: fetch last business day's rate immediately
                if not self._is_business_day(now_kst.date()):
                    try:
                        if await self._fetch_rate():
                            self._today_fetched = today_str
                            logger.info(f"[SMBS] Non-business day rate: {self._cache['rate']} KRW (from {self._cache['date']})")
                            continue
                    except Exception as e:
                        logger.error(f"[SMBS] Weekend fetch error: {e}")
                    await asyncio.sleep(3600)  # retry in 1h on failure
                    continue

                # Business day: wait for poll window
                if now_kst.hour < self.POLL_START_HOUR:
                    target = now_kst.replace(hour=self.POLL_START_HOUR, minute=0, second=0, microsecond=0)
                    wait_seconds = (target - now_kst).total_seconds()
                    await self._sleep_until(wait_seconds)
                    continue

                # Within poll window or after - try fetching
                try:
                    success = await self._fetch_rate()
                    if success and self._cache.get('rate'):
                        self._today_fetched = today_str
                        logger.info(f"[SMBS] Today's rate confirmed: {self._cache['rate']} KRW")
                        continue
                except Exception as e:
                    logger.error(f"[SMBS] Fetch error: {e}")

                jitter = random.uniform(-60, 60)
                await asyncio.sleep(self.POLL_INTERVAL + jitter)

        finally:
            if self.session:
                await self.session.close()

    async def _sleep_until(self, seconds: float):
        remaining = seconds
        while remaining > 0 and self.running:
            sleep_time = min(remaining, self.SLEEP_CHECK_INTERVAL)
            await asyncio.sleep(sleep_time)
            remaining -= sleep_time

    async def stop(self):
        self.running = False
        logger.info("[SMBS] Stopped")

    async def _fetch_rate(self) -> bool:
        """Fetch USD/KRW rate from SMBS for the latest business day."""
        now_kst = datetime.now(KST)
        target_date = self._last_business_day(now_kst.date())
        target_str = target_date.isoformat()

        headers = {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html, */*',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8',
            'Referer': 'http://smbs.biz/ExRate/TodayExRate.jsp',
            'Connection': 'keep-alive',
        }

        try:
            url = f"{self.BASE_URL}?tr_date={target_str}"
            async with self.session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"[SMBS] HTTP {resp.status}")
                    return False

                # Response is plain text in EUC-KR, but rate data is ASCII
                text = await resp.text(encoding='euc-kr', errors='replace')

                # Parse USD rate from query-string-style response
                # Format: ...&USD=1,427.00&...
                usd_match = re.search(r'USD=([\d,]+\.?\d*)', text)
                if not usd_match:
                    logger.warning("[SMBS] USD rate not found in response")
                    return False

                rate_str = usd_match.group(1).replace(',', '')
                rate = float(rate_str)

                if rate <= 0:
                    return False

                self._cache['rate'] = rate
                self._cache['date'] = target_str
                self._cache['last_updated'] = datetime.now(KST).isoformat()

                logger.info(f"[SMBS] USD/KRW = {rate} ({target_str})")
                return True

        except asyncio.TimeoutError:
            logger.warning("[SMBS] Request timeout")
            return False
        except Exception as e:
            logger.error(f"[SMBS] Error: {e}")
            return False


# Global instance
_smbs_client: Optional[SMBSClient] = None


def get_smbs_client() -> SMBSClient:
    global _smbs_client
    if _smbs_client is None:
        _smbs_client = SMBSClient()
    return _smbs_client
