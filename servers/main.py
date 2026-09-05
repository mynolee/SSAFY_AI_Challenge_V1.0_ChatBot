import os
import warnings
warnings.filterwarnings("ignore")


# transformers 및 huggingface 캐시 관련 경고 방지
if "HF_HOME" not in os.environ and "TRANSFORMERS_CACHE" not in os.environ:
    os.environ["HF_HOME"] = os.path.expanduser("~/.cache/huggingface")

import shutil
from pathlib import Path
from contextlib import asynccontextmanager
from typing import TypedDict, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_community.document_loaders import PyMuPDFLoader, TextLoader
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

# LangGraph Core 임포트
from langgraph.graph import StateGraph, START, END

# .env 로드
load_dotenv()

# ==========================================
# [설정 영역]
# ==========================================
# ==========================================
# TODO: 01 .env에서 사용자 환경에 맞게 수정하세요. 
# ==========================================
OPENAI_API_KEY = os.getenv("API_KEY", "키를 입력하세요.")   # .env의 API_KEY 로드
BASE_URL = os.getenv("base_url")
GPT_MODEL = os.getenv("GPT_MODEL", "gpt-5-mini")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")

DATA_DIR = Path("./data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 500               # 텍스트를 분할할 글자 수 (청크 크기)
OVERLAP = 50                   # 청크 간 겹치게 할 글자 수 (문맥 보존용)
CHROMA_DB_PATH = "./chroma_data" # ChromaDB가 파일로 저장될 로컬 디렉토리 경로

# ==========================================
# [전역 변수] 서버 실행 중 메모리에 유지될 객체들
# ==========================================
llm = None                  # OpenAI 연결 클라이언트
embeddings = None           # 임베딩 모델 (텍스트 -> 벡터 변환)
vectorstore = None          # Chroma VectorStore 객체
prompt_template = None      # ChatPromptTemplate 객체 (RAG 전용)
prompt_template_general = None  # ChatPromptTemplate 객체 (일반 대화용)
rag_workflow = None         # 컴파일된 LangGraph RAG 에이전트 애플리케이션
prompt_template_fishing = None  # ChatPromptTemplate 객체 (낚시 지역 RAG 전용)
prompt_template_fishing_general = None  # ChatPromptTemplate 객체 (낚시 일반지식 폴백용)
fishing_workflow = None     # 컴파일된 낚시 지역 RAG 워크플로우


# ==========================================
# [LangGraph State 정의]
# ==========================================
class RAGState(TypedDict):
    question: str         # 사용자 질문
    context: str          # 유사도 검색을 통해 조립된 본문 컨텍스트
    answer: str           # LLM이 생성한 최종 답변
    source: str           # 정밀 답변 출처 태그
    use_rag: bool         # RAG 사용 여부 제어 플래그

# ==========================================
# [LangGraph Node 정의]
# ==========================================
def retrieve_node(state: RAGState) -> RAGState:
    """[Retrieve Node]: 질문(question)을 받아 관련 문서를 책장에서 검색한 뒤 컨텍스트(context)를 조립합니다."""
    question = state["question"]

    # 유사도 스코어(0.0~1.0)와 함께 검색 실행
    docs_with_scores = vectorstore.similarity_search_with_relevance_scores(
        question,
        k=5,
        score_threshold=0.00
    )

    # 터미널 디버그용 출력 (점수 정보 추가)
    print("\n--- [RAG 통합 검색 결과] ---")
    for i, (doc, score) in enumerate(docs_with_scores):
        print(f"[{i+1}위] 점수: {score:.4f} | 출처: {doc.metadata.get('source', '알 수 없음')}")
        print(f"   내용: {doc.page_content.strip()}...")
    print("----------------------------\n")

    # 튜플 리스트에서 문서 객체 리스트 분리
    docs = [doc for doc, _ in docs_with_scores]

    # 검색 결과를 문자열로 포맷팅
    context = "\n\n".join([doc.page_content for doc in docs])

    # 출처 태그 조립 (기존 API 규격 유지용)
    source_tag = ", ".join(sorted({doc.metadata.get("source", "알 수 없음") for doc in docs})) if docs else "ChatGPT 일반 지식"

    return {
        "context": context,
        "source": source_tag
    }

def generate_node(state: RAGState) -> RAGState:
    """[Generate Node]: 검색된 참고문서(context)를 기반으로 사용자 질문(question)에 답변을 생성합니다."""
    question = state["question"]
    context = state.get("context", "")
    use_rag = state.get("use_rag", True)

    # RAG 사용 유무와 컨텍스트 탑재 상태에 따라 적절한 프롬프트 체인을 분기하여 호출
    if use_rag :
        # RAG 모드 프롬프트 실행
        response = (prompt_template | llm).invoke({"context": context, "question": question})
    else:
        # 일반 대화 모드 프롬프트 실행 (Chroma 검색 우회 시)
        response = (prompt_template_general | llm).invoke({"question": question})

    return {
        "answer": response.content
    }

# ==========================================
# [LangGraph RAG 워크플로우 빌드]
# ==========================================
def route_by_rag_flag(state: RAGState) -> str:
    """use_rag 플래그에 따라 다음 실행할 노드를 결정하는 조건부 라우터 함수"""
    if state.get("use_rag", True):
        return "retrieve"
    return "generate"

def build_rag_graph():
    # TODO: 03. workflow를 구성하고 compile 해서 반환하시오.
    #  workflow 생성
    workflow = StateGraph(RAGState)
    #  노드 추가
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate",generate_node)
    #  조건부 엣지 정의 (START에서 use_rag 분기에 따라 retrieve 혹은 generate로 바로 이동)
    workflow.add_conditional_edges(
        START,
        route_by_rag_flag,
        {
            "retrieve":"retrieve",
            "generate":"generate"
        }
    )
    #  나머지 엣지 정의
    workflow.add_edge("retrieve","generate"),
    workflow.add_edge("generate",END)
    #  컴파일 후 반환
    return workflow.compile()

    # END

# ==========================================
# [낚시 지역 RAG] 지역 선택 기반 낚시 정보 RAG
#  - 기존 RAG 워크플로우(build_rag_graph)는 그대로 두고, 낚시 전용 그래프를 따로 둔다.
#  - index_fishing.html에서 도/시를 고르면 그 지역명이 검색 쿼리와 프롬프트에 함께 들어간다.
# ==========================================
# 멀티턴 대화용 (기존 import 줄은 건드리지 않고 이 블록에서만 추가로 가져온다)
from langchain_core.prompts import MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

FISHING_TOP_K = 8          # 낚시 질문은 규제+낚시터+포인트를 함께 봐야 해서 넉넉히 검색
FISHING_MIN_SCORE = 0.20   # 이 점수에 못 미치면 '검색 실패'로 보고 LLM 일반지식으로 답한다
FISHING_HISTORY_MAX = 8    # 직전 8개 메시지(약 4턴)까지 대화 맥락으로 사용


class FishingRAGState(TypedDict):
    question: str      # 사용자 질문 원문
    region: str        # 선택한 시/도 (예: 경상남도)
    city: str          # 선택한 시/군/구 (예: 김해시)
    history: list      # 이전 대화 [{"role": "user"|"assistant", "content": "..."}]
    use_rag: bool      # RAG 검색 사용 여부
    context: str       # 검색으로 조립된 참고 문서
    sources: str       # 출처 파일명 목록
    mode: str          # "rag"(업로드 문서 근거) 또는 "llm"(모델 일반지식)
    answer: str        # 최종 답변


def to_lc_messages(history) -> list:
    """프런트에서 온 대화 기록을 LangChain 메시지로 변환한다."""
    messages = []
    for item in (history or [])[-FISHING_HISTORY_MAX:]:
        if not isinstance(item, dict):
            continue
        content = (item.get("content") or "").strip()
        if not content:
            continue
        role = (item.get("role") or "").lower()
        messages.append(AIMessage(content=content) if role in ("assistant", "ai", "bot")
                        else HumanMessage(content=content))
    return messages


def fishing_retrieve_node(state: FishingRAGState) -> FishingRAGState:
    """[Fishing Retrieve]: 선택 지역명을 검색 쿼리에 결합해 낚시 관련 문서를 모은다."""
    question = state["question"]
    place = " ".join(x for x in (state.get("region", ""), state.get("city", "")) if x).strip()

    # 지역이 선택되면 '질문 / 규제 / 낚시터·포인트' 3방향으로 나눠 검색해 회수율을 높인다.
    if place:
        queries = [
            f"{place} {question}",
            f"{place} 낚시금지구역 낚시제한구역 낚시통제구역",
            f"{place} 낚시터 낚시포인트 주요어종",
        ]
    else:
        queries = [question]

    collected: Dict[str, Any] = {}
    for query in queries:
        for doc, score in vectorstore.similarity_search_with_relevance_scores(
            query, k=FISHING_TOP_K, score_threshold=0.00
        ):
            key = doc.page_content
            if key not in collected or score > collected[key][1]:
                collected[key] = (doc, score)

    ranked = sorted(collected.values(), key=lambda pair: pair[1], reverse=True)[:FISHING_TOP_K * 2]

    print(f"\n--- [낚시 RAG 검색 결과] 지역: {place or '전체'} / 질문: {question} ---")
    for i, (doc, score) in enumerate(ranked):
        print(f"[{i+1}위] 점수: {score:.4f} | 출처: {doc.metadata.get('source', '알 수 없음')}")
    print("--------------------------------------------\n")

    # 최고 점수가 기준에 못 미치면 '문서에 근거 없음'으로 보고 LLM 일반지식 모드로 넘긴다.
    top_score = ranked[0][1] if ranked else 0.0
    if not ranked or top_score < FISHING_MIN_SCORE:
        print(f"[낚시 RAG] 관련 문서 없음 (최고점수 {top_score:.4f}) -> LLM 일반지식으로 답변합니다.")
        return {"context": "", "sources": "", "mode": "llm"}

    sources = ", ".join(sorted({d.metadata.get("source", "알 수 없음") for d, _ in ranked}))
    return {
        "context": "\n\n".join(doc.page_content for doc, _ in ranked),
        "sources": sources,
        "mode": "rag",
    }


def fishing_generate_node(state: FishingRAGState) -> FishingRAGState:
    """[Fishing Generate]: 참고 문서가 있으면 RAG 프롬프트로, 없으면 일반지식 프롬프트로 답한다."""
    place = " ".join(x for x in (state.get("region", ""), state.get("city", "")) if x).strip()
    history = to_lc_messages(state.get("history"))
    context = state.get("context", "")
    mode = "rag" if context else "llm"

    template = prompt_template_fishing if mode == "rag" else prompt_template_fishing_general
    payload = {
        "place": place or "대한민국 전체",
        "history": history,
        "question": state["question"],
    }
    if mode == "rag":
        payload["context"] = context
    else:
        # 검색을 껐을 때와, 검색했는데 근거를 못 찾았을 때를 구분해 안내한다.
        payload["fallback_reason"] = (
            "업로드된 낚시 자료에서 관련 내용을 찾지 못해 일반 지식으로 안내합니다."
            if state.get("use_rag", True)
            else "자료 검색(RAG)을 끈 상태라 모델의 일반 지식으로 안내합니다."
        )

    response = (template | llm).invoke(payload)
    return {"answer": response.content, "mode": mode}


def route_fishing(state: FishingRAGState) -> str:
    """use_rag 플래그에 따라 검색 노드를 탈지 결정한다."""
    return "retrieve" if state.get("use_rag", True) else "generate"


def build_fishing_graph():
    """낚시 지역 RAG 워크플로우(retrieve -> generate)를 구성해 컴파일한다."""
    workflow = StateGraph(FishingRAGState)
    workflow.add_node("retrieve", fishing_retrieve_node)
    workflow.add_node("generate", fishing_generate_node)
    workflow.add_conditional_edges(START, route_fishing,
                                   {"retrieve": "retrieve", "generate": "generate"})
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)
    return workflow.compile()


