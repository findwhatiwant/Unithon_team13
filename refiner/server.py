import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from refiner.cli import load_env
from refiner.llm import GeminiClient, LLMClient, LLMError
from refiner.models import Mode, RefineRequest, Tone
from refiner.pipeline import Pipeline
from refiner.supabase_store import SupabaseError, SupabaseStore


load_env()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST_DIR = PROJECT_ROOT / "dist"
FRONTEND_INDEX_PATH = FRONTEND_DIST_DIR / "index.html"
LOCAL_CORS_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:8001",
    "http://localhost:8001",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
]


def _cors_origins() -> list[str]:
    configured = [
        origin.strip().rstrip("/")
        for origin in os.environ.get("REFINER_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    return configured or LOCAL_CORS_ORIGINS

app = FastAPI(title="Message Refiner API", version="0.1.0")
cors_origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

if (FRONTEND_DIST_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="frontend-assets")


OPTIONAL_SCHEMA_COLUMNS = {
    "user_profiles": {"style_profile_message_count"},
    "message_sessions": {"input_tone", "ai_reason", "summary_text"},
    "compose_candidates": {"ai_reason"},
    "mirror_analyses": {"tone_evidence", "ai_reason"},
}


class UserCreateRequest(BaseModel):
    user_id: str | None = None
    email: str | None = None
    nickname: str | None = None
    provider: str = "anonymous"
    style_profile: str | None = None


class UserCreateResponse(BaseModel):
    user_id: str
    email: str | None = None
    nickname: str | None = None
    provider: str
    style_profile: str | None = None


class ConsentRequest(BaseModel):
    user_id: str
    save_message_history: bool = False
    coach_analysis: bool = False
    sensitive_info_storage: bool = False


class ComposeRequest(BaseModel):
    user_id: str | None = None
    recipient: str | None = None
    context: str = Field(..., min_length=1)
    purpose: str | None = None
    tone: str | None = None
    save_history: bool = False


class ComposeCandidate(BaseModel):
    candidate_id: str
    candidate_index: int
    candidate_text: str
    ai_reason: str | None = None


class ComposeResponse(BaseModel):
    session_id: str
    candidates: list[ComposeCandidate]


class MirrorRequest(BaseModel):
    user_id: str | None = None
    session_id: str | None = None
    candidate_id: str | None = None
    text: str = Field(..., min_length=1)
    source_type: Literal["direct_input", "quick_compose_candidate"] = "direct_input"
    recipient: str | None = None
    context: str | None = None
    purpose: str | None = None
    tone: str | None = None
    save_history: bool = False


class MirrorResponse(BaseModel):
    session_id: str
    analysis_id: str
    intent_summary: str
    perceived_tone: str
    tone_evidence: str
    risk_level: str
    risk_reasons: list[str]
    ai_reason: str
    soft_rewrite: str
    clear_rewrite: str
    short_rewrite: str


class RefineAPIRequest(BaseModel):
    user_id: str | None = None
    text: str = Field(..., min_length=1)
    mode: Mode = Mode.POLISH
    tone: Tone | None = None
    context: str | None = None
    save_history: bool = False


class RefineAPIResponse(BaseModel):
    session_id: str
    refined_text: str
    changes: list[str]


class LongReviewRequest(BaseModel):
    user_id: str | None = None
    text: str = Field(..., min_length=1)
    document_type: str | None = None
    purpose: str | None = None
    save_history: bool = False


class LongReviewResponse(BaseModel):
    session_id: str
    edited_text: str
    summary_text: str
    key_points: list[str]
    changes: list[str]
    ai_reason: str


class StyleAnalyzeRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    min_messages: int = 3


class StyleAnalyzeResponse(BaseModel):
    user_id: str
    analyzed_messages: int
    style_profile: str


class RefineLogRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    session_id: str | None = None
    changes: list[str] = Field(default_factory=list)


class ReportRequest(BaseModel):
    user_id: str = Field(..., min_length=1)


class ReportResponse(BaseModel):
    total_reviews: int = 0
    total_corrections: int = 0
    top_mistakes: list[dict[str, Any]] = Field(default_factory=list)
    tone_habits: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    generated_at: str | None = None


class AuthSignUpRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    nickname: str | None = None


class AuthLoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class AuthResponse(BaseModel):
    user_id: str
    email: str | None = None
    nickname: str | None = None
    access_token: str
    refresh_token: str | None = None


def get_store() -> SupabaseStore:
    try:
        return SupabaseStore.from_env()
    except SupabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def get_llm_client() -> LLMClient:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY가 없습니다.")
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    return GeminiClient(api_key=api_key, model=model)


def _llm_error_response(message: str) -> tuple[int, str]:
    if "RESOURCE_EXHAUSTED" in message or "429" in message or "quota" in message.lower():
        return 429, "Gemini 사용량 제한에 도달했어요. 잠시 뒤 다시 시도하거나 다른 API 키/모델을 사용해 주세요."
    return 503, f"AI 호출에 실패했어요: {message}"


def _llm_http_exception(exc: LLMError) -> HTTPException:
    status_code, detail = _llm_error_response(str(exc))
    return HTTPException(status_code=status_code, detail=detail)


@app.post("/api/auth/signup", response_model=AuthResponse)
def auth_sign_up(
    request: AuthSignUpRequest,
    store: SupabaseStore = Depends(get_store),
) -> AuthResponse:
    try:
        data = store.sign_up(request.email.strip(), request.password)
        user = data["user"]
        user_id = user["id"]
        row = store.upsert(
            "user_profiles",
            {
                "id": user_id,
                "email": request.email.strip(),
                "nickname": request.nickname,
                "provider": "email",
            },
            on_conflict="id",
        )
        return AuthResponse(
            user_id=user_id,
            email=row.get("email"),
            nickname=row.get("nickname"),
            access_token=data.get("access_token", ""),
            refresh_token=data.get("refresh_token"),
        )
    except SupabaseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auth/login", response_model=AuthResponse)
def auth_login(
    request: AuthLoginRequest,
    store: SupabaseStore = Depends(get_store),
) -> AuthResponse:
    try:
        data = store.sign_in_with_password(request.email.strip(), request.password)
        user = data.get("user") or {}
        user_id = user.get("id", "")
        if not user_id:
            raise HTTPException(status_code=401, detail="로그인에 실패했습니다.")
        try:
            store.upsert(
                "user_profiles",
                {"id": user_id, "email": request.email.strip(), "provider": "email"},
                on_conflict="id",
            )
        except SupabaseError:
            pass
        return AuthResponse(
            user_id=user_id,
            email=user.get("email"),
            nickname=(user.get("user_metadata") or {}).get("nickname"),
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
        )
    except SupabaseError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "supabase_configured": SupabaseStore.is_configured(),
        "gemini_configured": bool(os.environ.get("GEMINI_API_KEY")),
    }


@app.post("/api/users", response_model=UserCreateResponse)
def create_user(
    request: UserCreateRequest,
    store: SupabaseStore = Depends(get_store),
) -> UserCreateResponse:
    payload = {
        "email": request.email,
        "nickname": request.nickname,
        "provider": request.provider,
    }
    if request.style_profile is not None:
        payload["style_profile"] = request.style_profile
    if request.user_id:
        payload["id"] = request.user_id
        row = store.upsert("user_profiles", payload, on_conflict="id")
    else:
        row = store.insert("user_profiles", payload)
    return UserCreateResponse(
        user_id=row["id"],
        email=row.get("email"),
        nickname=row.get("nickname"),
        provider=row.get("provider", "anonymous"),
        style_profile=row.get("style_profile"),
    )


@app.post("/api/consents")
def save_consent(
    request: ConsentRequest,
    store: SupabaseStore = Depends(get_store),
) -> dict[str, Any]:
    now_field = "consented_at" if request.save_message_history or request.coach_analysis else "revoked_at"
    now = datetime.now(timezone.utc).isoformat()
    row = store.upsert(
        "user_consents",
        {
            "user_id": request.user_id,
            "save_message_history": request.save_message_history,
            "coach_analysis": request.coach_analysis,
            "sensitive_info_storage": request.sensitive_info_storage,
            now_field: now,
        },
        on_conflict="user_id",
    )
    return {"user_id": row["user_id"], "saved": True}


@app.post("/api/compose", response_model=ComposeResponse)
def compose(
    request: ComposeRequest,
    store: SupabaseStore = Depends(get_store),
    client: LLMClient = Depends(get_llm_client),
) -> ComposeResponse:
    started = time.perf_counter()
    try:
        should_save_history = _should_save_history(request.user_id, request.save_history)
        candidates = _generate_compose_candidates(client, request)
        ai_reason = _join_ai_reasons(candidate["ai_reason"] for candidate in candidates)
        session = _insert_with_optional_columns(
            store,
            "message_sessions",
            {
                "user_id": request.user_id,
                "flow_type": "quick_compose",
                "source_type": "direct_input",
                "original_text": None,
                "context": request.context if should_save_history else None,
                "recipient": request.recipient if should_save_history else None,
                "purpose": request.purpose,
                "tone": request.tone,
                "input_tone": None,
                "ai_reason": ai_reason if should_save_history else None,
                "save_history": should_save_history,
            },
        )
        rows = _bulk_insert_with_optional_columns(
            store,
            "compose_candidates",
            [
                {
                    "session_id": session["id"],
                    "candidate_index": index + 1,
                    "candidate_text": candidate["text"] if should_save_history else "[not saved]",
                    "ai_reason": candidate["ai_reason"] if should_save_history else None,
                }
                for index, candidate in enumerate(candidates)
            ],
        )
        _log_ai_request(store, request.user_id, session["id"], "compose", True, started)
        return ComposeResponse(
            session_id=session["id"],
            candidates=[
                ComposeCandidate(
                    candidate_id=row["id"],
                    candidate_index=row["candidate_index"],
                    candidate_text=candidates[index]["text"],
                    ai_reason=candidates[index]["ai_reason"],
                )
                for index, row in enumerate(rows)
            ],
        )
    except LLMError as exc:
        _log_ai_request(store, request.user_id, None, "compose", False, started, str(exc))
        raise _llm_http_exception(exc) from exc
    except (SupabaseError, ValueError) as exc:
        _log_ai_request(store, request.user_id, None, "compose", False, started, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/mirror", response_model=MirrorResponse)
def mirror(
    request: MirrorRequest,
    store: SupabaseStore = Depends(get_store),
    client: LLMClient = Depends(get_llm_client),
) -> MirrorResponse:
    started = time.perf_counter()
    try:
        should_save_history = _should_save_history(request.user_id, request.save_history)
        analysis = _generate_mirror_analysis(client, request)
        session_id = request.session_id
        if session_id:
            _update_with_optional_columns(
                store,
                "message_sessions",
                {
                    "selected_candidate_id": request.candidate_id,
                    "final_text": request.text if should_save_history else None,
                    "input_tone": analysis["perceived_tone"] if should_save_history else None,
                    "ai_reason": analysis["ai_reason"] if should_save_history else None,
                    "save_history": should_save_history,
                },
                {"id": f"eq.{session_id}"},
            )
        else:
            session = _insert_with_optional_columns(
                store,
                "message_sessions",
                {
                    "user_id": request.user_id,
                    "flow_type": "direct_mirror",
                    "source_type": request.source_type,
                    "original_text": request.text if should_save_history else None,
                    "context": request.context if should_save_history else None,
                    "recipient": request.recipient if should_save_history else None,
                    "purpose": request.purpose,
                    "tone": request.tone,
                    "input_tone": analysis["perceived_tone"] if should_save_history else None,
                    "ai_reason": analysis["ai_reason"] if should_save_history else None,
                    "save_history": should_save_history,
                    "final_text": request.text if should_save_history else None,
                },
            )
            session_id = session["id"]

        if request.candidate_id:
            store.update(
                "compose_candidates",
                {"is_selected": True},
                {"id": f"eq.{request.candidate_id}"},
            )

        row = _insert_with_optional_columns(
            store,
            "mirror_analyses",
            {
                "session_id": session_id,
                "analyzed_text": request.text if should_save_history else None,
                "intent_summary": analysis["intent_summary"] if should_save_history else None,
                "perceived_tone": analysis["perceived_tone"] if should_save_history else None,
                "tone_evidence": analysis["tone_evidence"] if should_save_history else None,
                "risk_level": analysis["risk_level"] if should_save_history else None,
                "risk_reasons": analysis["risk_reasons"] if should_save_history else [],
                "ai_reason": analysis["ai_reason"] if should_save_history else None,
                "soft_rewrite": analysis["soft_rewrite"] if should_save_history else None,
                "clear_rewrite": analysis["clear_rewrite"] if should_save_history else None,
                "short_rewrite": analysis["short_rewrite"] if should_save_history else None,
            },
        )
        _log_ai_request(store, request.user_id, session_id, "mirror", True, started)
        if should_save_history and request.user_id:
            maybe_update_style_profile(store, client, request.user_id)
        return MirrorResponse(
            session_id=session_id,
            analysis_id=row["id"],
            intent_summary=analysis["intent_summary"],
            perceived_tone=analysis["perceived_tone"],
            tone_evidence=analysis["tone_evidence"],
            risk_level=analysis["risk_level"],
            risk_reasons=analysis["risk_reasons"],
            ai_reason=analysis["ai_reason"],
            soft_rewrite=analysis["soft_rewrite"],
            clear_rewrite=analysis["clear_rewrite"],
            short_rewrite=analysis["short_rewrite"],
        )
    except LLMError as exc:
        _log_ai_request(store, request.user_id, request.session_id, "mirror", False, started, str(exc))
        raise _llm_http_exception(exc) from exc
    except (SupabaseError, ValueError) as exc:
        _log_ai_request(store, request.user_id, request.session_id, "mirror", False, started, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/refine", response_model=RefineAPIResponse)
def refine(
    request: RefineAPIRequest,
    store: SupabaseStore = Depends(get_store),
    client: LLMClient = Depends(get_llm_client),
) -> RefineAPIResponse:
    try:
        style_profile = _load_style_profile(store, request.user_id)
        result = Pipeline(client).run(
            RefineRequest(
                text=request.text,
                mode=request.mode,
                tone=request.tone,
                context=request.context,
                style_profile=style_profile,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result.success:
        status_code, detail = _llm_error_response(result.error)
        raise HTTPException(status_code=status_code, detail=detail)
    should_save_history = _should_save_history(request.user_id, request.save_history)
    session = _insert_with_optional_columns(
        store,
        "message_sessions",
        {
            "user_id": request.user_id,
            "flow_type": "refine",
            "source_type": "direct_input",
            "original_text": request.text if should_save_history else None,
            "context": request.context if should_save_history else None,
            "tone": request.tone.value if request.tone else None,
            "input_tone": None,
            "ai_reason": _join_ai_reasons(result.changes) if should_save_history else None,
            "save_history": should_save_history,
            "final_text": result.refined_text if should_save_history else None,
        },
    )
    _log_corrections(store, request.user_id, session["id"], result.changes if should_save_history else [])
    if should_save_history and request.user_id:
        maybe_update_style_profile(store, client, request.user_id)
    return RefineAPIResponse(
        session_id=session["id"],
        refined_text=result.refined_text,
        changes=result.changes,
    )


@app.post("/api/long-review", response_model=LongReviewResponse)
def long_review(
    request: LongReviewRequest,
    store: SupabaseStore = Depends(get_store),
    client: LLMClient = Depends(get_llm_client),
) -> LongReviewResponse:
    started = time.perf_counter()
    try:
        result = _generate_long_review(client, request)
        should_save_history = _should_save_history(request.user_id, request.save_history)
        session = _insert_with_optional_columns(
            store,
            "message_sessions",
            {
                "user_id": request.user_id,
                "flow_type": "long_review",
                "source_type": "direct_input",
                "original_text": request.text if should_save_history else None,
                "context": None,
                "purpose": request.document_type or request.purpose,
                "tone": None,
                "input_tone": None,
                "ai_reason": result["ai_reason"] if should_save_history else None,
                "summary_text": result["summary_text"] if should_save_history else None,
                "save_history": should_save_history,
                "final_text": result["edited_text"] if should_save_history else None,
            },
        )
        _log_ai_request(store, request.user_id, session["id"], "long_review", True, started)
        _log_corrections(store, request.user_id, session["id"], result["changes"] if should_save_history else [])
        if should_save_history and request.user_id:
            maybe_update_style_profile(store, client, request.user_id)
        return LongReviewResponse(
            session_id=session["id"],
            edited_text=result["edited_text"],
            summary_text=result["summary_text"],
            key_points=result["key_points"],
            changes=result["changes"],
            ai_reason=result["ai_reason"],
        )
    except LLMError as exc:
        _log_ai_request(store, request.user_id, None, "long_review", False, started, str(exc))
        raise _llm_http_exception(exc) from exc
    except (SupabaseError, ValueError) as exc:
        _log_ai_request(store, request.user_id, None, "long_review", False, started, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _should_save_history(user_id: str | None, save_history: bool) -> bool:
    return bool(user_id and save_history)


def _insert_with_optional_columns(
    store: SupabaseStore,
    table: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        return store.insert(table, payload)
    except SupabaseError as exc:
        if not _is_optional_column_error(exc, table):
            raise
        return store.insert(table, _without_optional_columns(table, payload))


def _bulk_insert_with_optional_columns(
    store: SupabaseStore,
    table: str,
    payload: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    try:
        return store.bulk_insert(table, payload)
    except SupabaseError as exc:
        if not _is_optional_column_error(exc, table):
            raise
        cleaned = [_without_optional_columns(table, row) for row in payload]
        return store.bulk_insert(table, cleaned)


def _update_with_optional_columns(
    store: SupabaseStore,
    table: str,
    payload: dict[str, Any],
    filters: dict[str, str],
) -> list[dict[str, Any]]:
    try:
        return store.update(table, payload, filters)
    except SupabaseError as exc:
        if not _is_optional_column_error(exc, table):
            raise
        return store.update(table, _without_optional_columns(table, payload), filters)


def _is_optional_column_error(exc: SupabaseError, table: str) -> bool:
    message = str(exc)
    return (
        table in OPTIONAL_SCHEMA_COLUMNS
        and "Could not find" in message
        and "schema cache" in message
    )


def _without_optional_columns(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    optional = OPTIONAL_SCHEMA_COLUMNS.get(table, set())
    return {key: value for key, value in payload.items() if key not in optional}


def _join_ai_reasons(reasons: Any) -> str:
    return "\n".join(str(reason).strip() for reason in reasons if str(reason).strip())


@app.post("/api/style/analyze", response_model=StyleAnalyzeResponse)
def analyze_style(
    request: StyleAnalyzeRequest,
    store: SupabaseStore = Depends(get_store),
    client: LLMClient = Depends(get_llm_client),
) -> StyleAnalyzeResponse:
    started = time.perf_counter()
    try:
        rows = store.select(
            "message_sessions",
            filters={
                "user_id": f"eq.{request.user_id}",
                "original_text": "not.is.null",
            },
            order="created_at.desc",
            limit=30,
            columns="original_text",
        )
        texts = [str(row["original_text"]).strip() for row in rows if row.get("original_text")]
        if len(texts) < request.min_messages:
            raise HTTPException(
                status_code=400,
                detail=f"분석할 원본 메시지가 부족합니다 ({len(texts)}개, 최소 {request.min_messages}개 필요).",
            )

        profile = _generate_style_profile(client, texts[:20])
        _update_with_optional_columns(
            store,
            "user_profiles",
            {
                "style_profile": profile,
                "style_profile_message_count": len(texts),
            },
            {"id": f"eq.{request.user_id}"},
        )
        _log_ai_request(store, request.user_id, None, "style_analyze", True, started)
        return StyleAnalyzeResponse(
            user_id=request.user_id,
            analyzed_messages=len(texts[:20]),
            style_profile=profile,
        )
    except HTTPException:
        raise
    except LLMError as exc:
        _log_ai_request(store, request.user_id, None, "style_analyze", False, started, str(exc))
        raise _llm_http_exception(exc) from exc
    except (SupabaseError, ValueError) as exc:
        _log_ai_request(store, request.user_id, None, "style_analyze", False, started, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


_STYLE_ANALYZE_MIN_MESSAGES = 5
_STYLE_ANALYZE_BATCH = 5


def maybe_update_style_profile(store: SupabaseStore, client: LLMClient, user_id: str) -> None:
    try:
        rows = store.select(
            "user_profiles",
            filters={"id": f"eq.{user_id}"},
            limit=1,
            columns="style_profile_message_count",
        )
        last_count = rows[0].get("style_profile_message_count", 0) if rows else 0

        sessions = store.select(
            "message_sessions",
            filters={
                "user_id": f"eq.{user_id}",
                "original_text": "not.is.null",
            },
            order="created_at.desc",
            limit=50,
            columns="original_text",
        )
        texts = [str(row["original_text"]).strip() for row in sessions if row.get("original_text")]
        if len(texts) < _STYLE_ANALYZE_MIN_MESSAGES:
            return
        if len(texts) - int(last_count or 0) < _STYLE_ANALYZE_BATCH:
            return

        profile = _generate_style_profile(client, texts[:20])
        _update_with_optional_columns(
            store,
            "user_profiles",
            {"style_profile": profile, "style_profile_message_count": len(texts)},
            {"id": f"eq.{user_id}"},
        )
    except Exception:
        pass


@app.post("/api/refine/log")
def log_corrections(
    request: RefineLogRequest,
    store: SupabaseStore = Depends(get_store),
) -> dict[str, Any]:
    try:
        rows = _insert_correction_logs(store, request.user_id, request.session_id, request.changes[:30])
        return {"saved": len(rows)}
    except SupabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/report", response_model=ReportResponse)
def get_report(
    request: ReportRequest,
    force: bool = False,
    store: SupabaseStore = Depends(get_store),
    client: LLMClient = Depends(get_llm_client),
) -> ReportResponse:
    user_id = request.user_id

    if not force:
        try:
            cached = store.select(
                "user_reports",
                filters={"user_id": f"eq.{user_id}", "report_date": f"eq.{date.today().isoformat()}"},
                order="created_at.desc",
                limit=1,
            )
        except SupabaseError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        if cached:
            payload = cached[0].get("payload") or {}
            if not isinstance(payload, dict):
                payload = {}
            payload = {
                **payload,
                "total_reviews": cached[0].get("total_reviews", 0),
                "total_corrections": cached[0].get("total_corrections", 0),
                "generated_at": cached[0].get("created_at"),
            }
            return ReportResponse(**payload)

    started = time.perf_counter()
    try:
        sessions = store.select(
            "message_sessions",
            filters={"user_id": f"eq.{user_id}", "original_text": "not.is.null"},
            order="created_at.desc",
            limit=200,
            columns="id,original_text,final_text",
        )
        logs = store.select(
            "correction_log",
            filters={"user_id": f"eq.{user_id}"},
            order="created_at.desc",
            limit=300,
            columns="change_text",
        )
        changes = [str(row["change_text"]) for row in logs if row.get("change_text")]
        if not changes:
            return ReportResponse()

        profile_rows = store.select(
            "user_profiles",
            filters={"id": f"eq.{user_id}"},
            limit=1,
            columns="style_profile",
        )
        style_profile = (profile_rows[0].get("style_profile") if profile_rows else None) or "없음"

        clustered = _cluster_corrections(client, changes, style_profile)
        report = ReportResponse(
            total_reviews=len(sessions),
            total_corrections=len(changes),
            top_mistakes=clustered.get("top_mistakes", []),
            tone_habits=clustered.get("tone_habits", []),
            suggestions=clustered.get("suggestions", []),
        )
        store.insert(
            "user_reports",
            {
                "user_id": user_id,
                "total_reviews": report.total_reviews,
                "total_corrections": report.total_corrections,
                "payload": _report_payload(report),
            },
        )
        _log_ai_request(store, user_id, None, "report", True, started)
        return report
    except LLMError as exc:
        _log_ai_request(store, user_id, None, "report", False, started, str(exc))
        raise _llm_http_exception(exc) from exc
    except (SupabaseError, ValueError) as exc:
        _log_ai_request(store, user_id, None, "report", False, started, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _load_style_profile(store: SupabaseStore, user_id: str | None) -> str | None:
    if not user_id:
        return None
    try:
        rows = store.select(
            "user_profiles",
            filters={"id": f"eq.{user_id}", "style_profile": "not.is.null"},
            limit=1,
            columns="style_profile",
        )
    except SupabaseError:
        return None
    if rows and rows[0].get("style_profile"):
        return str(rows[0]["style_profile"])
    return None


def _generate_style_profile(client: LLMClient, texts: list[str]) -> str:
    system = """너는 한국어 메시지 말투 분석 전문가다.
한 사람이 직접 쓴 메시지 여러 개를 보고 그 사람 고유의 말투를 객관적으로 요약한다.
절대 내용을 판단하거나 교정하지 말고 어투만 분석한다.
반드시 아래 JSON 형식으로만 응답한다.
{"style_profile": "말투 특징 요약 (300자 이내, 다듬기 프롬프트에 그대로 쓸 수 있는 지시문 형태)"}

style_profile에는 이런 항목을 포함한다:
- 평소 어미/높임 습관 (~해요체, ~함체 등)
- 자주 쓰는 표현, 감탄사, 이모지/ㅋㅋ 사용 패턴
- 문장 길이와 구두점 습관
- 전체적으로 부드러운지 직설적인지"""
    joined = "\n---\n".join(f"{index + 1}. {text}" for index, text in enumerate(texts))
    data = _parse_json(client.generate(system, f"[분석할 메시지들]\n{joined}"))
    profile = str(data.get("style_profile", "")).strip()
    if not profile:
        raise ValueError("말투 분석 결과가 비어 있습니다.")
    return profile


def _log_corrections(
    store: SupabaseStore,
    user_id: str | None,
    session_id: str | None,
    changes: list[str],
) -> None:
    if not user_id:
        return
    try:
        _insert_correction_logs(store, user_id, session_id, changes)
    except SupabaseError:
        pass


def _insert_correction_logs(
    store: SupabaseStore,
    user_id: str,
    session_id: str | None,
    changes: list[str],
) -> list[dict[str, Any]]:
    payload = [
        {
            "user_id": user_id,
            "session_id": session_id,
            "change_text": str(change).strip(),
        }
        for change in changes
        if str(change).strip()
    ]
    if not payload:
        return []
    return store.bulk_insert("correction_log", payload)


def _cluster_corrections(client: LLMClient, changes: list[str], style_profile: str) -> dict[str, Any]:
    system = """너는 한국어 글쓰기 분석 전문가다.
한 사람이 다듬기 서비스에서 받은 교정 요약(change) 목록을 보고 비슷한 유형끼리 묶어 통계를 만든다.
반드시 아래 JSON 형식으로만 응답한다.
{
  "top_mistakes": [
    {"label": "실수 유형명(짧게)", "count": 빈도수(정수), "example_before": "원래 표현 예시", "example_after": "교정 예시"}
  ],
  "tone_habits": ["말투 습관 한 줄"],
  "suggestions": ["개선 제안 한 줄"]
}
top_mistakes는 빈도순 최대 5개, tone_habits와 suggestions는 각 최대 4개다."""
    joined = "\n".join(f"- {change}" for change in changes[:150])
    data = _parse_json(client.generate(system, f"[교정 요약 목록]\n{joined}\n\n[기존 말투 프로필]\n{style_profile}"))
    return data if isinstance(data, dict) else {}


def _report_payload(report: ReportResponse) -> dict[str, Any]:
    if hasattr(report, "model_dump"):
        return report.model_dump(exclude={"generated_at"})
    return report.dict(exclude={"generated_at"})


def _generate_compose_candidates(client: LLMClient, request: ComposeRequest) -> list[dict[str, str]]:
    system = """너는 한국어 메시지 초안 작성 전문가다.
사용자가 보내려는 상황에 맞춰 서로 다른 전략의 후보 문장 3개를 만든다.
반드시 JSON만 응답한다.
{"candidates":[{"text":"후보 문장","strategy":"사용자에게 보여줄 수 있는 추천 근거"}]}"""
    user = "\n".join(
        [
            "[상대]",
            request.recipient or "지정 안 됨",
            "[상황]",
            request.context,
            "[목적]",
            request.purpose or "지정 안 됨",
            "[원하는 말투]",
            request.tone or "자연스럽고 부담 없는 말투",
        ]
    )
    data = _parse_json(client.generate(system, user))
    raw_candidates = data.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ValueError("Compose 응답에 candidates가 없습니다.")
    candidates: list[dict[str, str]] = []
    for item in raw_candidates[:3]:
        if isinstance(item, str):
            text = item
            ai_reason = ""
        elif isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            ai_reason = str(item.get("ai_reason") or item.get("strategy") or "").strip()
        else:
            continue
        if text:
            candidates.append({"text": text, "ai_reason": ai_reason})
    if len(candidates) < 3:
        raise ValueError("Compose 후보가 3개 미만입니다.")
    return candidates


def _generate_mirror_analysis(client: LLMClient, request: MirrorRequest) -> dict[str, Any]:
    system = """너는 한국어 메시지 전달 점검 전문가다.
상대가 실제로 어떻게 느낀다고 단정하지 말고, 그렇게 읽힐 가능성을 분석한다.
반드시 JSON만 응답한다.
{
  "intent_summary":"전달 의도 요약",
  "perceived_tone":"상대가 느낄 수 있는 말투",
  "tone_evidence":"그 말투로 읽힐 수 있는 표현상 근거",
  "risk_level":"낮음|보통|높음",
  "risk_reasons":["오해 가능성 이유"],
  "ai_reason":"분석과 수정 제안의 종합 근거",
  "soft_rewrite":"더 부드러운 추천 문장",
  "clear_rewrite":"더 명확한 추천 문장",
  "short_rewrite":"더 짧은 추천 문장"
}"""
    user = "\n".join(
        [
            "[분석할 문장]",
            request.text,
            "[상대]",
            request.recipient or "지정 안 됨",
            "[상황]",
            request.context or "지정 안 됨",
            "[목적]",
            request.purpose or "지정 안 됨",
            "[원래 의도한 말투]",
            request.tone or "지정 안 됨",
        ]
    )
    data = _parse_json(client.generate(system, user))
    required = [
        "intent_summary",
        "perceived_tone",
        "risk_level",
        "risk_reasons",
        "soft_rewrite",
        "clear_rewrite",
        "short_rewrite",
    ]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"Mirror 응답 누락: {', '.join(missing)}")
    risk_reasons = data["risk_reasons"]
    if not isinstance(risk_reasons, list):
        risk_reasons = [str(risk_reasons)]
    cleaned_reasons = [str(reason).strip() for reason in risk_reasons if str(reason).strip()]
    perceived_tone = str(data["perceived_tone"]).strip()
    tone_evidence = str(data.get("tone_evidence") or "").strip()
    ai_reason = str(data.get("ai_reason") or "").strip()
    if not tone_evidence:
        tone_evidence = f"{perceived_tone}로 읽힐 수 있는 표현이 포함되어 있습니다."
    if not ai_reason:
        ai_reason = _join_ai_reasons(cleaned_reasons)
    return {
        "intent_summary": str(data["intent_summary"]).strip(),
        "perceived_tone": perceived_tone,
        "tone_evidence": tone_evidence,
        "risk_level": str(data["risk_level"]).strip(),
        "risk_reasons": cleaned_reasons,
        "ai_reason": ai_reason,
        "soft_rewrite": str(data["soft_rewrite"]).strip(),
        "clear_rewrite": str(data["clear_rewrite"]).strip(),
        "short_rewrite": str(data["short_rewrite"]).strip(),
    }


def _generate_long_review(client: LLMClient, request: LongReviewRequest) -> dict[str, Any]:
    system = """너는 한국어 긴 글 첨삭과 요약 전문가다.
사용자의 원래 의도와 사실관계는 유지하고, 문장을 더 자연스럽고 읽기 쉽게 다듬는다.
글 유형이 논문이면 논리성/객관성/학술적 표현을, 메일이면 목적 전달/예의/명확성을, 편지이면 감정과 진정성을, 블로그이면 가독성과 흐름을, 기타이면 일반적인 문장 품질을 우선한다.
과장하거나 없는 내용을 추가하지 않는다.
반드시 JSON만 응답한다.
{
  "edited_text":"첨삭한 전체 글",
  "summary_text":"전체 내용을 2~3문장으로 요약",
  "key_points":["핵심 내용"],
  "changes":["수정한 부분 요약"],
  "ai_reason":"왜 이렇게 첨삭했는지 사용자에게 보여줄 수 있는 근거"
}"""
    user = "\n".join(
        [
            "[글 유형]",
            request.document_type or "기타",
            "[글의 목적]",
            request.purpose or request.document_type or "지정 안 됨",
            "[원문]",
            request.text,
        ]
    )
    data = _parse_json(client.generate(system, user))
    required = ["edited_text", "summary_text", "key_points", "changes", "ai_reason"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"긴글 첨삭 응답 누락: {', '.join(missing)}")

    key_points = data["key_points"]
    if not isinstance(key_points, list):
        key_points = [str(key_points)]
    changes = data["changes"]
    if not isinstance(changes, list):
        changes = [str(changes)]

    edited_text = str(data["edited_text"]).strip()
    summary_text = str(data["summary_text"]).strip()
    ai_reason = str(data["ai_reason"]).strip()
    if not edited_text:
        raise ValueError("긴글 첨삭 결과가 비어 있습니다.")
    if not summary_text:
        raise ValueError("긴글 요약 결과가 비어 있습니다.")

    return {
        "edited_text": edited_text,
        "summary_text": summary_text,
        "key_points": [str(point).strip() for point in key_points if str(point).strip()],
        "changes": [str(change).strip() for change in changes if str(change).strip()],
        "ai_reason": ai_reason,
    }


def _parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[:-3]
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise ValueError("AI 응답 JSON 파싱 실패") from exc
    if not isinstance(data, dict):
        raise ValueError("AI 응답이 JSON 객체가 아닙니다.")
    return data


def _log_ai_request(
    store: SupabaseStore,
    user_id: str | None,
    session_id: str | None,
    feature_type: str,
    success: bool,
    started: float,
    error_message: str | None = None,
) -> None:
    try:
        store.insert(
            "ai_request_logs",
            {
                "user_id": user_id,
                "session_id": session_id,
                "feature_type": feature_type,
                "model": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                "success": success,
                "error_message": error_message,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            },
        )
    except SupabaseError:
        pass


def _frontend_index_response() -> FileResponse:
    if not FRONTEND_INDEX_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail="React 화면 빌드 결과가 없습니다. npm run build를 먼저 실행해 주세요.",
        )
    return FileResponse(FRONTEND_INDEX_PATH)


@app.get("/", include_in_schema=False)
def frontend_index() -> FileResponse:
    return _frontend_index_response()


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_fallback(full_path: str) -> FileResponse:
    if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
        raise HTTPException(status_code=404, detail="Not Found")
    return _frontend_index_response()


def main() -> None:
    import uvicorn

    host = os.environ.get("REFINER_API_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT") or os.environ.get("REFINER_API_PORT") or "8000")
    reload = os.environ.get("REFINER_API_RELOAD", "").strip().lower() in {"1", "true", "yes"}
    uvicorn.run("refiner.server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
