import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox
from typing import Any, Callable
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageTk
from pystray import Icon, Menu, MenuItem

from refiner.cli import load_env


APP_NAME = "Message Refiner"
DISPLAY_NAME = "Magic Note"
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8000
DEFAULT_API_BASE_URL = f"http://{DEFAULT_API_HOST}:{DEFAULT_API_PORT}"
REQUIRED_API_PATHS = frozenset({"/api/users", "/api/compose", "/api/mirror", "/api/long-review"})
WINDOW_WIDTH = 360
WINDOW_HEIGHT = 520
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST_DIR = PROJECT_ROOT / "dist"
FRONTEND_INDEX_PATH = FRONTEND_DIST_DIR / "index.html"
FRONTEND_SOURCE_PATHS = (
    PROJECT_ROOT / "App.tsx",
    PROJECT_ROOT / "index.css",
    PROJECT_ROOT / "index.html",
    PROJECT_ROOT / "package.json",
    PROJECT_ROOT / "src" / "main.tsx",
)

WHITE = "#ffffff"
INK = "#1f2328"
SUB_TEXT = "#8c9199"
SURFACE = "#fafafa"
HAIRLINE = "#e8e8e8"
ACCENT = "#41456b"
ACCENT_DARK = "#2c2f52"
ROSE = "#b05a5b"
ACCENT_MUTED = "#f3f3f3"
ERROR = "#cc4033"
FRAME_BG = "#eceaf2"
FRAME_LINE = "#ffffff"
CARD_BG = "#f8f7fb"
CARD_BORDER = "#d9d7df"
MUTED_INK = "#77747e"
WARN_BG = "#e1d4dc"
WARN_FG = "#be6a6e"
PURPOSES = ("사과", "거절", "요청", "피드백")
LONG_REVIEW_TYPES = ("논문", "메일", "편지", "블로그", "기타")
DRAFT_BADGES = ("기본형", "부드럽게", "명확하게")


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

    def has_frontend(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
        except requests.RequestException:
            return False
        return response.status_code == 200 and '<div id="root"' in response.text

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

    def long_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/long-review", payload, timeout=90)

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
        self._image_refs: list[Any] = []

        self.root = tk.Tk()
        self.root.title(DISPLAY_NAME)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.root.withdraw()

        self.save_history_var = tk.BooleanVar(value=bool(self.settings_data.get("save_history", False)))
        self.status_var = tk.StringVar(value="준비 중...")
        self.active_view = tk.StringVar(value="home")
        self.quick_text_var = tk.StringVar()
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

        self.home_screen = tk.Frame(self.root, bg=WHITE, width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
        self.work_screen = tk.Frame(self.root, bg=WHITE, width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
        self._build_home_screen(self.home_screen)

        app = tk.Frame(self.work_screen, bg=WHITE)
        app.pack(fill="both", expand=True, padx=14, pady=12)

        work_header = tk.Frame(app, bg=WHITE)
        work_header.pack(fill="x", pady=(0, 8))
        tk.Button(
            work_header,
            text="‹",
            command=lambda: self._switch_view("home"),
            bd=0,
            bg=WHITE,
            fg=SUB_TEXT,
            activebackground=WHITE,
            activeforeground=INK,
            cursor="hand2",
            font=("Pretendard", 16, "bold"),
            width=2,
        ).pack(side="left")
        tk.Label(
            work_header,
            text=DISPLAY_NAME,
            bg=WHITE,
            fg=INK,
            font=("Pretendard", 13, "bold"),
        ).pack(side="left", padx=(4, 0))

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

        self.segment_frame = tk.Frame(app, bg=SURFACE, highlightbackground=HAIRLINE, highlightthickness=1)
        self.compose_mode_button = tk.Button(
            self.segment_frame,
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
            self.segment_frame,
            text="말투 점검",
            command=lambda: self._switch_view("mirror"),
            bd=0,
            relief="flat",
            cursor="hand2",
            font=("Pretendard", 10, "bold"),
            pady=6,
        )
        self.mirror_mode_button.pack(side="left", fill="x", expand=True, padx=(1, 2), pady=2)

        self.body = tk.Frame(app, bg=WHITE)
        self.body.pack(fill="both", expand=True)
        self.content_canvas = tk.Canvas(self.body, bg=WHITE, bd=0, highlightthickness=0)
        self.content_canvas.pack(side="left", fill="both", expand=True)
        self.content_scrollbar = tk.Scrollbar(self.body, orient="vertical", command=self.content_canvas.yview, width=10)
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
            text="⌂",
            command=lambda: self._switch_view("home"),
            bd=0,
            bg=ACCENT_MUTED,
            fg=INK,
            activebackground="#e9e9e9",
            activeforeground=INK,
            cursor="hand2",
            font=("Pretendard", 8, "bold"),
            width=3,
        ).pack(side="left", padx=(8, 0))
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

        self._switch_view("home")

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
        if view == "home":
            self.work_screen.pack_forget()
            self.home_screen.pack(fill="both", expand=True)
            return

        self.home_screen.pack_forget()
        if not self.work_screen.winfo_ismapped():
            self.work_screen.pack(fill="both", expand=True)
        self.compose_tab.pack_forget()
        self.mirror_tab.pack_forget()
        if not self.segment_frame.winfo_ismapped():
            self.segment_frame.pack(fill="x", pady=(0, 10), before=self.body)
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

    @staticmethod
    def _rounded_rect(
        canvas: tk.Canvas,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int,
        **kwargs: Any,
    ) -> None:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        canvas.create_polygon(points, smooth=True, **kwargs)

    @staticmethod
    def _rounded_gradient_image(
        width: int,
        height: int,
        radius: int,
        start_hex: str,
        end_hex: str,
    ) -> ImageTk.PhotoImage:
        def rgb(hex_color: str) -> tuple[int, int, int]:
            value = hex_color.lstrip("#")
            return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

        start = rgb(start_hex)
        end = rgb(end_hex)
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for y in range(height):
            blend = y / max(height - 1, 1)
            color = tuple(int(start[index] * (1 - blend) + end[index] * blend) for index in range(3))
            draw.line((0, y, width, y), fill=color + (255,))
        mask = Image.new("L", (width, height), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)
        image.putalpha(mask)
        return ImageTk.PhotoImage(image)

    def _build_home_screen(self, parent: tk.Frame) -> None:
        parent.pack_propagate(False)

        header = tk.Frame(parent, bg=WHITE, width=WINDOW_WIDTH, height=50)
        header.place(x=0, y=0)

        logo = tk.Canvas(header, width=26, height=26, bg=WHITE, bd=0, highlightthickness=0)
        logo.place(x=16, y=14)
        logo_image = self._rounded_gradient_image(26, 26, 8, ROSE, ACCENT)
        self._image_refs.append(logo_image)
        logo.create_image(13, 13, image=logo_image)
        logo.create_polygon(
            13,
            3,
            15.2,
            10.5,
            23,
            10.5,
            16.8,
            15,
            19,
            22.5,
            13,
            18,
            7,
            22.5,
            9.2,
            15,
            3,
            10.5,
            10.8,
            10.5,
            fill=WHITE,
        )
        tk.Label(
            header,
            text=DISPLAY_NAME,
            bg=WHITE,
            fg="#2e3036",
            font=("Pretendard", 14, "bold"),
        ).place(x=50, y=18)

        tk.Frame(parent, bg="#f0f0f0", height=1, width=WINDOW_WIDTH).place(x=0, y=50)

        tk.Label(
            parent,
            text="지금 메세지는 어떤 상태인가요?",
            bg=WHITE,
            fg="#26282d",
            font=("Pretendard", 18, "bold"),
        ).place(x=0, y=136, width=WINDOW_WIDTH)

        mood = tk.Canvas(parent, width=92, height=34, bg=WHITE, bd=0, highlightthickness=0, cursor="hand2")
        mood.place(x=134, y=216)
        self._rounded_rect(mood, 1, 1, 91, 33, 16, fill=WHITE, outline="#d9a2a3", width=2)
        mood.create_text(46, 17, text="막혔어요", fill=ROSE, font=("Pretendard", 13, "bold"))
        mood.bind("<Button-1>", lambda _event: self._switch_view("compose"))

        placeholder = "작성 중이던 초안이나 답장을 입력해 보세요"
        input_canvas = tk.Canvas(parent, width=320, height=44, bg=WHITE, bd=0, highlightthickness=0)
        input_canvas.place(x=20, y=282)
        self._rounded_rect(input_canvas, 0, 0, 320, 44, 22, fill=WHITE, outline="#ebebeb", width=1)

        quick_entry = tk.Entry(
            input_canvas,
            textvariable=self.quick_text_var,
            bd=0,
            relief="flat",
            bg=WHITE,
            fg="#a8a8a8",
            insertbackground=INK,
            font=("Pretendard", 9),
        )
        input_canvas.create_window(16, 22, window=quick_entry, anchor="w", width=252, height=28)
        quick_entry.insert(0, placeholder)

        send = tk.Canvas(input_canvas, width=30, height=30, bg=WHITE, bd=0, highlightthickness=0, cursor="hand2")
        send_image = self._rounded_gradient_image(30, 30, 15, ACCENT, ACCENT_DARK)
        self._image_refs.append(send_image)
        send.create_image(15, 15, image=send_image)
        send.create_line(15, 22, 15, 8, fill=WHITE, width=2, capstyle="round")
        send.create_line(15, 8, 9, 14, fill=WHITE, width=2, capstyle="round")
        send.create_line(15, 8, 21, 14, fill=WHITE, width=2, capstyle="round")
        send.bind("<Button-1>", lambda _event: self._send_home_text(placeholder))
        input_canvas.create_window(284, 22, window=send, anchor="center")

        def on_focus_in(_: object) -> None:
            if quick_entry.get() == placeholder:
                quick_entry.delete(0, "end")
                quick_entry.configure(fg="#333333")

        def on_focus_out(_: object) -> None:
            if not quick_entry.get().strip():
                quick_entry.insert(0, placeholder)
                quick_entry.configure(fg="#a8a8a8")

        quick_entry.bind("<FocusIn>", on_focus_in)
        quick_entry.bind("<FocusOut>", on_focus_out)
        quick_entry.bind("<Return>", lambda _event: self._send_home_text(placeholder))

        tk.Frame(parent, bg="#f0f0f0", height=1, width=WINDOW_WIDTH).place(x=0, y=477)

        footer_btn = tk.Canvas(parent, width=26, height=26, bg=WHITE, bd=0, highlightthickness=0)
        footer_btn.place(x=14, y=486)
        self._rounded_rect(footer_btn, 0, 0, 26, 26, 7, fill="#f3f3f3", outline="")
        footer_btn.create_oval(7, 7, 19, 19, outline="#777777", width=1)
        footer_btn.create_oval(11, 11, 15, 15, outline="#777777", width=1)
        footer_btn.create_line(13, 2, 13, 5, fill="#777777", width=1, capstyle="round")
        footer_btn.create_line(13, 21, 13, 24, fill="#777777", width=1, capstyle="round")
        footer_btn.create_line(2, 13, 5, 13, fill="#777777", width=1, capstyle="round")
        footer_btn.create_line(21, 13, 24, 13, fill="#777777", width=1, capstyle="round")

    def _send_home_text(self, placeholder: str) -> None:
        text = self.quick_text_var.get().strip()
        if not text or text == placeholder:
            return
        self._switch_view("mirror")
        self.mirror_text.delete("1.0", "end")
        self.mirror_text.insert("1.0", text)
        self._set_status("말투 점검에 초안을 넣었어요")

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
            activebackground=ACCENT_DARK,
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
        self.icon = Icon(APP_NAME, image, DISPLAY_NAME, menu)
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
        for y in range(8, 56):
            blend = (y - 8) / 48
            red = int(176 * (1 - blend) + 65 * blend)
            green = int(90 * (1 - blend) + 69 * blend)
            blue = int(91 * (1 - blend) + 107 * blend)
            draw.line((8, y, 56, y), fill=(red, green, blue, 255))
        mask = Image.new("L", (64, 64), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((8, 8, 56, 56), radius=14, fill=255)
        image.putalpha(mask)
        draw = ImageDraw.Draw(image)
        draw.polygon(
            [
                (32, 15),
                (36, 27),
                (49, 27),
                (39, 35),
                (43, 48),
                (32, 40),
                (21, 48),
                (25, 35),
                (15, 27),
                (28, 27),
            ],
            fill=WHITE,
        )
        return image


class FeedTrayApp:
    def __init__(self):
        load_env()
        base_url = os.environ.get("REFINER_API_BASE_URL", DEFAULT_API_BASE_URL)
        self.api = APIClient(base_url)
        self.backend = BackendProcess(self.api)
        self.settings = SettingsStore()
        self.settings_data = self.settings.load()
        self.user_id: str | None = self.settings_data.get("user_id")
        self.icon: Icon | None = None
        self._image_refs: list[Any] = []

        self.root = tk.Tk()
        self.root.title(DISPLAY_NAME)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.root.withdraw()
        window_icon = ImageTk.PhotoImage(TrayApp._create_icon_image())
        self._image_refs.append(window_icon)
        self.root.iconphoto(True, window_icon)

        self.save_history_var = tk.BooleanVar(value=bool(self.settings_data.get("save_history", False)))
        self.status_message = "준비 중..."
        self.mode = "review"
        self.step = "idle"
        self.purpose_var = tk.StringVar(value="요청")
        self.long_type_var = tk.StringVar(value="메일")
        self.input_var = tk.StringVar()
        self.input_has_placeholder = False
        self.placeholder_text = ""
        self.sent_text = ""
        self.sent_mode = "review"
        self.compose_session_id: str | None = None
        self.compose_candidates: list[dict[str, Any]] = []
        self.selected_draft_index = 0
        self.draft_copied_index: int | None = None
        self.mirror_result: dict[str, Any] | None = None
        self.long_review_result: dict[str, Any] | None = None
        self.final_copied = False
        self.is_busy = False

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
        self.root.configure(bg=FRAME_BG)

        self.shell = tk.Frame(
            self.root,
            bg=FRAME_BG,
            highlightbackground=FRAME_LINE,
            highlightcolor=FRAME_LINE,
            highlightthickness=1,
        )
        self.shell.pack(fill="both", expand=True)

        self._build_header()
        self._build_feed()
        self._build_footer()
        self._render_feed()

    def _build_header(self) -> None:
        header = tk.Frame(self.shell, bg=FRAME_BG)
        header.pack(fill="x", padx=16, pady=(14, 10))

        logo = tk.Canvas(header, width=26, height=26, bg=FRAME_BG, bd=0, highlightthickness=0)
        logo.pack(side="left")
        logo_image = TrayApp._rounded_gradient_image(26, 26, 8, ROSE, ACCENT)
        self._image_refs.append(logo_image)
        logo.create_image(13, 13, image=logo_image)
        logo.create_polygon(
            13,
            3,
            15.2,
            10.5,
            23,
            10.5,
            16.8,
            15,
            19,
            22.5,
            13,
            18,
            7,
            22.5,
            9.2,
            15,
            3,
            10.5,
            10.8,
            10.5,
            fill=WHITE,
        )

        tk.Label(
            header,
            text=DISPLAY_NAME,
            bg=FRAME_BG,
            fg="#2e3036",
            font=("Pretendard", 14, "bold"),
        ).pack(side="left", padx=(8, 0))

    def _build_feed(self) -> None:
        feed_wrap = tk.Frame(self.shell, bg=FRAME_BG)
        feed_wrap.pack(fill="both", expand=True, padx=16, pady=(0, 0))

        self.feed_canvas = tk.Canvas(feed_wrap, bg=FRAME_BG, bd=0, highlightthickness=0)
        self.feed_canvas.pack(fill="both", expand=True)
        self.feed_content = tk.Frame(self.feed_canvas, bg=FRAME_BG)
        self.feed_window = self.feed_canvas.create_window((0, 0), window=self.feed_content, anchor="nw")
        self.feed_content.bind("<Configure>", self._on_feed_configure)
        self.feed_canvas.bind("<Configure>", self._on_feed_canvas_configure)
        self.root.bind_all("<MouseWheel>", self._on_feed_mousewheel)

    def _build_footer(self) -> None:
        self.footer = tk.Frame(self.shell, bg=FRAME_BG)
        self.footer.pack(fill="x", padx=14, pady=(10, 14))

        self.composer = tk.Frame(self.footer, bg=FRAME_BG)
        self.composer.pack(fill="x")

        self.mode_row = tk.Frame(self.composer, bg=FRAME_BG)
        self.mode_row.pack(anchor="center")
        self.mood_button = tk.Canvas(
            self.mode_row,
            width=104,
            height=36,
            bd=0,
            bg=FRAME_BG,
            highlightthickness=0,
            cursor="hand2",
        )
        self.mood_button.pack(side="left", padx=(0, 8))
        self.mood_button.bind("<Button-1>", lambda _event: self._toggle_mode())

        self.long_button = tk.Canvas(
            self.mode_row,
            width=112,
            height=36,
            bd=0,
            bg=FRAME_BG,
            highlightthickness=0,
            cursor="hand2",
        )
        self.long_button.pack(side="left")
        self.long_button.bind("<Button-1>", lambda _event: self._toggle_long_mode())

        self.purpose_row = tk.Frame(self.composer, bg=FRAME_BG)
        self.purpose_buttons: dict[str, tk.Button] = {}
        for purpose in PURPOSES:
            button = tk.Button(
                self.purpose_row,
                text=purpose,
                command=lambda selected=purpose: self._set_purpose(selected),
                bd=0,
                relief="flat",
                cursor="hand2",
                font=("Pretendard", 10),
                padx=0,
                pady=6,
            )
            button.pack(side="left", fill="x", expand=True, padx=(0, 6 if purpose != PURPOSES[-1] else 0))
            self.purpose_buttons[purpose] = button

        self.long_type_row = tk.Frame(self.composer, bg=FRAME_BG)
        self.long_type_buttons: dict[str, tk.Button] = {}
        for doc_type in LONG_REVIEW_TYPES:
            button = tk.Button(
                self.long_type_row,
                text=doc_type,
                command=lambda selected=doc_type: self._set_long_type(selected),
                bd=0,
                relief="flat",
                cursor="hand2",
                font=("Pretendard", 9),
                padx=0,
                pady=6,
            )
            button.pack(side="left", fill="x", expand=True, padx=(0, 5 if doc_type != LONG_REVIEW_TYPES[-1] else 0))
            self.long_type_buttons[doc_type] = button

        input_row = tk.Frame(
            self.composer,
            bg="#f8f7fb",
            highlightbackground="#d9d7df",
            highlightcolor="#d9d7df",
            highlightthickness=1,
        )
        input_row.pack(fill="x", pady=(8, 0), ipady=4)

        self.input_entry = tk.Entry(
            input_row,
            textvariable=self.input_var,
            bd=0,
            relief="flat",
            bg="#f8f7fb",
            fg="#3a3840",
            insertbackground=INK,
            font=("Pretendard", 10),
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(16, 8), ipady=7)
        self.input_entry.bind("<Return>", lambda _event: self._send_composer())
        self.input_entry.bind("<FocusIn>", self._clear_input_placeholder)
        self.input_entry.bind("<FocusOut>", self._restore_input_placeholder)
        self.input_entry.bind("<KeyPress>", self._on_input_keypress)

        self.send_button = tk.Canvas(
            input_row,
            width=38,
            height=36,
            bd=0,
            bg="#f8f7fb",
            highlightthickness=0,
            cursor="hand2",
        )
        self.send_button.pack(side="right", padx=(0, 6))
        self.send_button.bind("<Button-1>", lambda _event: self._send_composer())

        footer_line = tk.Frame(self.footer, bg="#d9d7df", height=1)
        footer_line.pack(fill="x", pady=(12, 8))

        footer_bottom = tk.Frame(self.footer, bg=FRAME_BG)
        footer_bottom.pack(fill="x")
        self.reset_button = tk.Button(
            footer_bottom,
            text="◎",
            command=self._reset_feed,
            bd=0,
            relief="flat",
            bg="#dedce5",
            fg=MUTED_INK,
            activebackground="#d2cfda",
            activeforeground=INK,
            cursor="hand2",
            font=("Pretendard", 11, "bold"),
            width=3,
            pady=2,
        )
        self.reset_button.pack(side="left")

        self._update_composer_state()
        self._restore_input_placeholder()

    def _on_feed_configure(self, _event: object) -> None:
        self.feed_canvas.configure(scrollregion=self.feed_canvas.bbox("all"))

    def _on_feed_canvas_configure(self, event: object) -> None:
        width = getattr(event, "width", WINDOW_WIDTH - 32)
        self.feed_canvas.itemconfigure(self.feed_window, width=width)

    def _on_feed_mousewheel(self, event: object) -> None:
        delta = getattr(event, "delta", 0)
        if delta:
            self.feed_canvas.yview_scroll(int(-1 * (delta / 120)), "units")

    def _toggle_mode(self) -> None:
        if self.is_busy or self.step != "idle":
            return
        self.mode = "review" if self.mode == "blocked" else "blocked"
        self.input_has_placeholder = False
        self.input_var.set("")
        self._update_composer_state()
        self._render_feed()
        self.input_entry.focus_set()

    def _toggle_long_mode(self) -> None:
        if self.is_busy or self.step != "idle":
            return
        self.mode = "longform" if self.mode != "longform" else "review"
        self.input_has_placeholder = False
        self.input_var.set("")
        self._update_composer_state()
        self._render_feed()
        self.input_entry.focus_set()

    def _set_purpose(self, purpose: str) -> None:
        if self.is_busy or self.step != "idle":
            return
        self.purpose_var.set(purpose)
        self._update_composer_state()

    def _set_long_type(self, doc_type: str) -> None:
        if self.is_busy or self.step != "idle":
            return
        self.long_type_var.set(doc_type)
        self._update_composer_state()
        self._render_feed()

    def _send_composer(self) -> None:
        if self.is_busy or self.step != "idle":
            return
        text = self._actual_input_text()
        if not text:
            return

        self.sent_text = text
        self.sent_mode = self.mode
        self.input_var.set("")
        self.input_has_placeholder = False
        self.is_busy = True

        if self.mode == "blocked":
            self.step = "drafting"
            self._render_feed()
            self._update_composer_state()
            payload = {
                "user_id": self.user_id,
                "recipient": None,
                "context": text,
                "purpose": self.purpose_var.get(),
                "tone": "부드럽게",
                "save_history": self.save_history_var.get(),
            }
            self._run_background("상황에 맞는 초안 생성 중...", lambda: self._compose_worker(payload))
            return

        if self.mode == "longform":
            self.step = "long_reviewing"
            self._render_feed()
            self._update_composer_state()
            payload = {
                "user_id": self.user_id,
                "text": text,
                "document_type": self.long_type_var.get(),
                "purpose": self.long_type_var.get(),
                "save_history": self.save_history_var.get(),
            }
            self._run_background("긴 글을 첨삭하고 요약하는 중...", lambda: self._long_review_worker(payload))
            return

        self.step = "analyzing"
        self._render_feed()
        self._update_composer_state()
        payload = {
            "user_id": self.user_id,
            "text": text,
            "source_type": "direct_input",
            "recipient": None,
            "context": None,
            "purpose": self.purpose_var.get(),
            "tone": None,
            "save_history": self.save_history_var.get(),
        }
        self._run_background("상대방에게 어떻게 전달될지 분석 중...", lambda: self._mirror_worker(payload))

    def _compose_worker(self, payload: dict[str, Any]) -> None:
        data = self.api.compose(payload)
        self.root.after(0, lambda: self._show_drafts(data))

    def _show_drafts(self, data: dict[str, Any]) -> None:
        self.compose_session_id = str(data["session_id"])
        self.compose_candidates = list(data["candidates"])
        self.selected_draft_index = min(1, max(len(self.compose_candidates) - 1, 0))
        self.is_busy = False
        self.step = "drafts"
        self._set_status("추천 초안 생성 완료")
        self._render_feed()
        self._update_composer_state()

    def _select_draft(self, index: int) -> None:
        self.selected_draft_index = index
        self._render_feed()

    def _copy_draft(self, index: int) -> None:
        if index >= len(self.compose_candidates):
            return
        text = str(self.compose_candidates[index].get("candidate_text", ""))
        self._copy_to_clipboard(text)
        self.draft_copied_index = index
        self._render_feed()
        self.root.after(1400, self._clear_draft_copied)

    def _clear_draft_copied(self) -> None:
        self.draft_copied_index = None
        if self.step == "drafts":
            self._render_feed()

    def _confirm_draft(self) -> None:
        if self.is_busy or not self.compose_candidates:
            return
        selected = self.compose_candidates[self.selected_draft_index]
        self.is_busy = True
        self.step = "analyzing"
        self._render_feed()
        self._update_composer_state()
        payload = {
            "user_id": self.user_id,
            "session_id": self.compose_session_id,
            "candidate_id": selected.get("candidate_id"),
            "text": selected.get("candidate_text", ""),
            "source_type": "quick_compose_candidate",
            "recipient": None,
            "context": self.sent_text,
            "purpose": self.purpose_var.get(),
            "tone": "부드럽게",
            "save_history": self.save_history_var.get(),
        }
        self._run_background("선택한 초안을 Mirror로 확인 중...", lambda: self._mirror_worker(payload))

    def _mirror_worker(self, payload: dict[str, Any]) -> None:
        data = self.api.mirror(payload)
        self.root.after(0, lambda: self._show_analysis(data))

    def _long_review_worker(self, payload: dict[str, Any]) -> None:
        data = self.api.long_review(payload)
        self.root.after(0, lambda: self._show_long_review(data))

    def _show_long_review(self, data: dict[str, Any]) -> None:
        self.long_review_result = data
        self.is_busy = False
        self.step = "long_done"
        self._set_status("긴글 첨삭 완료")
        self._render_feed()
        self._update_composer_state()

    def _show_analysis(self, data: dict[str, Any]) -> None:
        self.mirror_result = data
        self.is_busy = False
        self.step = "analyzed"
        self._set_status("Mirror 분석 완료")
        self._render_feed()
        self._update_composer_state()

    def _confirm_rewrite(self) -> None:
        if self.is_busy or not self.mirror_result:
            return
        self.is_busy = True
        self.step = "rewriting"
        self._render_feed()
        self.root.after(700, self._show_final)

    def _show_final(self) -> None:
        self.is_busy = False
        self.step = "done"
        self._set_status("교정 문장 준비 완료")
        self._render_feed()
        self._update_composer_state()

    def _copy_final(self) -> None:
        final_text = self._final_text()
        if not final_text:
            return
        self._copy_to_clipboard(final_text)
        self.final_copied = True
        self._render_feed()
        self.root.after(1800, self._clear_final_copied)

    def _clear_final_copied(self) -> None:
        self.final_copied = False
        if self.step == "done":
            self._render_feed()

    def _copy_long_edited(self) -> None:
        if not self.long_review_result:
            return
        text = str(self.long_review_result.get("edited_text") or "").strip()
        if text:
            self._copy_to_clipboard(text)
            self._set_status("첨삭본 복사 완료")

    def _copy_long_summary(self) -> None:
        if not self.long_review_result:
            return
        text = str(self.long_review_result.get("summary_text") or "").strip()
        if text:
            self._copy_to_clipboard(text)
            self._set_status("요약 복사 완료")

    def _reset_feed(self) -> None:
        self.step = "idle"
        self.is_busy = False
        self.sent_text = ""
        self.sent_mode = self.mode
        self.compose_session_id = None
        self.compose_candidates = []
        self.selected_draft_index = 0
        self.draft_copied_index = None
        self.mirror_result = None
        self.long_review_result = None
        self.final_copied = False
        self._set_status("새 메시지 준비")
        self._render_feed()
        self._update_composer_state()
        self._restore_input_placeholder()
        self.input_entry.focus_set()

    def _render_feed(self) -> None:
        for child in self.feed_content.winfo_children():
            child.destroy()

        if self.step == "idle":
            empty = tk.Frame(self.feed_content, bg=FRAME_BG)
            empty.pack(fill="both", expand=True, pady=(118, 0))
            tk.Label(
                empty,
                text=self._idle_question(),
                bg=FRAME_BG,
                fg="#2d2b32",
                font=("Pretendard", 15, "bold"),
                justify="center",
                wraplength=310,
            ).pack(anchor="center")
        else:
            feed = tk.Frame(self.feed_content, bg=FRAME_BG)
            feed.pack(fill="both", expand=True, pady=(6, 0))
            self._user_bubble(feed, self.sent_text)

            if self.step == "drafting":
                self._loading_row(feed, "상황에 맞는 초안 3개를 생성 중이에요...")

            if self.step == "long_reviewing":
                self._loading_row(feed, "긴 글을 첨삭하고 핵심을 요약 중이에요...")

            if self.step == "drafts":
                self._draft_list_card(feed)

            if self.step == "analyzing":
                self._loading_row(feed, "상대방에게 어떻게 전달될지 분석 중이에요...")

            if self.step in {"analyzed", "rewriting", "done"}:
                self._analysis_card(feed)

            if self.step == "rewriting":
                self._loading_row(feed, "문장을 교정 중이에요...")

            if self.step == "done":
                self._final_card(feed)

            if self.step == "long_done":
                self._long_review_card(feed)

        self.root.after(0, self._scroll_to_bottom)

    def _user_bubble(self, parent: tk.Widget, text: str) -> None:
        row = tk.Frame(parent, bg=FRAME_BG)
        row.pack(fill="x", pady=(0, 14))
        bubble = tk.Label(
            row,
            text=text,
            bg=ACCENT,
            fg=WHITE,
            font=("Pretendard", 10),
            justify="left",
            wraplength=240,
            padx=13,
            pady=10,
        )
        bubble.pack(side="right", anchor="e")

    def _loading_row(self, parent: tk.Widget, label: str) -> None:
        row = tk.Frame(parent, bg=FRAME_BG)
        row.pack(fill="x", pady=(0, 14))
        tk.Label(
            row,
            text="◌",
            bg=FRAME_BG,
            fg=ACCENT,
            font=("Pretendard", 14, "bold"),
        ).pack(side="left")
        tk.Label(
            row,
            text=label,
            bg=FRAME_BG,
            fg="#5e5b65",
            font=("Pretendard", 10, "bold"),
        ).pack(side="left", padx=(8, 0))

    def _draft_list_card(self, parent: tk.Widget) -> None:
        card = self._feed_card(parent)
        self._section_label(card, "추천 초안 3가지")

        for index, candidate in enumerate(self.compose_candidates[:3]):
            selected = index == self.selected_draft_index
            draft = tk.Frame(
                card,
                bg="#eef0f7" if selected else "#fbfafc",
                highlightbackground="#9da2bd" if selected else "#dddddf",
                highlightthickness=1,
            )
            draft.pack(fill="x", pady=(0, 8), ipady=1)
            draft.bind("<Button-1>", lambda _event, i=index: self._select_draft(i))

            top = tk.Frame(draft, bg=draft["bg"])
            top.pack(fill="x", padx=11, pady=(9, 5))
            badge_text = DRAFT_BADGES[index] if index < len(DRAFT_BADGES) else f"후보 {index + 1}"
            tk.Label(
                top,
                text=badge_text,
                bg="#e5e7f1",
                fg=ACCENT,
                font=("Pretendard", 8, "bold"),
                padx=7,
                pady=2,
            ).pack(side="left")
            copy_text = "✓" if self.draft_copied_index == index else "⧉"
            tk.Button(
                top,
                text=copy_text,
                command=lambda i=index: self._copy_draft(i),
                bd=0,
                relief="flat",
                bg="#ecebf0",
                fg=ACCENT if self.draft_copied_index == index else MUTED_INK,
                activebackground="#dedce5",
                cursor="hand2",
                font=("Pretendard", 8, "bold"),
                width=3,
            ).pack(side="right")

            label = tk.Label(
                draft,
                text=str(candidate.get("candidate_text", "")),
                bg=draft["bg"],
                fg="#56525b",
                font=("Pretendard", 9),
                justify="left",
                wraplength=280,
            )
            label.pack(fill="x", padx=11, pady=(0, 10), anchor="w")
            label.bind("<Button-1>", lambda _event, i=index: self._select_draft(i))

        self._primary_button(card, "선택하고 Mirror로 확인", self._confirm_draft).pack(fill="x", pady=(2, 0))

    def _analysis_card(self, parent: tk.Widget) -> None:
        if not self.mirror_result:
            return
        data = self.mirror_result
        card = self._feed_card(parent)

        feedback = tk.Frame(card, bg=WARN_BG, highlightbackground="#c58c8f", highlightthickness=1)
        feedback.pack(fill="x", pady=(0, 12), ipady=2)
        header = tk.Frame(feedback, bg=WARN_BG)
        header.pack(fill="x", padx=12, pady=(10, 5))
        tk.Label(
            header,
            text="!",
            bg=WARN_BG,
            fg=WARN_FG,
            font=("Pretendard", 9, "bold"),
        ).pack(side="left")
        tk.Label(
            header,
            text="이렇게 읽힐 수 있어요",
            bg=WARN_BG,
            fg=WARN_FG,
            font=("Pretendard", 8, "bold"),
        ).pack(side="left", padx=(6, 0))

        feedback_text = self._analysis_feedback_text(data)
        tk.Label(
            feedback,
            text=feedback_text,
            bg=WARN_BG,
            fg=WARN_FG,
            font=("Pretendard", 9),
            justify="left",
            wraplength=278,
        ).pack(fill="x", padx=12, pady=(0, 10), anchor="w")

        self._section_label(card, "분석 상태")
        status_grid = tk.Frame(card, bg=CARD_BG)
        status_grid.pack(fill="x", pady=(0, 12))
        tags = self._status_tags(data)
        for row_index in range(2):
            row = tk.Frame(status_grid, bg=CARD_BG)
            row.pack(fill="x", pady=(0, 6 if row_index == 0 else 0))
            for col_index in range(2):
                tag_index = row_index * 2 + col_index
                label, warn = tags[tag_index]
                tag = tk.Label(
                    row,
                    text=label,
                    bg=WARN_BG if warn else "#fbfafc",
                    fg=WARN_FG if warn else "#77747e",
                    font=("Pretendard", 8, "bold"),
                    padx=8,
                    pady=7,
                    highlightbackground="#c58c8f" if warn else "#dddddf",
                    highlightthickness=1,
                )
                tag.pack(side="left", fill="x", expand=True, padx=(0, 6 if col_index == 0 else 0))

        if self.step == "analyzed":
            self._primary_button(card, "교정 문장 확인하기", self._confirm_rewrite).pack(fill="x")

    def _final_card(self, parent: tk.Widget) -> None:
        card = self._feed_card(parent)
        self._section_label(card, "최종 미리보기")
        preview = tk.Frame(card, bg="#fbfafc", highlightbackground="#dddddf", highlightthickness=1)
        preview.pack(fill="x", pady=(0, 12))
        tk.Label(
            preview,
            text=self._final_text(),
            bg="#fbfafc",
            fg="#56525b",
            font=("Pretendard", 9),
            justify="left",
            wraplength=282,
        ).pack(fill="x", padx=12, pady=12, anchor="w")
        label = "복사 완료 ✓" if self.final_copied else "복사하기"
        color = ROSE if self.final_copied else ACCENT
        self._primary_button(card, label, self._copy_final, bg=color).pack(fill="x")

    def _long_review_card(self, parent: tk.Widget) -> None:
        if not self.long_review_result:
            return
        data = self.long_review_result
        card = self._feed_card(parent)

        self._section_label(card, "자동 요약")
        self._text_panel(card, str(data.get("summary_text") or ""))

        key_points = data.get("key_points") or []
        if key_points:
            self._section_label(card, "핵심 포인트")
            self._text_panel(card, "\n".join(f"- {point}" for point in key_points))

        self._section_label(card, "첨삭본")
        self._text_panel(card, str(data.get("edited_text") or ""))

        changes = data.get("changes") or []
        if changes:
            self._section_label(card, "수정 포인트")
            self._text_panel(card, "\n".join(f"- {change}" for change in changes))

        reason = str(data.get("ai_reason") or "").strip()
        if reason:
            self._section_label(card, "첨삭 근거")
            self._text_panel(card, reason)

        actions = tk.Frame(card, bg=CARD_BG)
        actions.pack(fill="x", pady=(2, 0))
        self._primary_button(actions, "첨삭본 복사", self._copy_long_edited).pack(
            side="left",
            fill="x",
            expand=True,
            padx=(0, 6),
        )
        self._primary_button(actions, "요약 복사", self._copy_long_summary, bg=ROSE).pack(
            side="left",
            fill="x",
            expand=True,
        )

    def _text_panel(self, parent: tk.Widget, text: str) -> None:
        panel = tk.Frame(parent, bg="#fbfafc", highlightbackground="#dddddf", highlightthickness=1)
        panel.pack(fill="x", pady=(0, 12))
        tk.Label(
            panel,
            text=text,
            bg="#fbfafc",
            fg="#56525b",
            font=("Pretendard", 9),
            justify="left",
            wraplength=282,
        ).pack(fill="x", padx=12, pady=10, anchor="w")

    def _feed_card(self, parent: tk.Widget) -> tk.Frame:
        card = tk.Frame(
            parent,
            bg=CARD_BG,
            highlightbackground=CARD_BORDER,
            highlightcolor=CARD_BORDER,
            highlightthickness=1,
        )
        card.pack(fill="x", pady=(0, 14), ipady=2)
        inner = tk.Frame(card, bg=CARD_BG)
        inner.pack(fill="x", padx=14, pady=14)
        return inner

    def _section_label(self, parent: tk.Widget, text: str) -> None:
        tk.Label(
            parent,
            text=text,
            bg=CARD_BG,
            fg="#8a8790",
            font=("Pretendard", 8, "bold"),
        ).pack(anchor="w", pady=(0, 6))

    def _primary_button(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        bg: str = ACCENT,
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bd=0,
            relief="flat",
            bg=bg,
            fg=WHITE,
            activebackground=ACCENT_DARK,
            activeforeground=WHITE,
            cursor="hand2",
            font=("Pretendard", 10, "bold"),
            pady=9,
        )

    def _analysis_feedback_text(self, data: dict[str, Any]) -> str:
        ai_reason = str(data.get("ai_reason") or "").strip()
        tone_evidence = str(data.get("tone_evidence") or "").strip()
        if ai_reason and tone_evidence:
            return f"{ai_reason}\n{tone_evidence}"
        if ai_reason:
            return ai_reason
        if tone_evidence:
            return tone_evidence
        reasons = data.get("risk_reasons") or []
        if isinstance(reasons, list) and reasons:
            return str(reasons[0])
        return "문장의 의도는 보존하면서 상대가 부담을 덜 느끼도록 표현을 조정할 수 있어요."

    def _status_tags(self, data: dict[str, Any]) -> list[tuple[str, bool]]:
        risk = str(data.get("risk_level") or "").strip()
        warn = risk in {"보통", "높음"}
        return [
            ("의도 보존 ✓", False),
            ("톤 주의" if warn else "톤 안정 ✓", warn),
            ("구조 ✓", False),
            ("위험 단어 없음" if not warn else f"위험도 {risk}", warn),
        ]

    def _final_text(self) -> str:
        if not self.mirror_result:
            return ""
        return str(
            self.mirror_result.get("soft_rewrite")
            or self.mirror_result.get("clear_rewrite")
            or self.mirror_result.get("short_rewrite")
            or ""
        ).strip()

    def _update_composer_state(self) -> None:
        locked = self.step != "idle" or self.is_busy
        mood_active = self.mode == "blocked"
        long_active = self.mode == "longform"
        self._draw_mood_button(mood_active=mood_active, locked=locked)
        self._draw_long_button(active=long_active, locked=locked)

        if self.mode == "blocked":
            if not self.purpose_row.winfo_ismapped():
                self.purpose_row.pack(fill="x", pady=(8, 0))
        else:
            self.purpose_row.pack_forget()

        if self.mode == "longform":
            if not self.long_type_row.winfo_ismapped():
                self.long_type_row.pack(fill="x", pady=(8, 0))
        else:
            self.long_type_row.pack_forget()

        for purpose, button in self.purpose_buttons.items():
            active = self.purpose_var.get() == purpose
            button.configure(
                bg="#e9eaf2" if active else "#fbfafc",
                fg=ACCENT if active else "#77747e",
                activebackground="#e9eaf2",
                state="disabled" if locked else "normal",
            )

        for doc_type, button in self.long_type_buttons.items():
            active = self.long_type_var.get() == doc_type
            button.configure(
                bg="#e9eaf2" if active else "#fbfafc",
                fg=ACCENT if active else "#77747e",
                activebackground="#e9eaf2",
                state="disabled" if locked else "normal",
            )

        self.input_entry.configure(
            state="disabled" if locked else "normal",
            fg="#8f8b95" if self.input_has_placeholder else "#3a3840",
        )
        self.input_entry["disabledforeground"] = "#8f8b95"
        self.input_entry["insertbackground"] = INK
        self._draw_send_button(locked=locked)
        if self.input_has_placeholder or not self.input_var.get().strip():
            self._restore_input_placeholder()

    def _draw_mood_button(self, mood_active: bool, locked: bool) -> None:
        self.mood_button.delete("all")
        fill = ROSE if mood_active else "#fbfafc"
        outline = ROSE if mood_active else "#d6aaa9"
        text_fill = WHITE if mood_active else ROSE
        if locked:
            fill = "#eeeaf0"
            outline = "#ddd7df"
            text_fill = "#b5a9b0"
        TrayApp._rounded_rect(self.mood_button, 2, 2, 102, 34, 17, fill=fill, outline=outline, width=1)
        self.mood_button.create_text(
            52,
            18,
            text="막혔어요",
            fill=text_fill,
            font=("Pretendard", 11, "bold"),
        )

    def _draw_long_button(self, active: bool, locked: bool) -> None:
        self.long_button.delete("all")
        fill = ACCENT if active else "#fbfafc"
        outline = ACCENT if active else "#c8cad8"
        text_fill = WHITE if active else ACCENT
        if locked:
            fill = "#eeeaf0"
            outline = "#ddd7df"
            text_fill = "#b5a9b0"
        TrayApp._rounded_rect(self.long_button, 2, 2, 110, 34, 17, fill=fill, outline=outline, width=1)
        self.long_button.create_text(
            56,
            18,
            text="긴글 첨삭",
            fill=text_fill,
            font=("Pretendard", 11, "bold"),
        )

    def _draw_send_button(self, locked: bool) -> None:
        self.send_button.delete("all")
        fill = "#9ca0b8" if locked else ACCENT
        self.send_button.create_oval(4, 3, 34, 33, fill=fill, outline=fill)
        self.send_button.create_line(19, 25, 19, 11, fill=WHITE, width=2, capstyle="round")
        self.send_button.create_line(19, 11, 13, 17, fill=WHITE, width=2, capstyle="round")
        self.send_button.create_line(19, 11, 25, 17, fill=WHITE, width=2, capstyle="round")

    def _current_placeholder(self) -> str:
        if self.mode == "longform":
            return f"{self.long_type_var.get()} 글을 붙여넣으면 첨삭과 요약을 해드려요"
        if self.mode == "blocked":
            return "핵심 상황이나 생각을 자유롭게 적어보세요"
        return "작성 중이던 초안이나 답장을 입력해 보세요"

    def _idle_question(self) -> str:
        if self.mode == "longform":
            return "어떤 글을 첨삭할까요?"
        if self.mode == "blocked":
            return "어떤 상황에서 막혔나요?"
        return "지금 메세지는 어떤 상태인가요?"

    def _known_placeholders(self) -> set[str]:
        placeholders = {
            self.placeholder_text,
            "핵심 상황이나 생각을 자유롭게 적어보세요",
            "작성 중이던 초안이나 답장을 입력해 보세요",
        }
        placeholders.update(f"{doc_type} 글을 붙여넣으면 첨삭과 요약을 해드려요" for doc_type in LONG_REVIEW_TYPES)
        return {text for text in placeholders if text}

    def _actual_input_text(self) -> str:
        text = self.input_var.get().strip()
        for placeholder in self._known_placeholders():
            if text == placeholder:
                return ""
            if text.startswith(placeholder):
                return text[len(placeholder) :].strip()
        return text

    def _on_input_keypress(self, event: object) -> None:
        if not self.input_has_placeholder:
            return
        keysym = getattr(event, "keysym", "")
        if keysym in {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Tab", "Caps_Lock"}:
            return
        self._clear_input_placeholder()

    def _clear_input_placeholder(self, _event: object | None = None) -> None:
        if not self.input_has_placeholder:
            return
        self.input_has_placeholder = False
        self.placeholder_text = ""
        self.input_var.set("")
        self.input_entry.configure(fg="#3a3840")

    def _restore_input_placeholder(self, _event: object | None = None) -> None:
        if self.step != "idle" or self.is_busy:
            return
        if self.input_var.get().strip() and not self.input_has_placeholder:
            return
        self.input_has_placeholder = True
        self.placeholder_text = self._current_placeholder()
        self.input_var.set(self.placeholder_text)
        self.input_entry.configure(fg="#8f8b95")

    def _scroll_to_bottom(self) -> None:
        self.feed_canvas.configure(scrollregion=self.feed_canvas.bbox("all"))
        self.feed_canvas.yview_moveto(1.0)

    def _copy_to_clipboard(self, text: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def _run_background(self, status: str, task: Callable[[], Any]) -> None:
        self._set_status(status)

        def runner() -> None:
            try:
                task()
            except Exception as exc:
                message = str(exc)
                self.root.after(0, lambda error=message: self._show_error(error))

        threading.Thread(target=runner, daemon=True).start()

    def _show_error(self, message: str) -> None:
        self.is_busy = False
        if self.step in {"drafting", "analyzing", "rewriting", "long_reviewing"}:
            self.step = "idle"
        self._render_feed()
        self._update_composer_state()
        self._set_status("오류 발생")
        messagebox.showerror(APP_NAME, message)

    def _run_tray_icon(self) -> None:
        image = TrayApp._create_icon_image()
        menu = Menu(
            MenuItem("작업창 열기", lambda _icon, _item: self.show_window(), default=True),
            MenuItem("숨기기", lambda _icon, _item: self.root.after(0, self.hide_window)),
            MenuItem("종료", lambda _icon, _item: self.quit()),
        )
        self.icon = Icon(APP_NAME, image, DISPLAY_NAME, menu)
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
        work_area = TrayApp._get_windows_work_area()
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

    def _set_status(self, message: str) -> None:
        self.status_message = message
        self.root.after(0, lambda: self.root.title(DISPLAY_NAME))


class WebTrayApp:
    def __init__(self):
        load_env()
        base_url = os.environ.get("REFINER_API_BASE_URL", DEFAULT_API_BASE_URL)
        self.api = APIClient(base_url)
        self.backend = BackendProcess(self.api)
        self.icon: Icon | None = None
        self.web_process: subprocess.Popen[str] | None = None
        self._startup_done = threading.Event()
        self._startup_error: str | None = None
        self._open_lock = threading.Lock()

    def run(self) -> None:
        threading.Thread(target=self._startup, daemon=True).start()
        self._run_tray_icon()

    def show_window(self) -> None:
        threading.Thread(target=self._show_window_worker, daemon=True).start()

    def hide_window(self) -> None:
        self._close_web_window()

    def quit(self) -> None:
        self._close_web_window()
        self.backend.stop()
        if self.icon:
            self.icon.stop()

    def _startup(self) -> None:
        try:
            self._ensure_frontend_built()
            self._ensure_backend_with_frontend()
        except Exception as exc:
            self._startup_error = str(exc)
        finally:
            self._startup_done.set()

        if not self._startup_error:
            self.show_window()

    def _show_window_worker(self) -> None:
        if not self._startup_done.wait(timeout=180):
            self._show_error("초기화가 오래 걸리고 있어요. 잠시 뒤 트레이 아이콘을 다시 눌러 주세요.")
            return
        if self._startup_error:
            self._show_error(self._startup_error)
            return

        with self._open_lock:
            try:
                self._open_web_window()
            except Exception as exc:
                self._show_error(str(exc))

    def _ensure_frontend_built(self) -> None:
        if not self._frontend_needs_build():
            return

        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm:
            raise RuntimeError("React 화면을 빌드하려면 Node.js/npm이 필요합니다.")

        if not (PROJECT_ROOT / "node_modules").is_dir():
            self._run_command([npm, "install"], timeout=180)
        self._run_command([npm, "run", "build"], timeout=180)

    def _frontend_needs_build(self) -> bool:
        if not FRONTEND_INDEX_PATH.is_file():
            return True
        built_at = FRONTEND_INDEX_PATH.stat().st_mtime
        return any(path.is_file() and path.stat().st_mtime > built_at for path in FRONTEND_SOURCE_PATHS)

    def _ensure_backend_with_frontend(self) -> None:
        self.backend.ensure_running()
        if self.api.has_frontend():
            return

        if self.backend.process and self.backend.process.poll() is None:
            self.backend.stop()

        current_port = self.backend._preferred_port()
        port = self.backend._find_free_port(current_port + 1)
        self.api.set_base_url(f"http://{DEFAULT_API_HOST}:{port}")
        self.backend._start(port)
        for _ in range(30):
            if self.api.has_tray_api() and self.api.has_frontend():
                return
            time.sleep(0.5)
        raise RuntimeError("React 화면을 포함한 로컬 백엔드 서버를 시작하지 못했습니다.")

    def _open_web_window(self) -> None:
        if self.web_process and self.web_process.poll() is None:
            return

        browser = self._find_browser_executable()
        url = f"{self.api.base_url}/"
        if not browser:
            webbrowser.open(url, new=1)
            return

        x, y = self._window_position()
        profile_dir = SettingsStore().path.parent / "browser-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.web_process = subprocess.Popen(
            [
                str(browser),
                f"--app={url}",
                f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
                f"--window-position={x},{y}",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--disable-extensions",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            text=True,
        )

    def _close_web_window(self) -> None:
        if not self.web_process or self.web_process.poll() is not None:
            self.web_process = None
            return
        self.web_process.terminate()
        try:
            self.web_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.web_process.kill()
        finally:
            self.web_process = None

    @staticmethod
    def _find_browser_executable() -> Path | None:
        candidates: list[Path] = []
        configured = os.environ.get("REFINER_BROWSER_PATH")
        if configured:
            candidates.append(Path(configured))

        for root in (
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ):
            if root:
                base = Path(root)
                candidates.extend(
                    [
                        base / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                        base / "Google" / "Chrome" / "Application" / "chrome.exe",
                    ]
                )

        for name in ("msedge", "chrome"):
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))

        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _window_position() -> tuple[int, int]:
        work_area = TrayApp._get_windows_work_area()
        if work_area:
            left, top, right, bottom = work_area
            return max(left + 16, right - WINDOW_WIDTH - 16), max(top + 16, bottom - WINDOW_HEIGHT - 16)

        return 20, 20

    @staticmethod
    def _run_command(command: list[str], timeout: int) -> None:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=flags,
        )
        if completed.returncode != 0:
            output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
            raise RuntimeError(output[-1500:] or f"명령 실행 실패: {' '.join(command)}")

    @staticmethod
    def _show_error(message: str) -> None:
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.user32.MessageBoxW(None, message, DISPLAY_NAME, 0x10)
                return
            except Exception:
                pass
        print(message, file=sys.stderr)

    def _run_tray_icon(self) -> None:
        image = TrayApp._create_icon_image()
        menu = Menu(
            MenuItem("작업창 열기", lambda _icon, _item: self.show_window(), default=True),
            MenuItem("작업창 닫기", lambda _icon, _item: self.hide_window()),
            MenuItem("종료", lambda _icon, _item: self.quit()),
        )
        self.icon = Icon(APP_NAME, image, DISPLAY_NAME, menu)
        self.icon.run()


def main() -> None:
    if os.environ.get("REFINER_USE_TK_UI") == "1":
        app = FeedTrayApp()
    else:
        app = WebTrayApp()
    app.run()


if __name__ == "__main__":
    main()
