# PDCA Plan: Production Release - eurasiametal.net/price/

## 1. 개요

### 1.1 프로젝트 배경
기존 `price-api.goldbef.com` 실시간 금융 데이터 비교 시스템을 기반으로, 내부 직원/트레이더 전용 프로덕션 대시보드를 `eurasiametal.net/price/`에 배포한다.

### 1.2 목표
- naugold.com/naugold_td 레이아웃을 참고한 전문 트레이더용 가격 대시보드 구축
- 5개 귀금속/환율 실시간 가격 표시 (Gold, Silver, Platinum, Palladium, USD/KRW)
- 퍼센트별 KRW 환산 그리드 제공
- ShadCN UI 디자인 스타일 + Toss 스타일 숫자 롤링 애니메이션
- 서버 부하 없이 프론트엔드만 개선 (백엔드 API는 기존 것 공유)

### 1.3 대상 사용자
- 내부 직원/트레이더 (근무시간 중 페이지 상시 표시)
- 데스크톱 모니터 기준 최적화, 모바일 대응

---

## 2. 요구사항 정리

### 2.1 페이지 구조 (4개 섹션)

#### 섹션 1: 실시간 가격 카드 (상단)
- **5개 자산**: Gold (XAU/USD), Silver (XAG/USD), Platinum (XPT/USD), Palladium (XPD/USD), USD/KRW
- **카드 표시 정보**: 현재가, Bid/Ask, 변동률(%), 타임스탬프
- **데이터 소스**: 기존 SSE 스트림 (`/api/stream`)
- **애니메이션**: Toss 스타일 숫자 롤링 (CSS `translateY`로 digit slot 단위 전환)
- **플래시**: 가격 상승 시 초록, 하락 시 빨간 배경 플래시

#### 섹션 2: 퍼센트별 KRW 환산 그리드 (중단)
- **Gold/Silver**: 100% ~ 110% (1% 단위, 11개 행)
- **Platinum/Palladium**: 100% ~ 104% (1% 단위, 5개 행)
- **계산 방식**: `USD가격 × 퍼센트 × USD/KRW환율 ÷ 트로이온스(31.1035g)` → g당 KRW
- **열 구성**: 퍼센트, 3.75g, 11.25g, 37.5g, 100g, 1kg
- **실시간 업데이트**: 가격 또는 환율 변동 시 그리드 전체 재계산

#### 섹션 3: 하단 정보
- **최초고시환율 (USD/KRW)**: 당일 최초 고시환율 표시 (Spot Price 대체)
- **London Fix AM/PM**: 금/은 런던 픽싱 가격 (AM/PM)
- naugold_td 레이아웃의 하단 정보 영역 참고

#### 섹션 4: 설정 페이지
- **테마**: 다크/라이트 모드 토글 (CSS 변수 전환)
- **프로바이더 선택**: EODHD / Twelve Data / Massive 라디오 버튼
- **업데이트 간격**: 3초 / 5초 / 10초 선택
- **설정 저장**: `localStorage` 기반 (서버 불필요)

