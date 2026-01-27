@echo off
REM Windows용 실행 스크립트

echo ====================================
echo 실시간 금융 데이터 비교 시스템
echo ====================================
echo.

REM Python 버전 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo Python 3.9 이상을 설치해주세요: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] Python 버전 확인...
python --version

REM .env 파일 확인
if not exist .env (
    echo.
    echo [경고] .env 파일이 없습니다.
    echo .env.example을 복사하여 .env 파일을 생성합니다...
    copy .env.example .env
    echo.
    echo .env 파일을 열어서 실제 API 키를 입력해주세요!
    echo 편집 후 이 스크립트를 다시 실행하세요.
    pause
    exit /b 1
)

REM 가상 환경 확인 및 생성
if not exist venv (
    echo.
    echo [2/4] 가상 환경 생성 중...
    python -m venv venv
    if errorlevel 1 (
        echo [오류] 가상 환경 생성 실패
        pause
        exit /b 1
    )
    echo 가상 환경이 생성되었습니다.
) else (
    echo [2/4] 가상 환경 확인 완료
)

REM 가상 환경 활성화
echo.
echo [3/4] 가상 환경 활성화...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [오류] 가상 환경 활성화 실패
    pause
    exit /b 1
)

REM 의존성 설치 확인
echo.
echo [4/4] 의존성 확인 중...
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo 의존성이 설치되어 있지 않습니다. 설치 중...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [오류] 의존성 설치 실패
        pause
        exit /b 1
    )
) else (
    echo 의존성 확인 완료
)

REM 서버 실행
echo.
echo ====================================
echo 서버 시작 중...
echo ====================================
echo.
echo 브라우저에서 다음 주소로 접속하세요:
echo   http://localhost:8000
echo.
echo API 문서:
echo   http://localhost:8000/docs
echo.
echo 종료하려면 Ctrl+C를 누르세요.
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
