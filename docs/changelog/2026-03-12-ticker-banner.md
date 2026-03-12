# 2026-03-12: Scrolling Ticker Banner

## 개요

gold-assets.com/price/ 화면 하단에 환율/지수 정보가 왼쪽으로 스크롤되는 티커 배너 추가.
증권방송이나 뉴스 채널의 하단 시세 표시줄과 동일한 형태.

## 티커 배너

- **위치**: 뷰포트 하단 고정 (`position: fixed; bottom: 0`)
- **높이**: 44px, z-index 150 (header 100 < ticker 150 < drawer 200)
- **배경**: 다크 네이비 (`hsl(220 30% 15%)`) — 페이지 테마와 무관하게 독립 색상
- **스크롤**: CSS `@keyframes` + `translateX(-50%)`, 콘텐츠 2벌 복제로 무한 루프
- **속도**: 30px/s (가독성 우선)

### 표시 자산 (14개)

| 자산 | 화폐기호 |
|------|----------|
| USD/KRW, USD/JPY, USD/CNY, EUR/USD | ₩, ¥, ¥, € |
| KOSPI, KOSDAQ, S&P 500, VIX, DXY | (없음) |
| Copper, Brent Oil | $ |
| ETH/USD | $ |
| Platinum, Palladium | $ |

### 변동값/변동율 표시

- **1차**: 참조가격(today_open/NYSE/LSE) 기반 계산
- **Fallback**: EODHD REST API의 `change`/`change_p` 메타데이터 활용
  - REST 폴링 자산(KOSPI, S&P 500 등)은 previousClose = today_open이 되어 변동값 0 발생
  - API 제공 변동값으로 대체하여 정상 표시

## 모바일 대응

- **CSS**: `@media (max-width: 768px), (pointer: coarse) and (max-width: 1200px)` 숨김
- **JS**: `'ontouchstart' in window || navigator.maxTouchPoints > 0` 터치 디바이스 감지
  - 터치 디바이스에서 `display: none` + `padding-bottom: 0` 직접 적용
  - 모바일 `position: fixed` 스크롤 시 바운싱 문제 회피

## 백엔드 변경

- `websocket_manager.py`: SSE broadcast에 `change`/`change_p` 필드 추가
  - EODHD REST 메타데이터에서 추출하여 프론트엔드로 전달
  - 기존 참조가격 기능과 병행 (fallback 용도)

## ASSETS unit 속성 추가

모든 자산에 `unit` 프로퍼티 추가 — 티커 및 향후 확장에서 화폐기호 표시용:
- `$`: gold, silver, platinum, palladium, copper, brent_oil, btc_usd, eth_usd
- `¥`: usd_jpy, usd_cny
- `€`: eur_usd
- `₩`: usd_krw
- `''`: kospi, kosdaq, sp500, vix, dxy

## 변경 파일

### Backend
- `app/services/websocket_manager.py` — SSE broadcast에 change/change_p 추가

### Frontend (gold-assets)
- `index.html` — 티커 배너 HTML 컨테이너, 캐시 버전 업데이트
- `static/css/style.css` — 티커 스타일, 스크롤 애니메이션, 반응형 숨김
- `static/js/app.js` — 티커 초기화/빌드/업데이트, unit 속성, API 변동값 fallback
