# 🧪 API 키 없이 테스트하기

실제 API 키가 없어도 Mock 서버를 사용하여 전체 시스템을 테스트할 수 있습니다!

## 방법 1: Mock WebSocket 서버 사용 (추천)

### 1단계: Mock 서버 실행

새 터미널/명령 프롬프트를 열고:

```bash
python test_mock_server.py
```

**출력 예시:**
```
==================================================
Mock WebSocket Price Server
==================================================
Listening on: ws://localhost:9000
Generating mock price data for:
  - XAUUSD (Gold)
  - XAGUSD (Silver)
  - USDKRW (USD/KRW)

Press Ctrl+C to stop
==================================================
```

### 2단계: WebSocket 클라이언트 수정

각 WebSocket 클라이언트를 Mock 서버를 가리키도록 임시 수정:

#### `app/services/eodhd_ws_client.py` 수정

```python
def get_websocket_url(self) -> str:
    # Mock 서버 사용
    return "ws://localhost:9000"
```

#### `app/services/twelve_data_ws_client.py` 수정

```python
def get_websocket_url(self) -> str:
    # Mock 서버 사용
    return "ws://localhost:9000"
```

#### `app/services/massive_ws_client.py` 수정

```python
def get_websocket_url(self) -> str:
    # Mock 서버 사용
    return "ws://localhost:9000"
```

### 3단계: .env 파일 설정

`.env` 파일에 더미 API 키 입력 (실제 키 아님):

```env
EODHD_API_KEY=mock_test_key
TWELVE_DATA_API_KEY=mock_test_key
MASSIVE_API_KEY=mock_test_key
```

### 4단계: 메인 애플리케이션 실행

새 터미널/명령 프롬프트를 열고:

**Windows:**
```bash
run.bat
```

**macOS/Linux:**
```bash
./run.sh
```

또는 직접:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5단계: 브라우저에서 확인

http://localhost:8000 으로 접속하면:

- ✅ 3개 제공업체의 실시간 가격 업데이트
- ✅ 1초마다 자동 갱신
- ✅ 가격 변동 표시 (초록/빨강 플래시)
- ✅ 통계 계산 (평균, 최고, 최저, 스프레드)
- ✅ 과거 데이터 저장 및 조회

## 방법 2: 단일 클라이언트 테스트

개별 WebSocket 클라이언트만 테스트하려면:

### 1단계: Mock 서버 실행

```bash
python test_mock_server.py
```

### 2단계: 클라이언트 수정 및 테스트

```bash
# 위의 "WebSocket 클라이언트 수정" 참고하여 URL 변경 후

# EODHD 테스트
python -m app.services.eodhd_ws_client

# 출력 예시:
# [eodhd] Connecting to ws://localhost:9000
# [eodhd] Connected successfully
# Received data: {'provider': 'eodhd', 'asset_type': 'gold', 'price': 2050.25, ...}
# Received data: {'provider': 'eodhd', 'asset_type': 'silver', 'price': 24.50, ...}
```

## 예상 결과

### Mock 서버 터미널
```
Client connected: ('127.0.0.1', 50234)
Received: {"action": "subscribe", "symbols": ["XAUUSD", "XAGUSD", "USDKRW"]}
```

### 메인 앱 터미널
```
INFO: [eodhd] Connected successfully
INFO: [twelve_data] Connected successfully
INFO: [massive] Connected successfully
DEBUG: Saved price: eodhd - gold = 2050.25
DEBUG: Saved price: twelve_data - silver = 24.52
DEBUG: Saved price: massive - usd_krw = 1320.15
```

### 브라우저
- 연결 상태: **● 연결됨** (초록색)
- 모든 제공업체에서 실시간 가격 업데이트 중
- 가격이 변동할 때마다 초록/빨강 플래시 효과
- 과거 기록 테이블에 데이터 쌓임

## 문제 해결

### Mock 서버가 시작되지 않는 경우

```bash
# websockets 패키지 설치 확인
pip install websockets

# 포트가 사용 중인 경우
# test_mock_server.py에서 port = 9000을 다른 번호로 변경
```

### 클라이언트가 연결되지 않는 경우

1. Mock 서버가 실행 중인지 확인
2. WebSocket URL이 올바른지 확인 (`ws://localhost:9000`)
3. 방화벽 설정 확인

### 데이터가 표시되지 않는 경우

1. 브라우저 개발자 도구 (F12) 확인
2. 서버 로그 확인 (`logs/app.log`)
3. SSE 연결 확인 (Network 탭에서 `/api/stream`)

## 실제 API로 전환하기

테스트 완료 후 실제 API를 사용하려면:

1. **WebSocket URL 복원**: 각 클라이언트 파일에서 원래 URL로 변경
2. **실제 API 키 입력**: `.env` 파일에 실제 API 키 입력
3. **API 문서 확인**: 실제 API의 메시지 형식에 맞게 `parse_message()` 수정
4. **재시작**: 서버 재시작

## 장점

✅ **API 키 불필요**: 실제 API 등록 없이 전체 시스템 테스트
✅ **무료**: 요금 걱정 없이 테스트 가능
✅ **빠른 개발**: 즉시 개발 및 디버깅 가능
✅ **안정적**: 외부 API 의존성 없음

## 다음 단계

Mock 서버로 시스템이 정상 작동하는 것을 확인한 후:

1. 실제 API 제공업체에 가입
2. API 키 발급
3. WebSocket 문서 확인 및 클라이언트 구현 수정
4. 실제 API로 전환

---

**준비 완료!** Mock 서버로 시스템을 테스트해보세요! 🧪
