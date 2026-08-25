import json
import os
import time
from datetime import date, datetime, timezone
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from refiner.cli import load_env
from refiner.llm import GeminiClient, LLMClient
from refiner.models import Mode, RefineRequest, Tone
from refiner.pipeline import Pipeline
from refiner.supabase_store import SupabaseError, SupabaseStore


load_env()

app = FastAPI(title="Message Refiner API", version="0.1.0")


class UserCreateRequest(BaseModel):
    user_id: str | None = None
    email: str | None = None
    nickname: str | None = None
    provider: str = "anonymous"


class UserCreateResponse(BaseModel):
    user_id: str
    email: str | None = None
    nickname: str | None = None
    provider: str


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
    risk_level: str
    risk_reasons: list[str]
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


class StyleAnalyzeRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    min_messages: int = 3


class StyleAnalyzeResponse(BaseModel):
    user_id: str
    analyzed_messages: int
    style_profile: str


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


class RefineAPIResponse(BaseModel):
    session_id: str
    refined_text: str
    changes: list[str]


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
        # 프로필이 없으면 생성 (Supabase Auth로 만든 계정 보완)
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
        candidates = _generate_compose_candidates(client, request)
        session = store.insert(
            "message_sessions",
            {
                "user_id": request.user_id,
                "flow_type": "quick_compose",
                "source_type": "direct_input",
                "original_text": None,
                "context": request.context if request.save_history else None,
                "recipient": request.recipient if request.save_history else None,
                "purpose": request.purpose,
                "tone": request.tone,
                "save_history": request.save_history,
            },
        )
        rows = store.bulk_insert(
            "compose_candidates",
            [
                {
                    "session_id": session["id"],
                    "candidate_index": index + 1,
                    "candidate_text": candidate["text"] if request.save_history else "[not saved]",
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
                )
                for index, row in enumerate(rows)
            ],
        )
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
        analysis = _generate_mirror_analysis(client, request)
        session_id = request.session_id
        if session_id:
            store.update(
                "message_sessions",
                {
                    "selected_candidate_id": request.candidate_id,
                    "final_text": request.text if request.save_history else None,
                    "save_history": request.save_history,
                },
                {"id": f"eq.{session_id}"},
            )
        else:
            session = store.insert(
                "message_sessions",
                {
                    "user_id": request.user_id,
                    "flow_type": "direct_mirror",
                    "source_type": request.source_type,
                    "original_text": request.text if request.save_history else None,
                    "context": request.context if request.save_history else None,
                    "recipient": request.recipient if request.save_history else None,
                    "purpose": request.purpose,
                    "tone": request.tone,
                    "save_history": request.save_history,
                    "final_text": request.text if request.save_history else None,
                },
            )
            session_id = session["id"]

        if request.candidate_id:
            store.update(
                "compose_candidates",
                {"is_selected": True},
                {"id": f"eq.{request.candidate_id}"},
            )

        row = store.insert(
            "mirror_analyses",
            {
                "session_id": session_id,
                "analyzed_text": request.text if request.save_history else None,
                "intent_summary": analysis["intent_summary"] if request.save_history else None,
                "perceived_tone": analysis["perceived_tone"] if request.save_history else None,
                "risk_level": analysis["risk_level"] if request.save_history else None,
                "risk_reasons": analysis["risk_reasons"] if request.save_history else [],
                "soft_rewrite": analysis["soft_rewrite"] if request.save_history else None,
                "clear_rewrite": analysis["clear_rewrite"] if request.save_history else None,
                "short_rewrite": analysis["short_rewrite"] if request.save_history else None,
            },
        )
        _log_ai_request(store, request.user_id, session_id, "mirror", True, started)
        return MirrorResponse(
            session_id=session_id,
            analysis_id=row["id"],
            intent_summary=analysis["intent_summary"],
            perceived_tone=analysis["perceived_tone"],
            risk_level=analysis["risk_level"],
            risk_reasons=analysis["risk_reasons"],
            soft_rewrite=analysis["soft_rewrite"],
            clear_rewrite=analysis["clear_rewrite"],
            short_rewrite=analysis["short_rewrite"],
        )
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
        raise HTTPException(status_code=500, detail=result.error)
    session = store.insert(
        "message_sessions",
        {
            "user_id": request.user_id,
            "flow_type": "refine",
            "source_type": "direct_input",
            "original_text": request.text if request.save_history else None,
            "context": request.context if request.save_history else None,
            "tone": request.tone.value if request.tone else None,
            "save_history": request.save_history,
            "final_text": result.refined_text if request.save_history else None,
        },
    )
    return RefineAPIResponse(
        session_id=session["id"],
        refined_text=result.refined_text,
        changes=result.changes,
    )


@app.post("/api/style/analyze", response_model=StyleAnalyzeResponse)
def analyze_style(
    request: StyleAnalyzeRequest,
    store: SupabaseStore = Depends(get_store),
    client: LLMClient = Depends(get_llm_client),
) -> StyleAnalyzeResponse:
    """사용자의 최근 원본 메시지들을 분석해 말투 프로필을 생성·저장한다."""
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
        store.update(
            "user_profiles",
            {"style_profile": profile},
            {"id": f"eq.{request.user_id}"},
        )
        return StyleAnalyzeResponse(
            user_id=request.user_id,
            analyzed_messages=len(texts[:20]),
            style_profile=profile,
        )
    except HTTPException:
        raise
    except SupabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


