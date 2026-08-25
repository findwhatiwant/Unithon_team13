import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class SupabaseError(RuntimeError):
    pass


class SupabaseStore:
    def __init__(self, url: str, service_role_key: str):
        self._url = url.rstrip("/")
        self._service_role_key = service_role_key

    @classmethod
    def from_env(cls) -> "SupabaseStore":
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        if not url or not key:
            raise SupabaseError("SUPABASE_URL 또는 SUPABASE_SERVICE_ROLE_KEY가 없습니다.")
        return cls(url, key)

    @staticmethod
    def is_configured() -> bool:
        return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))

    def insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request(
            "POST",
            table,
            payload,
            prefer="return=representation",
        )
        return self._first_row(rows, table)

    def bulk_insert(self, table: str, payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = self._request(
            "POST",
            table,
            payload,
            prefer="return=representation",
        )
        if not isinstance(rows, list):
            raise SupabaseError(f"{table} 저장 응답이 배열이 아닙니다.")
        return rows

    def upsert(
        self,
        table: str,
        payload: dict[str, Any],
        on_conflict: str,
    ) -> dict[str, Any]:
        rows = self._request(
            "POST",
            table,
            payload,
            query={"on_conflict": on_conflict},
            prefer="resolution=merge-duplicates,return=representation",
        )
        return self._first_row(rows, table)

    def update(
        self,
        table: str,
        payload: dict[str, Any],
        filters: dict[str, str],
    ) -> list[dict[str, Any]]:
        rows = self._request(
            "PATCH",
            table,
            payload,
            query=filters,
            prefer="return=representation",
        )
        if not isinstance(rows, list):
            raise SupabaseError(f"{table} 수정 응답이 배열이 아닙니다.")
        return rows

    def _request(
        self,
        method: str,
        table: str,
        payload: dict[str, Any] | list[dict[str, Any]] | None = None,
        query: dict[str, str] | None = None,
        prefer: str | None = None,
    ) -> Any:
        query_string = f"?{urlencode(query)}" if query else ""
        url = f"{self._url}/rest/v1/{table}{query_string}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer

        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SupabaseError(f"Supabase HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise SupabaseError(f"Supabase 연결 실패: {exc.reason}") from exc

        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SupabaseError(f"Supabase 응답 파싱 실패: {raw[:200]}") from exc

    @staticmethod
    def _first_row(rows: Any, table: str) -> dict[str, Any]:
        if not isinstance(rows, list) or not rows:
            raise SupabaseError(f"{table} 저장 결과가 비어 있습니다.")
        first = rows[0]
        if not isinstance(first, dict):
            raise SupabaseError(f"{table} 저장 응답 형식이 올바르지 않습니다.")
        return first
