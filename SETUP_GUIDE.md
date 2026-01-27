# 실시간 금융 데이터 비교 시스템 설치 및 실행 가이드

## 📋 목차

1. [시스템 요구사항](#시스템-요구사항)
2. [설치 단계](#설치-단계)
3. [API 설정](#api-설정)
4. [실행 방법](#실행-방법)
5. [테스트](#테스트)
6. [문제 해결](#문제-해결)

## 시스템 요구사항

- **Python**: 3.9 이상
- **운영체제**: Windows, macOS, Linux
- **메모리**: 최소 512MB RAM
- **디스크**: 최소 100MB 여유 공간

## 설치 단계

### 1. Python 가상 환경 생성 (권장)

```bash
python -m venv venv
```

### 2. 가상 환경 활성화

**Windows:**
```bash
venv\Scripts\activate
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

## API 설정

### 1. 환경 변수 파일 생성

`.env.example` 파일을 복사하여 `.env` 파일을 생성합니다:

```bash
copy .env.example .env   # Windows
# 또는
cp .env.example .env     # macOS/Linux
```

### 2. API 키 입력

`.env` 파일을 편집하여 실제 API 키를 입력합니다:

```env
# API Keys
EODHD_API_KEY=your_actual_eodhd_api_key_here
TWELVE_DATA_API_KEY=your_actual_twelve_data_api_key_here
MASSIVE_API_KEY=your_actual_massive_api_key_here

# Database
DATABASE_URL=sqlite+aiosqlite:///./price_data.db

# Application
DEBUG=True
LOG_LEVEL=INFO
DATA_RETENTION_DAYS=30
```

### 3. API 제공업체별 설정 확인

#### ⚠️ 중요: WebSocket API 문서 확인 필요

각 API 제공업체의 WebSocket 클라이언트 구현을 **실제 API 문서에 맞게 수정**해야 합니다:

1. **EODHD**: `app/services/eodhd_ws_client.py`
   - WebSocket URL 확인
   - 구독 메시지 형식 확인
   - 응답 메시지 형식 확인
   - 심볼 이름 확인 (예: XAUUSD, XAGUSD, USDKRW)

2. **Twelve Data**: `app/services/twelve_data_ws_client.py`
   - WebSocket URL 확인
   - 구독 메시지 형식 확인
   - 응답 메시지 형식 확인
   - 심볼 이름 확인

3. **Massive.com**: `app/services/massive_ws_client.py`
   - WebSocket URL 확인
   - 구독 메시지 형식 확인
   - 응답 메시지 형식 확인
   - 심볼 이름 확인

각 파일에는 `TODO` 주석이 있어 수정이 필요한 부분을 표시하고 있습니다.

## 실행 방법

### 개발 서버 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

또는 Python 모듈로 직접 실행:

```bash
python -m app.main
```

### 브라우저에서 확인

서버가 시작되면 다음 URL로 접속합니다:

- **메인 페이지**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs
- **헬스 체크**: http://localhost:8000/health
- **WebSocket 상태**: http://localhost:8000/api/status

## 테스트

### 1. WebSocket 클라이언트 개별 테스트

각 API 클라이언트를 개별적으로 테스트할 수 있습니다:

```bash
# EODHD 테스트
python -m app.services.eodhd_ws_client

# Twelve Data 테스트
python -m app.services.twelve_data_ws_client

# Massive.com 테스트
python -m app.services.massive_ws_client
```

이 명령어들은 각 API와의 WebSocket 연결을 시도하고, 수신된 메시지를 콘솔에 출력합니다.

### 2. 데이터베이스 확인

SQLite 데이터베이스를 확인하려면:

```bash
sqlite3 price_data.db

# SQLite 쉘에서
SELECT * FROM price_records LIMIT 10;
SELECT COUNT(*) FROM price_records;
SELECT provider, asset_type, MAX(timestamp), price FROM price_records GROUP BY provider, asset_type;
```

### 3. 로그 확인

로그 파일은 `logs/app.log`에 저장됩니다:

```bash
# 실시간 로그 확인 (Windows)
type logs\app.log

# 실시간 로그 확인 (macOS/Linux)
tail -f logs/app.log
```

## API 엔드포인트

### REST API

- `GET /api/history` - 과거 가격 데이터 조회
  - 쿼리 파라미터: `page`, `page_size`, `asset`, `provider`, `start_date`, `end_date`

- `GET /api/statistics?asset={asset}` - 자산별 통계
  - asset: `gold`, `silver`, `usd_krw`

- `GET /api/latest/{provider}/{asset}` - 최신 가격 조회

- `GET /api/status` - WebSocket 연결 상태

### SSE (Server-Sent Events)

- `GET /api/stream` - 실시간 가격 스트리밍

## 문제 해결

### WebSocket 연결 실패

**증상**: 로그에 "WebSocket error" 또는 "Failed to connect" 메시지

**해결 방법**:
1. API 키가 올바른지 확인
2. 각 API 제공업체의 WebSocket 클라이언트 구현 확인
3. 네트워크 연결 확인
4. API 제공업체의 서비스 상태 확인
5. 로그 레벨을 DEBUG로 변경하여 상세 정보 확인:
   ```env
   LOG_LEVEL=DEBUG
   ```

### 데이터베이스 오류

**증상**: "Database error" 또는 "Failed to insert" 메시지

**해결 방법**:
1. 데이터베이스 파일 권한 확인
2. 디스크 공간 확인
3. 데이터베이스 파일 삭제 후 재시작 (개발 환경):
   ```bash
   rm price_data.db  # 기존 데이터 삭제
   ```

### SSE 연결 끊김

**증상**: 브라우저에서 "연결 끊김" 상태 표시

**해결 방법**:
1. 브라우저 콘솔에서 오류 메시지 확인
2. 서버 로그 확인
3. 페이지 새로고침 (자동 재연결 시도)
4. 방화벽/프록시 설정 확인

### API 파싱 오류

**증상**: 로그에 "Error parsing message" 메시지

**해결 방법**:
1. 각 WebSocket 클라이언트의 `parse_message()` 함수 확인
2. 실제 API 응답 형식과 비교
3. 로그의 "Raw message" 출력 확인
4. API 문서를 참고하여 필드 이름 및 형식 수정

## 프로덕션 배포

### PostgreSQL 사용

프로덕션 환경에서는 PostgreSQL 사용을 권장합니다:

1. PostgreSQL 설치
2. 데이터베이스 생성:
   ```sql
   CREATE DATABASE pricedb;
   CREATE USER priceuser WITH PASSWORD 'yourpassword';
   GRANT ALL PRIVILEGES ON DATABASE pricedb TO priceuser;
   ```

3. `.env` 파일 수정:
   ```env
   DATABASE_URL=postgresql+asyncpg://priceuser:yourpassword@localhost:5432/pricedb
   ```

### Gunicorn 사용 (Linux/macOS)

```bash
pip install gunicorn

gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker 사용 (선택사항)

Docker Compose 설정이 필요한 경우 별도로 문의하세요.

## 추가 문서

- **API 문서**: http://localhost:8000/docs (서버 실행 후)
- **README.md**: 프로젝트 개요
- **PLAN.md**: 상세 구현 계획 (`C:\Users\min\.claude\plans\velvety-twirling-oasis.md`)

## 지원

문제가 발생하면 다음을 확인하세요:
1. 로그 파일 (`logs/app.log`)
2. 브라우저 개발자 도구 콘솔
3. API 제공업체의 문서 및 상태 페이지
