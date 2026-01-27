# 🚀 빠른 시작 가이드

## 현재 상태

✅ 모든 코드 구현 완료!
- 백엔드 (FastAPI + WebSocket)
- 프론트엔드 (HTML/CSS/JavaScript)
- 데이터베이스 (SQLite)
- 3개 API WebSocket 클라이언트

## 바로 실행하기

### 1단계: API 키 설정 (필수)

`.env` 파일을 열어서 실제 API 키를 입력하세요:

```env
EODHD_API_KEY=실제_EODHD_API_키
TWELVE_DATA_API_KEY=실제_Twelve_Data_API_키
MASSIVE_API_KEY=실제_Massive_API_키
```

**API 키 발급 방법:**
- EODHD: https://eodhistoricaldata.com/r/?ref=3XR4N7ST
- Twelve Data: https://twelvedata.com/
- Massive.com: 해당 사이트에서 가입 후 API 키 발급

### 2단계: 의존성 설치

```bash
pip install -r requirements.txt
```

가상 환경을 사용하는 것을 권장합니다:

```bash
# 가상 환경 생성 및 활성화
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

### 3단계: WebSocket API 구현 수정 (중요!)

⚠️ **필수 작업**: 각 API 제공업체의 WebSocket 문서를 확인하고 다음 파일을 수정해야 합니다:

#### A. EODHD API (`app/services/eodhd_ws_client.py`)

파일을 열고 다음을 확인/수정:

1. **WebSocket URL** (약 54번째 줄):
   ```python
   def get_websocket_url(self) -> str:
       # EODHD 문서에서 실제 WebSocket URL 확인
       return f"wss://실제주소?api_token={self.api_key}"
   ```

2. **구독 메시지** (약 62번째 줄):
   ```python
   def get_subscribe_message(self) -> Dict[str, Any]:
       # EODHD 문서에서 실제 구독 메시지 형식 확인
       return {
           "action": "subscribe",  # 실제 필드명 확인
           "symbols": ["XAUUSD", "XAGUSD", "USDKRW"]  # 실제 심볼명 확인
       }
   ```

3. **메시지 파싱** (약 85번째 줄):
   ```python
   def parse_message(self, raw_message: str) -> Optional[Dict[str, Any]]:
       # EODHD 응답 형식에 맞게 수정
       symbol = data.get('s')  # 실제 필드명 확인
       price = data.get('p')   # 실제 필드명 확인
   ```

#### B. Twelve Data API (`app/services/twelve_data_ws_client.py`)

동일한 방식으로 수정:
- WebSocket URL 확인
- 구독 메시지 형식 확인
- 응답 메시지 파싱 확인

#### C. Massive.com API (`app/services/massive_ws_client.py`)

동일한 방식으로 수정

### 4단계: 개별 테스트 (권장)

각 API 클라이언트를 개별적으로 테스트하여 연결 및 데이터 수신을 확인:

```bash
# EODHD 테스트
python -m app.services.eodhd_ws_client

# Twelve Data 테스트
python -m app.services.twelve_data_ws_client

# Massive.com 테스트
python -m app.services.massive_ws_client
```

**기대 출력:**
```
[eodhd] Connecting to wss://...
[eodhd] Connected successfully
[eodhd] Sent subscribe message
Received data: {'provider': 'eodhd', 'asset_type': 'gold', 'price': 2050.25, ...}
```

### 5단계: 서버 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**기대 출력:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Started WebSocket Manager
INFO:     [eodhd] Connected successfully
INFO:     [twelve_data] Connected successfully
INFO:     [massive] Connected successfully
```

### 6단계: 브라우저 접속

- **메인 페이지**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs
- **연결 상태**: http://localhost:8000/api/status

## 예상 화면

### 메인 페이지
```
┌─────────────────────────────────────────┐
│ 💰 실시간 금융 데이터 비교              │
│ 연결 상태: ● 연결됨                     │
└─────────────────────────────────────────┘

🥇 Gold (XAU/USD)
┌──────────┬──────────┬──────────┐
│  EODHD   │ Twelve   │ Massive  │
├──────────┼──────────┼──────────┤
│ 2050.25  │ 2050.30  │ 2050.28  │
│ +5.20    │ +5.25    │ +5.23    │
└──────────┴──────────┴──────────┘
평균: 2050.28 | 최고: 2050.30 | 최저: 2050.25

(Silver, USD/KRW 섹션도 동일하게 표시)

📊 과거 기록
[필터] [자산] [제공업체] [적용]
시간             제공업체    자산    가격
2024-01-23 15:30 EODHD      Gold    2050.25
2024-01-23 15:29 Twelve     Gold    2050.20
...
```

## 문제 해결

### Python이 설치되지 않은 경우

1. Python 다운로드: https://www.python.org/downloads/
2. 설치 시 "Add Python to PATH" 체크
3. 설치 후 터미널 재시작

### pip 명령어가 작동하지 않는 경우

```bash
python -m pip install -r requirements.txt
```

### WebSocket 연결 실패

1. `.env` 파일의 API 키 확인
2. 각 WebSocket 클라이언트 구현 확인 (URL, 메시지 형식)
3. 로그 확인:
   ```bash
   # 로그 레벨을 DEBUG로 변경
   # .env 파일에서:
   LOG_LEVEL=DEBUG
   ```
4. 로그 파일 확인: `logs/app.log`

### 데이터가 표시되지 않는 경우

1. 브라우저 개발자 도구 열기 (F12)
2. Console 탭에서 오류 확인
3. Network 탭에서 `/api/stream` 요청 확인
4. 서버 로그 확인

## 다음 단계

### 커스터마이징

1. **추가 자산 지원**:
   - 각 WebSocket 클라이언트의 `SYMBOL_MAPPING` 수정
   - 프론트엔드 HTML에 섹션 추가

2. **데이터 보관 기간 변경**:
   ```env
   DATA_RETENTION_DAYS=90  # 90일로 변경
   ```

3. **PostgreSQL 사용** (프로덕션):
   ```env
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/pricedb
   ```

### 프로덕션 배포

1. **Gunicorn 사용** (Linux/macOS):
   ```bash
   pip install gunicorn
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

2. **환경 변수**:
   ```env
   DEBUG=False
   LOG_LEVEL=WARNING
   ```

3. **HTTPS 설정** (Nginx 등)

## 도움말

- **상세 설치 가이드**: [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **프로젝트 개요**: [README.md](README.md)
- **구현 계획**: `C:\Users\min\.claude\plans\velvety-twirling-oasis.md`

## 체크리스트

- [ ] Python 3.9+ 설치 확인
- [ ] `.env` 파일에 실제 API 키 입력
- [ ] `pip install -r requirements.txt` 실행
- [ ] 각 WebSocket 클라이언트 구현 수정
- [ ] 개별 클라이언트 테스트 성공
- [ ] 서버 실행 성공
- [ ] 브라우저에서 실시간 데이터 확인
- [ ] 과거 데이터 조회 테스트

---

**준비 완료!** 이제 위 단계를 따라 실행하시면 됩니다. 🚀
