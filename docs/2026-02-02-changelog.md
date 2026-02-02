# 2026-02-02 작업 내역

## 1. EODHD XPT/USD (Platinum) 데이터 프론트엔드 연결

**배경**: EODHD WebSocket이 XPTUSD 심볼을 구독하고 있었으나,
프론트엔드 `PROVIDER_ASSETS`에 platinum이 빠져있어 EODHD 선택 시
fallback 메커니즘으로 다른 프로바이더(massive)의 데이터를 표시하고 있었음.

**조사 결과**:
- REST API: `XPTUSD.FOREX` 히스토리 데이터 정상 반환 확인
- WebSocket: EODHD에서 XPT/USD bid/ask 데이터 실시간 수신 확인
- `/api/latest-all` 응답에서 EODHD platinum 데이터 정상 확인

**수정 파일**:
- `price/static/js/app.js` - EODHD PROVIDER_ASSETS에 platinum 추가

**변경 내용**:
```javascript
// Before
eodhd: ['gold', 'silver', 'palladium', 'usd_krw'],

// After
eodhd: ['gold', 'silver', 'platinum', 'palladium', 'usd_krw'],
```

**데이터 흐름** (백엔드는 이미 구현 완료):
1. EODHD WebSocket (`eodhd_ws_client.py`) → XPTUSD 구독
2. WebSocket Manager → 3초 버퍼링/평균 → SSE 브로드캐스트 + DB 저장
3. 프론트엔드 (`app.js`) → EODHD 프로바이더 선택 시 platinum 직접 수신

---

## 2. eurasiametal.net 루트 페이지 리다이렉트 제거

**배경**: `https://eurasiametal.net/` 접속 시 `/price/`로 자동 리다이렉트(302)되던 동작 제거 요청.

**수정 파일**:
- `C:\inetpub\eurasiametal\web.config` - RootToPrice 리다이렉트 규칙 제거, BlankRoot 규칙 추가
- `C:\inetpub\eurasiametal\index.html` - 빈 페이지 생성 (차후 콘텐츠 추가 예정)

**변경 후 동작**:
| URL | 동작 |
|-----|------|
| `https://eurasiametal.net/` | 빈 페이지 (로컬 index.html 서빙) |
| `https://eurasiametal.net/price/` | Price 대시보드 (FastAPI 프록시) |
| 기타 경로 | FastAPI (localhost:8001) 프록시 |

---

## 3. Flash Animation 안정성 개선

**배경**: 업데이트 간격을 6초 이상으로 설정하면 가격 변동 시 플래시 애니메이션이
재시작되지 않는 경우 발생.

**원인**:
- CSS animation 클래스(`flash-up`/`flash-down`)가 애니메이션 종료 후 제거되지 않음
- 동일 클래스 제거→재추가 시 단일 `requestAnimationFrame`으로는 브라우저가 제거를 처리하지 못함
- 가격 변동 없을 때도 불필요한 플래시 발생 (`tickChange >= 0`이 0 포함)

**수정 내용**:
- `animationend` 이벤트 리스너로 애니메이션 종료 시 클래스 자동 제거
- Double `requestAnimationFrame`으로 제거→재추가 사이 브라우저 처리 보장
- `data.price !== prevPrice` 조건으로 가격 변동 시에만 플래시 발생

---

## 4. 글로벌 Throttle 적용 + 업데이트 간격 조정

**배경**: 기존 per-asset throttle은 각 메탈별로 독립 타이머를 사용하여
사용자가 기대하는 전체 화면 동시 업데이트와 다르게 동작할 수 있었음.

**수정 내용**:
- **Per-asset throttle → Global throttle**: 단일 타이머로 모든 자산 동시 업데이트
- 500ms 배치 윈도우로 같은 flush의 모든 자산이 함께 통과
- 저부하 모드 옵션 10초 → 12초로 변경 (3초 flush 주기의 배수에 맞춤)

**Global throttle 동작 방식**:
1. 인터벌 경과 후 첫 메시지 도착 → gate open + 500ms 배치 윈도우
2. 500ms 내 도착하는 나머지 자산(같은 flush) → 모두 통과
3. 500ms 후 gate 닫힘 → 다음 인터벌까지 차단

---

## 5. 정적 파일 Cache-Busting 추가

**배경**: JS 파일 변경 후 브라우저 캐시로 인해 구버전이 로딩되는 문제 발생.

**수정**: `index.html`의 `<script>` 태그에 `?v=20260202d` 쿼리 파라미터 추가.

---

## 변경 파일 요약

| 파일 | 변경 내용 |
|------|-----------|
| `price/static/js/app.js` | EODHD platinum 추가, flash 안정성 개선, global throttle |
| `price/index.html` | cache-busting 추가, 12초 간격 옵션 |
| `price/settings.html` | 12초 간격 옵션 |
| `C:\inetpub\eurasiametal\web.config` | 루트 리다이렉트 제거, 빈 페이지 서빙 규칙 추가 |
| `C:\inetpub\eurasiametal\index.html` | 빈 HTML 페이지 생성 |
