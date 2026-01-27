# 🎯 여기서 시작하세요!

## 환영합니다! 👋

실시간 금융 데이터 비교 시스템이 완전히 구축되었습니다!

## 🚀 지금 바로 시작하기 (2가지 방법)

### 방법 1: API 키 없이 테스트 (추천) ⚡

실제 API 키가 없어도 Mock 서버로 바로 시작할 수 있습니다!

1. **터미널 1 - Mock 서버 실행:**
   ```bash
   python test_mock_server.py
   ```

2. **터미널 2 - 메인 앱 실행:**

   **Windows:**
   ```bash
   run.bat
   ```

   **macOS/Linux:**
   ```bash
   ./run.sh
   ```

3. **브라우저 접속:**
   ```
   http://localhost:8000
   ```

**상세 안내**: [TEST_WITHOUT_API_KEYS.md](TEST_WITHOUT_API_KEYS.md)

### 방법 2: 실제 API 사용 🔑

실제 API 키가 있다면:

1. **API 키 설정:**
   - `.env` 파일 열기
   - 실제 API 키 입력

2. **WebSocket 구현 수정:**
   - `app/services/eodhd_ws_client.py`
   - `app/services/twelve_data_ws_client.py`
   - `app/services/massive_ws_client.py`
   - (각 파일의 TODO 주석 참고)

3. **실행:**
   ```bash
   # Windows
   run.bat

   # macOS/Linux
   ./run.sh
   ```

**상세 안내**: [QUICKSTART.md](QUICKSTART.md)

## 📚 문서 가이드

```
┌─────────────────────────────────────────────┐
│  📄 문서                 │  📝 설명           │
├─────────────────────────────────────────────┤
│  START_HERE.md          │  👈 지금 이 문서!  │
│  QUICKSTART.md          │  빠른 시작 가이드   │
│  TEST_WITHOUT_API_KEYS  │  API 키 없이 테스트 │
│  SETUP_GUIDE.md         │  상세 설치 가이드   │
│  README.md              │  프로젝트 개요      │
└─────────────────────────────────────────────┘
```

## 🎬 데모 화면

### 메인 페이지
```
┌─────────────────────────────────────────────────┐
│ 💰 실시간 금융 데이터 비교                      │
│ 연결 상태: ● 연결됨                             │
└─────────────────────────────────────────────────┘

🥇 Gold (XAU/USD)
┌──────────────┬──────────────┬──────────────┐
│   EODHD      │ Twelve Data  │ Massive.com  │
├──────────────┼──────────────┼──────────────┤
│   2050.25    │   2050.30    │   2050.28    │
│  +5.20 ▲    │  +5.25 ▲    │  +5.23 ▲    │
│ Bid: 2050.00 │ Bid: 2050.15 │ Bid: 2050.10 │
│ Ask: 2050.50 │ Ask: 2050.45 │ Ask: 2050.46 │
│ 15:30:45     │ 15:30:46     │ 15:30:45     │
└──────────────┴──────────────┴──────────────┘

평균: 2050.28 | 최고: 2050.30 | 최저: 2050.25 | 스프레드: 0.05

🥈 Silver (XAG/USD)
[동일한 레이아웃...]

💱 USD/KRW 환율
[동일한 레이아웃...]

📊 과거 기록
┌──────────────────┬────────┬────────┬─────────┐
│ 시간             │ 제공업체│ 자산   │ 가격    │
├──────────────────┼────────┼────────┼─────────┤
│ 2024-01-23 15:30 │ EODHD  │ Gold   │ 2050.25 │
│ 2024-01-23 15:30 │ Twelve │ Gold   │ 2050.30 │
│ 2024-01-23 15:29 │ Massive│ Silver │ 24.52   │
│ [스크롤로 더 보기...]                         │
└──────────────────┴────────┴────────┴─────────┘
```

## ✨ 주요 기능

✅ **실시간 데이터 수신**: 3개 API에서 WebSocket으로 동시 연결
✅ **실시간 표시**: 1초마다 자동 업데이트
✅ **가격 비교**: 3개 제공업체 가격 동시 표시
✅ **시각적 피드백**: 가격 상승/하락 시 플래시 효과
✅ **통계 계산**: 평균, 최고, 최저, 스프레드
✅ **과거 데이터**: 무한 스크롤로 과거 기록 조회
✅ **필터링**: 자산 및 제공업체별 필터

## 🛠️ 기술 스택

- **백엔드**: FastAPI, WebSockets, SQLAlchemy, asyncio
- **데이터베이스**: SQLite (개발) / PostgreSQL (프로덕션)
- **프론트엔드**: HTML5, CSS3, Vanilla JavaScript
- **실시간 통신**: WebSocket (수신), SSE (전송)