def warmup_vectorstore():
    """Chroma 인덱스 파일을 부팅 시점에 미리 만들어 둔다.

    Chroma는 첫 쓰기 때 chroma_data/<컬렉션UUID>/ 폴더와 .bin 파일 4개를 '새로' 만든다.
    이 파일 생성 이벤트가 Live Server 같은 개발용 정적 서버의 자동 새로고침을 건드려서,
    서버 부팅 후 첫 질문 때만 웹페이지가 리로드되는(첫 화면으로 튕기는) 현상이 있었다.
    부팅할 때 더미 문서를 넣었다 지워 인덱스 파일을 먼저 만들어 두면 첫 질문에서는
    파일이 새로 생기지 않으므로 리로드가 발생하지 않는다.
    """
    try:
        warm_id = "__warmup__"
        vectorstore.add_documents(
            [Document(page_content="워밍업용 임시 문서", metadata={"source": "__warmup__"})],
            ids=[warm_id],
        )
        vectorstore.similarity_search("워밍업", k=1)
        vectorstore.delete(ids=[warm_id])
        print("   - Chroma 인덱스 예열 완료 (첫 질문 시 파일 신규 생성 없음)")
    except Exception as e:
        print(f"   - Chroma 인덱스 예열 실패(동작에는 영향 없음): {e}")