### 2.2 디자인 요구사항
- **디자인 시스템**: ShadCN UI (https://ui.shadcn.com/) 컴포넌트 스타일
- **테마**: 다크/라이트 토글 지원 (CSS 변수 기반)
- **폰트**: 시스템 폰트 스택 + tabular-nums
- **숫자 애니메이션**: Toss 스타일 digit-by-digit rolling (translateY)
- **가격 플래시**: 상승(초록)/하락(빨간) 배경 애니메이션
- **번인 방지**: 10분마다 1~2px 미세 시프트 (모니터 상시 표시 대응)

### 2.3 기술 제약사항
- **프론트엔드**: Vanilla HTML/CSS/JS 유지 (프레임워크 미사용)
- **백엔드**: 기존 FastAPI 서버 공유 (새 엔드포인트만 추가)
- **서버**: Windows Server + IIS 역방향 프록시
- **DB**: 기존 SQLite + WAL 모드 유지
- **서버 부하 최소화**: 순수 프론트엔드 JS 계산, 서버 추가 부하 없음

---

## 3. 아키텍처 설계

### 3.1 배포 구조

```
eurasiametal.net/price/   →  IIS 역방향 프록시  →  localhost:8000
                                                      ↓
                                              FastAPI (기존 서버)
                                                ├── /price/          → price/index.html (새 대시보드)
                                                ├── /price/static/   → 새 CSS/JS 파일
                                                ├── /api/stream      → SSE (기존)
                                                ├── /api/latest-all  → REST (기존)
                                                └── /api/history     → REST (기존)
```

### 3.2 파일 구조 (신규)

```
c:\inetpub\wwwroot\API\
├── frontend/                    # 기존 대시보드 (goldbef.com)
│   ├── index.html
│   └── static/
│       ├── css/style.css
│       └── js/main.js
│
├── price/                       # 신규 대시보드 (eurasiametal.net/price/)
│   ├── index.html               # 메인 페이지
│   ├── settings.html            # 설정 페이지
│   └── static/
│       ├── css/
│       │   ├── style.css        # 메인 스타일 (ShadCN + 다크/라이트)
│       │   └── animations.css   # Toss 롤링 + 플래시 + 번인방지
│       └── js/
│           ├── app.js           # 메인 앱 (SSE 연결, 가격 업데이트)
│           ├── grid.js          # KRW 환산 그리드 계산/렌더링
│           ├── rolling.js       # Toss 스타일 숫자 롤링 애니메이션
│           └── settings.js      # 설정 관리 (localStorage)
│
├── app/
│   ├── main.py                  # 수정: /price/ 라우트 추가
│   ├── routers/
│   │   └── api.py               # 수정: London Fix / 최초고시환율 엔드포인트 추가
│   └── services/
│       ├── london_fix_client.py # 신규: London Fix AM/PM 크롤링
│       └── initial_rate_client.py # 신규: 최초고시환율 API (차후)
```

### 3.3 데이터 흐름

```
[EODHD WS] ──┐
[TwelveData] ─┤── WebSocketManager ── SSE /api/stream ──→ price/app.js
[Massive DB] ─┘         │                                      │
                         │                                      ├── 가격 카드 업데이트
                    Save to SQLite                              ├── 롤링 애니메이션
                                                                ├── KRW 그리드 재계산
                                                                └── 플래시 애니메이션
```

---

## 4. 구현 계획

### Phase 1: 프로젝트 구조 설정
1. `price/` 디렉토리 생성 및 기본 파일 구조 생성
2. FastAPI에 `/price/` 라우트 및 정적 파일 마운트 추가
3. ShadCN 스타일 CSS 변수 설정 (다크/라이트 모드)

### Phase 2: 메인 페이지 HTML 구조
1. `price/index.html` 작성
   - 헤더 (타이틀 + 연결 상태 + 설정 버튼)
   - 섹션 1: 5개 가격 카드 그리드
   - 섹션 2: KRW 환산 그리드 테이블 (Gold/Silver + Platinum/Palladium)
   - 섹션 3: 최초고시환율 + London Fix AM/PM
   - 푸터

### Phase 3: CSS 스타일링
1. `price/static/css/style.css`
   - ShadCN UI 디자인 토큰 (다크/라이트 CSS 변수)
   - 가격 카드 레이아웃
   - KRW 그리드 테이블 스타일
   - 하단 정보 영역
   - 반응형 (모바일 대응)
2. `price/static/css/animations.css`
   - Toss 스타일 digit rolling (`@keyframes roll-up/roll-down`)
   - 가격 플래시 애니메이션
   - 번인 방지 미세 시프트 (`@keyframes pixel-shift`)

### Phase 4: JavaScript 구현
1. `price/static/js/app.js` - 메인 앱
   - SSE 연결 관리 (재연결 로직)
   - 가격 데이터 수신 및 카드 업데이트
   - 프로바이더 필터링 (설정 기반)
   - 업데이트 간격 제어 (쓰로틀링)
   - 번인 방지 타이머 (10분 간격)
2. `price/static/js/grid.js` - KRW 환산 그리드
   - 실시간 환산 계산 로직
   - `USD가격 × % × 환율 ÷ 31.1035` 공식
   - 중량별 환산 (3.75g, 11.25g, 37.5g, 100g, 1kg)
   - 그리드 DOM 업데이트 (변경된 셀만)
3. `price/static/js/rolling.js` - 숫자 롤링 애니메이션
   - digit slot 생성/관리
   - translateY 기반 숫자 전환
   - 소수점, 콤마 처리
   - 방향 감지 (상승/하락)
4. `price/static/js/settings.js` - 설정 관리
   - localStorage 읽기/쓰기
   - 테마 전환 (다크/라이트)
   - 프로바이더 선택
   - 업데이트 간격 선택

### Phase 5: 설정 페이지
1. `price/settings.html` 작성
   - 다크/라이트 모드 토글
   - 프로바이더 라디오 버튼
   - 업데이트 간격 라디오 버튼
   - 저장/적용 버튼

### Phase 6: 백엔드 수정
1. `app/main.py` 수정
   - `/price/` 경로에 `price/index.html` 서빙
   - `/price/settings` 경로에 `price/settings.html` 서빙
   - `/price/static/` 정적 파일 마운트
2. **London Fix AM/PM 크롤링 서비스** 추가
   - API 미제공 → 웹사이트 크롤링으로 데이터 수집
   - LBMA 또는 관련 사이트에서 AM/PM 가격 스크래핑
   - 하루 2회 업데이트 (AM: 런던 10:30, PM: 런던 15:00)
   - `app/services/london_fix_client.py` 신규 생성
   - 스크래핑 결과를 메모리 캐시 + SQLite 저장
   - REST API 엔드포인트: `GET /api/london-fix`
3. **최초고시환율 API** (차후 연동)
   - API 신청 진행 중 → API 키 수령 후 연동
   - 우선 수동 입력 또는 플레이스홀더로 구현
   - `app/services/initial_rate_client.py` 신규 생성 (API 키 수령 후)
   - REST API 엔드포인트: `GET /api/initial-rate`

### Phase 7: 테스트 및 최적화
1. 기능 테스트
   - SSE 연결/재연결
   - 5개 자산 실시간 업데이트
   - KRW 그리드 계산 정확성
   - 롤링 애니메이션 부드러움
   - 다크/라이트 모드 전환
   - 프로바이더 필터링
   - 번인 방지 동작
2. 성능 테스트
   - 장시간 실행 시 메모리 누수 확인
   - DOM 업데이트 빈도 최적화
   - 애니메이션 프레임 드롭 확인
3. 브라우저 호환성
   - Chrome (주 대상)
   - Edge

### Phase 8: IIS 배포 설정
1. IIS에 `eurasiametal.net` 사이트 설정
2. `/price/` 경로 역방향 프록시 → `localhost:8000/price/`
3. SSL 인증서 설정
4. 최종 배포 확인

---

## 5. KRW 환산 그리드 상세 스펙

### 5.1 레이아웃
- **가로 스크롤 테이블**: 퍼센티지를 열(column)로, 중량(1g/3.75g)을 행(row)으로 배치
- **서브 섹션**: 현재환율 기준 + 최초고시환율 기준 (2세트)
- **중량**: 1g, 3.75g (돈) — 실무에서 사용하는 단위만 제공

### 5.2 Gold/Silver 퍼센티지 (34단계)
100.00, 100.10, 100.20, 100.25, 100.30, 100.35, 100.40, 100.45,
100.50, 100.55, 100.60, 100.65, 100.70, 100.75, 100.80, 100.90,
101.00, 101.10, 101.20, 101.30, 101.40, 101.50, 101.60, 101.70,
101.80, 101.90, 102.00, 102.20, 102.50, 103.00, 104.00, 105.00,
107.00, 110.00

### 5.3 Platinum/Palladium 퍼센티지 (8단계)
100.00, 101.00, 101.50, 101.80, 102.00, 102.50, 103.00, 104.00

### 5.4 계산 공식

```
1g당 KRW = (USD가격 × 퍼센트% × USD/KRW환율) ÷ 31.1035
3.75g당 KRW = 1g당 KRW × 3.75
```

- **트로이온스**: 31.1035g
- **환율**: 실시간 USD/KRW (선택된 프로바이더) + 최초고시환율
- **퍼센트**: 마진율 적용

---

## 6. Toss 스타일 숫자 롤링 애니메이션 스펙

### 6.1 원리
- 각 digit 위치에 0~9 숫자가 세로로 배치된 "digit column" 생성
- `translateY`로 해당 숫자 위치로 슬라이딩
- 소수점(`.`), 콤마(`,`) 위치는 고정

### 6.2 구현 방식
```
┌─────┐
│  8  │  ← 보이는 영역 (overflow: hidden)
│  9  │
│  0  │  ← translateY로 이동
│  1  │
│  2  │
└─────┘
```

### 6.3 성능 고려
- `will-change: transform` 적용
- `transform: translateY()` 사용 (GPU 가속)
- `transition-duration: 600ms` (자연스러운 속도)
- 소수점 이하 자릿수 고정 (리플로우 방지)

---

## 7. 번인 방지 스펙

### 7.1 미세 시프트 방식
- 10분(`600,000ms`)마다 `main` 컨테이너에 1~2px 랜덤 오프셋
- `transform: translate(Xpx, Ypx)` 사용 (리플로우 없음)
- 사용자 인지 불가 수준의 미세한 이동

### 7.2 구현
```javascript
setInterval(() => {
    const x = Math.random() * 2 - 1;  // -1 ~ 1px
    const y = Math.random() * 2 - 1;  // -1 ~ 1px
    document.querySelector('main').style.transform = `translate(${x}px, ${y}px)`;
}, 600000);  // 10분
```

---

## 8. 설정 페이지 스펙

### 8.1 다크/라이트 모드
- `<html data-theme="dark|light">` 어트리뷰트로 전환
- CSS 변수 2세트 정의 (`:root` + `[data-theme="dark"]`)
- `localStorage.setItem('theme', 'dark|light')`

### 8.2 프로바이더 선택
- 라디오 버튼: EODHD / Twelve Data / Massive
- 선택된 프로바이더의 가격만 표시
- SSE 수신은 모두 받되, 프론트엔드에서 필터링
- `localStorage.setItem('provider', 'eodhd|twelve_data|massive')`

### 8.3 업데이트 간격
- 라디오 버튼: 3초 / 5초 / 10초
- 프론트엔드 쓰로틀링으로 구현 (SSE는 그대로 수신)
- `localStorage.setItem('updateInterval', '3000|5000|10000')`

---

## 9. 리스크 및 고려사항

| 리스크 | 대응 |
|--------|------|
| SSE 연결 끊김 | 자동 재연결 + 초기 가격 REST API 로드 |
| 장시간 실행 메모리 | DOM 요소 최소화, 불필요한 참조 정리 |
| 롤링 애니메이션 성능 | GPU 가속(transform), requestAnimationFrame |
| KRW 그리드 계산 부하 | 변경된 값만 업데이트 (diff 체크) |
| 번인 방지 시각적 불쾌감 | 1-2px 이하 미세 이동, 사용자 인지 불가 |
| London Fix 데이터 소스 | API 미제공 → 웹사이트 크롤링 (하루 2회) |
| 최초고시환율 데이터 소스 | API 신청 중 → 키 수령 전 플레이스홀더, 수령 후 연동 |

---

## 10. 완료 기준

- [ ] 5개 자산 실시간 가격 카드 정상 표시
- [ ] Toss 스타일 숫자 롤링 애니메이션 동작
- [ ] 가격 상승/하락 플래시 애니메이션 동작
- [ ] KRW 환산 그리드 정확한 계산 및 실시간 업데이트
- [ ] 다크/라이트 모드 토글 동작
- [ ] 프로바이더 선택 기능 동작
- [ ] 업데이트 간격 선택 기능 동작
- [ ] 번인 방지 미세 시프트 동작
- [ ] 모바일 반응형 대응
- [ ] 장시간 실행 안정성 확인 (메모리 누수 없음)
- [ ] IIS 배포 및 도메인 연결 완료
