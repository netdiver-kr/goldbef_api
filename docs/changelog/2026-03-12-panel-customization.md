# 2026-03-12: Configurable Panels + New Assets + Dark Mode Overhaul

## Panel Customization (gold-assets.com/price/)

상단 5개 실시간 시세 패널 중 3번째, 4번째 패널을 사용자가 설정에서 선택 가능하도록 변경.

- **고정 패널**: Gold (1), Silver (2), USD/KRW (5)
- **커스터마이징 패널**: Panel 3, Panel 4 — 14개 자산 중 선택
- **기본값**: Panel 3 = BTC/USD, Panel 4 = USD/JPY
- **설정 UI**: 기존 설정 드로어에 "패널 설정" 카드 추가 (select dropdown)
- **설정 저장**: localStorage (`em_panel3`, `em_panel4`)

## New Data Sources

### EODHD WebSocket (실시간)
- USD/CNY (`USDCNY`), EUR/USD (`EURUSD`), ETH/USD (`ETH-USD`), Brent Oil (`XBRUSD`)

### EODHD REST Polling (5분 간격, 신규 클라이언트)
- **파일**: `app/services/eodhd_realtime_client.py`
- **자산**: KOSPI (`KS11.INDX`), KOSDAQ (`KQ11.INDX`), S&P 500 (`GSPC.INDX`), VIX (`VIX.INDX`), DXY (`DXY.INDX`), Copper (`XCUUSD.FOREX`)
- **Fallback**: `close`가 NA일 때 `previousClose` 사용 (장외 시간)
- **설정**: `EODHD_REALTIME_INTERVAL` (기본 300초)

### 제거된 자산
- Natural Gas: EODHD에서 어떤 API/티커로도 데이터 미제공

## Reference Price Fix

- S&P 500 등 REST 폴링 자산의 `timestamp`가 마지막 거래 시점으로 고정되어 `today_open` 참조가격을 찾지 못하는 문제 수정
- `timestamp` 기준 실패 시 `created_at` 기준으로 fallback 조회 추가 (`repository.py`)

## Dark Mode Overhaul

### Color Hierarchy (shadcn/ui 참조)
- Hue를 240(무채색) → 222(blue tint)로 변경
- 명도 간격 확대: page(6%) → header(8%) → card(10%) → row-alt(13%) → border(23%)
- 기존 대비 카드-배경 간 구분감 대폭 개선

### Font Rendering
- 다크 모드에서 `-webkit-font-smoothing: auto` (halation 보상)
- `-webkit-text-stroke: 0.2px` 추가 (텍스트 선명도 향상)

### Flash Animation
- 업/다운 배경색 밝기 18% → 22%로 상향 (대형 디스플레이 대응)

### Delay Badge
- REST 폴링 자산에 "~20m" 배지 표시
- 부드러운 회색 톤 (`hsl(220 12% 72%)`) + 다크 모드 별도 색상

## 변경 파일

### Backend
- `app/services/eodhd_ws_client.py` — USDCNY, EURUSD, XBRUSD 추가
- `app/services/eodhd_crypto_ws_client.py` — ETH-USD 추가
- `app/services/eodhd_realtime_client.py` — **신규** REST 폴링 클라이언트
- `app/services/websocket_manager.py` — REST 클라이언트 통합
- `app/routers/api.py` — valid_assets 확장 (3곳)
- `app/main.py` — assets_list 확장, REST 클라이언트 시작/종료
- `app/config.py` — EODHD_REALTIME_INTERVAL 추가
- `app/database/repository.py` — created_at fallback for today_open

### Frontend (gold-assets)
- `index.html` — 패널 data-panel-slot 속성, 설정 드롭다운, 동적 ref-prices
- `static/css/style.css` — 다크 모드 색상 전면 개편, delay badge, font rendering
- `static/js/app.js` — 18개 자산 메타, 패널 동적 렌더링, 참조가격 동적 생성
- `static/js/settings.js` — PANEL3/PANEL4 키 추가

## 데이터 수신 현황

| 자산 | 소스 | 상태 |
|------|------|------|
| Gold, Silver, Pt, Pd, USD/KRW, USD/JPY | EODHD WS Forex | 실시간 |
| USD/CNY, EUR/USD, Brent Oil | EODHD WS Forex | 실시간 |
| BTC/USD, ETH/USD | EODHD WS Crypto | 실시간 |
| KOSPI, KOSDAQ, VIX, Copper | EODHD REST | 5분 |
| S&P 500, DXY | EODHD REST (previousClose) | 장외시간 전일종가 |
