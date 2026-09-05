# SSAFY 규정 RAG 챗봇

![EnjoyTrip RAG 챗봇 실행 화면](./clients/assets/enjoytrip-demo.gif)

SSAFY 생활 규정과 사용자가 업로드한 문서를 검색해 답변하는 웹 챗봇입니다. 정적 HTML/CSS/JavaScript 클라이언트가 FastAPI 서버를 호출하고, 서버는 LangGraph로 일반 대화와 RAG(Retrieval-Augmented Generation) 흐름을 분기합니다.

> 생성형 AI API 호출, 비동기 웹 통신, 문서 청킹·임베딩·검색, 검색 결과 기반 답변 생성의 전체 흐름을 학습하기 위한 프로젝트입니다.

## 주요 기능

- **일반 AI 대화**: RAG를 끄면 문서 검색 없이 LLM이 바로 답변합니다.
- **문서 기반 질의응답**: RAG를 켜면 질문과 유사한 문서 청크 최대 5개를 검색합니다.
- **동적 문서 업로드**: `.txt`, `.md`, `.pdf`를 저장하고 즉시 청킹·임베딩합니다.
- **출처 표시**: RAG 답변 아래에 검색된 문서 파일명을 표시합니다.
- **벡터 DB 초기화**: 화면이나 API에서 Chroma 컬렉션을 비울 수 있습니다.
- **RAG 품질 평가**: Ragas로 충실도, 답변 관련성, 문맥 재현율·정밀도를 평가합니다.
- **CORS 실습**: simple request와 preflight request 예제 API를 제공합니다.

## 동작 구조

```text
브라우저 (clients/)
  ├─ 질문 + RAG 여부 ───────────── POST /chat
  ├─ txt/md/pdf ───────────────── POST /upload
  └─ 초기화 요청 ──────────────── POST /reset-db
                        │
                        ▼
FastAPI (servers/main.py)
  ├─ RAG OFF: 일반 프롬프트 ──────────────┐
  └─ RAG ON                               │
       질문 임베딩 → Chroma 유사도 검색   │
       → 상위 5개 청크 → RAG 프롬프트     │
                                           ▼
                            OpenAI 호환 Chat API
                                           │
                      답변 + 출처 ◀────────┘
```

LangGraph는 `START`에서 `use_rag`를 확인합니다. `true`이면 `retrieve → generate`, `false`이면 검색을 건너뛰고 `generate`로 이동한 뒤 `END`에서 종료합니다.

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Frontend | HTML5, CSS3, JavaScript (Fetch API) |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic |
| AI | LangChain, LangGraph, OpenAI 호환 API |
| RAG | OpenAI Embeddings, ChromaDB, RecursiveCharacterTextSplitter |
| 문서 처리 | PyMuPDF (`PyMuPDFLoader`), `TextLoader` |
| 평가 | Ragas, pandas |

## 프로젝트 구조

```text
EnjoyTrip_ChatBot/
├─ clients/
│  ├─ index.html                 # 챗봇·업로드 UI
│  ├─ index_v0.html              # 초기 UI 버전
│  ├─ script.js                  # 채팅, 업로드, DB 초기화 API 호출
│  ├─ style.css                  # 화면 스타일
│  └─ sample_data/RAG_TEST.txt   # RAG 동작 확인용 샘플
├─ servers/
│  ├─ main.py                    # FastAPI, LangGraph, RAG 핵심 구현
│  ├─ eval_ragas.py              # Ragas 평가 및 결과 저장
│  ├─ test_cases.json            # 평가 질문과 기준 답변
│  ├─ requirements.txt           # Python 의존성
│  └─ .env.example               # 환경변수 예시
├─ README.md
└─ 고찰보고서.md
```

실행 중 `servers/data`, `servers/chroma_data`, 평가 CSV·Markdown 파일이 생성될 수 있으며 Git에서 제외됩니다.

## 실행 준비

### 1. 요구 사항