# 답변 서식 규칙 (RAG 응답 / 일반지식 응답에 공통 적용)
FISHING_FORMAT_RULES = (
    "[출력 형식] 아래를 반드시 지키세요.\n"
    "- 마크다운 기호(**, ##, 표, 코드블록)를 절대 쓰지 마세요.\n"
    "- 소제목은 다음 네 개만, 이 순서로, 각각 한 줄에 단독으로 씁니다.\n"
    "  ① 낚시 규제\n"
    "  ② 추천 낚시터·포인트\n"
    "  ③ 어종과 시기\n"
    "  ④ 참고 팁\n"
    "- 소제목 아래 각 항목은 '- '로 시작하는 한 줄로 쓰고, 줄 맨 앞에 장소나 대상 이름을 둡니다.\n"
    "- 그 장소의 세부값은 두 칸 들여쓴 '  - 항목: 값' 형태로 한 단계만 더 씁니다.\n"
    "- 한 줄은 최대 60자로 짧게 끊고, 한 줄에 여러 항목을 몰아 쓰지 마세요.\n"
    "- 자료에 없는 소제목은 그 아래에 '- 자료 없음' 한 줄만 씁니다.\n"
    "- 되묻는 제안('원하시면 ~해드릴까요?')이나 인사말은 쓰지 마세요.\n"
    "- 후속 질문이라 일부 항목만 필요하면 그 소제목만 쓰세요.\n\n"
    "[형식 예시]\n"
    "① 낚시 규제\n"
    "- 대포천 (지방하천) — 낚시금지구역\n"
    "  - 구간: 상동면 금동초 앞 ~ 상동 IC 삼거리\n"
    "  - 금지행위: 모든 형태의 낚시, 취사, 야영\n"
    "  - 지정일: 2016-08-01 / 길이: 1.33km\n"
)


