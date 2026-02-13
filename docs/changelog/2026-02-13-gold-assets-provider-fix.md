# Gold Assets - Reference Prices Provider 파라미터 수정

**날짜**: 2026-02-13
**적용 대상**: gold-assets.com/price

## 문제점

gold-assets.com에서 변동 기준가(today_open)가 비정상적으로 높게 표시됨:
- Gold: 5,076.72 (정상: 4,925.70)
- Silver: 83.06 (정상: 75.31)

## 원인

`_loadReferencePrices()` 함수에서 provider 파라미터가 누락되어,
API가 모든 provider 중 첫 번째 데이터를 반환 (massive의 비정상 데이터 포함)

```javascript
// 수정 전 (gold-assets)
const response = await fetch('/api/reference-prices');

// eurasiametal (정상)
const response = await fetch(`/api/reference-prices?provider=${provider}`);
```

## 해결

```javascript
// 수정 후
const provider = this.settings.getProvider();
const response = await fetch(`/api/reference-prices?provider=${provider}`);
```

## 변경 파일 (gold-assets - git 외부)

| 파일 | 변경 내용 |
|------|-----------|
| `C:\inetpub\gold-assets\price\static\js\app.js` | provider 파라미터 추가 |
| `C:\inetpub\gold-assets\price\index.html` | 버전 v=20260213a |

## 두 사이트 코드 차이점 정리

### 의도적 차이 (디자인)
| 항목 | EurasiaMetal | Gold Assets |
|------|--------------|-------------|
| 언어 | 한국어 | 영어 |
| 헤더 | 텍스트 제목 | 로고 이미지 |
| 백금/팔라듐 | 항상 표시 | 접이식 (collapsed) |
| TradingView 차트 | 없음 | Gold/Silver 차트 |
| 카피라이트 | EurasiaMetal | Gold Assets |

### 기능적으로 동일해야 하는 부분
- settings.js: 동일
- rolling.js: 동일
- API 호출 로직: **이제 동일** (provider 파라미터 수정 완료)