_STYLE_ANALYZE_MIN_MESSAGES = 5
_STYLE_ANALYZE_BATCH = 5


def maybe_update_style_profile(store: SupabaseStore, client: LLMClient, user_id: str) -> None:
    """새 원본이 5개 쌓일 때마다 말투 프로필을 자동 갱신한다 (백그라운드)."""
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
        texts = [str(r["original_text"]).strip() for r in sessions if r.get("original_text")]
        if len(texts) < _STYLE_ANALYZE_MIN_MESSAGES:
            return
        if len(texts) - int(last_count or 0) < _STYLE_ANALYZE_BATCH:
            return

        profile = _generate_style_profile(client, texts[:20])
        store.update(
            "user_profiles",
            {"style_profile": profile, "style_profile_message_count": len(texts)},
            {"id": f"eq.{user_id}"},
        )
    except Exception:  # 프로필 갱신 실패는 본 요청에 영향 주지 않음
        pass


class RefineLogRequest(BaseModel):
    user_id: str
    session_id: str | None = None
    changes: list[str]


@app.post("/api/refine/log")
def log_corrections(
    request: RefineLogRequest,
    store: SupabaseStore = Depends(get_store),
) -> dict[str, Any]:
    """다듬기 결과의 변경 요약을 로그로 저장 (리포트 재료)."""
    try:
        rows = store.bulk_insert(
            "correction_log",
            [
                {"user_id": request.user_id, "session_id": request.session_id, "change_text": c}
                for c in request.changes[:30]
                if c.strip()
            ],
        )
        return {"saved": len(rows)}
    except SupabaseError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class ReportResponse(BaseModel):
    total_reviews: int = 0
    total_corrections: int = 0
    top_mistakes: list[dict[str, Any]] = []
    tone_habits: list[str] = []
    suggestions: list[str] = []
    generated_at: str | None = None


@app.post("/api/report", response_model=ReportResponse)
def get_report(
    request: UserCreateRequest,  # user_id만 사용
    force: bool = False,
    store: SupabaseStore = Depends(get_store),
    client: LLMClient = Depends(get_llm_client),
) -> ReportResponse:
    """누적 교정 이력을 클러스터링해 개인화 말투 리포트를 생성/반환."""
    user_id = request.user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id가 필요합니다.")

    # 같은 날 캐시 재사용 (force면 무시)
    if not force:
        cached = store.select(
            "user_reports",
            filters={"user_id": f"eq.{user_id}", "report_date": f"eq.{date.today().isoformat()}"},
            order="created_at.desc",
            limit=1,
        )
        if cached:
            payload = cached[0].get("payload") or {}
            return ReportResponse(**{
                **payload,
                "total_reviews": cached[0].get("total_reviews", 0),
                "total_corrections": cached[0].get("total_corrections", 0),
                "generated_at": cached[0].get("created_at"),
            })

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
    changes = [str(l["change_text"]) for l in logs if l.get("change_text")]
    if not changes:
        return ReportResponse()

    profile_rows = store.select(
        "user_profiles", filters={"id": f"eq.{user_id}"}, limit=1, columns="style_profile"
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

    import json as _json

    store.insert(
        "user_reports",
        {
            "user_id": user_id,
            "total_reviews": report.total_reviews,
            "total_corrections": report.total_corrections,
            "payload": _json.loads(report.model_dump_json(exclude={"generated_at"})),
        },
    )
    return report


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
    joined = "\n".join(f"- {c}" for c in changes[:150])
    data = _parse_json(client.generate(system, f"[교정 요약 목록]\n{joined}\n\n[기존 말투 프로필]\n{style_profile}"))
    return data if isinstance(data, dict) else {}


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


def _generate_compose_candidates(client: LLMClient, request: ComposeRequest) -> list[dict[str, str]]:
    system = """너는 한국어 메시지 초안 작성 전문가다.
사용자가 보내려는 상황에 맞춰 서로 다른 전략의 후보 문장 3개를 만든다.
반드시 JSON만 응답한다.
{"candidates":[{"text":"후보 문장","strategy":"전략 요약"}]}"""
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
            strategy = ""
        elif isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            strategy = str(item.get("strategy", "")).strip()
        else:
            continue
        if text:
            candidates.append({"text": text, "strategy": strategy})
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
  "risk_level":"낮음|보통|높음",
  "risk_reasons":["오해 가능성 이유"],
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
    return {
        "intent_summary": str(data["intent_summary"]).strip(),
        "perceived_tone": str(data["perceived_tone"]).strip(),
        "risk_level": str(data["risk_level"]).strip(),
        "risk_reasons": [str(reason).strip() for reason in risk_reasons if str(reason).strip()],
        "soft_rewrite": str(data["soft_rewrite"]).strip(),
        "clear_rewrite": str(data["clear_rewrite"]).strip(),
        "short_rewrite": str(data["short_rewrite"]).strip(),
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


def main() -> None:
    import uvicorn

    uvicorn.run("refiner.server:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
