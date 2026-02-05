"""
London Fix Price Client - Metals.dev API

Fetches LBMA fix prices from Metals.dev API.
One API call returns all 7 prices: Gold AM/PM, Silver, Platinum AM/PM, Palladium AM/PM.

Free tier: 100 requests/month
Optimized: ~22 calls/month (skip 2nd fetch if 1st succeeded for same London date)

Schedule (2 slots per UK business day):
- 01:30 KST (16:30 UTC) : primary fetch, right after all London fixes
- 09:30 KST (00:30 UTC) : backup only if primary missed/failed for that London date
- Skips UK weekends and bank holidays
- Skips fetch if data for that London date already cached
- Max 2 retries (30 min apart) per fetch
- Initial fetch at startup for immediate data availability
"""

import asyncio
import aiohttp
from typing import Dict, Optional, Set, Tuple
from datetime import datetime, timezone, timedelta, date
from app.config import get_settings
from app.utils.logger import app_logger as logger


KST = timezone(timedelta(hours=9))

# UK Bank Holidays - update annually
UK_HOLIDAYS: Set[date] = {
    # 2025
    date(2025, 1, 1), date(2025, 4, 18), date(2025, 4, 21),
    date(2025, 5, 5), date(2025, 5, 26), date(2025, 8, 25),
    date(2025, 12, 25), date(2025, 12, 26),
    # 2026
    date(2026, 1, 1), date(2026, 4, 3), date(2026, 4, 6),
    date(2026, 5, 4), date(2026, 5, 25), date(2026, 8, 31),
    date(2026, 12, 25), date(2026, 12, 28),
    # 2027
    date(2027, 1, 1), date(2027, 3, 26), date(2027, 3, 29),
    date(2027, 5, 3), date(2027, 5, 31), date(2027, 8, 30),
    date(2027, 12, 27), date(2027, 12, 28),
}


