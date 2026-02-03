# API 성능 최적화 보고서

## 개요

페이지 첫 로드 시 데이터 표시까지 2~3초 이상 딜레이 발생 문제를 분석하고 해결.

**대상 사이트:** eurasiametal.net/price, gold-assets.com/price
**날짜:** 2026-02-03

---

## 문제 분석

### 병목 구간 측정 (최적화 전)

| 엔드포인트 | 직접 호출 (HTTP) | HTTPS (TLS 포함) | 역할 |
|-----------|-----------------|-------------------|------|
| `/api/latest-all` | 270ms | 2,200ms | 전체 자산 최신 가격 |
| `/api/reference-prices` | **6,400ms** | **6,200ms** | 전일 대비 변동률 계산용 기준가 |
| `/api/stream` (SSE) | 즉시 연결 | 즉시 연결 | 실시간 가격 스트림 |

### 근본 원인

1. **`/api/reference-prices` — DB 인덱스 미비 (6.4초)**
   - SQLite `price_records` 테이블: **155만 행** (451MB)
   - 3개 벌크 쿼리 각각 ~1.9초 소요 (합계 5.7초)
   - `EXPLAIN QUERY PLAN` 결과: `ix_price_records_asset_type (asset_type=?)` 단일 컬럼 인덱스만 사용
   - `asset_type`으로 필터링 후 50만+ 행에서 `timestamp` 범위 풀스캔 발생

2. **`/api/latest-all` — 24개 순차 DB 쿼리 (270ms)**
   - 3 providers × 8 assets = 24개 개별 쿼리를 순차 실행
   - 각 쿼리는 빠르지만 (10ms), 합산 시 비효율

3. **프론트엔드 — 순차 초기화**
   - SSE 연결 → API 응답 대기 → SSE 시작 (순차)
   - 첫 데이터 표시까지 모든 API 응답 완료 필요

---

## 해결 방안 및 적용

### 1. DB 인덱스 추가 (핵심 해결)

**파일:** `app/models/price_data.py`

```python
__table_args__ = (
    Index('idx_provider_asset_time', 'provider', 'asset_type', 'timestamp'),
    Index('idx_asset_timestamp', 'asset_type', 'timestamp'),  # 신규 추가
)
```

```sql
CREATE INDEX idx_asset_timestamp ON price_records (asset_type, timestamp);
```

**효과:** `(asset_type, timestamp)` 복합 인덱스 추가로 reference-prices 쿼리가 covering index를 사용하여 range scan 가능.

| 쿼리 | Before | After | 개선 |
|------|--------|-------|------|
| Today open (MIN id) | 1,886ms | 78ms | **24x** |
| LSE close (MAX id) | 1,926ms | 1ms | **1,926x** |
| NYSE close (MAX id) | 1,889ms | <1ms | **instant** |
| **합계** | **5,700ms** | **80ms** | **70x** |

### 2. 벌크 쿼리 (15 → 3 쿼리)

**파일:** `app/database/repository.py` — `get_reference_prices_bulk()`

기존: 5 assets × 3 reference types = **15개 개별 쿼리**
개선: 3개 벌크 쿼리 (today_open, lse_close, nyse_close) 각각 5 assets 동시 처리

```python
# MIN(id) GROUP BY asset_type WHERE timestamp >= today_start
# MAX(id) GROUP BY asset_type WHERE timestamp BETWEEN lse_start AND lse_close
# MAX(id) GROUP BY asset_type WHERE timestamp BETWEEN nyse_start AND nyse_close
```

### 3. 인메모리 캐시

**파일:** `app/routers/api.py`

| 엔드포인트 | 캐시 TTL | 이유 |
|-----------|---------|------|
| `/api/latest-all` | 2초 | 페이지 로드 시 중복 호출 방지 |
| `/api/reference-prices` | 60초 | 기준가는 자주 변하지 않음 |

### 4. 프론트엔드 병렬 초기화

**파일:** `price/static/js/app.js`

```javascript
// Before: 순차 실행
Promise.all([loadInitialPrices(), loadReferencePrices()]).then(() => connectSSE());

// After: 병렬 실행
this._connectSSE();          // SSE 즉시 연결
this._loadInitialPrices();   // API 호출 병렬
this._loadReferencePrices(); // API 호출 병렬
```

---

## 최종 성능 (HTTPS, TLS 포함)

| 측정 항목 | Before | After | 개선 |
|-----------|--------|-------|------|
| `/api/reference-prices` 첫 호출 | 6,200ms | **1,106ms** | **5.6x** |
| `/api/reference-prices` 캐시 히트 | - | **27ms** | - |
| `/api/latest-all` 첫 호출 | 2,200ms | **133ms** | **16x** |
| `/api/latest-all` 캐시 히트 | - | **24ms** | - |
| SSE 스트림 연결 | 즉시 | 즉시 | - |
| **체감 첫 데이터 표시** | **3~7초** | **< 1초** | - |

> 참고: HTTPS 첫 호출의 ~1초는 TLS 핸드셰이크 오버헤드 (keep-alive 이후 요청은 30ms 이내)

---

## 변경 파일 요약

| 파일 | 변경 내용 |
|------|----------|
| `app/models/price_data.py` | `idx_asset_timestamp` 인덱스 선언 추가 |
| `app/database/repository.py` | `get_all_latest_prices()`, `get_reference_prices_bulk()` 벌크 쿼리 메서드 추가 |
| `app/routers/api.py` | `/latest-all` 2초 캐시, `/reference-prices` 60초 캐시 + 벌크 쿼리 사용 |
| `price/static/js/app.js` | SSE/API 병렬 초기화 |
| `price_data.db` (런타임) | `idx_asset_timestamp` 인덱스 생성 (3.5초 소요) |
