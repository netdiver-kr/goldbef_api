# Page Visibility API - 모바일 백그라운드 탭 데이터 갱신

**날짜**: 2026-02-13
**적용 대상**: eurasiametal.net/price, gold-assets.com/price

## 문제점

모바일에서 페이지를 열어두고 다음 날 접속하면 새로고침 전까지 변동 기준가가 업데이트되지 않음.

**원인**: 모바일 브라우저에서 백그라운드 탭은 JavaScript 타이머(setInterval)가 일시 중지됨.
탭을 다시 열어도 "재개"만 되고 데이터는 갱신되지 않음.

## 해결 방법

**Page Visibility API** 사용: 탭이 다시 활성화될 때 데이터 자동 새로고침

```javascript
_setupVisibilityRefresh() {
    this._lastVisibleTime = Date.now();

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            const elapsed = Date.now() - this._lastVisibleTime;

            // 5분 이상 백그라운드에 있었으면 데이터 갱신
            if (elapsed > 5 * 60 * 1000) {
                this._loadReferencePrices();
                this._loadLondonFix();
                this._loadInitialRate();
                this._loadInitialPrices();
            }

            this._lastVisibleTime = Date.now();
        }
    });
}
```

## 변경 파일

| 사이트 | 파일 | 버전 |
|--------|------|------|
| eurasiametal.net | `price/static/js/app.js` | v=20260213b |
| eurasiametal.net | `price/index.html` | v=20260213b |
| gold-assets.com | `price/static/js/app.js` | v=20260213b |
| gold-assets.com | `price/index.html` | v=20260213b |

## 확인 방법

1. 페이지 열기
2. 다른 탭으로 이동하거나 브라우저 최소화 (5분 이상)
3. 다시 탭으로 돌아오기
4. 콘솔에서 확인: `[Visibility] Tab visible after 10min, refreshing data`