- Python 3.12 권장
- OpenAI 호환 API 키와 base URL
- VS Code Live Server 또는 Python 정적 파일 서버

### 2. 가상환경과 의존성

프로젝트 루트의 PowerShell에서 실행합니다.

```powershell
py -3.12 -m venv .\servers\.venv
& .\servers\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r .\servers\requirements.txt
```

가상환경 활성화가 막히면 Python을 직접 호출합니다.

```powershell
& .\servers\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\servers\.venv\Scripts\python.exe -m pip install -r .\servers\requirements.txt
```

### 3. 환경변수

```powershell
Copy-Item .\servers\.env.example .\servers\.env
```

`servers/.env`를 열어 값을 설정합니다.

```dotenv
API_KEY=replace-with-your-api-key
base_url=https://gms.ssafy.io/gmsapi/api.openai.com/v1
GPT_MODEL=gpt-5-mini
EMBEDDING_MODEL_NAME=text-embedding-3-large
```

API 키는 소스 코드나 커밋에 넣지 마세요. `.env`는 Git에서 제외됩니다.

## 실행 방법

### 1. 백엔드

`main.py`가 `./data`, `./chroma_data` 상대 경로를 사용하므로 **반드시 `servers`에서 실행**합니다.

```powershell
cd .\servers
& .\.venv\Scripts\python.exe .\main.py
```

- API: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`

프로젝트 루트에서 `python servers/main.py`를 실행하면 루트에 별도 데이터 경로가 만들어질 수 있습니다.

### 2. 프런트엔드

별도 PowerShell을 프로젝트 루트에서 엽니다.

```powershell
& .\servers\.venv\Scripts\python.exe -m http.server 5500
```

`http://127.0.0.1:5500/clients/index.html`에 접속합니다. 또는 `clients/index.html`을 Live Server로 엽니다.

서버 CORS는 `http://127.0.0.1`의 모든 포트를 허용합니다. 프런트엔드를 `localhost`로 열면 origin이 달라 차단될 수 있으므로 `127.0.0.1`을 권장합니다.

## 사용 방법

### 일반 대화

질문을 입력하고 `RAG`를 끈 뒤 전송합니다. 벡터 검색을 하지 않으며 응답의 `source`는 `null`입니다.

### 문서 기반 대화

1. **문서 추가**에서 `.txt`, `.md`, `.pdf`를 선택합니다.
2. **업로드** 후 `업로드 완료!`와 0보다 큰 청크 수를 확인합니다.
3. `RAG`를 켜고 문서 내용에 관해 질문합니다.
4. 답변 하단에서 검색된 파일명을 확인합니다.

### 샘플 검증

`clients/sample_data/RAG_TEST.txt`를 업로드하고 질문합니다.

```text
테스트 행사의 코드네임과 시작 시간, 준비물은 무엇인가요?
```

정상적인 문서 기반 응답에는 `파란여우-739`, `오후 1시 30분`, `파란색 명찰`이 포함되고 출처에는 `RAG_TEST.txt`가 표시됩니다. 표현은 실행마다 달라질 수 있습니다.

## API 명세