def init_fishing_prompt():
    """낚시 지역 안내 전용 프롬프트 템플릿을 생성합니다."""
    return ChatPromptTemplate.from_messages([
        ("system", (
            "당신은 대한민국 낚시 여행을 안내하는 AI 어시스턴트입니다.\n"
            "[참고문서]는 공공데이터 기반의 낚시터 정보, 낚시금지·제한·통제구역, "
            "갯바위/선상 낚시포인트, 해역별 어획 정보입니다.\n\n"
            "규칙:\n"
            "1. 사용자가 선택한 지역은 '{place}'입니다. [참고문서]에서 이 지역에 해당하는 내용을 "
            "우선 사용하고, 다른 지역 내용은 섞지 마세요.\n"
            "2. 해당 지역에 낚시금지·제한·통제구역이 있으면 반드시 답변 맨 앞에 먼저 안내하세요.\n"
            "3. 낚시터·낚시포인트는 이름, 주소나 좌표, 주요어종, 이용요금처럼 "
            "[참고문서]에 실제로 적힌 값만 그대로 사용하세요. 값을 지어내지 마세요.\n"
            "4. [참고문서]에 그 지역 정보가 없으면 '제공된 자료에 해당 지역 정보가 없습니다.'라고 "
            "밝힌 뒤, 자료에 있는 가장 가까운 지역을 대안으로 제시하세요.\n"
            "5. 이전 대화가 있으면 그 맥락을 이어서 답하세요. '거기', '그럼 근처는' 같은 "
            "후속 질문은 직전에 이야기한 지역·장소를 가리킵니다.\n\n"
            + FISHING_FORMAT_RULES +
            "\n[참고문서]\n\n"
            "{context}"
        )),
        MessagesPlaceholder("history"),
        ("user", "{question}")
    ])


