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

## 변경 파일 요약

| 파일 | 변경 내용 |
|------|-----------|
| `price/static/js/app.js` | EODHD PROVIDER_ASSETS에 platinum 추가 |
| `C:\inetpub\eurasiametal\web.config` | 루트 리다이렉트 제거, 빈 페이지 서빙 규칙 추가 |
| `C:\inetpub\eurasiametal\index.html` | 빈 HTML 페이지 생성 |
