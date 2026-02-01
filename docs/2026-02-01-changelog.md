# 2026-02-01 작업 내역

## Phase 2: Frontend Redesign & Backend Optimization

---

### 1. 가격 기준 변경 (mid-price → ASK)

**문제**: EODHD와 NauGold 모두 `(bid + ask) / 2` 중간가를 price로 사용 중이었음.
기존에는 ASK를 기준가로 사용했었으므로 불일치 발생.

**수정 파일**:
- `app/services/eodhd_ws_client.py` - price = ask (fallback to bid)
- `app/services/naugold_client.py` - price = ask (fallback to bid)

**변경 로직**:
```python
# Before: mid-price
price = (bid + ask) / 2

# After: ask-first
if ask:
    price = ask
elif bid:
    price = bid
```

---

### 2. 설정 UI 개선

#### 2-1. NauGold → Massive.com 명칭 복원
- `price/index.html` - 설정 drawer 내 프로바이더 이름
- `price/settings.html` - 설정 페이지 프로바이더 이름

#### 2-2. 설정 초기화 버튼 추가
설정 drawer 상단에 "초기화" 버튼 추가. 클릭 시 모든 설정을 기본값으로 복원.

**수정 파일**:
- `price/index.html` - drawer-header에 `btn-reset-settings` 버튼 추가
- `price/static/css/style.css` - `.btn-reset` 스타일 추가
- `price/static/js/app.js` - `_initSettingsDrawer()`에 리셋 로직 추가

**기본값**: theme=light, provider=eodhd, interval=3000ms, changeRef=today_open

---

### 3. 그리드 스크롤바 가시성 개선

**문제**: 골드/실버 퍼센테지 테이블의 가로 스크롤바가 거의 보이지 않았음.

**수정 파일**: `price/static/css/style.css`

**변경 내용**:
- WebKit 스크롤바: height 8px, muted-foreground 색상, 라운드 코너
- Firefox: `scrollbar-width: thin`, `scrollbar-color` 지정
- 호버 시 foreground 색상으로 강조

---

### 4. 롤링 애니메이션 속도 조정

**문제**: 3초 업데이트 주기에 600ms 애니메이션이 느리게 느껴짐.

**수정 파일**:
- `price/static/css/animations.css` - `.digit-column` transition: `0.6s` → `0.4s`
- `price/static/js/rolling.js` - default duration: `600` → `400`

---

### 5. 성능 점검 및 최적화

#### 5-1. 백엔드 점검 결과

| 항목 | 상태 | 비고 |
|------|------|------|
| 프로세스 메모리 | 78~81MB | Python FastAPI 정상 범위 |
| SSE 큐 관리 | 정상 | maxsize=100, 오버플로우 처리 |
| EODHD/Massive 버퍼 | 정상 | 3초마다 클리어 |
| DB 세션 관리 | 정상 | async with 패턴 |
| **DB 자동 정리** | **미구현** | 275MB 무한 증가 중 |

#### 5-2. 프론트엔드 점검 결과

| 항목 | 상태 | 비고 |
|------|------|------|
| 메모리 누수 | 없음 | 이벤트리스너 고정, DOM 무한증가 없음 |
| EventSource 재연결 | 정상 | close 후 재연결 |
| 타이머 정리 | 정상 | destroy()에서 해제 |
| **그리드 셀 리플로우** | **비효율** | 셀당 개별 reflow 수백 회/업데이트 |
| **가격 카드 플래시** | **비효율** | 카드당 개별 reflow |

#### 5-3. DB 자동 정리 스케줄러 추가

**수정 파일**: `app/main.py`

- 서버 시작 시 즉시 30일 이전 레코드 삭제
- 이후 6시간마다 반복 실행
- `settings.DATA_RETENTION_DAYS` (기본 30일) 설정 사용

```python
# main.py lifespan에 추가
async def _db_cleanup_loop():
    # Initial cleanup on startup
    async for session in get_db_session():
        repo = PriceRepository(session)
        deleted = await repo.delete_old_records(days=settings.DATA_RETENTION_DAYS)

    # Periodic cleanup every 6 hours
    while True:
        await asyncio.sleep(6 * 3600)
        ...
```

#### 5-4. 그리드 셀 리플로우 최적화

**수정 파일**: `price/static/js/grid.js`

**Before**: 셀 하나마다 `void td.offsetWidth` 강제 리플로우 (수백 회/업데이트)
**After**: `requestAnimationFrame`으로 배치 처리, 전체 배치에서 1회만 리플로우

```javascript
// Before
td.classList.remove('grid-cell-updated');
void td.offsetWidth;  // 셀마다 강제 리플로우
td.classList.add('grid-cell-updated');

// After
if (!this._pendingCells) {
    this._pendingCells = [];
    requestAnimationFrame(() => {
        const cells = this._pendingCells;
        this._pendingCells = null;
        cells.forEach(c => c.classList.remove('grid-cell-updated'));
        document.body.offsetHeight;  // 1회만 리플로우
        cells.forEach(c => c.classList.add('grid-cell-updated'));
    });
}
this._pendingCells.push(td);
```

#### 5-5. 가격 카드 플래시 리플로우 최적화

**수정 파일**: `price/static/js/app.js`

**Before**: `void card.offsetWidth` 강제 리플로우
**After**: `requestAnimationFrame`으로 다음 프레임에서 클래스 추가

```javascript
// Before
card.classList.remove('flash-up', 'flash-down');
void card.offsetWidth;
card.classList.add(tickChange >= 0 ? 'flash-up' : 'flash-down');

// After
card.classList.remove('flash-up', 'flash-down');
requestAnimationFrame(() => {
    card.classList.add(cls);
});
```

---

### 6. PT(Platinum) 데이터 EODHD 선택 시 표시 확인

**결론**: 정상 동작 (버그 아님)

EODHD의 `PROVIDER_ASSETS`에 platinum이 포함되어 있지 않아,
`fallbackLock` 메커니즘에 의해 첫 번째로 데이터를 전송한 프로바이더(massive)가
platinum 데이터를 담당하게 됨. 의도된 설계.

```javascript
// app.js PROVIDER_ASSETS
eodhd: ['gold', 'silver', 'palladium', 'usd_krw'],  // platinum 없음
```

---

## 변경 파일 요약

| 파일 | 변경 내용 |
|------|-----------|
| `app/services/eodhd_ws_client.py` | price = ask 우선 |
| `app/services/naugold_client.py` | price = ask 우선 |
| `app/main.py` | DB 자동 정리 스케줄러 |
| `price/index.html` | 초기화 버튼, Massive.com 명칭 |
| `price/settings.html` | Massive.com 명칭 |
| `price/static/css/style.css` | 초기화 버튼 CSS, 스크롤바 개선 |
| `price/static/css/animations.css` | 롤링 애니메이션 0.6s → 0.4s |
| `price/static/js/app.js` | 초기화 로직, 플래시 리플로우 최적화 |
| `price/static/js/grid.js` | 셀 리플로우 배치 최적화 |
| `price/static/js/rolling.js` | duration 600 → 400 |
| `price/static/js/settings.js` | (이전 세션) defaults 업데이트 |