def init_fishing_general_prompt():
    """업로드 문서를 근거로 쓰지 못할 때 사용하는 일반지식 프롬프트."""
    return ChatPromptTemplate.from_messages([
        ("system", (
            "당신은 대한민국 낚시 여행을 안내하는 AI 어시스턴트입니다.\n"
            "지금은 업로드된 낚시 자료를 참고하지 않고 모델의 일반 지식으로 답하는 상황입니다.\n\n"
            "규칙:\n"
            "1. 사용자가 선택한 지역은 '{place}'입니다.\n"
            "2. 답변 첫 줄에 '{fallback_reason}'라고 먼저 밝히세요.\n"
            "3. 낚시금지구역·이용요금·좌표처럼 최신 고시나 실제 데이터가 필요한 값은 단정하지 "
            "말고, 확인해야 할 기관(시·군청 담당부서, 공공데이터포털 등)을 함께 안내하세요.\n"
            "4. 이전 대화가 있으면 그 맥락을 이어서 답하세요.\n\n"
            + FISHING_FORMAT_RULES
        )),
        MessagesPlaceholder("history"),
        ("user", "{question}")
    ])


# ==========================================
# [헬퍼 함수] 문서 추출, 청킹, DB 적재
# ==========================================
def extract_documents(file_path: Path) -> list[Document]:
    """파일에서 Document 객체 리스트를 추출합니다. (PyMuPDFLoader 또는 TextLoader 사용)"""
    try:
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            loader = PyMuPDFLoader(str(file_path))
        else:
            loader = TextLoader(str(file_path), encoding="utf-8")

        docs = loader.load()
        # 모든 문서의 metadata에 source 정보로 파일명 저장
        for doc in docs:
            doc.metadata["source"] = file_path.name
        return docs
    except Exception as e:
        print(f"문서 추출 오류: {e}")
    return []

def chunk_documents(documents: list[Document], size=CHUNK_SIZE, overlap=OVERLAP) -> list[Document]:
    """LangChain의 RecursiveCharacterTextSplitter를 사용하여 Document 리스트를 분할합니다."""
    if not documents:
        return []
    # TODO: 04. RecursiveCharacterTextSplitter를 구성해보자.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators = ["\n\n", "\n", ".", " "],
        length_function = len
    )
    result = text_splitter.split_documents(documents)
    print(f"청킹 완료 : ", len(result))
    return result

    # END


def add_to_db(documents: list[Document]) -> int:
    """분할된 Document 객체 리스트를 Chroma DB에 추가합니다."""
    if not documents:
        return 0

    vectorstore.add_documents(documents)
    return len(documents)

def init_vectorstore():
    """Chroma VectorStore 객체를 생성/초기화합니다."""
    global vectorstore
    vectorstore = Chroma(
        collection_name="ssafy_docs",
        embedding_function=embeddings,
        persist_directory=CHROMA_DB_PATH,
        collection_configuration={"hnsw": {"space": "cosine"}}
    )
    return vectorstore

def init_prompt_templates():
    """RAG용 및 일반 대화용 프롬프트 템플릿을 생성합니다."""
    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "당신은 SSAFY 교육 과정을 돕는 AI 어시스턴트입니다.\n"
            "아래의 [참고 문서] 내용을 바탕으로 사용자의 질문에 답변하세요.\n"
            "답변은 필요한 말만 두괄식으로 간략하게 하세요. 불필요한 서론은 생략하세요.\n"
            "[참고문서]에 없는 내용은 '문의 사항은 참고 문서에 없습니다.' 라고만 답하세요.\n\n"
            "[참고문서]\n\n"
            "{context}"
        )),
        ("user", "{question}")
    ])

    general_prompt = ChatPromptTemplate.from_messages([
        ("system", "당신은 SSAFY 교육 과정을 돕는 친절한 AI 어시스턴트입니다. 사용자 질문에 대해 최선을 다해 친절하게 답변해주세요."),
        ("user", "{question}")
    ])
    return rag_prompt, general_prompt