| Method | Path | 입력 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/chat` | JSON: `message`, `use_rag` | 일반 또는 RAG 답변 생성 |
| `POST` | `/upload` | multipart: `file` | 문서 저장, 추출, 청킹, 임베딩 |
| `POST` | `/reset-db` | 없음 | Chroma 컬렉션의 모든 문서 삭제 |
| `POST` | `/simpleparam` | form: `message` | CORS simple request 실습 |
| `POST` | `/simplejson` | JSON: `message`, `use_rag` | CORS preflight 실습 |

### `/chat` 호출 예시

```powershell
$body = @{
    message = "교육 시간은 어떻게 되나요?"
    use_rag = $true
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body $body
```

```json
{
  "answer": "문서를 바탕으로 생성된 답변",
  "source": "업로드한_문서.txt"
}
```

## RAG 처리 상세

1. 파일을 `servers/data`에 저장합니다.
2. PDF는 페이지 단위로, 텍스트·Markdown은 UTF-8 문서로 읽습니다.
3. 500자 단위, 50자 중첩으로 분할합니다.
4. 청크를 임베딩해 `ssafy_docs` Chroma 컬렉션에 추가합니다.
5. 질문을 임베딩하고 cosine 공간에서 최대 5개 청크를 검색합니다.
6. 검색 문맥과 질문으로 짧은 근거 기반 답변을 생성합니다.
7. 검색된 문서 파일명을 중복 제거해 출처로 반환합니다.

현재 `score_threshold=0.00`이라 관련성 필터링은 매우 느슨합니다. 품질을 높이려면 평가 결과에 따라 threshold, `k`, 청크 크기와 분리자를 조정해야 합니다.

## Ragas 평가

평가는 API 비용이 발생할 수 있습니다. `servers/data/SSAFY_GUIDE.md`가 있으면 빈 DB에 자동 적재합니다. 파일도 기존 Chroma 데이터도 없으면 결과가 유효하지 않을 수 있습니다.

```powershell
cd .\servers
& .\.venv\Scripts\python.exe .\eval_ragas.py
```

- **Faithfulness**: 답변이 검색 문맥에 충실한 정도
- **Answer Relevancy**: 답변이 질문과 관련된 정도
- **Context Recall**: 필요한 근거가 검색 문맥에 포함된 정도
- **Context Precision**: 검색 문맥 중 유용한 근거의 비율

상세 결과는 `ragas_eval_results.csv`, 실행 이력은 `ragas_eval_history.md`에 저장되며 둘 다 Git에서 제외됩니다.

## 데이터 초기화와 종료

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/reset-db
```

정상 종료 시 `servers/chroma_data`가 자동 삭제됩니다. 원본 `servers/data`는 남지만 시작 시 자동 재색인하지 않으므로 재시작 후 문서를 다시 업로드해야 합니다.

## 문제 해결

### 참고 문서에 없다는 답만 나오는 경우

- 업로드 응답의 `success`가 `true`, `chunks_added`가 0보다 큰지 확인합니다.
- `RAG`가 켜져 있는지 확인합니다.
- 백엔드 터미널의 `RAG 통합 검색 결과`를 확인합니다.
- 서버를 재시작했다면 문서를 다시 업로드합니다.

### 서버 연결 실패

- `http://127.0.0.1:8000/docs`가 열리는지 확인합니다.
- 백엔드 실행 위치, `.env`, 8000번 포트를 확인합니다.
- 프런트엔드를 `http://127.0.0.1:...`로 열었는지 확인합니다.

### PDF 업로드 실패

스캔 이미지만 있는 PDF는 텍스트가 추출되지 않을 수 있습니다. OCR은 현재 구현에 포함되지 않았습니다.

## 현재 한계

- 관련성 임계값이 0이라 약하게 관련된 청크도 문맥에 포함될 수 있습니다.
- 모든 문서에 고정 500자 청킹을 사용해 표·제목·문단 구조가 깨질 수 있습니다.
- 동일 파일을 다시 업로드하면 청크가 중복 추가됩니다.
- 파일 크기 제한, 안전한 파일명 처리, 인증·권한, 호출 제한이 없습니다.
- 동기 API에서 외부 모델을 호출해 긴 요청이 작업자를 점유할 수 있습니다.
- 종료 시 벡터 DB를 삭제하고 시작 시 재색인하지 않아 영속성이 불완전합니다.
- 자동화된 단위·통합 테스트와 고정 평가 기준선이 없습니다.

상세 분석은 [고찰보고서.md](./고찰보고서.md)를 참고하세요.

## 커밋 전 확인

```powershell
git status --short
git check-ignore -v .\servers\.env
git check-ignore -v .\servers\.venv
git check-ignore -v .\servers\chroma_data
git check-ignore -v .\servers\data
```

비밀 키, 가상환경, 실행 데이터, 평가 결과, 캐시 파일이 커밋되지 않아야 합니다.
