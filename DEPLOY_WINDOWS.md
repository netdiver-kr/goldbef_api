# Windows Server 배포 가이드

## 1. 사전 준비

### Python 설치
1. https://www.python.org/downloads/ 에서 Python 3.10+ 다운로드
2. 설치 시 **"Add Python to PATH"** 체크 필수
3. 확인: `python --version`

### 프로젝트 파일 복사
프로젝트 폴더를 서버로 복사 (예: `C:\Apps\api-test`)

---

## 2. 가상환경 및 패키지 설치

```powershell
cd C:\Apps\api-test

# 가상환경 생성
python -m venv venv

# 가상환경 활성화
.\venv\Scripts\Activate.ps1

# 패키지 설치
pip install -r requirements.txt
```

---

## 3. 환경변수 설정

`.env` 파일 생성 (또는 수정):

```env
EODHD_API_KEY=your_api_key_here
TWELVE_DATA_API_KEY=your_api_key_here
DATABASE_URL=sqlite:///./data/prices.db
```

---

## 4. 실행 테스트

```powershell
# 가상환경 활성화 상태에서
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

브라우저에서 `http://서버IP:8000` 접속 확인

---

## 5. Windows 서비스로 등록 (NSSM 사용)

### NSSM 설치
1. https://nssm.cc/download 에서 다운로드
2. `nssm.exe`를 `C:\Windows\System32`에 복사

### 서비스 등록

```powershell
# 관리자 권한 PowerShell에서 실행
nssm install PriceAPI
```

NSSM GUI에서 설정:
- **Path**: `C:\Apps\api-test\venv\Scripts\python.exe`
- **Startup directory**: `C:\Apps\api-test`
- **Arguments**: `-m uvicorn app.main:app --host 0.0.0.0 --port 8000`

### 서비스 관리

```powershell
# 서비스 시작
nssm start PriceAPI

# 서비스 중지
nssm stop PriceAPI

# 서비스 재시작
nssm restart PriceAPI

# 서비스 상태 확인
nssm status PriceAPI

# 서비스 삭제 (필요시)
nssm remove PriceAPI confirm
```

---

## 6. 방화벽 설정

```powershell
# 관리자 권한 PowerShell에서
New-NetFirewallRule -DisplayName "Price API" -Direction Inbound -Port 8000 -Protocol TCP -Action Allow
```

---

## 7. (선택) IIS 리버스 프록시 설정

### URL Rewrite 모듈 설치
1. https://www.iis.net/downloads/microsoft/url-rewrite 에서 다운로드
2. ARR (Application Request Routing) 설치

### IIS 설정
1. IIS 관리자 열기
2. 새 웹사이트 생성 (포트 80 또는 443)
3. URL Rewrite 규칙 추가:

```xml
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="ReverseProxy" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite" url="http://localhost:8000/{R:1}" />
        </rule>
      </rules>
    </rewrite>
  </system.webServer>
</configuration>
```

---

## 8. 로그 확인

NSSM 로그 설정 (서비스 등록 시):
- **I/O 탭** → Output (stdout): `C:\Apps\api-test\logs\service.log`
- **I/O 탭** → Error (stderr): `C:\Apps\api-test\logs\error.log`

```powershell
# 로그 폴더 생성
mkdir C:\Apps\api-test\logs
```

---

## 9. 자동 시작 설정

NSSM으로 등록된 서비스는 기본적으로 **시스템 시작 시 자동 실행**됩니다.

확인:
```powershell
Get-Service PriceAPI | Select-Object Name, Status, StartType
```

---

## 문제 해결

### 서비스가 시작되지 않을 때
```powershell
# 이벤트 로그 확인
Get-EventLog -LogName Application -Source PriceAPI -Newest 10
```

### 포트 충돌 확인
```powershell
netstat -ano | findstr :8000
```

### 가상환경 경로 확인
서비스 등록 시 반드시 가상환경의 python.exe 경로 사용
