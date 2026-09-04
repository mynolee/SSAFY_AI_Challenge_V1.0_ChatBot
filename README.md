# SSAFY 규정 RAG 챗봇

SSAFY 생활 규정 문서(`.txt`, `.md`, `.pdf`)를 업로드하고, ChromaDB 검색 결과를 바탕으로 질문에 답하는 FastAPI 기반 RAG 챗봇입니다.

## 프로젝트 구조

```text
EnjoyTrip_ChatBot/
├─ clients/
│  ├─ index.html
│  ├─ script.js
│  ├─ style.css
│  └─ sample_data/RAG_TEST.txt
└─ servers/
   ├─ main.py
   ├─ requirements.txt
   └─ .env.example
```

`servers/data`와 `servers/chroma_data`는 실행 중 자동 생성되며 Git에 포함되지 않습니다.

## 요구 사항

- Python 3.12 권장
- OpenAI 호환 API 키
- 프런트엔드 실행을 위한 VS Code Live Server 또는 Python 정적 파일 서버

## 1. 저장소 클론 및 가상환경 구성

PowerShell에서 실행합니다.

```powershell
git clone <repository-url>
cd .\EnjoyTrip_ChatBot

py -3.12 -m venv .\servers\.venv
& .\servers\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r .\servers\requirements.txt
```

PowerShell 실행 정책 때문에 가상환경 활성화가 막히면 활성화 없이 가상환경 Python을 직접 사용할 수 있습니다.

```powershell
& .\servers\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\servers\.venv\Scripts\python.exe -m pip install -r .\servers\requirements.txt
```

## 2. 환경변수 설정

예제 파일을 복사합니다.

```powershell
Copy-Item .\servers\.env.example .\servers\.env
```

`servers/.env`를 열어 `API_KEY`를 실제 키로 변경합니다.

```dotenv
API_KEY=replace-with-your-api-key
base_url=https://gms.ssafy.io/gmsapi/api.openai.com/v1
GPT_MODEL=gpt-5-mini
EMBEDDING_MODEL_NAME=text-embedding-3-large
```

`.env`는 Git에서 제외됩니다. API 키를 README, 소스 코드 또는 커밋에 직접 넣지 마세요.

## 3. 백엔드 서버 실행

중요: 현재 코드는 `./data`, `./chroma_data` 같은 상대 경로를 사용하므로 반드시 `servers` 디렉터리에서 실행해야 합니다.

```powershell
cd .\servers
& .\.venv\Scripts\python.exe .\main.py
```

정상적으로 시작되면 다음 주소에서 API가 실행됩니다.

```text
http://127.0.0.1:8000
```

실행 위치는 다음 명령으로 확인할 수 있습니다.

```powershell
Get-Location
```

경로 끝이 `EnjoyTrip_ChatBot\servers`여야 합니다. 프로젝트 루트에서 `python servers/main.py`로 실행하면 다른 `data`, `chroma_data`가 생성될 수 있으므로 사용하지 않습니다.

## 4. 프런트엔드 실행

### VS Code Live Server 사용

`clients/index.html`을 열고 **Open with Live Server**를 실행한 다음 아래 주소에 접속합니다.

```text
http://127.0.0.1:5500/clients/index.html
```

### Python 정적 파일 서버 사용

백엔드 터미널과 별도의 PowerShell을 열고 프로젝트 루트에서 실행합니다.

```powershell
cd C:\path\to\EnjoyTrip_ChatBot
& .\servers\.venv\Scripts\python.exe -m http.server 5500
```

그다음 아래 주소에 접속합니다.

```text
http://127.0.0.1:5500/clients/index.html
```

## 5. 문서 업로드 및 RAG 테스트

1. 화면 상단의 **문서 추가**를 누릅니다.
2. `clients/sample_data/RAG_TEST.txt`를 선택하고 업로드합니다.
3. 반드시 `업로드 완료!` 메시지와 0보다 큰 청크 수를 확인합니다.
4. 입력창 옆의 **RAG** 체크박스를 체크합니다.
5. 다음 질문을 입력합니다.

```text
테스트 행사의 코드네임과 시작 시간, 준비물은 무엇인가요?
```

정상 응답에는 `파란여우-739`, `오후 1시 30분`, `파란색 명찰`이 포함되며 출처가 `RAG_TEST.txt`로 표시됩니다. 백엔드 터미널에도 `RAG 통합 검색 결과`와 검색된 문서 내용이 출력됩니다.

### API로 직접 검증

브라우저 문제와 백엔드 문제를 분리하려면 별도 PowerShell에서 실행합니다.

```powershell
$body = @{
    message = "테스트 행사의 코드네임과 시작 시간, 준비물은 무엇인가요?"
    use_rag = $true
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body $body
```

정상일 때 응답의 `source`는 `RAG_TEST.txt`입니다. `ChatGPT 일반 지식`이 나오면 문서가 현재 서버의 ChromaDB에 적재되지 않은 상태입니다.

## 6. DB 초기화 및 종료

서버가 실행 중일 때 별도 PowerShell에서 DB를 초기화할 수 있습니다.

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/reset-db
```

서버 터미널에서 `Ctrl+C`를 눌러 종료합니다. 현재 구현은 정상 종료 시 `servers/chroma_data`를 삭제하므로 서버를 다시 시작한 뒤에는 문서를 다시 업로드해야 합니다.

## 문제 해결

### `문의 사항은 참고 문서에 없습니다.`가 계속 나오는 경우

- 백엔드를 `servers` 디렉터리에서 실행했는지 확인합니다.
- 업로드 응답이 `success: true`이고 `chunks_added`가 0보다 큰지 확인합니다.
- RAG 체크박스가 체크되어 있는지 확인합니다.
- 백엔드 터미널의 `RAG 통합 검색 결과`와 출처를 확인합니다.
- 서버를 재시작했다면 문서를 다시 업로드합니다.

### 서버 연결 실패

- `http://127.0.0.1:8000/docs`가 열리는지 확인합니다.
- 8000번 포트를 다른 프로세스가 사용 중인지 확인합니다.
- `servers/.env`의 API 키와 모델 설정을 확인합니다.

## 커밋 전 확인

```powershell
git status --short
git check-ignore -v .\servers\.env
git check-ignore -v .\servers\.venv
git check-ignore -v .\servers\chroma_data
```

`.env`, `.venv`, `chroma_data`, `data`, `__pycache__`가 커밋 목록에 없어야 합니다.