# ==========================================
# [FastAPI 수명주기 초기화]
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global embeddings, llm, vectorstore, prompt_template, prompt_template_general, rag_workflow
    global prompt_template_fishing, prompt_template_fishing_general, fishing_workflow
    print("1. AI 모델 및 클라이언트 초기화 중...")

    # LangChain ChatOpenAI 초기화 (base_url 지원)
    llm = ChatOpenAI(
        model=GPT_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=BASE_URL
    )
    # embedding 모델 초기화
    embeddings = OpenAIEmbeddings(
        model=EMBEDDING_MODEL_NAME,
        api_key=OPENAI_API_KEY,
        base_url=BASE_URL
    )

    # ChromaDB 저장소 초기화 및 연결
    init_vectorstore()

    # 프롬프트 템플릿 초기화
    prompt_template, prompt_template_general = init_prompt_templates()

    # LangGraph 워크플로우 구성 및 컴파일
    print("2. LangGraph RAG 워크플로우 빌드 중...")
    rag_workflow = build_rag_graph()

    # 낚시 지역 RAG 프롬프트 / 워크플로우 초기화
    prompt_template_fishing = init_fishing_prompt()
    prompt_template_fishing_general = init_fishing_general_prompt()
    fishing_workflow = build_fishing_graph()
    warmup_vectorstore()
    print("준비 완료! 서버가 시작되었습니다.")
    yield
    print("서버가 종료됩니다.")
    # [종료 시 클린업] Chroma SQLite 연결을 닫고 물리 폴더 삭제
    if vectorstore is not None:
        if hasattr(vectorstore, "_client"):
            try:
                vectorstore._client.close()
            except Exception:
                pass
    if os.path.exists(CHROMA_DB_PATH):
        shutil.rmtree(CHROMA_DB_PATH)
        print(f"'{CHROMA_DB_PATH}' 폴더가 자동 정리 및 삭제되었습니다.")

def setup_cors(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        # TODO: 02. CORS 설정을 적용합니다. (127.0.0.1의 모든 포트 허용)
        allow_origin_regex = r"http://127\.0\.0\.1(:\d+)?",
        allow_methods=["*"],
        allow_headers=["*"],
        # END
    )

app = FastAPI(lifespan=lifespan)
setup_cors(app)

# API 요청용 스키마
class ChatReq(BaseModel):
    message: str
    use_rag: bool = False     # 기본값으로 RAG 사용을 활성화

class FishingChatReq(BaseModel):
    """index_fishing.html 전용 요청 스키마 (지도에서 고른 지역과 대화 기록이 함께 전달된다)"""
    message: str
    region: str = ""          # 선택한 시/도 (예: 경상남도)
    city: str = ""            # 선택한 시/군/구 (예: 김해시)
    use_rag: bool = True      # False면 검색을 건너뛰고 LLM 일반지식으로만 답한다
    history: list = []        # 이전 대화 [{"role": "user"|"assistant", "content": "..."}]

# ==========================================
# [CORS 테스트 API] Simple vs Preflight 실습
# ==========================================
# 1. Simple Request - form 파라미터 (CORS 프리플라이트 대상 아님)
@app.post("/simpleparam")
def simple_param(message: str = Form(...)):
    print("message: ", message)
    return {
        "type": "simple_request",
        "message": f"받은 메시지: {message}",
        "preflight": "불필요 (application/x-www-form-urlencoded)"
    }

# 2. Preflight 필요 - JSON (CORS 프리플라이트 강제 대상)
@app.post("/simplejson")
def simple_json(req: ChatReq):
    print("message: ", req)
    return {
        "type": "preflight_request",
        "message": f"받은 메시지: {req.message}",
        "preflight": "필요 (application/json)"
    }

# ==========================================
# 통합 채팅 (LangGraph RAG 워크플로우 호출)
# ==========================================
@app.post("/chat")
def chat(req: ChatReq):
    initial_state = {
        "question": req.message,
        "use_rag": req.use_rag,
        "context": "",
        "source": ""
    }

    final_state = rag_workflow.invoke(initial_state)

    return {
        "answer": final_state["answer"],
        "source": final_state.get("source") if req.use_rag else None
    }

