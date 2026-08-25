import json
import os
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Any, Callable
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

from refiner.cli import load_env


APP_NAME = "Message Refiner"
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8000
DEFAULT_API_BASE_URL = f"http://{DEFAULT_API_HOST}:{DEFAULT_API_PORT}"
REQUIRED_API_PATHS = frozenset({"/api/users", "/api/compose", "/api/mirror"})
WINDOW_WIDTH = 360
WINDOW_HEIGHT = 520

WHITE = "#ffffff"
INK = "#1f2328"
SUB_TEXT = "#8c9199"
SURFACE = "#fafafa"
HAIRLINE = "#e8e8e8"
ACCENT = "#111111"
ACCENT_MUTED = "#f3f3f3"
ERROR = "#cc4033"


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def set_base_url(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def openapi(self) -> dict[str, Any]:
        return self._request("GET", "/openapi.json", timeout=5)

    def has_tray_api(self) -> bool:
        data = self.openapi()
        paths = data.get("paths")
        return isinstance(paths, dict) and REQUIRED_API_PATHS.issubset(paths)

    def create_user(self, nickname: str = "windows-user") -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/users",
            {"nickname": nickname, "provider": "windows_tray"},
        )

    def save_consent(self, user_id: str, save_history: bool) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/consents",
            {
                "user_id": user_id,
                "save_message_history": save_history,
                "coach_analysis": False,
                "sensitive_info_storage": False,
            },
        )

    def compose(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/compose", payload)

    def mirror(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/mirror", payload)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: int = 60,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = requests.request(method, url, json=payload, timeout=timeout)
        if response.status_code >= 400:
            raise RuntimeError(f"{response.status_code}: {response.text}")
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("서버 응답 형식이 올바르지 않습니다.")
        return data


class SettingsStore:
    def __init__(self):
        root = Path(os.environ.get("APPDATA", str(Path.home())))
        self.path = root / APP_NAME / "settings.json"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class BackendProcess:
    def __init__(self, api: APIClient):
        self.api = api
        self.process: subprocess.Popen[str] | None = None

    def ensure_running(self) -> None:
        if self._is_compatible():
            return

        port = self._preferred_port()
        if not self._can_start_on_port(DEFAULT_API_HOST, port):
            port = self._find_free_port(port + 1)
            self.api.set_base_url(f"http://{DEFAULT_API_HOST}:{port}")

        self._start(port)
        for _ in range(30):
            if self._is_compatible():
                return
            time.sleep(0.5)
        raise RuntimeError("로컬 백엔드 서버를 시작하지 못했습니다.")

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def _is_compatible(self) -> bool:
        try:
            return self.api.has_tray_api()
        except Exception:
            return False

    def _start(self, port: int) -> None:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "refiner.server:app",
                "--host",
                DEFAULT_API_HOST,
                "--port",
                str(port),
            ],
            cwd=Path(__file__).resolve().parents[1],
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def _preferred_port(self) -> int:
        parsed = urlparse(self.api.base_url)
        return parsed.port or DEFAULT_API_PORT

    @staticmethod
    def _can_start_on_port(host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return False
        except OSError:
            return True

    def _find_free_port(self, start_port: int) -> int:
        for port in range(max(start_port, 1024), start_port + 50):
            if self._can_start_on_port(DEFAULT_API_HOST, port):
                return port
        raise RuntimeError("사용 가능한 로컬 포트를 찾지 못했습니다.")


class TrayApp:
    def __init__(self):
        load_env()
        base_url = os.environ.get("REFINER_API_BASE_URL", DEFAULT_API_BASE_URL)
        self.api = APIClient(base_url)
        self.backend = BackendProcess(self.api)
        self.settings = SettingsStore()
        self.settings_data = self.settings.load()
        self.user_id: str | None = self.settings_data.get("user_id")
        self.icon: Icon | None = None

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.root.withdraw()

        self.save_history_var = tk.BooleanVar(value=bool(self.settings_data.get("save_history", False)))
        self.status_var = tk.StringVar(value="준비 중...")
        self.active_view = tk.StringVar(value="compose")
        self.compose_candidates: list[dict[str, Any]] = []
        self.compose_session_id: str | None = None

        self._build_window()

    def run(self) -> None:
        self._run_background("초기화 중...", self._startup)
        threading.Thread(target=self._run_tray_icon, daemon=True).start()
        self.root.after(300, self._show_window)
        self.root.mainloop()

    def show_window(self) -> None:
        self.root.after(0, self._show_window)

    def hide_window(self) -> None:
        self.root.withdraw()

    def quit(self) -> None:
        self.backend.stop()
        if self.icon:
            self.icon.stop()
        self.root.after(0, self.root.destroy)

    def _startup(self) -> None:
        self.backend.ensure_running()
        if not self.user_id:
            created = self.api.create_user()
            self.user_id = str(created["user_id"])
            self.settings_data["user_id"] = self.user_id
            self.settings.save(self.settings_data)
        self._set_status("서버 연결 완료")

    def _build_window(self) -> None:
        self.root.configure(bg=WHITE)

        app = tk.Frame(self.root, bg=WHITE)
        app.pack(fill="both", expand=True, padx=14, pady=12)

        header = tk.Frame(app, bg=WHITE)
        header.pack(fill="x", pady=(0, 10))
        tk.Label(
            header,
            text="Message Refiner",
            bg=WHITE,
            fg=INK,
            font=("Pretendard", 16, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="보내기 전, 내 말이 어떻게 들릴지 먼저 확인하세요.",
            bg=WHITE,
            fg=SUB_TEXT,
            font=("Pretendard", 9),
        ).pack(anchor="w", pady=(4, 0))

        controls = tk.Frame(app, bg=WHITE)
        controls.pack(fill="x", pady=(0, 8))
        tk.Checkbutton(
            controls,
            text="기록 저장 동의",
            variable=self.save_history_var,
            command=self._on_consent_changed,
            bg=WHITE,
            activebackground=WHITE,
            fg=INK,
            selectcolor=WHITE,
            font=("Pretendard", 9),
            borderwidth=0,
            highlightthickness=0,
        ).pack(side="left")
        tk.Label(
            controls,
            textvariable=self.status_var,
            bg=WHITE,
            fg=SUB_TEXT,
            font=("Pretendard", 8),
        ).pack(side="right")

        segments = tk.Frame(app, bg=SURFACE, highlightbackground=HAIRLINE, highlightthickness=1)
        segments.pack(fill="x", pady=(0, 10))
        self.compose_mode_button = tk.Button(
            segments,
            text="추천받기",
            command=lambda: self._switch_view("compose"),
            bd=0,
            relief="flat",
            cursor="hand2",
            font=("Pretendard", 10, "bold"),
            pady=6,
        )
        self.compose_mode_button.pack(side="left", fill="x", expand=True, padx=(2, 1), pady=2)
        self.mirror_mode_button = tk.Button(
            segments,
            text="말투 점검",
            command=lambda: self._switch_view("mirror"),
            bd=0,
            relief="flat",
            cursor="hand2",
            font=("Pretendard", 10, "bold"),
            pady=6,
        )
        self.mirror_mode_button.pack(side="left", fill="x", expand=True, padx=(1, 2), pady=2)

        body = tk.Frame(app, bg=WHITE)
        body.pack(fill="both", expand=True)
        self.content_canvas = tk.Canvas(body, bg=WHITE, bd=0, highlightthickness=0)
        self.content_canvas.pack(side="left", fill="both", expand=True)
        self.content_scrollbar = tk.Scrollbar(body, orient="vertical", command=self.content_canvas.yview, width=10)
        self.content_scrollbar.pack(side="right", fill="y")
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)

        self.content_frame = tk.Frame(self.content_canvas, bg=WHITE)
        self.content_window = self.content_canvas.create_window(
            (0, 0),
            window=self.content_frame,
            anchor="nw",
        )
        self.content_frame.bind("<Configure>", self._on_content_configure)
        self.content_canvas.bind("<Configure>", self._on_canvas_configure)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

        self.compose_tab = tk.Frame(self.content_frame, bg=WHITE)
        self.mirror_tab = tk.Frame(self.content_frame, bg=WHITE)

        self._build_compose_tab(self.compose_tab)
        self._build_mirror_tab(self.mirror_tab)

        footer = tk.Frame(app, bg=WHITE)
        footer.pack(fill="x", pady=(8, 0))
        tk.Frame(footer, height=1, bg=HAIRLINE).pack(fill="x", pady=(0, 6))
        tk.Label(
            footer,
            text="Unithon Team13",
            bg=WHITE,
            fg=SUB_TEXT,
            font=("Pretendard", 8),
        ).pack(side="left")
        tk.Button(
            footer,
            text="종료",
            command=self.quit,
            bd=0,
            bg=WHITE,
            fg=SUB_TEXT,
            activebackground=WHITE,
            activeforeground=INK,
            cursor="hand2",
            font=("Pretendard", 8),
        ).pack(side="right")

        self._switch_view("compose")

    def _on_content_configure(self, _event: object) -> None:
        self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))

    def _on_canvas_configure(self, event: object) -> None:
        width = getattr(event, "width", WINDOW_WIDTH)
        self.content_canvas.itemconfigure(self.content_window, width=width)

    def _on_mousewheel(self, event: object) -> None:
        delta = getattr(event, "delta", 0)
        if delta:
            self.content_canvas.yview_scroll(int(-1 * (delta / 120)), "units")

    def _switch_view(self, view: str) -> None:
        self.active_view.set(view)
        self.compose_tab.pack_forget()
        self.mirror_tab.pack_forget()
        if view == "mirror":
            self.mirror_tab.pack(fill="both", expand=True)
        else:
            self.compose_tab.pack(fill="both", expand=True)
        self._refresh_mode_buttons()
        self.root.after(0, lambda: self.content_canvas.yview_moveto(0))
        self.root.after(0, lambda: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all")))

    def _refresh_mode_buttons(self) -> None:
        for view, button in (
            ("compose", self.compose_mode_button),
            ("mirror", self.mirror_mode_button),
        ):
            selected = self.active_view.get() == view
            button.configure(
                bg=ACCENT if selected else ACCENT_MUTED,
                fg=WHITE if selected else INK,
                activebackground=ACCENT if selected else ACCENT_MUTED,
                activeforeground=WHITE if selected else INK,
            )

    def _build_compose_tab(self, parent: tk.Frame) -> None:
        self.compose_recipient = self._entry(parent, "상대", "예: 동아리 팀원")
        self.compose_purpose = self._entry(parent, "목적", "예: 부탁, 거절, 사과")
        self.compose_tone = self._entry(parent, "원하는 말투", "예: 부드럽게, 정중하게")
        self.compose_context = self._text(parent, "상황", 3)

        self._primary_button(parent, "추천 문장 3개 만들기", self._compose).pack(fill="x", pady=(2, 12))

        self._section_title(parent, "추천 후보")
        self.candidate_frame = tk.Frame(parent, bg=SURFACE, highlightbackground=HAIRLINE, highlightthickness=1)
        self.candidate_frame.pack(fill="x", pady=(4, 12))
        tk.Label(
            self.candidate_frame,
            text="아직 추천 후보가 없습니다.",
            bg=SURFACE,
            fg=SUB_TEXT,
            font=("Pretendard", 9),
            padx=10,
            pady=12,
        ).pack(anchor="w")

        self.compose_result = self._result_box(parent, "Mirror 분석 결과")

    def _build_mirror_tab(self, parent: tk.Frame) -> None:
        self.mirror_recipient = self._entry(parent, "상대", "예: 팀원, 교수님, 친구")
        self.mirror_purpose = self._entry(parent, "목적", "예: 부탁, 일정 변경")
        self.mirror_tone = self._entry(parent, "원하는 말투", "예: 부드럽게")
        self.mirror_context = self._text(parent, "상황", 2)
        self.mirror_text = self._text(parent, "내가 쓴 문장", 4)

        self._primary_button(parent, "말투와 오해 가능성 점검", self._mirror_direct).pack(fill="x", pady=(2, 12))
        self.mirror_result = self._result_box(parent, "분석 결과")

    def _section_title(self, parent: tk.Widget, text: str) -> None:
        tk.Label(
            parent,
            text=text,
            bg=WHITE,
            fg=SUB_TEXT,
            font=("Pretendard", 8, "bold"),
        ).pack(anchor="w", pady=(0, 4))

    def _entry(self, parent: tk.Frame, label: str, placeholder: str) -> tk.StringVar:
        frame = tk.Frame(parent, bg=WHITE)
        frame.pack(fill="x", pady=(0, 9))
        self._section_title(frame, label)
        value = tk.StringVar()
        entry = tk.Entry(
            frame,
            textvariable=value,
            bd=0,
            relief="flat",
            bg=SURFACE,
            fg=SUB_TEXT,
            insertbackground=INK,
            font=("Pretendard", 9),
            highlightbackground=HAIRLINE,
            highlightcolor="#777777",
            highlightthickness=1,
        )
        entry.pack(fill="x", ipady=7)
        entry.insert(0, placeholder)

        def on_focus_in(_: object) -> None:
            if entry.get() == placeholder:
                entry.delete(0, "end")
                entry.configure(fg=INK)

        def on_focus_out(_: object) -> None:
            if not entry.get().strip():
                entry.insert(0, placeholder)
                entry.configure(fg=SUB_TEXT)

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        return value

    def _text(self, parent: tk.Frame, label: str, height: int) -> tk.Text:
        self._section_title(parent, label)
        box = tk.Text(
            parent,
            height=height,
            wrap="word",
            relief="flat",
            borderwidth=0,
            bg=SURFACE,
            fg=INK,
            insertbackground=INK,
            font=("Pretendard", 9),
            padx=9,
            pady=6,
            highlightbackground=HAIRLINE,
            highlightcolor="#777777",
            highlightthickness=1,
        )
        box.pack(fill="x", pady=(0, 10))
        return box

    def _result_box(self, parent: tk.Frame, label: str) -> tk.Text:
        self._section_title(parent, label)
        box = tk.Text(
            parent,
            height=6,
            wrap="word",
            relief="flat",
            borderwidth=0,
            bg=SURFACE,
            fg=INK,
            font=("Pretendard", 9),
            padx=9,
            pady=6,
            highlightbackground=HAIRLINE,
            highlightthickness=1,
        )
        box.pack(fill="both", expand=True, pady=(0, 0))
        box.insert("1.0", "결과가 여기에 표시됩니다.")
        box.configure(state="disabled", fg=SUB_TEXT)
        return box

    def _primary_button(self, parent: tk.Widget, text: str, command: Callable[[], None]) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bd=0,
            relief="flat",
            bg=ACCENT,
            fg=WHITE,
            activebackground="#333333",
            activeforeground=WHITE,
            cursor="hand2",
            font=("Pretendard", 10, "bold"),
            pady=8,
        )

    def _ghost_button(self, parent: tk.Widget, text: str, command: Callable[[], None]) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bd=0,
            relief="flat",
            bg=ACCENT_MUTED,
            fg=INK,
            activebackground="#e9e9e9",
            activeforeground=INK,
            cursor="hand2",
            font=("Pretendard", 9, "bold"),
            padx=10,
            pady=6,
        )

    def _compose(self) -> None:
        context = self._text_value(self.compose_context)
        if not context:
            messagebox.showwarning(APP_NAME, "상황을 입력해주세요.")
            return
        payload = {
            "user_id": self.user_id,
            "recipient": self._entry_value(self.compose_recipient),
            "context": context,
            "purpose": self._entry_value(self.compose_purpose),
            "tone": self._entry_value(self.compose_tone),
            "save_history": self.save_history_var.get(),
        }
        self._run_background("추천 문장 생성 중...", lambda: self._compose_worker(payload))

    def _compose_worker(self, payload: dict[str, Any]) -> None:
        data = self.api.compose(payload)
        self.compose_session_id = str(data["session_id"])
        self.compose_candidates = list(data["candidates"])
        self.root.after(0, self._render_candidates)
        self._set_status("추천 후보 생성 완료")

    def _render_candidates(self) -> None:
        for child in self.candidate_frame.winfo_children():
            child.destroy()
        for candidate in self.compose_candidates:
            index = candidate["candidate_index"]
            text = candidate["candidate_text"]
            container = tk.Frame(self.candidate_frame, bg=SURFACE)
            container.pack(fill="x", padx=10, pady=(10, 6))
            tk.Label(
                container,
                text=f"후보 {index}",
                bg=SURFACE,
                fg=INK,
                font=("Pretendard", 9, "bold"),
            ).pack(anchor="w")
            message = tk.Text(
                container,
                height=3,
                wrap="word",
                relief="flat",
                borderwidth=0,
                bg=WHITE,
                fg=INK,
                font=("Pretendard", 9),
                padx=8,
                pady=6,
                highlightbackground=HAIRLINE,
                highlightthickness=1,
            )
            message.insert("1.0", text)
            message.configure(state="disabled")
            message.pack(fill="x", pady=(4, 6))
            self._ghost_button(
                container,
                "Mirror 분석",
                command=lambda selected=candidate: self._mirror_candidate(selected),
            ).pack(anchor="e")
        self.root.after(0, lambda: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all")))

    def _mirror_candidate(self, candidate: dict[str, Any]) -> None:
        payload = {
            "user_id": self.user_id,
            "session_id": self.compose_session_id,
            "candidate_id": candidate["candidate_id"],
            "text": candidate["candidate_text"],
            "source_type": "quick_compose_candidate",
            "recipient": self._entry_value(self.compose_recipient),
            "context": self._text_value(self.compose_context),
            "purpose": self._entry_value(self.compose_purpose),
            "tone": self._entry_value(self.compose_tone),
            "save_history": self.save_history_var.get(),
        }
        self._run_background("Mirror 분석 중...", lambda: self._mirror_worker(payload, self.compose_result))

    def _mirror_direct(self) -> None:
        text = self._text_value(self.mirror_text)
        if not text:
            messagebox.showwarning(APP_NAME, "점검할 문장을 입력해주세요.")
            return
        payload = {
            "user_id": self.user_id,
            "text": text,
            "source_type": "direct_input",
            "recipient": self._entry_value(self.mirror_recipient),
            "context": self._text_value(self.mirror_context),
            "purpose": self._entry_value(self.mirror_purpose),
            "tone": self._entry_value(self.mirror_tone),
            "save_history": self.save_history_var.get(),
        }
        self._run_background("Mirror 분석 중...", lambda: self._mirror_worker(payload, self.mirror_result))

    def _mirror_worker(self, payload: dict[str, Any], target: tk.Text) -> None:
        data = self.api.mirror(payload)
        text = self._format_mirror_result(data)
        self.root.after(0, lambda: self._write_result(target, text))
        self._set_status("Mirror 분석 완료")

    def _format_mirror_result(self, data: dict[str, Any]) -> str:
        reasons = "\n".join(f"- {reason}" for reason in data.get("risk_reasons", []))
        return "\n\n".join(
            [
                f"전달 의도\n{data.get('intent_summary', '')}",
                f"상대가 느낄 수 있는 말투\n{data.get('perceived_tone', '')}",
                f"오해 가능성: {data.get('risk_level', '')}\n{reasons}",
                f"더 부드럽게\n{data.get('soft_rewrite', '')}",
                f"더 명확하게\n{data.get('clear_rewrite', '')}",
                f"더 짧게\n{data.get('short_rewrite', '')}",
            ]
        )

    def _on_consent_changed(self) -> None:
        enabled = self.save_history_var.get()
        self.settings_data["save_history"] = enabled
        self.settings.save(self.settings_data)
        if not self.user_id:
            return
        self._run_background("저장 동의 반영 중...", lambda: self.api.save_consent(self.user_id or "", enabled))

    def _run_background(self, status: str, task: Callable[[], Any]) -> None:
        self._set_status(status)

        def runner() -> None:
            try:
                task()
            except Exception as exc:
                message = str(exc)
                self.root.after(0, lambda error=message: messagebox.showerror(APP_NAME, error))
                self._set_status("오류 발생")

        threading.Thread(target=runner, daemon=True).start()

    def _run_tray_icon(self) -> None:
        image = self._create_icon_image()
        menu = Menu(
            MenuItem("작업창 열기", lambda _icon, _item: self.show_window(), default=True),
            MenuItem("숨기기", lambda _icon, _item: self.root.after(0, self.hide_window)),
            MenuItem("종료", lambda _icon, _item: self.quit()),
        )
        self.icon = Icon(APP_NAME, image, APP_NAME, menu)
        self.icon.run()

    def _show_window(self) -> None:
        self._position_window()
        self.root.deiconify()
        self.root.update()
        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", True)
        self.root.after(600, lambda: self.root.attributes("-topmost", False))

    def _position_window(self) -> None:
        self.root.update_idletasks()
        width = WINDOW_WIDTH
        height = WINDOW_HEIGHT
        work_area = self._get_windows_work_area()
        if work_area:
            left, top, right, bottom = work_area
            x = max(left + 16, right - width - 16)
            y = max(top + 16, bottom - height - 16)
        else:
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = max(20, screen_width - width - 24)
            y = max(20, screen_height - height - 72)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    @staticmethod
    def _get_windows_work_area() -> tuple[int, int, int, int] | None:
        if sys.platform != "win32":
            return None
        try:
            import ctypes

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            rect = RECT()
            spi_get_work_area = 0x0030
            ok = ctypes.windll.user32.SystemParametersInfoW(
                spi_get_work_area,
                0,
                ctypes.byref(rect),
                0,
            )
            if not ok:
                return None
            return rect.left, rect.top, rect.right, rect.bottom
        except Exception:
            return None

    def _set_status(self, message: str) -> None:
        self.root.after(0, lambda: self.status_var.set(message))

    def _write_result(self, target: tk.Text, text: str) -> None:
        target.configure(state="normal", fg=INK)
        target.delete("1.0", "end")
        target.insert("1.0", text)
        target.configure(state="disabled")
        self.root.after(0, lambda: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all")))

    def _entry_value(self, value: tk.StringVar) -> str | None:
        text = value.get().strip()
        if text.startswith("예:"):
            return None
        return text or None

    @staticmethod
    def _text_value(box: tk.Text) -> str:
        return box.get("1.0", "end").strip()

    @staticmethod
    def _create_icon_image() -> Image.Image:
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((8, 8, 56, 48), radius=12, fill="#ffd21f")
        draw.polygon([(26, 48), (22, 58), (38, 48)], fill="#ffd21f")
        draw.ellipse((18, 20, 46, 38), fill="#2b1230")
        return image


def main() -> None:
    app = TrayApp()
    app.run()


if __name__ == "__main__":
    main()
