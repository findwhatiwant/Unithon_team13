import json
import os
import time
from datetime import datetime, timezone
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
    model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash").strip()
    return GeminiClient(api_key=api_key, model=model)


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
        result = Pipeline(client).run(
            RefineRequest(
                text=request.text,
                mode=request.mode,
                tone=request.tone,
                context=request.context,
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
                "model": os.environ.get("GEMINI_MODEL", "gemini-3.6-flash"),
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
