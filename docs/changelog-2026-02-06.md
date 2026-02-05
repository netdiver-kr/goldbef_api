# Changelog - 2026-02-06

## 1. SQLite Concurrency Fix

**Problem:** `cannot commit transaction - SQL statements in progress` errors occurring for ~1.5 hours (22:39-00:15 KST). 3 concurrent WebSocket writers (eodhd, massive, twelve_data) and multiple API readers sharing a single DB connection via StaticPool.

**Changes:**
- `connection.py`: Replaced `StaticPool` (single connection) with `QueuePool` (pool_size=3, max_overflow=2) to allow concurrent read/write on separate connections
- `data_processor.py`: Added `asyncio.Lock()` to serialize all DB writes (`save_price`, `save_prices_batch`), preventing write-write conflicts
- Added `check_same_thread=False` for SQLite multi-thread support

**Files:** `app/database/connection.py`, `app/services/data_processor.py`

---

## 2. WebSocket Monitoring & Error Detection

**Problem:** eodhd WebSocket disconnected silently with empty error messages (`Unexpected error:` with no detail). No detection mechanism for data receive stalls.

**Changes:**
- Added `_watchdog()` coroutine: forces reconnect if no messages received within `WS_MESSAGE_TIMEOUT` (60s)
- Enhanced error logging: `type(e).__name__` + full `traceback.format_exc()` on all exceptions
- Added `_message_count`, `_error_count` counters logged on connect/disconnect
- Added `get_health()` method returning connection metrics (connected, message count, error count, seconds since last message)

**Files:** `app/services/base_ws_client.py`

---

## 3. DB Cleanup Fix

**Problem:** Cleanup job was running every 6 hours but deleting 0 records because `DATA_RETENTION_DAYS=30` in .env (all data < 30 days old). When triggered, large DELETE caused `database is locked` error. VACUUM inside async session also problematic. WAL file grew to 660MB.

**Changes:**
- `.env`: `DATA_RETENTION_DAYS` 30 -> 7
- `repository.py` `delete_old_records()`: Changed from single bulk DELETE to batch deletion (5,000 records per batch with 0.5s sleep between batches). Replaced `VACUUM` with `PRAGMA wal_checkpoint(TRUNCATE)` for WAL file cleanup.
- `main.py`: Added 10-second delay before startup cleanup to avoid collision with other service initialization

**Result:** DB 719MB + WAL 660MB (1,161MB total) -> DB 501MB + WAL 1.3MB (503MB total). 57% reduction.

**Files:** `.env`, `app/database/repository.py`, `app/main.py`

---

## 4. Reference Price KST 08:00 Boundary Fix

**Problem:** After midnight KST, `today_open` reference price became null because `today_start_utc` pointed to today's 08:00 KST (future time at midnight-8AM). This caused change rate/value to not display.

**Changes:**
- `api.py`: Before 8 AM KST, use previous day's 8 AM as reference start so change values keep showing until new day's data arrives
- `repository.py`: Added `provider` parameter to `get_reference_prices_bulk()` for provider-specific reference prices
- `app.js`: Provider-aware reference price loading (`/api/reference-prices?provider=X`)

**Files:** `app/routers/api.py`, `app/database/repository.py`, `price/static/js/app.js`

---

## 5. London Fix Date Fix

**Problem:** London Fix `_fetch()` always used `utc.date().isoformat()` as cache date, which could be wrong for the 00:30 UTC slot (should show previous day's London date). Also, `_fetch()` was called without `london_date_iso` parameter during scheduled fetches.

**Changes:**
- `london_fix_client.py`: Added `london_date_iso` parameter to `_fetch()`. Scheduled fetches now pass the calculated London date. Startup fetch auto-calculates London date from current UTC time with business day walk-back.

**Files:** `app/services/london_fix_client.py`

---

## 6. Frontend: Grid & Style Updates

**Changes:**
- `grid.js`: Simplified percentage steps (gold/silver: 100-110% in 1% steps, platinum/palladium: 100-105%). Integer percentages now display without decimals (e.g., "100%" instead of "100.00%").
- `style.css`: Increased font sizes across grid tables for better readability (10px->14px headers, 12px->14px cells, 11px->13px labels)

**Files:** `price/static/js/grid.js`, `price/static/css/style.css`