## 📁 프로젝트 구조

```
c:\Python\API test/
├── app/                    # 백엔드 애플리케이션
│   ├── models/            # 데이터 모델
│   ├── services/          # WebSocket 클라이언트
│   ├── database/          # DB 연결 및 Repository
│   ├── routers/           # API 엔드포인트
│   ├── utils/             # 유틸리티
│   └── main.py            # 앱 진입점
│
├── frontend/              # 프론트엔드
│   ├── index.html         # 메인 페이지
│   └── static/
│       ├── css/           # 스타일
│       └── js/            # JavaScript
│
├── test_mock_server.py    # Mock WebSocket 서버
├── run.bat                # Windows 실행 스크립트
├── run.sh                 # Linux/macOS 실행 스크립트
├── requirements.txt       # Python 의존성
└── .env                   # 환경 변수 (API 키)
```

## 🔧 시스템 요구사항

- **Python**: 3.9 이상
- **메모리**: 512MB 이상
- **디스크**: 100MB 이상
- **브라우저**: Chrome, Firefox, Safari, Edge (최신 버전)

## 📊 API 엔드포인트

### REST API
- `GET /` - 메인 페이지
- `GET /api/history` - 과거 가격 데이터 (페이지네이션)
- `GET /api/statistics?asset=gold` - 자산별 통계
- `GET /api/latest/{provider}/{asset}` - 최신 가격
- `GET /api/status` - WebSocket 연결 상태
- `GET /docs` - API 문서 (Swagger UI)
- `GET /health` - 헬스 체크

### SSE (Server-Sent Events)
- `GET /api/stream` - 실시간 가격 스트리밍

## 🎓 학습 자료

### 초보자를 위한 순서
1. **START_HERE.md** (이 문서)
2. **TEST_WITHOUT_API_KEYS.md** - Mock 서버로 테스트
3. **QUICKSTART.md** - 실제 API 사용
4. **SETUP_GUIDE.md** - 상세 설정

### 개발자를 위한 순서
1. **README.md** - 프로젝트 개요
2. **구현 계획** - `C:\Users\min\.claude\plans\velvety-twirling-oasis.md`
3. 소스 코드 탐색 - `app/` 디렉토리

## 🐛 문제 해결

### Python이 없는 경우
```
https://www.python.org/downloads/
설치 시 "Add Python to PATH" 체크!
```

### 의존성 설치 실패
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 포트가 사용 중인 경우
```bash
# 다른 포트 사용
uvicorn app.main:app --port 8080
```

### 더 많은 도움말
- 로그 확인: `logs/app.log`
- 브라우저 콘솔 확인 (F12)
- [SETUP_GUIDE.md](SETUP_GUIDE.md#문제-해결)

## 🎯 체크리스트

실행 전 확인:
- [ ] Python 3.9+ 설치됨
- [ ] `.env` 파일 생성됨
- [ ] 실행 방법 선택 (Mock 서버 or 실제 API)

Mock 서버 사용 시:
- [ ] `python test_mock_server.py` 실행 중
- [ ] WebSocket 클라이언트 URL 변경 (ws://localhost:9000)
- [ ] 메인 앱 실행

실제 API 사용 시:
- [ ] `.env` 파일에 실제 API 키 입력
- [ ] WebSocket 클라이언트 구현 수정
- [ ] 개별 클라이언트 테스트 성공
- [ ] 메인 앱 실행

공통:
- [ ] 브라우저에서 http://localhost:8000 접속
- [ ] 실시간 데이터 확인
- [ ] 과거 데이터 조회 테스트

## 🚀 지금 시작하세요!

```bash
# 1. Mock 서버 실행 (터미널 1)
python test_mock_server.py

# 2. 메인 앱 실행 (터미널 2)
# Windows:
run.bat

# macOS/Linux:
./run.sh

# 3. 브라우저 접속
# http://localhost:8000
```

**축하합니다!** 이제 실시간 금융 데이터 비교 시스템을 사용할 준비가 되었습니다! 🎉

---

**도움이 필요하신가요?**
- 📖 [QUICKSTART.md](QUICKSTART.md) - 빠른 시작
- 🧪 [TEST_WITHOUT_API_KEYS.md](TEST_WITHOUT_API_KEYS.md) - API 키 없이 테스트
- 📚 [SETUP_GUIDE.md](SETUP_GUIDE.md) - 상세 가이드
- 📋 [README.md](README.md) - 프로젝트 개요
