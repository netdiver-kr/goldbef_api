# Gold-Assets BTC/USD, USD/JPY 지원 추가

**날짜**: 2026-02-25
**적용 대상**: gold-assets.com/price (프론트엔드), 공통 백엔드 API

## 변경 사항

### 상단 가격 패널 변경 (gold-assets.com만)
- **기존**: Gold, Silver, Platinum, Palladium, USD/KRW
- **변경**: Gold, Silver, **BTC/USD**, **USD/JPY**, USD/KRW
- eurasiametal.net은 변경 없음 (기존 유지)

### 백엔드 - EODHD Crypto WebSocket 추가
- EODHD forex endpoint (`ws/forex`)는 암호화폐 미지원
- 별도 crypto endpoint (`ws/crypto`) 전용 클라이언트 생성
- BTC 심볼: `BTC-USD` (crypto endpoint은 하이픈 형식 사용)
- BTC 데이터는 bid/ask 없이 체결가(trade price)만 제공
  - `p`: 체결가, `q`: 수량, `dc`: 일간변동률(%), `dd`: 일간변동폭

### 백엔드 - USD/JPY 추가
- EODHD forex endpoint에서 `USDJPY` 심볼로 수신
- Twelve Data에서 `USD/JPY` 심볼로 수신

## 변경 파일

### 백엔드 (git 관리)
| 파일 | 변경 내용 |
|------|-----------|
| `app/services/eodhd_crypto_ws_client.py` | **신규** - EODHD crypto WebSocket 클라이언트 |
| `app/services/eodhd_ws_client.py` | btc_usd 제거 (forex 미지원), usd_jpy 추가 |
| `app/services/twelve_data_client.py` | btc_usd, usd_jpy 심볼 추가 |
| `app/services/websocket_manager.py` | EODHDCryptoWebSocketClient 등록 |
| `app/routers/api.py` | statistics, latest-all, reference-prices에 btc_usd, usd_jpy 추가 |
| `app/main.py` | 캐시 워밍업 자산 목록에 btc_usd, usd_jpy 추가 |
| `app/database/repository.py` | reference-prices 쿼리 개선 (id→timestamp 기반) |

### 프론트엔드 - gold-assets.com (git 외부)
| 파일 | 변경 내용 |
|------|-----------|
| `C:\inetpub\gold-assets\price\static\js\app.js` | ASSETS에서 platinum/palladium → btc_usd/usd_jpy 교체 |
| `C:\inetpub\gold-assets\price\index.html` | 가격 카드 교체, 버전 업데이트 |

## EODHD WebSocket 아키텍처

```
EODHD API
├── ws/forex  (EODHDWebSocketClient)
│   ├── XAUUSD (gold)
│   ├── XAGUSD (silver)
│   ├── XPTUSD (platinum)
│   ├── XPDUSD (palladium)
│   ├── USDKRW (usd_krw)
│   └── USDJPY (usd_jpy)
│
└── ws/crypto (EODHDCryptoWebSocketClient)  ← 신규
    └── BTC-USD (btc_usd)
```

두 클라이언트 모두 동일한 EODHD 버퍼(`_handle_eodhd_message`)를 사용하여
3초 평균값으로 DB 저장 및 SSE 브로드캐스트.