class LondonFixClient:
    """
    Fetches LBMA fix prices via Metals.dev API.

    ~22 calls/month (1 per business day normally, 2nd slot only if 1st failed).
    Well within 100/month free tier.
    """

    API_URL = "https://api.metals.dev/v1/metal/authority"

    # Metals.dev response key -> internal cache key
    RATE_MAP = {
        'lbma_gold_am': 'gold_am',
        'lbma_gold_pm': 'gold_pm',
        'lbma_silver': 'silver',
        'lbma_platinum_am': 'platinum_am',
        'lbma_platinum_pm': 'platinum_pm',
        'lbma_palladium_am': 'palladium_am',
        'lbma_palladium_pm': 'palladium_pm',
    }

    # Two fetch times per day (UTC hour, minute)
    # 00:30 UTC = 09:30 KST (Korean morning)
    # 16:30 UTC = 01:30 KST (after London PM fix)
    FETCH_SLOTS = [(0, 30), (16, 30)]

    MAX_RETRIES = 2
    RETRY_INTERVAL = 1800  # 30 min
    SLEEP_CHECK = 60

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.METALS_DEV_API_KEY
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict = {
            'gold_am': None, 'gold_pm': None, 'silver': None,
            'platinum_am': None, 'platinum_pm': None,
            'palladium_am': None, 'palladium_pm': None,
            'last_updated': None, 'date': None
        }
        self._last_slot_utc: Optional[datetime] = None
        self._fetched_london_dates: Set[str] = set()  # e.g. {"2026-02-02"}

    @property
    def cached_data(self) -> Dict:
        return dict(self._cache)

    @staticmethod
    def _is_business_day(d: date) -> bool:
        return d.weekday() < 5 and d not in UK_HOLIDAYS

    @staticmethod
    def _london_date_for_slot(utc_date: date, hour: int) -> date:
        """Determine the London Fix business date for a given UTC slot.
        16:30 UTC → same UTC date (PM fix done)
        00:30 UTC → previous UTC date (data from yesterday)
        """
        return utc_date if hour >= 8 else utc_date - timedelta(days=1)

    def _next_slot_wait(self) -> Tuple[float, str, str]:
        """Find seconds until next fetch slot, its description, and London date.
        Returns (wait_seconds, kst_description, london_date_iso).
        Skips slots whose London date is already fetched.
        """
        utc_now = datetime.now(timezone.utc)

        for day_offset in range(10):
            d = utc_now.date() + timedelta(days=day_offset)
            for hour, minute in self.FETCH_SLOTS:
                slot = datetime(d.year, d.month, d.day,
                                hour, minute, 0, tzinfo=timezone.utc)

                # Skip past slots
                if slot <= utc_now:
                    continue

                # Skip already-fetched slot
                if self._last_slot_utc and slot <= self._last_slot_utc:
                    continue

                london_date = self._london_date_for_slot(d, hour)

                if not self._is_business_day(london_date):
                    continue

                london_date_iso = london_date.isoformat()

                # Skip if data for this London date already fetched
                if london_date_iso in self._fetched_london_dates:
                    logger.info(
                        f"[LondonFix] Skipping slot {hour:02d}:{minute:02d} UTC "
                        f"- London date {london_date_iso} already fetched"
                    )
                    continue

                wait = (slot - utc_now).total_seconds()
                kst_str = slot.astimezone(KST).strftime('%m-%d %H:%M KST')
                return (wait, kst_str, london_date_iso)

        return (3600, "fallback 1h", "")

    async def start(self):
        self.running = True
        self.session = aiohttp.ClientSession()
        logger.info("[LondonFix] Starting (Metals.dev, ~22 calls/month, skips if date already fetched)")

        try:
            # Initial fetch for immediate data
            if self.api_key:
                try:
                    await self._fetch()
                except Exception as e:
                    logger.error(f"[LondonFix] Initial fetch error: {e}")
            else:
                logger.warning("[LondonFix] No METALS_DEV_API_KEY configured")

            # Clean old dates on startup (keep only recent 5 days)
            self._cleanup_old_dates()

            while self.running:
                if not self.api_key:
                    await asyncio.sleep(3600)
                    continue

                # Wait for next slot
                wait, info, london_date_iso = self._next_slot_wait()
                if wait > 0:
                    logger.info(f"[LondonFix] Next fetch: {info} (London date: {london_date_iso})")
                    await self._sleep_until(wait)

                if not self.running:
                    break

                # Mark current time as this slot
                utc_now = datetime.now(timezone.utc)

                # Double-check: date might have been fetched while we were sleeping
                if london_date_iso and london_date_iso in self._fetched_london_dates:
                    logger.info(f"[LondonFix] London date {london_date_iso} already fetched, skipping")
                    self._last_slot_utc = utc_now
                    continue

                # Fetch with retries
                success = False
                for attempt in range(1 + self.MAX_RETRIES):
                    if not self.running:
                        break
                    try:
                        if await self._fetch(london_date_iso):
                            success = True
                            break
                    except Exception as e:
                        logger.error(f"[LondonFix] Attempt {attempt + 1} failed: {e}")
                    if attempt < self.MAX_RETRIES:
                        logger.info(f"[LondonFix] Retry in {self.RETRY_INTERVAL}s...")
                        await asyncio.sleep(self.RETRY_INTERVAL)

                # On success, mark this London date as fetched
                if success and london_date_iso:
                    self._fetched_london_dates.add(london_date_iso)
                    logger.info(
                        f"[LondonFix] London date {london_date_iso} marked as fetched "
                        f"(saves next slot for same date)"
                    )
                    self._cleanup_old_dates()

                # Record slot as done (prevent re-fetch of same slot)
                self._last_slot_utc = utc_now

        finally:
            if self.session:
                await self.session.close()

    async def _sleep_until(self, seconds: float):
        remaining = seconds
        while remaining > 0 and self.running:
            await asyncio.sleep(min(remaining, self.SLEEP_CHECK))
            remaining -= self.SLEEP_CHECK

    def _cleanup_old_dates(self):
        """Remove London dates older than 5 days to prevent memory growth."""
        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=5)).isoformat()
        old = {d for d in self._fetched_london_dates if d < cutoff}
        if old:
            self._fetched_london_dates -= old
            logger.debug(f"[LondonFix] Cleaned up old dates: {old}")

    async def stop(self):
        self.running = False
        logger.info("[LondonFix] Stopped")

    async def _fetch(self, london_date_iso: str = None) -> bool:
        """Fetch LBMA fix prices from Metals.dev. Returns True if data updated.
        london_date_iso: the London business date this data corresponds to.
        If None (startup), auto-calculated from current UTC time.
        """
        params = {
            'api_key': self.api_key,
            'authority': 'lbma',
            'currency': 'USD',
            'unit': 'toz'
        }

        try:
            async with self.session.get(
                self.API_URL, params=params,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning(f"[LondonFix] HTTP {resp.status}: {body[:200]}")
                    return False
                data = await resp.json()
        except asyncio.TimeoutError:
            logger.warning("[LondonFix] Request timeout")
            return False
        except Exception as e:
            logger.error(f"[LondonFix] Request error: {e}")
            return False

        if data.get('status') != 'success':
            logger.warning(f"[LondonFix] API error: {data.get('status', 'unknown')}")
            return False

        rates = data.get('rates', {})
        if not rates:
            logger.warning("[LondonFix] Empty rates in response")
            return False

        updated = False
        for api_key, cache_key in self.RATE_MAP.items():
            val = rates.get(api_key)
            if val is not None:
                self._cache[cache_key] = float(val)
                updated = True

        if updated:
            self._cache['last_updated'] = datetime.now(KST).isoformat()
            if london_date_iso:
                self._cache['date'] = london_date_iso
            else:
                # Startup fetch: calculate London date from current UTC time
                utc_now = datetime.now(timezone.utc)
                london_date = self._london_date_for_slot(utc_now.date(), utc_now.hour)
                # Walk back to last business day if weekend/holiday
                while not self._is_business_day(london_date):
                    london_date -= timedelta(days=1)
                self._cache['date'] = london_date.isoformat()
            logger.info(
                f"[LondonFix] Gold AM={self._cache['gold_am']} PM={self._cache['gold_pm']}, "
                f"Silver={self._cache['silver']}, "
                f"Pt AM={self._cache['platinum_am']} PM={self._cache['platinum_pm']}, "
                f"Pd AM={self._cache['palladium_am']} PM={self._cache['palladium_pm']}"
            )

        return updated


# Global singleton
_london_fix_client: Optional[LondonFixClient] = None


def get_london_fix_client() -> LondonFixClient:
    global _london_fix_client
    if _london_fix_client is None:
        _london_fix_client = LondonFixClient()
    return _london_fix_client
