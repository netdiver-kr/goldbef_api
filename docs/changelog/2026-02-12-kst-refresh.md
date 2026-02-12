# KST 08:00 자동 새로고침 기능 추가

**날짜**: 2026-02-12
**적용 대상**: eurasiametal.net/price, gold-assets.com/price

## 문제점

페이지를 하루 이상 열어두면 다음 데이터가 자동으로 갱신되지 않음:
- 변동 기준가 (특히 KST 08:00에 갱신되는 `today_open`)
- 런던 픽스
- 최초고시환율

## 해결 방법

### 1. KST 08:00 스케줄 기반 새로고침
- 매분 현재 시간 체크
- KST 08:00, 08:05, 08:10, 08:15에 자동 데이터 갱신
- 4번 재시도로 안정성 확보

```javascript
_scheduleKSTRefresh() {
    const KST_REFRESH_HOURS = [8];
    const KST_REFRESH_MINUTES = [0, 5, 10, 15];

    const checkAndRefresh = () => {
        const kst = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Seoul' }));
        if (KST_REFRESH_HOURS.includes(hour) && KST_REFRESH_MINUTES.includes(minute)) {
            this._loadReferencePrices();
            this._loadLondonFix();
            this._loadInitialRate();
        }
    };

    this._kstRefreshTimer = setInterval(checkAndRefresh, 60000);
}
```

### 2. 30분 주기 갱신에 변동 기준가 추가
기존 30분 타이머에 `_loadReferencePrices()` 추가

## 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `price/static/js/app.js` | `_scheduleKSTRefresh()` 메서드 추가, 30분 타이머에 reference prices 추가 |
| `price/index.html` | 버전 번호 업데이트 (v=20260212a) |
| `C:\inetpub\gold-assets\price\static\js\app.js` | 동일 수정 적용 |
| `C:\inetpub\gold-assets\price\index.html` | 버전 번호 업데이트 |

## 확인 방법

브라우저 개발자 도구 콘솔에서 KST 08:00~08:15 사이에 다음 로그 확인:
```
[KST Refresh] Triggered at KST 8:00
```