# ==========================================
# [API 2] 파일 업로드 (동적 문서 추가)
# ==========================================
@app.post("/upload")
def upload_file(file: UploadFile = File(...)):
    allowed_extensions = {".txt", ".md", ".pdf"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        return {
            "success": False,
            "message": f"지원하지 않는 파일 형식입니다. ({', '.join(allowed_extensions)} 만 허용)"
        }
    try:
        # 파일을 data 폴더에 백업 저장
        save_path = DATA_DIR / file.filename
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 백업된 파일 경로를 전달하여 Document 객체 리스트 추출
        docs = extract_documents(file_path=save_path)
        if not docs:
           return {"success": False, "message": "파일 내용이 없거나 읽을 수 없습니다."}

        # Document 청킹 및 DB 벡터 적재
        chunk_docs = chunk_documents(docs)

        # vdctor store에 데이터 저장
        chunks_added = add_to_db(chunk_docs)
        return {
            "success": True,
            "message": f"'{file.filename}' 업로드 완료! ({chunks_added}개 청크 추가)",
            "chunks_added": chunks_added
        }
    except Exception as e:
        return {"success": False, "message": f"파일 처리 중 오류 발생: {str(e)}"}

# ==========================================
# [API 3] DB 초기화 (Chroma DB 비우기)
# ==========================================
@app.post("/reset-db")
def reset_db():
    try:
        if vectorstore is not None:
            # 컬렉션을 지우고 새로 만드는 대신, 기존 컬렉션 안의 모든 문서 ID를 삭제
            all_ids = vectorstore.get()["ids"]
            if all_ids:
                vectorstore.delete(ids=all_ids)

        return {"success": True, "message": "Chroma DB 데이터가 완전히 초기화되었습니다."}
    except Exception as e:
        return {"success": False, "message": f"DB 초기화 중 오류 발생: {str(e)}"}

# ==========================================
# [API 4] 다중 파일 업로드 (index_fishing.html 전용, 최대 15개)
#  - 기존 /upload는 그대로 두고, 여러 TXT를 한 번에 올릴 수 있는 엔드포인트를 추가한다.
# ==========================================
MAX_UPLOAD_FILES = 15

@app.post("/upload-multi")
def upload_files(files: list[UploadFile] = File(...)):
    allowed_extensions = {".txt", ".md", ".pdf"}

    if not files:
        return {"success": False, "message": "업로드할 파일이 없습니다.", "results": []}
    if len(files) > MAX_UPLOAD_FILES:
        return {
            "success": False,
            "message": f"한 번에 최대 {MAX_UPLOAD_FILES}개까지 업로드할 수 있습니다. "
                       f"(요청: {len(files)}개)",
            "results": []
        }

    results = []
    total_chunks = 0
    for file in files:
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            results.append({
                "filename": file.filename,
                "success": False,
                "chunks_added": 0,
                "message": f"지원하지 않는 형식 ({', '.join(sorted(allowed_extensions))} 만 허용)"
            })
            continue
        try:
            # 파일을 data 폴더에 백업 저장
            save_path = DATA_DIR / file.filename
            with open(save_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            docs = extract_documents(file_path=save_path)
            if not docs:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "chunks_added": 0,
                    "message": "파일 내용이 없거나 읽을 수 없습니다."
                })
                continue

            chunks_added = add_to_db(chunk_documents(docs))
            total_chunks += chunks_added
            results.append({
                "filename": file.filename,
                "success": True,
                "chunks_added": chunks_added,
                "message": f"{chunks_added}개 청크 추가"
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "chunks_added": 0,
                "message": f"처리 중 오류: {str(e)}"
            })

    ok_count = sum(1 for r in results if r["success"])
    return {
        "success": ok_count > 0,
        "message": f"{len(files)}개 중 {ok_count}개 업로드 완료 (총 {total_chunks}개 청크 추가)",
        "total_chunks": total_chunks,
        "results": results
    }

# ==========================================
# [API 5] 낚시 지역 RAG 채팅 (index_fishing.html 전용)
#  - 지도에서 고른 도/시가 검색 쿼리와 프롬프트에 함께 들어간다.
# ==========================================
@app.post("/fishing-chat")
def fishing_chat(req: FishingChatReq):
    initial_state = {
        "question": req.message,
        "region": req.region or "",
        "city": req.city or "",
        "history": req.history or [],
        "use_rag": req.use_rag,
        "context": "",
        "sources": "",
        "mode": "",
        "answer": ""
    }

    try:
        final_state = fishing_workflow.invoke(initial_state)
    except Exception as e:
        return {
            "success": False,
            "answer": f"답변 생성 중 오류가 발생했습니다: {str(e)}",
            "mode": "error",
            "source": None,
            "model": GPT_MODEL,
            "region": " ".join(x for x in (req.region, req.city) if x)
        }

    mode = final_state.get("mode") or "llm"
    return {
        "success": True,
        "answer": final_state["answer"],
        "mode": mode,                                   # "rag" | "llm"
        "rag_searched": req.use_rag,                    # llm일 때 '검색 실패'인지 '검색 끔'인지 구분
        "source": final_state.get("sources") or None,   # rag일 때만 파일명 목록
        "model": GPT_MODEL,
        "region": " ".join(x for x in (req.region, req.city) if x)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
