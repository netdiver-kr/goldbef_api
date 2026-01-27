# 실시간 금융 데이터 비교 시스템

3개 API 제공업체(EODHD, Twelve Data, Massive.com)로부터 **WebSocket**을 통해 골드, 실버, USD/KRW 실시간 가격을 수집하고 비교하는 웹 애플리케이션입니다.

## 주요 기능

- **실시간 데이터 수집**: 3개 API 제공업체로부터 WebSocket으로 동시 연결
- **실시간 가격 비교**: 골드, 실버, USD/KRW 가격을 3개 제공업체별로 동시 표시
- **과거 데이터 조회**: 데이터베이스에 저장된 과거 가격 데이터 스크롤 및 필터링
- **통계 계산**: 평균, 최고, 최저, 스프레드 자동 계산

## 기술 스택

- **Backend**: FastAPI, WebSockets, SQLAlchemy
- **Database**: SQLite (개발) / PostgreSQL (프로덕션)
- **Frontend**: HTML, CSS, JavaScript (Vanilla), Server-Sent Events

## 설치 방법

### 1. 필요 조건

- Python 3.9+
- pip

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env.example`을 복사하여 `.env` 파일을 생성하고 API 키를 입력합니다.

```bash
cp .env.example .env
```

`.env` 파일 수정:
```env
EODHD_API_KEY=your_actual_api_key
TWELVE_DATA_API_KEY=your_actual_api_key
MASSIVE_API_KEY=your_actual_api_key
```

### 4. 데이터베이스 초기화

```bash
python -m app.database.init_db
```

## 실행 방법

### 개발 서버

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

브라우저에서 http://localhost:8000 접속

## 프로젝트 구조

```
c:\Python\API test\
├── app/
│   ├── models/              # 데이터 모델
│   ├── services/            # WebSocket 클라이언트 및 비즈니스 로직
│   ├── database/            # DB 연결 및 Repository
│   ├── routers/             # FastAPI 라우터 (API 엔드포인트)
│   ├── utils/               # 유틸리티 함수
│   ├── config.py            # 설정
│   └── main.py              # FastAPI 앱 진입점
├── frontend/
│   ├── index.html           # 메인 페이지
│   └── static/              # CSS, JavaScript
├── tests/                   # 테스트
└── requirements.txt
```

## API 엔드포인트

- `GET /` - 메인 웹 페이지
- `GET /api/stream` - SSE 실시간 가격 스트리밍
- `GET /api/history` - 과거 가격 데이터 조회 (페이지네이션)
- `GET /api/statistics` - 자산별 통계

## 개발 가이드

### WebSocket 클라이언트 개별 테스트

각 API 클라이언트를 개별적으로 테스트할 수 있습니다.

```bash
python -m app.services.eodhd_ws_client
python -m app.services.twelve_data_ws_client
python -m app.services.massive_ws_client
```

### 테스트 실행

```bash
pytest tests/
```

## 라이센스

MIT License
