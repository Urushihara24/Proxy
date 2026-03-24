from __future__ import annotations

import json
import ipaddress
import logging
import os
import platform
import queue
import subprocess
import threading
import time
import tkinter as tk
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, Iterable, Optional, Sequence, Set, Tuple
from urllib.parse import quote

from proxy_seller_client import ProxySellerAPIError, ProxySellerClient
from system_proxy import (
    SystemProxyConfig,
    SystemProxyError,
    apply_system_proxy,
    disable_system_proxy,
)


APP_DATA_DIR = Path.home() / ".proxy-desktop-launcher"
SETTINGS_FILE = APP_DATA_DIR / "settings.json"
OUTPUT_DIR = APP_DATA_DIR / "generated_proxy_configs"
LAST_PROXY_FILE = APP_DATA_DIR / "last_proxy.json"
APP_LOG_FILE = APP_DATA_DIR / "app_debug.log"
PROXY_TYPES = ("ipv4", "ipv6", "mobile", "isp", "mix", "mix_isp", "resident", "scraper")
ACTIVE_PROXY_TYPES = PROXY_TYPES
PROTOCOL_OPTIONS = ("HTTP", "SOCKS5")
PAYMENT_METHODS = (
    ("Баланс (ID 1)", 1),
    ("Привязанная карта (ID 43)", 43),
)
PAYMENT_LABEL_TO_ID = {label: value for label, value in PAYMENT_METHODS}
PAYMENT_ID_TO_LABEL = {value: label for label, value in PAYMENT_METHODS}
GENERATE_AUTH_OPTIONS = ("N", "Y")
DEFAULT_CUSTOM_TARGET_NAME = "Proxy for Telegram"
MIX_TYPES = {"mix", "mix_isp"}
TARIFF_PROXY_TYPES = {"resident", "scraper"}
MOBILE_PROXY_TYPE = "mobile"
IPV6_PROXY_TYPE = "ipv6"
IPV6_MIN_QUANTITY = 10
WHEEL_SCROLL_STEP = 3
PASTE_V_KEYCODES = {9, 55, 86}
PASTE_V_KEYSYMS = {"v", "cyrillic_em"}
PASTE_V_CHARS = {"v", "V", "м", "М", "\x16"}
REFERENCE_TIMEOUT_SEC = 12
ASYNC_POLL_MS = 80
SCROLL_EVENT_SEQUENCES = (
    "<MouseWheel>",
    "<Shift-MouseWheel>",
    "<Option-MouseWheel>",
    "<Command-MouseWheel>",
    "<Button-4>",
    "<Button-5>",
)
WHEEL_CAPTURE_TAG = "WheelCapture"
ORDER_ID_KEYS = (
    "order_id",
    "orderId",
    "order_number",
    "orderNumber",
    "baseOrderNumber",
    "base_order_number",
    "listBaseOrderNumbers",
)

SYSTEM_NAME = platform.system().lower()
if SYSTEM_NAME == "darwin":
    FONT_UI = "SF Pro Text"
    FONT_TITLE = "SF Pro Display"
elif SYSTEM_NAME == "windows":
    FONT_UI = "Segoe UI"
    FONT_TITLE = "Segoe UI Semibold"
else:
    FONT_UI = "TkDefaultFont"
    FONT_TITLE = "TkHeadingFont"

APP_BG = "#0f1218"
CARD_BG = "#171c25"
HERO_BG = "#1a202b"
ACCENT = "#4d7ecf"
ACCENT_DARK = "#3f6db8"
SECONDARY = "#303c50"
SECONDARY_DARK = "#2a3445"
DANGER = "#77545d"
DANGER_DARK = "#65464e"
TEXT_PRIMARY = "#e7edf6"
TEXT_MUTED = "#9eacbf"
BORDER = "#2c3647"
INPUT_BG = "#202836"
LOG_BG = "#101722"
LOG_FG = "#d3deee"


@dataclass
class PurchasedProxy:
    host: str
    port: int
    protocol: str
    username: str
    password: str
    country: str
    country_alpha3: str
    order_id: str


class ProxyDesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Лаунчер прокси")
        self.root.geometry("760x860")
        self.root.minsize(640, 720)

        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._logger = self._create_logger()

        self.api_key_var = tk.StringVar(value=os.getenv("PROXY_SELLER_API_KEY", ""))
        self.proxy_type_var = tk.StringVar(value="ipv4")
        self.protocol_var = tk.StringVar(value="HTTP")
        self.quantity_var = tk.IntVar(value=1)
        self.country_var = tk.StringVar()
        self.period_var = tk.StringVar()
        self.payment_method_var = tk.StringVar(value=PAYMENT_METHODS[0][0])
        self.authorization_var = tk.StringVar(value="")
        self.generate_auth_var = tk.StringVar(value="N")
        self.order_filter_var = tk.StringVar(value="")
        self.tariff_var = tk.StringVar()
        self.custom_target_var = tk.StringVar(value=DEFAULT_CUSTOM_TARGET_NAME)
        self.mobile_service_type_var = tk.StringVar(value="dedicated")
        self.mobile_operator_var = tk.StringVar()
        self.mobile_rotation_var = tk.StringVar()
        self.order_rules_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Готово")
        self.active_proxy_var = tk.StringVar(value="Активный прокси: не подключен")

        self.countries_by_label: Dict[str, Dict[str, Any]] = {}
        self.periods_by_label: Dict[str, Dict[str, Any]] = {}
        self.mobile_operators_by_country_id: Dict[str, Dict[str, list[Dict[str, Any]]]] = {}
        self.mix_quantities_by_country_id: Dict[str, list[int]] = {}
        self.tariffs_by_label: Dict[str, Dict[str, Any]] = {}
        self.mobile_operators_by_label: Dict[str, Dict[str, Any]] = {}
        self.mobile_rotations_by_label: Dict[str, Dict[str, Any]] = {}
        self.active_proxy: Optional[PurchasedProxy] = None
        self.active_proxy_url = ""
        self.saved_country_id: Optional[Any] = None
        self.saved_period_id: Optional[Any] = None
        self.saved_tariff_id: Optional[Any] = None
        self.saved_mobile_operator_id: Optional[str] = None
        self.saved_mobile_rotation_id: Optional[str] = None
        self.busy = False
        self.advanced_controls_visible = False
        self._last_window_width = 0
        self._last_wheel_log_ts = 0.0
        self._wheel_fractional_accumulator = 0.0
        self._mac_wheel_sign = -1.0
        self._wheel_capture_bound = False
        self._last_wheel_event_signature: Optional[tuple[Any, ...]] = None
        self._last_wheel_event_ts = 0.0
        self._async_events: "queue.Queue[tuple[str, Any, Any]]" = queue.Queue()
        self.hero_subtitle_label: Optional[ttk.Label] = None
        self.api_hint_label: Optional[ttk.Label] = None
        self.main_canvas: Optional[tk.Canvas] = None
        self.main_canvas_window: Optional[int] = None
        self.log_entries: list[str] = []
        self.log_page_index = 0
        self.logs_per_page_var = tk.StringVar(value="40")
        self.log_page_label_var = tk.StringVar(value="Страница 1 из 1")
        self.logs_per_page_combo: Optional[ttk.Combobox] = None
        self.log_newer_button: Optional[ttk.Button] = None
        self.log_older_button: Optional[ttk.Button] = None
        self.log_page_label: Optional[ttk.Label] = None
        self.paste_api_button: Optional[ttk.Button] = None
        self.clear_api_button: Optional[ttk.Button] = None
        self.show_active_button: Optional[ttk.Button] = None
        self.balance_button: Optional[ttk.Button] = None
        self.more_button: Optional[ttk.Menubutton] = None
        self.more_menu: Optional[tk.Menu] = None
        self.payment_combo: Optional[ttk.Combobox] = None
        self.authorization_entry: Optional[ttk.Entry] = None
        self.generate_auth_combo: Optional[ttk.Combobox] = None
        self.order_filter_entry: Optional[ttk.Entry] = None
        self.advanced_toggle_button: Optional[ttk.Button] = None
        self.advanced_controls_frame: Optional[ttk.Frame] = None
        self.tariff_controls_frame: Optional[ttk.Frame] = None
        self.tariff_combo: Optional[ttk.Combobox] = None
        self.tariff_hint_label: Optional[ttk.Label] = None
        self.custom_target_entry: Optional[ttk.Entry] = None
        self.mobile_controls_frame: Optional[ttk.Frame] = None
        self.mobile_service_combo: Optional[ttk.Combobox] = None
        self.mobile_operator_combo: Optional[ttk.Combobox] = None
        self.mobile_rotation_combo: Optional[ttk.Combobox] = None
        self.order_rules_label: Optional[ttk.Label] = None
        self.progress_bar: Optional[ttk.Progressbar] = None

        self._setup_styles()
        self._build_ui()
        self._load_settings()
        self._refresh_dynamic_controls()
        self._schedule_async_poll()
        self._debug_log("UI initialized")

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.root.configure(bg=APP_BG)
        self.root.option_add("*Font", (FONT_UI, 11))
        self.root.option_add("*TCombobox*Listbox*Background", INPUT_BG)
        self.root.option_add("*TCombobox*Listbox*Foreground", TEXT_PRIMARY)
        self.root.option_add("*TCombobox*Listbox*selectBackground", ACCENT_DARK)
        self.root.option_add("*TCombobox*Listbox*selectForeground", "#ffffff")

        style.configure(".", background=APP_BG, foreground=TEXT_PRIMARY, font=(FONT_UI, 11))
        style.configure("App.TFrame", background=APP_BG)
        style.configure(
            "Hero.TFrame",
            background=HERO_BG,
            borderwidth=1,
            relief="solid",
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
        )
        style.configure(
            "HeroTitle.TLabel",
            background=HERO_BG,
            foreground="#ffffff",
            font=(FONT_TITLE, 16, "bold"),
        )
        style.configure(
            "HeroSub.TLabel",
            background=HERO_BG,
            foreground=TEXT_MUTED,
            font=(FONT_UI, 10),
        )

        style.configure(
            "Card.TLabelframe",
            background=CARD_BG,
            borderwidth=1,
            relief="solid",
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=CARD_BG,
            foreground="#d6deea",
            font=(FONT_UI, 12, "bold"),
        )
        style.configure("Card.TFrame", background=CARD_BG)
        style.configure("Card.TLabel", background=CARD_BG, foreground=TEXT_PRIMARY)
        style.configure("Hint.TLabel", background=CARD_BG, foreground=TEXT_MUTED)
        style.configure("Muted.TLabel", background=CARD_BG, foreground=TEXT_MUTED)
        style.configure("Pager.TLabel", background=CARD_BG, foreground=TEXT_MUTED, font=(FONT_UI, 10))
        style.configure(
            "StatusValue.TLabel",
            background=CARD_BG,
            foreground="#9ec7ff",
            font=(FONT_UI, 11, "bold"),
        )
        style.configure(
            "StatusReady.TLabel",
            background=CARD_BG,
            foreground="#79c28d",
            font=(FONT_UI, 11, "bold"),
        )
        style.configure(
            "StatusBusy.TLabel",
            background=CARD_BG,
            foreground="#9ec7ff",
            font=(FONT_UI, 11, "bold"),
        )
        style.configure(
            "StatusError.TLabel",
            background=CARD_BG,
            foreground="#d6939d",
            font=(FONT_UI, 11, "bold"),
        )

        style.configure(
            "Card.TEntry",
            fieldbackground=INPUT_BG,
            background=INPUT_BG,
            foreground=TEXT_PRIMARY,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            relief="flat",
            padding=6,
        )
        style.map(
            "Card.TEntry",
            bordercolor=[("focus", ACCENT), ("!focus", BORDER)],
            lightcolor=[("focus", ACCENT), ("!focus", BORDER)],
            darkcolor=[("focus", ACCENT), ("!focus", BORDER)],
        )
        style.configure(
            "Card.TCombobox",
            fieldbackground=INPUT_BG,
            background=INPUT_BG,
            foreground=TEXT_PRIMARY,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            arrowcolor=TEXT_MUTED,
            arrowsize=14,
            padding=6,
        )
        style.map(
            "Card.TCombobox",
            fieldbackground=[("readonly", INPUT_BG)],
            selectbackground=[("readonly", INPUT_BG)],
            selectforeground=[("readonly", TEXT_PRIMARY)],
            bordercolor=[("focus", ACCENT), ("!focus", BORDER)],
            lightcolor=[("focus", ACCENT), ("!focus", BORDER)],
            darkcolor=[("focus", ACCENT), ("!focus", BORDER)],
            arrowcolor=[("disabled", "#667085"), ("!disabled", TEXT_MUTED)],
        )
        style.configure(
            "Card.TSpinbox",
            arrowsize=14,
            fieldbackground=INPUT_BG,
            background=INPUT_BG,
            foreground=TEXT_PRIMARY,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            relief="flat",
            padding=5,
        )
        style.map(
            "Card.TSpinbox",
            bordercolor=[("focus", ACCENT), ("!focus", BORDER)],
            lightcolor=[("focus", ACCENT), ("!focus", BORDER)],
            darkcolor=[("focus", ACCENT), ("!focus", BORDER)],
        )

        style.configure(
            "Primary.TButton",
            background=ACCENT,
            foreground="#ffffff",
            borderwidth=0,
            padding=(11, 9),
            font=(FONT_UI, 11, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("active", ACCENT_DARK), ("pressed", ACCENT_DARK)],
            foreground=[("disabled", "#9cacbf"), ("!disabled", "#ffffff")],
        )

        style.configure(
            "Secondary.TButton",
            background=SECONDARY,
            foreground="#ffffff",
            borderwidth=0,
            padding=(11, 9),
            font=(FONT_UI, 11, "bold"),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", SECONDARY_DARK), ("pressed", SECONDARY_DARK)],
            foreground=[("disabled", "#9ba7b8"), ("!disabled", "#ffffff")],
        )

        style.configure(
            "Danger.TButton",
            background=DANGER,
            foreground="#ffffff",
            borderwidth=0,
            padding=(11, 9),
            font=(FONT_UI, 11, "bold"),
        )
        style.map(
            "Danger.TButton",
            background=[("active", DANGER_DARK), ("pressed", DANGER_DARK)],
            foreground=[("disabled", "#b9a3a3"), ("!disabled", "#ffffff")],
        )

        style.configure(
            "Ghost.TButton",
            background="#263143",
            foreground=TEXT_PRIMARY,
            borderwidth=0,
            padding=(11, 9),
            font=(FONT_UI, 11, "bold"),
        )
        style.map(
            "Ghost.TButton",
            background=[("active", "#2f3b4f"), ("pressed", "#344156")],
            foreground=[("disabled", "#6f7e92"), ("!disabled", TEXT_PRIMARY)],
        )

        style.configure(
            "Ghost.TMenubutton",
            background="#263143",
            foreground=TEXT_PRIMARY,
            borderwidth=0,
            padding=(11, 9),
            font=(FONT_UI, 11, "bold"),
            arrowcolor=TEXT_MUTED,
            relief="flat",
        )
        style.map(
            "Ghost.TMenubutton",
            background=[("active", "#2f3b4f"), ("pressed", "#344156")],
            foreground=[("disabled", "#6f7e92"), ("!disabled", TEXT_PRIMARY)],
            arrowcolor=[("disabled", "#6f7e92"), ("!disabled", TEXT_MUTED)],
        )

        style.configure(
            "Vertical.TScrollbar",
            background=CARD_BG,
            troughcolor=APP_BG,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            arrowcolor=TEXT_MUTED,
        )

    @staticmethod
    def _create_logger() -> logging.Logger:
        logger = logging.getLogger("proxy_desktop_launcher")
        logger.setLevel(logging.INFO)
        logger.propagate = False

        log_path = str(APP_LOG_FILE)
        has_file_handler = any(
            isinstance(handler, logging.FileHandler)
            and getattr(handler, "baseFilename", "") == log_path
            for handler in logger.handlers
        )
        if not has_file_handler:
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            )
            logger.addHandler(file_handler)

        return logger

    def _debug_log(self, message: str) -> None:
        try:
            self._logger.info(message)
        except Exception:
            pass

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, style="App.TFrame")
        shell.pack(fill="both", expand=True)

        self.main_canvas = tk.Canvas(
            shell,
            bg=APP_BG,
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
        )
        vertical_scrollbar = ttk.Scrollbar(
            shell,
            orient="vertical",
            command=self.main_canvas.yview,
            style="Vertical.TScrollbar",
        )
        self.main_canvas.configure(yscrollcommand=vertical_scrollbar.set)

        self.main_canvas.pack(side="left", fill="both", expand=True)
        vertical_scrollbar.pack(side="right", fill="y")

        root_frame = ttk.Frame(self.main_canvas, padding=(16, 16, 16, 14), style="App.TFrame")
        self.main_canvas_window = self.main_canvas.create_window((0, 0), window=root_frame, anchor="nw")
        root_frame.bind("<Configure>", self._on_content_frame_configure)
        self.main_canvas.bind("<Configure>", self._on_canvas_configure)
        for sequence in SCROLL_EVENT_SEQUENCES:
            self.root.bind_all(sequence, self._on_global_mousewheel, add="+")
        paste_shortcuts = (
            "<<Paste>>",
            "<Control-v>",
            "<Control-V>",
            "<Control-KeyPress-v>",
            "<Control-KeyPress-V>",
            "<Command-v>",
            "<Command-V>",
            "<Command-KeyPress-v>",
            "<Command-KeyPress-V>",
            "<Control-Insert>",
        )
        for sequence in paste_shortcuts:
            self.root.bind_all(sequence, self._on_global_paste_shortcut, add="+")
        self.root.bind_all("<KeyPress>", self._on_global_keypress_shortcut, add="+")

        root_frame.columnconfigure(0, weight=1)
        root_frame.rowconfigure(5, weight=1)

        hero = ttk.Frame(root_frame, padding=(16, 12), style="Hero.TFrame")
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        hero.columnconfigure(0, weight=1)
        ttk.Label(
            hero,
            text="Proxy Control",
            style="HeroTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        self.hero_subtitle_label = ttk.Label(
            hero,
            text=(
                "Минималистичный лаунчер прокси: выберите параметры, "
                "подключитесь в один клик."
            ),
            style="HeroSub.TLabel",
            justify="left",
        )
        self.hero_subtitle_label.grid(row=1, column=0, sticky="w", pady=(4, 0))

        credentials = ttk.LabelFrame(
            root_frame,
            text="API",
            padding=(14, 12),
            style="Card.TLabelframe",
        )
        credentials.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        credentials.columnconfigure(0, weight=1)
        credentials.columnconfigure(1, weight=0)

        ttk.Label(credentials, text="API-ключ Proxy-Seller", style="Card.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.api_key_entry = ttk.Entry(
            credentials,
            textvariable=self.api_key_var,
            show="*",
            style="Card.TEntry",
        )
        self.api_key_entry.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        for sequence in paste_shortcuts:
            self.api_key_entry.bind(sequence, self._on_api_key_paste_shortcut)
        self.api_key_entry.bind("<KeyPress>", self._on_api_key_keypress_shortcut, add="+")

        self.paste_api_button = ttk.Button(
            credentials,
            text="Вставить",
            command=self._paste_api_key_from_clipboard,
            style="Secondary.TButton",
        )
        self.paste_api_button.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))

        self.api_hint_label = ttk.Label(
            credentials,
            text="Ключ хранится локально. Вставьте его и обновите данные.",
            style="Hint.TLabel",
            justify="left",
        )
        self.api_hint_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self.save_button = ttk.Button(
            credentials,
            text="Сохранить",
            command=self._on_save_settings,
            style="Ghost.TButton",
        )
        self.save_button.grid(row=3, column=0, sticky="w", pady=(10, 0))

        self.clear_api_button = ttk.Button(
            credentials,
            text="Очистить ключ",
            command=self._on_clear_api_key,
            style="Danger.TButton",
        )
        self.clear_api_button.grid(row=3, column=1, sticky="e", pady=(10, 0))

        settings = ttk.LabelFrame(
            root_frame,
            text="Параметры",
            padding=(14, 12),
            style="Card.TLabelframe",
        )
        settings.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        settings.columnconfigure(0, weight=1)

        ttk.Label(settings, text="Тип прокси", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        self.proxy_type_combo = ttk.Combobox(
            settings,
            textvariable=self.proxy_type_var,
            values=PROXY_TYPES,
            state="readonly",
            style="Card.TCombobox",
        )
        self.proxy_type_combo.grid(row=1, column=0, sticky="ew", pady=(5, 12))
        self.proxy_type_combo.bind("<<ComboboxSelected>>", self._on_proxy_type_changed)

        ttk.Label(settings, text="Протокол", style="Card.TLabel").grid(row=2, column=0, sticky="w")
        self.protocol_combo = ttk.Combobox(
            settings,
            textvariable=self.protocol_var,
            values=PROTOCOL_OPTIONS,
            state="readonly",
            style="Card.TCombobox",
        )
        self.protocol_combo.grid(row=3, column=0, sticky="ew", pady=(5, 12))

        ttk.Label(settings, text="Страна", style="Card.TLabel").grid(row=4, column=0, sticky="w")
        self.country_combo = ttk.Combobox(
            settings,
            textvariable=self.country_var,
            values=[],
            state="readonly",
            style="Card.TCombobox",
        )
        self.country_combo.grid(row=5, column=0, sticky="ew", pady=(5, 12))
        self.country_combo.bind("<<ComboboxSelected>>", self._on_country_changed)

        ttk.Label(settings, text="Период", style="Card.TLabel").grid(row=6, column=0, sticky="w")
        self.period_combo = ttk.Combobox(
            settings,
            textvariable=self.period_var,
            values=[],
            state="readonly",
            style="Card.TCombobox",
        )
        self.period_combo.grid(row=7, column=0, sticky="ew", pady=(5, 12))

        self.tariff_controls_frame = ttk.Frame(settings, style="Card.TFrame")
        self.tariff_controls_frame.grid(row=8, column=0, sticky="ew", pady=(0, 10))
        self.tariff_controls_frame.columnconfigure(0, weight=1)
        ttk.Label(self.tariff_controls_frame, text="Тариф (resident/scraper)", style="Card.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.tariff_combo = ttk.Combobox(
            self.tariff_controls_frame,
            textvariable=self.tariff_var,
            values=[],
            state="readonly",
            style="Card.TCombobox",
        )
        self.tariff_combo.grid(row=1, column=0, sticky="ew", pady=(5, 6))
        self.tariff_combo.bind("<<ComboboxSelected>>", self._on_tariff_changed)
        self.tariff_hint_label = ttk.Label(
            self.tariff_controls_frame,
            text="Для resident/scraper сначала обновите список, затем выберите тариф.",
            style="Hint.TLabel",
            justify="left",
        )
        self.tariff_hint_label.grid(row=2, column=0, sticky="w")

        ttk.Label(settings, text="Количество", style="Card.TLabel").grid(row=9, column=0, sticky="w")
        self.quantity_spin = ttk.Spinbox(
            settings,
            from_=1,
            to=2000,
            textvariable=self.quantity_var,
            style="Card.TSpinbox",
        )
        self.quantity_spin.grid(row=10, column=0, sticky="ew", pady=(5, 10))

        self.advanced_toggle_button = ttk.Button(
            settings,
            text="Показать расширенные параметры",
            command=self._toggle_advanced_controls,
            style="Ghost.TButton",
        )
        self.advanced_toggle_button.grid(row=11, column=0, sticky="ew", pady=(0, 10))

        self.advanced_controls_frame = ttk.Frame(settings, style="Card.TFrame")
        self.advanced_controls_frame.grid(row=12, column=0, sticky="ew", pady=(0, 10))
        self.advanced_controls_frame.columnconfigure(0, weight=1)

        ttk.Label(self.advanced_controls_frame, text="Способ оплаты (paymentId)", style="Card.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.payment_combo = ttk.Combobox(
            self.advanced_controls_frame,
            textvariable=self.payment_method_var,
            values=[label for label, _ in PAYMENT_METHODS],
            state="readonly",
            style="Card.TCombobox",
        )
        self.payment_combo.grid(row=1, column=0, sticky="ew", pady=(5, 12))

        ttk.Label(
            self.advanced_controls_frame,
            text="IP авторизации (опционально)",
            style="Card.TLabel",
        ).grid(row=2, column=0, sticky="w")
        self.authorization_entry = ttk.Entry(
            self.advanced_controls_frame,
            textvariable=self.authorization_var,
            style="Card.TEntry",
        )
        self.authorization_entry.grid(row=3, column=0, sticky="ew", pady=(5, 12))

        ttk.Label(self.advanced_controls_frame, text="Generate auth (Y/N)", style="Card.TLabel").grid(
            row=4,
            column=0,
            sticky="w",
        )
        self.generate_auth_combo = ttk.Combobox(
            self.advanced_controls_frame,
            textvariable=self.generate_auth_var,
            values=GENERATE_AUTH_OPTIONS,
            state="readonly",
            style="Card.TCombobox",
        )
        self.generate_auth_combo.grid(row=5, column=0, sticky="ew", pady=(5, 12))

        ttk.Label(
            self.advanced_controls_frame,
            text="Фильтр активных (orderId / baseOrderNumber, опционально)",
            style="Card.TLabel",
        ).grid(row=6, column=0, sticky="w")
        self.order_filter_entry = ttk.Entry(
            self.advanced_controls_frame,
            textvariable=self.order_filter_var,
            style="Card.TEntry",
        )
        self.order_filter_entry.grid(row=7, column=0, sticky="ew", pady=(5, 12))

        ttk.Label(
            self.advanced_controls_frame,
            text="Назначение / сайт (customTargetName)",
            style="Card.TLabel",
        ).grid(row=8, column=0, sticky="w")
        self.custom_target_entry = ttk.Entry(
            self.advanced_controls_frame,
            textvariable=self.custom_target_var,
            style="Card.TEntry",
        )
        self.custom_target_entry.grid(row=9, column=0, sticky="ew", pady=(5, 0))

        self.order_rules_label = ttk.Label(
            settings,
            textvariable=self.order_rules_var,
            style="Hint.TLabel",
            justify="left",
        )
        self.order_rules_label.grid(row=13, column=0, sticky="w", pady=(0, 8))

        self.mobile_controls_frame = ttk.Frame(settings, style="Card.TFrame")
        self.mobile_controls_frame.grid(row=14, column=0, sticky="ew", pady=(0, 0))
        self.mobile_controls_frame.columnconfigure(0, weight=1)

        ttk.Label(self.mobile_controls_frame, text="Тип mobile-сервиса", style="Card.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.mobile_service_combo = ttk.Combobox(
            self.mobile_controls_frame,
            textvariable=self.mobile_service_type_var,
            values=("dedicated", "shared"),
            state="readonly",
            style="Card.TCombobox",
        )
        self.mobile_service_combo.grid(row=1, column=0, sticky="ew", pady=(5, 10))
        self.mobile_service_combo.bind("<<ComboboxSelected>>", self._on_mobile_service_changed)

        ttk.Label(self.mobile_controls_frame, text="Оператор", style="Card.TLabel").grid(
            row=2,
            column=0,
            sticky="w",
        )
        self.mobile_operator_combo = ttk.Combobox(
            self.mobile_controls_frame,
            textvariable=self.mobile_operator_var,
            values=[],
            state="readonly",
            style="Card.TCombobox",
        )
        self.mobile_operator_combo.grid(row=3, column=0, sticky="ew", pady=(5, 10))
        self.mobile_operator_combo.bind("<<ComboboxSelected>>", self._on_mobile_operator_changed)

        ttk.Label(self.mobile_controls_frame, text="Ротация", style="Card.TLabel").grid(
            row=4,
            column=0,
            sticky="w",
        )
        self.mobile_rotation_combo = ttk.Combobox(
            self.mobile_controls_frame,
            textvariable=self.mobile_rotation_var,
            values=[],
            state="readonly",
            style="Card.TCombobox",
        )
        self.mobile_rotation_combo.grid(row=5, column=0, sticky="ew", pady=(5, 0))

        actions = ttk.LabelFrame(
            root_frame,
            text="Действия",
            padding=(14, 12),
            style="Card.TLabelframe",
        )
        actions.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        self.actions_frame = actions

        self.load_button = ttk.Button(
            actions,
            text="Обновить данные",
            command=self.load_reference_data,
            style="Secondary.TButton",
        )

        self.connect_button = ttk.Button(
            actions,
            text="Купить и подключить",
            command=self.connect_proxy,
            style="Primary.TButton",
        )

        self.connect_existing_button = ttk.Button(
            actions,
            text="Подключить купленный",
            command=self.connect_active_proxy,
            style="Secondary.TButton",
        )

        self.reconnect_last_button = ttk.Button(
            actions,
            text="Подключить последний",
            command=self.reconnect_last_proxy,
            style="Ghost.TButton",
        )

        self.disconnect_button = ttk.Button(
            actions,
            text="Отключить прокси",
            command=self.disconnect_proxy,
            style="Danger.TButton",
        )

        self.open_configs_button = ttk.Button(
            actions,
            text="Открыть конфиги",
            command=self.open_configs_folder,
            style="Ghost.TButton",
        )

        self.show_active_button = ttk.Button(
            actions,
            text="Показать активные",
            command=self.show_active_proxies,
            style="Secondary.TButton",
        )

        self.balance_button = ttk.Button(
            actions,
            text="Проверить баланс",
            command=self.show_balance,
            style="Ghost.TButton",
        )

        self.more_menu = tk.Menu(
            actions,
            tearoff=False,
            bg=INPUT_BG,
            fg=TEXT_PRIMARY,
            activebackground=ACCENT_DARK,
            activeforeground="#ffffff",
            borderwidth=0,
        )
        self.more_menu.add_command(label="Подключить последний", command=self.reconnect_last_proxy)
        self.more_menu.add_command(label="Показать активные", command=self.show_active_proxies)
        self.more_menu.add_command(label="Проверить баланс", command=self.show_balance)
        self.more_menu.add_separator()
        self.more_menu.add_command(label="Открыть конфиги", command=self.open_configs_folder)

        self.more_button = ttk.Menubutton(
            actions,
            text="Ещё",
            style="Ghost.TMenubutton",
            direction="below",
        )
        self.more_button.configure(menu=self.more_menu)
        self.help_label = ttk.Label(
            actions,
            text="Покупка создаёт платный заказ в Proxy-Seller.",
            justify="left",
            style="Hint.TLabel",
        )

        status_bar = ttk.LabelFrame(
            root_frame,
            text="Состояние",
            padding=(14, 10),
            style="Card.TLabelframe",
        )
        status_bar.grid(row=4, column=0, sticky="ew", pady=(0, 12))
        status_bar.columnconfigure(0, weight=1)
        ttk.Label(status_bar, text="Статус:", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        self.status_label = ttk.Label(status_bar, textvariable=self.status_var, style="StatusReady.TLabel")
        self.status_label.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self.active_proxy_label = ttk.Label(
            status_bar,
            textvariable=self.active_proxy_var,
            style="Muted.TLabel",
            justify="left",
        )
        self.active_proxy_label.grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.progress_bar = ttk.Progressbar(status_bar, mode="indeterminate", length=220)
        self.progress_bar.grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.progress_bar.grid_remove()

        logs_frame = ttk.LabelFrame(
            root_frame,
            text="Журнал",
            padding=(14, 10),
            style="Card.TLabelframe",
        )
        logs_frame.grid(row=5, column=0, sticky="nsew")
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(1, weight=1)

        logs_controls = ttk.Frame(logs_frame, style="Card.TFrame")
        logs_controls.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        logs_controls.columnconfigure(2, weight=1)

        ttk.Label(logs_controls, text="Записей на страницу:", style="Hint.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.logs_per_page_combo = ttk.Combobox(
            logs_controls,
            textvariable=self.logs_per_page_var,
            values=("20", "40", "80", "120"),
            state="readonly",
            width=6,
            style="Card.TCombobox",
        )
        self.logs_per_page_combo.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.logs_per_page_combo.bind("<<ComboboxSelected>>", self._on_logs_per_page_changed)

        self.log_newer_button = ttk.Button(
            logs_controls,
            text="Новее",
            command=self._show_newer_logs,
            style="Ghost.TButton",
        )
        self.log_newer_button.grid(row=0, column=3, sticky="e", padx=(8, 6))

        self.log_page_label = ttk.Label(logs_controls, textvariable=self.log_page_label_var, style="Pager.TLabel")
        self.log_page_label.grid(
            row=0,
            column=4,
            sticky="e",
            padx=(0, 6),
        )

        self.log_older_button = ttk.Button(
            logs_controls,
            text="Старее",
            command=self._show_older_logs,
            style="Ghost.TButton",
        )
        self.log_older_button.grid(row=0, column=5, sticky="e")

        self.log_text = tk.Text(
            logs_frame,
            wrap="word",
            height=10,
            state="disabled",
            bg=LOG_BG,
            fg=LOG_FG,
            insertbackground=LOG_FG,
            selectbackground=ACCENT,
            selectforeground="#ffffff",
            borderwidth=0,
            relief="flat",
            padx=10,
            pady=10,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        self.log_text.grid(row=1, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(
            logs_frame,
            orient="vertical",
            command=self.log_text.yview,
            style="Vertical.TScrollbar",
        )
        scroll.grid(row=1, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

        self._append_log("Введите API-ключ, обновите справочные данные и подключитесь.")
        self._append_log(
            "Основной сценарий: Обновить данные → Купить и подключить."
        )
        self._append_log(
            "Вторичные функции (баланс, активные, последний, конфиги) доступны в меню 'Ещё'."
        )
        self._append_log(f"Debug-лог: {APP_LOG_FILE}")

        self._layout_action_buttons(self.root.winfo_width())
        self._apply_text_wrap(self.root.winfo_width())
        self.root.bind("<Configure>", self._on_window_resize)
        self._bind_scroll_capture(self.root)

    def _on_save_settings(self) -> None:
        self._save_settings(silent=False)

    def _on_clear_api_key(self) -> None:
        has_value = bool(self.api_key_var.get().strip())
        if not has_value and not SETTINGS_FILE.exists():
            self._append_log("API-ключ уже пустой.")
            return

        confirm = messagebox.askyesno(
            "Очистка API-ключа",
            "Удалить API-ключ из поля и локальных настроек?",
        )
        if not confirm:
            return

        self.api_key_var.set("")
        self._save_settings(silent=True)
        self.api_key_entry.focus_set()
        self._append_log("API-ключ очищен и удалён из локальных настроек.")

    def _save_settings(self, silent: bool = True) -> None:
        country_item = self.countries_by_label.get(self.country_var.get(), {})
        period_item = self.periods_by_label.get(self.period_var.get(), {})
        tariff_item = self.tariffs_by_label.get(self.tariff_var.get(), {})
        mobile_operator_item = self.mobile_operators_by_label.get(self.mobile_operator_var.get(), {})
        mobile_rotation_item = self.mobile_rotations_by_label.get(self.mobile_rotation_var.get(), {})
        try:
            quantity = int(self.quantity_var.get())
        except Exception:
            quantity = 1
        quantity = max(1, quantity)

        payload = {
            "api_key": self.api_key_var.get().strip(),
            "proxy_type": self.proxy_type_var.get().strip() or "ipv4",
            "protocol": self.protocol_var.get().strip() or "HTTP",
            "quantity": quantity,
            "country_id": country_item.get("id"),
            "period_id": period_item.get("id"),
            "tariff_id": tariff_item.get("id"),
            "payment_method": self.payment_method_var.get().strip(),
            "payment_id": PAYMENT_LABEL_TO_ID.get(self.payment_method_var.get().strip(), 1),
            "authorization": self.authorization_var.get().strip(),
            "generate_auth": self.generate_auth_var.get().strip().upper() or "N",
            "order_filter": self.order_filter_var.get().strip(),
            "custom_target_name": self.custom_target_var.get().strip(),
            "mobile_service_type": self.mobile_service_type_var.get().strip() or "dedicated",
            "mobile_operator_id": mobile_operator_item.get("id"),
            "mobile_rotation_id": mobile_rotation_item.get("id"),
        }

        try:
            SETTINGS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            self._append_log(f"Не удалось сохранить настройки: {exc}")
            if not silent:
                messagebox.showerror(
                    "Сохранение настроек",
                    f"Не удалось записать файл настроек: {exc}",
                )
            return

        if not silent:
            self._append_log(f"Настройки сохранены в: {SETTINGS_FILE}")

    def _load_settings(self) -> None:
        if not SETTINGS_FILE.exists():
            self._load_last_proxy_state()
            return

        try:
            payload = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self._append_log(f"Не удалось прочитать файл настроек: {exc}")
            return

        self.api_key_var.set(str(payload.get("api_key", self.api_key_var.get())))
        self.proxy_type_var.set(str(payload.get("proxy_type", "ipv4")))
        self.protocol_var.set(str(payload.get("protocol", "HTTP")))
        saved_payment_label = str(payload.get("payment_method", "")).strip()
        saved_payment_id = payload.get("payment_id")
        if saved_payment_label in PAYMENT_LABEL_TO_ID:
            self.payment_method_var.set(saved_payment_label)
        else:
            try:
                payment_id = int(saved_payment_id)
            except (TypeError, ValueError):
                payment_id = 1
            self.payment_method_var.set(
                PAYMENT_ID_TO_LABEL.get(payment_id, PAYMENT_METHODS[0][0])
            )

        self.authorization_var.set(str(payload.get("authorization", "")).strip())
        generate_auth = str(payload.get("generate_auth", "N")).strip().upper()
        self.generate_auth_var.set("Y" if generate_auth == "Y" else "N")
        self.order_filter_var.set(str(payload.get("order_filter", "")).strip())
        self.custom_target_var.set(
            str(payload.get("custom_target_name", DEFAULT_CUSTOM_TARGET_NAME))
            or DEFAULT_CUSTOM_TARGET_NAME
        )
        self.mobile_service_type_var.set(str(payload.get("mobile_service_type", "dedicated")) or "dedicated")

        custom_target_value = self.custom_target_var.get().strip()
        self.advanced_controls_visible = bool(
            self.payment_method_var.get().strip() != PAYMENT_METHODS[0][0]
            or self.authorization_var.get().strip()
            or self.generate_auth_var.get().strip().upper() == "Y"
            or self.order_filter_var.get().strip()
            or (
                custom_target_value
                and custom_target_value != DEFAULT_CUSTOM_TARGET_NAME
            )
        )

        try:
            quantity = int(payload.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1
        self.quantity_var.set(max(1, quantity))

        self.saved_country_id = payload.get("country_id")
        self.saved_period_id = payload.get("period_id")
        self.saved_tariff_id = payload.get("tariff_id")
        saved_operator = payload.get("mobile_operator_id")
        saved_rotation = payload.get("mobile_rotation_id")
        self.saved_mobile_operator_id = str(saved_operator) if saved_operator not in (None, "") else None
        self.saved_mobile_rotation_id = str(saved_rotation) if saved_rotation not in (None, "") else None
        self._append_log(f"Настройки загружены из: {SETTINGS_FILE}")
        self._load_last_proxy_state()

    def _load_last_proxy_state(self) -> None:
        if not LAST_PROXY_FILE.exists():
            return

        try:
            payload = json.loads(LAST_PROXY_FILE.read_text(encoding="utf-8"))
            proxy_data = payload.get("proxy", {})
            if not isinstance(proxy_data, dict):
                return

            host = str(proxy_data.get("host") or "").strip()
            port = int(proxy_data.get("port"))
            protocol = str(proxy_data.get("protocol") or "http").strip()
            username = str(proxy_data.get("username") or "").strip()
            password = str(proxy_data.get("password") or "").strip()
            country = str(proxy_data.get("country") or "").strip()
            country_alpha3 = str(proxy_data.get("country_alpha3") or "").strip()
            order_id = str(proxy_data.get("order_id") or "saved")
        except Exception:
            return

        if not host or port <= 0:
            return

        self.active_proxy = PurchasedProxy(
            host=host,
            port=port,
            protocol=protocol,
            username=username,
            password=password,
            country=country,
            country_alpha3=country_alpha3,
            order_id=order_id,
        )
        self.active_proxy_url = str(payload.get("proxy_url") or self._build_proxy_url(self.active_proxy))
        self._set_active_proxy_label()

    def load_reference_data(self) -> None:
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("API ключ", "Введите API ключ Proxy-Seller.")
            return

        proxy_type = self.proxy_type_var.get().strip() or "ipv4"
        self._debug_log(f"Load reference requested: proxy_type={proxy_type}")

        def worker() -> Dict[str, Any]:
            self._debug_log(
                f"Load reference worker start: proxy_type={proxy_type}, timeout={REFERENCE_TIMEOUT_SEC}s"
            )
            client = ProxySellerClient(api_key=api_key, timeout=REFERENCE_TIMEOUT_SEC)
            reference_items = client.get_reference(proxy_type)
            countries, periods = self._extract_reference_options(reference_items)
            tariffs = self._extract_tariff_options(reference_items)
            is_tariff_type = proxy_type in TARIFF_PROXY_TYPES
            if is_tariff_type:
                if not tariffs:
                    raise ProxySellerAPIError("API не вернул список тарифов для выбранного типа.")
            else:
                if not countries:
                    raise ProxySellerAPIError("API не вернул список стран.")
                if not periods:
                    raise ProxySellerAPIError("API не вернул варианты периода.")
            mobile_operators_by_country_id, mix_quantities_by_country_id = self._extract_reference_extras(
                reference_items
            )
            self._debug_log(
                f"Load reference worker done: countries={len(countries)}, periods={len(periods)}, tariffs={len(tariffs)}"
            )
            return {
                "countries": countries,
                "periods": periods,
                "tariffs": tariffs,
                "mobile_operators_by_country_id": mobile_operators_by_country_id,
                "mix_quantities_by_country_id": mix_quantities_by_country_id,
            }

        def on_success(result: Dict[str, Any]) -> None:
            countries = list(result.get("countries") or [])
            periods = list(result.get("periods") or [])
            tariffs = list(result.get("tariffs") or [])
            self.mobile_operators_by_country_id = dict(
                result.get("mobile_operators_by_country_id") or {}
            )
            self.mix_quantities_by_country_id = dict(result.get("mix_quantities_by_country_id") or {})
            self.countries_by_label = self._build_label_mapping(countries, self._country_label)
            self.periods_by_label = self._build_label_mapping(periods, self._period_label)
            self.tariffs_by_label = self._build_label_mapping(tariffs, self._tariff_label)

            country_labels = list(self.countries_by_label.keys())
            period_labels = list(self.periods_by_label.keys())
            tariff_labels = list(self.tariffs_by_label.keys())
            self.country_combo.configure(values=country_labels)
            self.period_combo.configure(values=period_labels)
            if self.tariff_combo is not None:
                self.tariff_combo.configure(values=tariff_labels)

            if self.saved_country_id is not None:
                for label, item in self.countries_by_label.items():
                    if str(item.get("id")) == str(self.saved_country_id):
                        self.country_var.set(label)
                        break
                self.saved_country_id = None
            if not self.country_var.get() and country_labels:
                self.country_var.set(country_labels[0])

            if self.saved_period_id is not None:
                for label, item in self.periods_by_label.items():
                    if str(item.get("id")) == str(self.saved_period_id):
                        self.period_var.set(label)
                        break
                self.saved_period_id = None
            if not self.period_var.get() and period_labels:
                self.period_var.set(period_labels[0])

            if self.saved_tariff_id is not None:
                for label, item in self.tariffs_by_label.items():
                    if str(item.get("id")) == str(self.saved_tariff_id):
                        self.tariff_var.set(label)
                        break
                self.saved_tariff_id = None
            if not self.tariff_var.get() and tariff_labels:
                self.tariff_var.set(tariff_labels[0])

            self._refresh_dynamic_controls()
            proxy_type_label = self.proxy_type_var.get().strip() or "ipv4"
            if proxy_type_label in TARIFF_PROXY_TYPES:
                self._append_log(f"Загружено тарифов: {len(tariff_labels)}.")
            else:
                self._append_log(
                    f"Загружено стран: {len(country_labels)}, периодов: {len(period_labels)}."
                )
            self._save_settings(silent=True)

        description = (
            "Загрузка тарифов из Proxy-Seller API..."
            if proxy_type in TARIFF_PROXY_TYPES
            else "Загрузка стран и периодов из Proxy-Seller API..."
        )
        self._run_async(description, worker, on_success)

    def _on_proxy_type_changed(self, _event: Optional[tk.Event] = None) -> None:
        self.countries_by_label = {}
        self.periods_by_label = {}
        self.mobile_operators_by_country_id = {}
        self.mix_quantities_by_country_id = {}
        self.tariffs_by_label = {}
        self.country_combo.configure(values=[])
        self.period_combo.configure(values=[])
        if self.tariff_combo is not None:
            self.tariff_combo.configure(values=[])
        self.country_var.set("")
        self.period_var.set("")
        self.tariff_var.set("")
        self.saved_country_id = None
        self.saved_period_id = None
        self.saved_tariff_id = None
        self.saved_mobile_operator_id = None
        self.saved_mobile_rotation_id = None
        self._refresh_dynamic_controls()
        self._append_log("Тип прокси изменен. Обновите справочные данные перед покупкой.")
        self._save_settings(silent=True)

    def _on_country_changed(self, _event: Optional[tk.Event] = None) -> None:
        self.saved_mobile_operator_id = None
        self.saved_mobile_rotation_id = None
        self._refresh_dynamic_controls()
        self._save_settings(silent=True)

    def _on_tariff_changed(self, _event: Optional[tk.Event] = None) -> None:
        self._save_settings(silent=True)

    def _toggle_advanced_controls(self) -> None:
        self._set_advanced_controls_visible(not self.advanced_controls_visible)

    def _set_advanced_controls_visible(self, visible: bool) -> None:
        self.advanced_controls_visible = bool(visible)
        if self.advanced_controls_frame is not None:
            if self.advanced_controls_visible:
                self.advanced_controls_frame.grid()
            else:
                self.advanced_controls_frame.grid_remove()
        if self.advanced_toggle_button is not None:
            label = (
                "Скрыть расширенные параметры ▴"
                if self.advanced_controls_visible
                else "Показать расширенные параметры ▾"
            )
            self.advanced_toggle_button.configure(text=label)

    def _on_mobile_service_changed(self, _event: Optional[tk.Event] = None) -> None:
        self.saved_mobile_operator_id = None
        self.saved_mobile_rotation_id = None
        self._refresh_mobile_operator_options(use_saved_ids=False)
        self._save_settings(silent=True)

    def _on_mobile_operator_changed(self, _event: Optional[tk.Event] = None) -> None:
        self.saved_mobile_rotation_id = None
        self._refresh_mobile_rotation_options(use_saved_ids=False)
        self._save_settings(silent=True)

    def _refresh_dynamic_controls(self) -> None:
        proxy_type = self.proxy_type_var.get().strip() or "ipv4"
        country_item = self.countries_by_label.get(self.country_var.get(), {})
        country_id = str(country_item.get("id") or "")
        min_qty, max_qty, allowed_quantities = self._get_quantity_constraints(proxy_type, country_id)
        self.quantity_spin.configure(from_=min_qty, to=max_qty)

        try:
            quantity = int(self.quantity_var.get())
        except Exception:
            quantity = min_qty
        quantity = min(max(quantity, min_qty), max_qty)
        if allowed_quantities and quantity not in allowed_quantities:
            quantity = min(allowed_quantities)
        self.quantity_var.set(quantity)

        if not self.custom_target_var.get().strip():
            self.custom_target_var.set(DEFAULT_CUSTOM_TARGET_NAME)
        if self.mobile_service_type_var.get().strip().lower() not in {"dedicated", "shared"}:
            self.mobile_service_type_var.set("dedicated")
        if self.payment_method_var.get().strip() not in PAYMENT_LABEL_TO_ID:
            self.payment_method_var.set(PAYMENT_METHODS[0][0])
        generate_auth = self.generate_auth_var.get().strip().upper()
        self.generate_auth_var.set("Y" if generate_auth == "Y" else "N")
        self.authorization_var.set(self.authorization_var.get().strip())
        self.order_filter_var.set(self.order_filter_var.get().strip())

        self.order_rules_var.set(self._build_order_rules_text(proxy_type, allowed_quantities))
        self._set_advanced_controls_visible(self.advanced_controls_visible)
        if self.tariff_controls_frame is not None:
            if proxy_type in TARIFF_PROXY_TYPES:
                self.tariff_controls_frame.grid()
                if self.tariff_var.get() not in self.tariffs_by_label and self.tariffs_by_label:
                    self.tariff_var.set(next(iter(self.tariffs_by_label.keys())))
            else:
                self.tariff_controls_frame.grid_remove()
                self.tariff_var.set("")

        if self.mobile_controls_frame is None:
            return
        if proxy_type == MOBILE_PROXY_TYPE:
            self.mobile_controls_frame.grid()
            self._refresh_mobile_operator_options(use_saved_ids=True)
        else:
            self.mobile_controls_frame.grid_remove()
            self.mobile_operators_by_label = {}
            self.mobile_rotations_by_label = {}
            self.mobile_operator_var.set("")
            self.mobile_rotation_var.set("")
            if self.mobile_operator_combo is not None:
                self.mobile_operator_combo.configure(values=[])
            if self.mobile_rotation_combo is not None:
                self.mobile_rotation_combo.configure(values=[])

        self._bind_scroll_capture(self.root)

    def _get_quantity_constraints(
        self,
        proxy_type: str,
        country_id: str,
    ) -> Tuple[int, int, Set[int]]:
        min_qty = 1
        max_qty = 2000
        allowed: Set[int] = set()

        if proxy_type == IPV6_PROXY_TYPE:
            min_qty = max(min_qty, IPV6_MIN_QUANTITY)

        if proxy_type in MIX_TYPES and country_id:
            values = self.mix_quantities_by_country_id.get(country_id, [])
            allowed = {value for value in values if value > 0}
            if allowed:
                min_qty = max(min_qty, min(allowed))
                max_qty = max(allowed)

        return min_qty, max_qty, allowed

    def _build_order_rules_text(self, proxy_type: str, allowed_quantities: Set[int]) -> str:
        hints: list[str] = []
        if proxy_type == IPV6_PROXY_TYPE:
            hints.append(f"Для IPv6 требуется количество не меньше {IPV6_MIN_QUANTITY}.")
        if proxy_type in TARIFF_PROXY_TYPES:
            hints.append("Для resident/scraper выбирается тариф, а не страна/период.")
        if proxy_type in MIX_TYPES:
            if allowed_quantities:
                quantity_options = ", ".join(str(v) for v in sorted(allowed_quantities))
                hints.append(f"Для MIX доступны только такие количества: {quantity_options}.")
            else:
                hints.append("Для MIX сначала загрузите страны, чтобы увидеть допустимые количества.")
        if proxy_type == MOBILE_PROXY_TYPE:
            hints.append("Для mobile обязательно выбрать сервис, оператора и ротацию.")
        hints.append("authorization и фильтр заказа — опциональны.")
        return "  ".join(hints)

    def _refresh_mobile_operator_options(self, use_saved_ids: bool) -> None:
        if self.mobile_operator_combo is None:
            return

        country_item = self.countries_by_label.get(self.country_var.get(), {})
        country_id = str(country_item.get("id") or "")
        service_type = (self.mobile_service_type_var.get().strip().lower() or "dedicated")
        country_map = self.mobile_operators_by_country_id.get(country_id, {})
        operators = list(country_map.get(service_type) or [])
        if not operators and country_map:
            service_type = next(iter(country_map))
            self.mobile_service_type_var.set(service_type)
            operators = list(country_map.get(service_type) or [])

        self.mobile_operators_by_label = self._build_label_mapping(operators, self._mobile_operator_label)
        labels = list(self.mobile_operators_by_label.keys())
        self.mobile_operator_combo.configure(values=labels)

        selected_label = self.mobile_operator_var.get()
        if use_saved_ids and self.saved_mobile_operator_id and self.mobile_operators_by_label:
            for label, item in self.mobile_operators_by_label.items():
                if str(item.get("id")) == self.saved_mobile_operator_id:
                    selected_label = label
                    break
            self.saved_mobile_operator_id = None
        if selected_label not in self.mobile_operators_by_label:
            selected_label = labels[0] if labels else ""
        self.mobile_operator_var.set(selected_label)

        self._refresh_mobile_rotation_options(use_saved_ids=use_saved_ids)

    def _refresh_mobile_rotation_options(self, use_saved_ids: bool) -> None:
        if self.mobile_rotation_combo is None:
            return

        operator_item = self.mobile_operators_by_label.get(self.mobile_operator_var.get(), {})
        rotations = list(operator_item.get("rotations") or [])
        self.mobile_rotations_by_label = self._build_label_mapping(rotations, self._mobile_rotation_label)
        labels = list(self.mobile_rotations_by_label.keys())
        self.mobile_rotation_combo.configure(values=labels)

        selected_label = self.mobile_rotation_var.get()
        if use_saved_ids and self.saved_mobile_rotation_id and self.mobile_rotations_by_label:
            for label, item in self.mobile_rotations_by_label.items():
                if str(item.get("id")) == self.saved_mobile_rotation_id:
                    selected_label = label
                    break
            self.saved_mobile_rotation_id = None
        if selected_label not in self.mobile_rotations_by_label:
            selected_label = labels[0] if labels else ""
        self.mobile_rotation_var.set(selected_label)

    def _prepare_order_options(
        self,
        proxy_type: str,
        country_item: Dict[str, Any],
        quantity: int,
    ) -> Dict[str, Any]:
        if quantity <= 0:
            raise ValueError("Количество должно быть больше нуля.")

        country_id = str(country_item.get("id") or "")
        min_qty, _max_qty, allowed_quantities = self._get_quantity_constraints(proxy_type, country_id)
        if quantity < min_qty:
            raise ValueError(f"Для выбранного типа минимальное количество: {min_qty}.")
        if allowed_quantities and quantity not in allowed_quantities:
            allowed_text = ", ".join(str(v) for v in sorted(allowed_quantities))
            raise ValueError(f"Для выбранного MIX доступны только количества: {allowed_text}.")

        custom_target_name = self.custom_target_var.get().strip() or DEFAULT_CUSTOM_TARGET_NAME
        payment_label = self.payment_method_var.get().strip()
        payment_id = PAYMENT_LABEL_TO_ID.get(payment_label)
        if payment_id is None:
            raise ValueError("Выберите корректный способ оплаты (paymentId).")

        authorization = self.authorization_var.get().strip()
        if authorization:
            try:
                ipaddress.ip_address(authorization)
            except ValueError as exc:
                raise ValueError(
                    "Поле authorization должно быть реальным IP-адресом "
                    "(например 1.2.3.4) или пустым."
                ) from exc
        generate_auth = self.generate_auth_var.get().strip().upper()
        if generate_auth not in {"Y", "N"}:
            raise ValueError("Generate auth должен быть Y или N.")

        order_filter = self.order_filter_var.get().strip()
        options: Dict[str, Any] = {
            "quantity": quantity,
            "payment_id": payment_id,
            "payment_label": payment_label,
            "authorization": authorization,
            "generate_auth": generate_auth,
            "order_filter": order_filter,
            "custom_target_name": custom_target_name,
        }

        if proxy_type == MOBILE_PROXY_TYPE:
            service_type = self.mobile_service_type_var.get().strip().lower() or "dedicated"
            if service_type not in {"dedicated", "shared"}:
                raise ValueError("Для mobile выберите корректный тип сервиса: shared или dedicated.")

            operator_item = self.mobile_operators_by_label.get(self.mobile_operator_var.get())
            if not operator_item:
                raise ValueError("Для mobile выберите оператора из списка.")
            operator_id = operator_item.get("id")
            if operator_id in (None, ""):
                raise ValueError("Для mobile не удалось определить operatorId.")

            rotation_item = self.mobile_rotations_by_label.get(self.mobile_rotation_var.get())
            if not rotation_item:
                raise ValueError("Для mobile выберите ротацию из списка.")

            rotation_id = rotation_item.get("id")
            if rotation_id in (None, ""):
                raise ValueError("Для mobile не удалось определить rotationId.")

            options.update(
                {
                    "mobile_service_type": service_type,
                    "mobile_operator_id": operator_id,
                    "mobile_operator_name": operator_item.get("name", "unknown"),
                    "mobile_rotation_id": rotation_id,
                    "mobile_rotation_name": rotation_item.get("name", rotation_id),
                }
            )

        return options

    def _extract_reference_extras(
        self,
        reference_items: Sequence[Dict[str, Any]],
    ) -> Tuple[Dict[str, Dict[str, list[Dict[str, Any]]]], Dict[str, list[int]]]:
        if not reference_items:
            return {}, {}

        root_item = reference_items[0] if isinstance(reference_items[0], dict) else {}
        countries = root_item.get("country")
        quantities = root_item.get("quantities")

        mobile_operators_by_country_id: Dict[str, Dict[str, list[Dict[str, Any]]]] = {}
        if isinstance(countries, list):
            for country in countries:
                if not isinstance(country, dict):
                    continue
                country_id = str(country.get("id") or "").strip()
                if not country_id:
                    continue

                operators_root = country.get("operators")
                if not isinstance(operators_root, dict):
                    continue

                by_service: Dict[str, list[Dict[str, Any]]] = {}
                for raw_service_type, raw_operators in operators_root.items():
                    service_type = str(raw_service_type or "").strip().lower()
                    if not service_type or not isinstance(raw_operators, list):
                        continue

                    normalized: list[Dict[str, Any]] = []
                    seen_operator_ids: Set[str] = set()
                    for operator in raw_operators:
                        if not isinstance(operator, dict):
                            continue
                        operator_id = str(operator.get("id") or "").strip()
                        if not operator_id or operator_id in seen_operator_ids:
                            continue
                        seen_operator_ids.add(operator_id)

                        rotations_raw = operator.get("rotations")
                        rotations: list[Dict[str, Any]] = []
                        if isinstance(rotations_raw, list):
                            for rotation in rotations_raw:
                                if not isinstance(rotation, dict):
                                    continue
                                rotation_id = rotation.get("id")
                                if rotation_id in (None, ""):
                                    continue
                                rotation_name = str(rotation.get("name", rotation_id)).strip() or str(
                                    rotation_id
                                )
                                rotations.append({"id": rotation_id, "name": rotation_name})

                        normalized.append(
                            {
                                "id": operator_id,
                                "name": str(operator.get("name") or operator_id).strip() or operator_id,
                                "traffic": str(operator.get("traffic") or "").strip(),
                                "service_type": service_type,
                                "rotations": rotations,
                            }
                        )

                    if normalized:
                        by_service[service_type] = normalized

                if by_service:
                    mobile_operators_by_country_id[country_id] = by_service

        mix_quantities_by_country_id: Dict[str, list[int]] = {}
        if isinstance(quantities, list):
            for item in quantities:
                if not isinstance(item, dict):
                    continue
                country_id = str(item.get("id") or "").strip()
                if not country_id:
                    continue
                raw_values = item.get("quantities")
                if not isinstance(raw_values, list):
                    continue
                values: Set[int] = set()
                for value in raw_values:
                    try:
                        parsed = int(value)
                    except (TypeError, ValueError):
                        continue
                    if parsed > 0:
                        values.add(parsed)
                if values:
                    mix_quantities_by_country_id[country_id] = sorted(values)

        return mobile_operators_by_country_id, mix_quantities_by_country_id

    @staticmethod
    def _extract_reference_options(
        reference_items: Sequence[Dict[str, Any]],
    ) -> Tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
        country_map: Dict[Any, Dict[str, Any]] = {}
        period_map: Dict[Any, Dict[str, Any]] = {}

        for item in reference_items:
            if not isinstance(item, dict):
                continue

            for country in item.get("country", []) or []:
                if not isinstance(country, dict):
                    continue
                country_id = country.get("id")
                if country_id is None:
                    continue
                country_map[country_id] = {
                    "id": country_id,
                    "name": str(country.get("name", "Unknown")),
                    "alpha3": str(country.get("alpha3", "")),
                }

            for period in item.get("period", []) or []:
                if not isinstance(period, dict):
                    continue
                period_id = period.get("id")
                if period_id is None:
                    continue
                period_map[period_id] = {
                    "id": period_id,
                    "name": str(period.get("name", period_id)),
                }

        countries = sorted(country_map.values(), key=lambda c: (c.get("name") or "").lower())
        periods = sorted(period_map.values(), key=lambda p: str(p.get("id")))
        return countries, periods

    @staticmethod
    def _extract_tariff_options(
        reference_items: Sequence[Dict[str, Any]],
    ) -> list[Dict[str, Any]]:
        if not reference_items:
            return []
        root_item = reference_items[0] if isinstance(reference_items[0], dict) else {}
        raw_tariffs = root_item.get("tarifs")
        if not isinstance(raw_tariffs, list):
            raw_tariffs = root_item.get("tariffs")
        if not isinstance(raw_tariffs, list):
            return []

        tariff_map: Dict[Any, Dict[str, Any]] = {}
        for tariff in raw_tariffs:
            if not isinstance(tariff, dict):
                continue
            tariff_id = tariff.get("id")
            if tariff_id in (None, ""):
                continue
            tariff_map[tariff_id] = {
                "id": tariff_id,
                "name": str(tariff.get("name") or tariff_id).strip() or str(tariff_id),
                "personal": bool(tariff.get("personal", False)),
            }
        return sorted(tariff_map.values(), key=lambda t: (t.get("name") or "").lower())

    def connect_proxy(self) -> None:
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("API ключ", "Введите API ключ Proxy-Seller.")
            return

        proxy_type = self.proxy_type_var.get().strip() or "ipv4"
        is_tariff_type = proxy_type in TARIFF_PROXY_TYPES
        country_item = self.countries_by_label.get(self.country_var.get())
        period_item = self.periods_by_label.get(self.period_var.get())
        tariff_item = self.tariffs_by_label.get(self.tariff_var.get())
        if is_tariff_type:
            if not tariff_item:
                messagebox.showerror(
                    "Нет выбора",
                    "Сначала обновите список и выберите тариф для resident/scraper.",
                )
                return
        else:
            if not country_item or not period_item:
                messagebox.showerror(
                    "Нет выбора",
                    "Сначала загрузите страны и выберите страну/период.",
                )
                return

        protocol = self.protocol_var.get().strip().upper()
        protocol_payload = "socks5" if protocol == "SOCKS5" else "http"

        try:
            quantity = int(self.quantity_var.get())
        except Exception:
            messagebox.showerror("Количество", "Количество должно быть числом.")
            return

        try:
            order_options = self._prepare_order_options(
                proxy_type=proxy_type,
                country_item=country_item or {},
                quantity=quantity,
            )
        except ValueError as exc:
            messagebox.showerror("Параметры заказа", str(exc))
            return

        confirm_message = (
            "Это действие создаст платный заказ в Proxy-Seller.\n\n"
            f"Тип: {proxy_type}\n"
            f"Протокол: {protocol_payload}\n"
            f"Количество: {order_options['quantity']}\n"
            f"Оплата: {order_options['payment_label']}\n"
            f"Authorization: {order_options['authorization'] or 'по логину/паролю'}\n"
            f"Generate auth: {order_options['generate_auth']}\n"
            f"Назначение: {order_options['custom_target_name']}\n"
        )
        if is_tariff_type:
            tariff_name = str(tariff_item.get("name", tariff_item.get("id", "неизвестно")))
            confirm_message += f"Тариф: {tariff_name}\n"
        else:
            country_name = str(country_item.get("name", "неизвестно"))
            period_name = str(period_item.get("name", period_item.get("id", "неизвестно")))
            confirm_message += f"Страна: {country_name}\nПериод: {period_name}\n"

        if proxy_type == MOBILE_PROXY_TYPE:
            confirm_message += (
                f"Mobile-сервис: {order_options['mobile_service_type']}\n"
                f"Оператор: {order_options['mobile_operator_name']}\n"
                f"Ротация: {order_options['mobile_rotation_name']}\n"
            )
        confirm_message += "\nПродолжить?"
        confirm = messagebox.askyesno(
            "Подтверждение платного заказа",
            confirm_message,
        )
        if not confirm:
            self._append_log("Создание заказа отменено пользователем.")
            return

        def worker() -> Dict[str, Any]:
            client = ProxySellerClient(api_key=api_key)
            if is_tariff_type:
                payload = client.build_tariff_order_payload(
                    tarif_id=int(tariff_item["id"]),
                    quantity=int(order_options["quantity"]),
                    payment_id=int(order_options["payment_id"]),
                    custom_target_name=str(order_options["custom_target_name"]),
                    authorization=str(order_options["authorization"]),
                    generate_auth=str(order_options["generate_auth"]),
                )
            else:
                payload = client.build_order_payload(
                    proxy_type=proxy_type,
                    country_id=int(country_item["id"]),
                    period_id=str(period_item["id"]),
                    quantity=int(order_options["quantity"]),
                    payment_id=int(order_options["payment_id"]),
                    protocol=protocol_payload,
                    custom_target_name=str(order_options["custom_target_name"]),
                    authorization=str(order_options["authorization"]),
                    generate_auth=str(order_options["generate_auth"]),
                )
            if proxy_type == MOBILE_PROXY_TYPE and not is_tariff_type:
                payload["mobileServiceType"] = str(order_options["mobile_service_type"])
                payload["operatorId"] = order_options["mobile_operator_id"]
                payload["rotationId"] = int(order_options["mobile_rotation_id"])
            calc = client.calculate_order(payload)
            order_result = client.place_order(payload)

            order_id = self._extract_order_id(order_result)
            if not order_id:
                raise ProxySellerAPIError(
                    "Заказ создан, но идентификатор заказа не найден в ответе API."
                )

            proxy_item = client.wait_for_order_proxy(
                proxy_type=proxy_type,
                order_id=order_id,
                timeout_sec=180,
                poll_interval_sec=4,
            )
            purchased_proxy = self._proxy_from_api_item(
                proxy_item=proxy_item,
                protocol=protocol_payload,
                order_id=order_id,
            )
            config_path, proxy_url = self._save_proxy_config(
                purchased_proxy=purchased_proxy,
                calc_response=calc,
                order_response=order_result,
                proxy_response=proxy_item,
            )

            system_result = apply_system_proxy(
                SystemProxyConfig(
                    host=purchased_proxy.host,
                    port=purchased_proxy.port,
                    protocol=purchased_proxy.protocol,
                    username=purchased_proxy.username,
                    password=purchased_proxy.password,
                )
            )

            return {
                "proxy": purchased_proxy,
                "config_path": str(config_path),
                "proxy_url": proxy_url,
                "system_result": system_result,
                "order_total": calc.get("total"),
                "order_currency": calc.get("currency"),
                "base_order_numbers": order_result.get("listBaseOrderNumbers"),
            }

        def on_success(result: Dict[str, Any]) -> None:
            purchased_proxy = result["proxy"]
            self.active_proxy = purchased_proxy
            self.active_proxy_url = result["proxy_url"]
            self._set_active_proxy_label()
            self._store_last_proxy_state(
                purchased_proxy=purchased_proxy,
                proxy_url=result["proxy_url"],
                config_path=result["config_path"],
            )

            total = result.get("order_total")
            currency = result.get("order_currency")
            total_info = ""
            if total is not None and currency:
                total_info = f" Предварительная стоимость: {total} {currency}."

            self._append_log(
                "Подключено. "
                f"Прокси: {result['proxy_url']}."
                f"{total_info}"
            )
            base_order_numbers = result.get("base_order_numbers")
            if isinstance(base_order_numbers, list) and base_order_numbers:
                joined = ", ".join(str(item) for item in base_order_numbers)
                self._append_log(f"Base order numbers: {joined}")
            self._append_log(f"Конфиг сохранен: {result['config_path']}")
            self._append_log(result["system_result"])
            self._save_settings(silent=True)

        self._run_async(
            "Создание заказа, ожидание активации и применение системного прокси...",
            worker,
            on_success,
        )

    def connect_active_proxy(self) -> None:
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("API ключ", "Введите API ключ Proxy-Seller.")
            return

        proxy_type = self.proxy_type_var.get().strip() or "ipv4"
        protocol = self.protocol_var.get().strip().upper()
        protocol_payload = "socks5" if protocol == "SOCKS5" else "http"
        selected_country = self.countries_by_label.get(self.country_var.get(), {})
        selected_country_name = str(selected_country.get("name", "")).strip().lower()
        selected_country_alpha3 = str(selected_country.get("alpha3", "")).strip().upper()
        order_filter = self.order_filter_var.get().strip()

        def worker() -> Dict[str, Any]:
            client = ProxySellerClient(api_key=api_key)
            items = self._fetch_active_proxies_for_type(
                client=client,
                proxy_type=proxy_type,
                order_filter=order_filter,
            )
            if not items:
                if order_filter:
                    raise ProxySellerAPIError(
                        f"По фильтру заказа '{order_filter}' активные прокси не найдены."
                    )
                raise ProxySellerAPIError("Для выбранного типа не найдено активных прокси.")

            def is_country_match(item: Dict[str, Any]) -> bool:
                if not selected_country_name and not selected_country_alpha3:
                    return True
                item_alpha3 = str(
                    item.get("country_alpha3") or item.get("countryAlpha3") or ""
                ).strip().upper()
                item_country = str(item.get("country") or "").strip().lower()
                if selected_country_alpha3 and item_alpha3 == selected_country_alpha3:
                    return True
                if selected_country_name and item_country == selected_country_name:
                    return True
                return False

            filtered = [item for item in items if is_country_match(item)]
            if not filtered:
                order_filter_info = (
                    f" и фильтра заказа '{order_filter}'" if order_filter else ""
                )
                raise ProxySellerAPIError(
                    f"Для выбранной страны{order_filter_info} нет активных прокси. "
                    "Попробуйте 'Купить и подключить' или выберите другую страну."
                )

            proxy_item = filtered[0]
            order_id = (
                str(
                    proxy_item.get("order_id")
                    or proxy_item.get("orderId")
                    or proxy_item.get("order_number")
                    or proxy_item.get("orderNumber")
                    or "active_proxy"
                )
            )
            purchased_proxy = self._proxy_from_api_item(
                proxy_item=proxy_item,
                protocol=protocol_payload,
                order_id=order_id,
            )
            config_path, proxy_url = self._save_proxy_config(
                purchased_proxy=purchased_proxy,
                calc_response={},
                order_response={"mode": "active_proxy"},
                proxy_response=proxy_item,
            )
            system_result = apply_system_proxy(
                SystemProxyConfig(
                    host=purchased_proxy.host,
                    port=purchased_proxy.port,
                    protocol=purchased_proxy.protocol,
                    username=purchased_proxy.username,
                    password=purchased_proxy.password,
                )
            )
            return {
                "proxy": purchased_proxy,
                "config_path": str(config_path),
                "proxy_url": proxy_url,
                "system_result": system_result,
                "available_count": len(filtered),
            }

        def on_success(result: Dict[str, Any]) -> None:
            purchased_proxy = result["proxy"]
            self.active_proxy = purchased_proxy
            self.active_proxy_url = result["proxy_url"]
            self._set_active_proxy_label()
            self._store_last_proxy_state(
                purchased_proxy=purchased_proxy,
                proxy_url=result["proxy_url"],
                config_path=result["config_path"],
            )
            order_filter_info = f" Фильтр заказа: {order_filter}." if order_filter else ""
            self._append_log(
                f"Подключен активный прокси: {result['proxy_url']}. "
                f"Найдено совпадений: {result['available_count']}."
                f"{order_filter_info}"
            )
            self._append_log(f"Конфиг сохранен: {result['config_path']}")
            self._append_log(result["system_result"])
            self._save_settings(silent=True)

        self._run_async(
            "Поиск активного прокси и применение системного прокси...",
            worker,
            on_success,
        )

    def reconnect_last_proxy(self) -> None:
        if not LAST_PROXY_FILE.exists():
            messagebox.showinfo(
                "Повторное подключение",
                "Сохраненный прокси еще не найден. Сначала подключитесь через API.",
            )
            return

        def worker() -> Dict[str, Any]:
            try:
                payload = json.loads(LAST_PROXY_FILE.read_text(encoding="utf-8"))
                proxy_data = payload.get("proxy", {})
                if not isinstance(proxy_data, dict):
                    raise ValueError("Некорректный формат сохраненного прокси.")
            except Exception as exc:
                raise ProxySellerAPIError(f"Не удалось прочитать файл сохраненного прокси: {exc}") from exc

            host = str(proxy_data.get("host") or "").strip()
            raw_port = proxy_data.get("port")
            protocol = str(proxy_data.get("protocol") or "http").strip().lower()
            username = str(proxy_data.get("username") or "").strip()
            password = str(proxy_data.get("password") or "").strip()
            country = str(proxy_data.get("country") or "").strip()
            country_alpha3 = str(proxy_data.get("country_alpha3") or "").strip()
            order_id = str(proxy_data.get("order_id") or "saved")

            if not host:
                raise ProxySellerAPIError("В сохраненном прокси отсутствует хост.")
            try:
                port = int(raw_port)
            except (TypeError, ValueError) as exc:
                raise ProxySellerAPIError("В сохраненном прокси отсутствует корректный порт.") from exc

            purchased_proxy = PurchasedProxy(
                host=host,
                port=port,
                protocol=protocol,
                username=username,
                password=password,
                country=country,
                country_alpha3=country_alpha3,
                order_id=order_id,
            )
            proxy_url = str(payload.get("proxy_url") or self._build_proxy_url(purchased_proxy))
            result = apply_system_proxy(
                SystemProxyConfig(
                    host=purchased_proxy.host,
                    port=purchased_proxy.port,
                    protocol=purchased_proxy.protocol,
                    username=purchased_proxy.username,
                    password=purchased_proxy.password,
                )
            )
            config_path = str(payload.get("config_path") or LAST_PROXY_FILE)
            return {
                "proxy": purchased_proxy,
                "proxy_url": proxy_url,
                "config_path": config_path,
                "system_result": result,
            }

        def on_success(result: Dict[str, Any]) -> None:
            self.active_proxy = result["proxy"]
            self.active_proxy_url = result["proxy_url"]
            self._set_active_proxy_label()
            self._append_log(f"Повторно подключен сохраненный прокси: {result['proxy_url']}")
            self._append_log(result["system_result"])
            self._append_log(f"Источник конфига: {result['config_path']}")

        self._run_async(
            "Применение последнего сохраненного прокси в системных настройках...",
            worker,
            on_success,
        )

    def disconnect_proxy(self) -> None:
        def worker() -> str:
            return disable_system_proxy()

        def on_success(message: str) -> None:
            self.active_proxy = None
            self.active_proxy_url = ""
            self._set_active_proxy_label()
            self._append_log(message)
            self._append_log("Прокси отключен.")

        self._run_async("Отключение системного прокси...", worker, on_success)

    def open_configs_folder(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = str(OUTPUT_DIR)

        system_name = platform.system().lower()
        try:
            if system_name == "darwin":
                subprocess.run(["open", path], check=False)
            elif system_name == "windows":
                subprocess.run(["explorer", path], check=False)
            else:
                raise SystemProxyError("Действие поддерживается только на macOS и Windows.")
        except Exception as exc:
            messagebox.showerror("Открытие папки", f"Не удалось открыть папку: {exc}")
            return

        self._append_log(f"Открыта папка конфигов: {path}")

    def show_balance(self) -> None:
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("API ключ", "Введите API ключ Proxy-Seller.")
            return

        def worker() -> Dict[str, Any]:
            client = ProxySellerClient(api_key=api_key)
            return client.get_balance()

        def on_success(result: Dict[str, Any]) -> None:
            balance = result.get("balance")
            if balance is None:
                balance = result.get("summ")
            currency = str(result.get("currency") or "").strip()
            if balance is None:
                text = f"Баланс получен, ответ API: {result}"
            elif currency:
                text = f"Баланс: {balance} {currency}"
            else:
                text = f"Баланс: {balance}"
            self._append_log(text)
            messagebox.showinfo("Баланс Proxy-Seller", text)

        self._run_async("Проверка баланса в Proxy-Seller API...", worker, on_success)

    def _fetch_active_proxies_for_type(
        self,
        client: ProxySellerClient,
        proxy_type: str,
        order_filter: str = "",
    ) -> list[Dict[str, Any]]:
        normalized_filter = str(order_filter or "").strip()
        if not normalized_filter:
            return client.get_active_proxies(proxy_type=proxy_type)

        candidates = (
            {"orderId": normalized_filter},
            {"baseOrderNumber": normalized_filter},
        )
        merged: list[Dict[str, Any]] = []
        seen: Set[tuple[str, ...]] = set()
        errors: list[str] = []

        for params in candidates:
            try:
                items = client.get_active_proxies(proxy_type=proxy_type, params=params)
            except ProxySellerAPIError as exc:
                errors.append(str(exc))
                continue

            for item in items:
                identity = self._proxy_item_identity(item)
                if identity in seen:
                    continue
                seen.add(identity)
                merged.append(item)

        if merged:
            return merged

        # Fallback: if server-side filter yields nothing, verify locally using full list.
        try:
            full_items = client.get_active_proxies(proxy_type=proxy_type)
        except ProxySellerAPIError:
            if errors:
                raise ProxySellerAPIError("; ".join(errors))
            raise

        filtered: list[Dict[str, Any]] = []
        for item in full_items:
            if str(self._extract_order_id(item)).strip() == normalized_filter:
                filtered.append(item)
        return filtered

    @staticmethod
    def _proxy_item_identity(item: Dict[str, Any]) -> tuple[str, ...]:
        return (
            str(item.get("ip_only") or item.get("ip") or item.get("host") or ""),
            str(
                item.get("port")
                or item.get("port_http")
                or item.get("portHttp")
                or item.get("port_socks")
                or item.get("portSocks")
                or ""
            ),
            str(item.get("login") or item.get("user") or item.get("username") or ""),
            str(
                item.get("order_id")
                or item.get("orderId")
                or item.get("baseOrderNumber")
                or item.get("order_number")
                or item.get("orderNumber")
                or ""
            ),
        )

    def show_active_proxies(self) -> None:
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("API ключ", "Введите API ключ Proxy-Seller.")
            return

        order_filter = self.order_filter_var.get().strip()

        def worker() -> Dict[str, Dict[str, Any]]:
            client = ProxySellerClient(api_key=api_key)
            result: Dict[str, Dict[str, Any]] = {}
            for proxy_type in ACTIVE_PROXY_TYPES:
                try:
                    items = self._fetch_active_proxies_for_type(
                        client=client,
                        proxy_type=proxy_type,
                        order_filter=order_filter,
                    )
                    result[proxy_type] = {"items": items}
                except Exception as exc:
                    result[proxy_type] = {"items": [], "error": str(exc)}
            return result

        def on_success(result: Dict[str, Dict[str, Any]]) -> None:
            report_text, total = self._build_active_proxies_report(
                result,
                order_filter=order_filter,
            )
            if order_filter:
                self._append_log(
                    f"Активные прокси по фильтру '{order_filter}': найдено {total}."
                )
            else:
                self._append_log(f"Активные прокси: найдено {total}.")
            self._show_text_report_window("Активные прокси", report_text)

        self._run_async(
            "Загрузка активных прокси из Proxy-Seller API...",
            worker,
            on_success,
        )

    def _build_active_proxies_report(
        self,
        payload: Dict[str, Dict[str, Any]],
        order_filter: str = "",
    ) -> Tuple[str, int]:
        normalized_filter = str(order_filter or "").strip()
        lines: list[str] = [
            "Активные прокси по всем типам:",
            "",
        ]
        if normalized_filter:
            lines.append(f"Фильтр заказа: {normalized_filter}")
            lines.append("")
        total = 0

        for proxy_type in ACTIVE_PROXY_TYPES:
            section = payload.get(proxy_type) or {}
            error_text = str(section.get("error") or "").strip()
            if error_text:
                lines.append(f"{proxy_type.upper()}: ошибка API: {error_text}")
                lines.append("")
                continue

            raw_items = section.get("items") or []
            items = [item for item in raw_items if isinstance(item, dict)]
            count = len(items)
            total += count
            lines.append(f"{proxy_type.upper()}: {count}")

            if not items:
                lines.append("  Нет активных прокси.")
                lines.append("")
                continue

            for index, item in enumerate(items[:40], start=1):
                host = str(item.get("ip") or item.get("host") or item.get("server") or "-")
                port = str(
                    item.get("port")
                    or item.get("port_http")
                    or item.get("portHttp")
                    or item.get("port_socks")
                    or item.get("portSocks")
                    or "-"
                )
                country = str(
                    item.get("country")
                    or item.get("country_alpha3")
                    or item.get("countryAlpha3")
                    or "-"
                )
                order_id = self._extract_order_id(item) or "-"
                user = str(item.get("login") or item.get("user") or item.get("username") or "-")
                expires = str(
                    item.get("date_end")
                    or item.get("dateEnd")
                    or item.get("expired_at")
                    or item.get("expire_at")
                    or "-"
                )
                lines.append(
                    f"  {index}. {host}:{port} | страна: {country} | order: {order_id} | user: {user} | до: {expires}"
                )
            hidden = count - 40
            if hidden > 0:
                lines.append(f"  ... и ещё {hidden} шт.")
            lines.append("")

        if total == 0:
            lines.append("Итог: активных прокси не найдено.")
        else:
            lines.append(f"Итог: {total} активных прокси.")
        return "\n".join(lines), total

    def _show_text_report_window(self, title: str, content: str) -> None:
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("900x620")
        window.minsize(680, 460)
        window.configure(bg=APP_BG)
        window.transient(self.root)

        container = ttk.Frame(window, style="App.TFrame", padding=(12, 12, 12, 10))
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        text = tk.Text(
            container,
            wrap="word",
            bg=LOG_BG,
            fg=LOG_FG,
            insertbackground=LOG_FG,
            selectbackground=ACCENT,
            selectforeground="#ffffff",
            borderwidth=0,
            relief="flat",
            padx=10,
            pady=10,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=text.yview,
            style="Vertical.TScrollbar",
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scrollbar.set)

        text.insert("1.0", content)
        text.configure(state="disabled")

        controls = ttk.Frame(container, style="App.TFrame")
        controls.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        controls.columnconfigure(0, weight=1)

        def copy_to_clipboard() -> None:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                self._append_log("Список активных прокси скопирован в буфер обмена.")
            except tk.TclError:
                messagebox.showinfo("Буфер обмена", "Не удалось скопировать список в буфер обмена.")

        ttk.Button(
            controls,
            text="Скопировать",
            command=copy_to_clipboard,
            style="Ghost.TButton",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            controls,
            text="Закрыть",
            command=window.destroy,
            style="Secondary.TButton",
        ).grid(row=0, column=1, sticky="e")

    def _on_window_resize(self, event: tk.Event) -> None:
        if event.widget is not self.root:
            return

        width = int(event.width)
        if width <= 0 or abs(width - self._last_window_width) < 4:
            return

        self._last_window_width = width
        content_width = width
        if self.main_canvas is not None:
            canvas_width = int(self.main_canvas.winfo_width())
            if canvas_width > 0:
                content_width = canvas_width
        self._layout_action_buttons(content_width)
        self._apply_text_wrap(content_width)

    def _on_content_frame_configure(self, _event: tk.Event) -> None:
        if self.main_canvas is None:
            return
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        if self.main_canvas is None or self.main_canvas_window is None:
            return
        content_width = max(int(event.width), 1)
        self.main_canvas.itemconfigure(self.main_canvas_window, width=content_width)

    def _bind_scroll_capture(self, widget: tk.Widget) -> None:
        if not self._wheel_capture_bound:
            for sequence in SCROLL_EVENT_SEQUENCES:
                try:
                    self.root.bind_class(
                        WHEEL_CAPTURE_TAG,
                        sequence,
                        self._on_global_mousewheel,
                        add="+",
                    )
                except tk.TclError:
                    continue
            self._wheel_capture_bound = True

        try:
            bind_tags = tuple(widget.bindtags())
        except tk.TclError:
            bind_tags = ()

        if bind_tags:
            filtered = tuple(tag for tag in bind_tags if tag != WHEEL_CAPTURE_TAG)
            widget.bindtags((WHEEL_CAPTURE_TAG, *filtered))

        for child in widget.winfo_children():
            self._bind_scroll_capture(child)

    @staticmethod
    def _can_scroll_view(view: Tuple[float, float]) -> bool:
        return view[0] > 0.0001 or view[1] < 0.9999

    def _scroll_log_text(self, delta_units: int) -> Tuple[bool, Tuple[float, float], Tuple[float, float]]:
        if self.log_text is None:
            neutral = (0.0, 1.0)
            return False, neutral, neutral

        try:
            before = tuple(float(v) for v in self.log_text.yview())
        except (tk.TclError, ValueError, TypeError):
            neutral = (0.0, 1.0)
            return False, neutral, neutral

        if not self._can_scroll_view(before):
            return False, before, before

        try:
            self.log_text.yview_scroll(delta_units, "units")
            after = tuple(float(v) for v in self.log_text.yview())
        except (tk.TclError, ValueError, TypeError):
            return False, before, before

        return after != before, before, after

    def _on_global_mousewheel(self, event: tk.Event) -> Optional[str]:
        if self.main_canvas is None:
            return None

        now = time.monotonic()
        event_signature = (
            getattr(event, "serial", None),
            getattr(event, "time", None),
            getattr(event, "delta", None),
            getattr(event, "num", None),
        )
        if (
            self._last_wheel_event_signature == event_signature
            and now - self._last_wheel_event_ts < 0.03
        ):
            return None
        self._last_wheel_event_signature = event_signature
        self._last_wheel_event_ts = now

        delta_units = 0
        wheel_delta = 0.0
        if getattr(event, "num", None) == 4:
            delta_units = -WHEEL_SCROLL_STEP
        elif getattr(event, "num", None) == 5:
            delta_units = WHEEL_SCROLL_STEP
        else:
            raw_delta_value = getattr(event, "delta", 0)
            try:
                wheel_delta = float(raw_delta_value or 0.0)
            except Exception:
                wheel_delta = 0.0

            if wheel_delta:
                system_name = platform.system().lower()
                if system_name == "darwin":
                    # On macOS delta can be small/float with touchpad; accumulate smoothly.
                    normalized = wheel_delta * self._mac_wheel_sign
                    self._wheel_fractional_accumulator += normalized
                    direction = -1 if self._wheel_fractional_accumulator < 0 else 1
                    magnitude = int(abs(self._wheel_fractional_accumulator))
                    if magnitude == 0:
                        magnitude = 1
                    magnitude = min(magnitude, 24)
                    self._wheel_fractional_accumulator = 0.0
                else:
                    direction = -1 if wheel_delta > 0 else 1
                    magnitude = max(1, min(int(abs(wheel_delta) / 120) or 1, 8))
                delta_units = direction * magnitude * WHEEL_SCROLL_STEP

        if now - self._last_wheel_log_ts > 0.25:
            self._debug_log(
                f"MouseWheel event: raw_delta={getattr(event, 'delta', 0)}, num={getattr(event, 'num', None)}, keysym={getattr(event, 'keysym', '')}, widget={event.widget}"
            )
            self._last_wheel_log_ts = now

        if not delta_units:
            return None

        target_widget = event.widget if isinstance(event.widget, tk.Widget) else None
        target_name = str(target_widget) if target_widget is not None else ""
        log_name = str(self.log_text) if self.log_text is not None else ""
        is_log_target = bool(
            log_name
            and target_name
            and (target_name == log_name or target_name.startswith(f"{log_name}."))
        )

        # If cursor is over log pane, scroll it first for predictable UX.
        if is_log_target:
            moved_log, before_log, after_log = self._scroll_log_text(delta_units)
            if moved_log:
                self._debug_log(
                    f"MouseWheel scroll applied: target=log, delta_units={delta_units}, before={before_log}, after={after_log}"
                )
                return "break"

        before_view = tuple(float(v) for v in self.main_canvas.yview())
        after_view = before_view
        moved_main = False
        if self._can_scroll_view(before_view):
            self.main_canvas.yview_scroll(delta_units, "units")
            after_view = tuple(float(v) for v in self.main_canvas.yview())
            moved_main = after_view != before_view

            if (
                platform.system().lower() == "darwin"
                and wheel_delta
                and not moved_main
            ):
                can_scroll_up = before_view[0] > 0.0001
                can_scroll_down = before_view[1] < 0.9999
                at_top_with_up_intent = delta_units < 0 and not can_scroll_up and can_scroll_down
                at_bottom_with_down_intent = delta_units > 0 and not can_scroll_down and can_scroll_up
                if at_top_with_up_intent or at_bottom_with_down_intent:
                    self._mac_wheel_sign *= -1.0
                    normalized = wheel_delta * self._mac_wheel_sign
                    direction = -1 if normalized < 0 else 1
                    magnitude = int(abs(normalized))
                    if magnitude == 0:
                        magnitude = 1
                    magnitude = min(magnitude, 24)
                    fallback_units = direction * magnitude * WHEEL_SCROLL_STEP
                    if fallback_units:
                        self.main_canvas.yview_scroll(fallback_units, "units")
                        after_view = tuple(float(v) for v in self.main_canvas.yview())
                        delta_units = fallback_units
                        moved_main = after_view != before_view
                    self._debug_log(f"MouseWheel direction auto-adjusted: sign={self._mac_wheel_sign}")

        if moved_main:
            self._debug_log(
                f"MouseWheel scroll applied: target=main, delta_units={delta_units}, before={before_view}, after={after_view}"
            )
            return "break"

        moved_log_fallback, before_log, after_log = self._scroll_log_text(delta_units)
        if moved_log_fallback:
            self._debug_log(
                f"MouseWheel scroll applied: target=log-fallback, delta_units={delta_units}, before={before_log}, after={after_log}"
            )
            return "break"

        self._debug_log(
            f"MouseWheel not applied: delta_units={delta_units}, target={target_name}, main_view={before_view}"
        )
        return None

    def _on_global_paste_shortcut(self, event: tk.Event) -> Optional[str]:
        if self.busy:
            return None

        target_widget = self.root.focus_get() or event.widget
        if self._is_api_key_widget(target_widget):
            self._debug_log(
                f"Global paste shortcut: keysym={getattr(event, 'keysym', '')}, keycode={getattr(event, 'keycode', '')}, state={getattr(event, 'state', 0)}"
            )
            self._paste_api_key_from_clipboard()
            return "break"
        return None

    def _on_global_keypress_shortcut(self, event: tk.Event) -> Optional[str]:
        if self.busy:
            return None
        target_widget = self.root.focus_get() or event.widget
        if not self._is_api_key_widget(target_widget):
            return None
        if not self._is_paste_key_combo(event):
            return None
        self._debug_log(
            f"Global keypress paste fallback: keysym={getattr(event, 'keysym', '')}, keycode={getattr(event, 'keycode', '')}, state={getattr(event, 'state', 0)}, char={repr(getattr(event, 'char', ''))}"
        )
        self._paste_api_key_from_clipboard()
        return "break"

    def _on_api_key_keypress_shortcut(self, event: tk.Event) -> Optional[str]:
        if self.busy:
            return "break"
        if not self._is_paste_key_combo(event):
            return None
        self._debug_log(
            f"Entry keypress paste fallback: keysym={getattr(event, 'keysym', '')}, keycode={getattr(event, 'keycode', '')}, state={getattr(event, 'state', 0)}, char={repr(getattr(event, 'char', ''))}"
        )
        self._paste_api_key_from_clipboard()
        return "break"

    @staticmethod
    def _is_paste_key_combo(event: tk.Event) -> bool:
        keysym = str(getattr(event, "keysym", "") or "").strip().lower()
        char = str(getattr(event, "char", "") or "")
        try:
            keycode = int(getattr(event, "keycode", -1))
        except Exception:
            keycode = -1
        try:
            state = int(getattr(event, "state", 0) or 0)
        except Exception:
            state = 0

        # Ctrl+Insert is common on Windows.
        if keysym == "insert" and (state & 0x0004):
            return True

        is_v_like = (
            keysym in PASTE_V_KEYSYMS
            or keycode in PASTE_V_KEYCODES
            or char in PASTE_V_CHARS
        )
        if not is_v_like:
            return False

        # Cross-platform masks observed in Tk: Control/Alt/Meta/Command variants.
        modifier_masks = (0x0004, 0x0008, 0x0010, 0x0040, 0x0080, 0x100000)
        has_known_modifier = any(state & mask for mask in modifier_masks)
        has_any_non_shift_modifier = bool(state & ~0x0001)
        return has_known_modifier or has_any_non_shift_modifier

    def _is_api_key_widget(self, widget: Any) -> bool:
        if widget is None:
            return False
        try:
            return str(widget) == str(self.api_key_entry)
        except Exception:
            return False

    def _layout_action_buttons(self, width: int) -> None:
        buttons = [
            self.load_button,
            self.connect_button,
            self.connect_existing_button,
            self.reconnect_last_button,
            self.disconnect_button,
            self.open_configs_button,
            self.show_active_button,
            self.balance_button,
            self.more_button,
        ]
        for button in buttons:
            if button is not None:
                button.grid_forget()

        self.help_label.grid_forget()

        compact = width < 980

        if compact:
            self.actions_frame.columnconfigure(0, weight=1)
            self.actions_frame.columnconfigure(1, weight=0)
            self.load_button.grid(row=0, column=0, sticky="ew")
            if self.more_button is not None:
                self.more_button.grid(row=0, column=1, sticky="ew", padx=(8, 0))
            self.connect_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
            self.connect_existing_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
            self.disconnect_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
            self.help_label.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
            return

        self.actions_frame.columnconfigure(0, weight=1)
        self.actions_frame.columnconfigure(1, weight=1)
        self.load_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        if self.more_button is not None:
            self.more_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.connect_button.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.connect_existing_button.grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=(8, 0))
        self.disconnect_button.grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=(8, 0))
        self.help_label.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def _apply_text_wrap(self, width: int) -> None:
        help_wrap = max(360, width - 140)
        status_wrap = max(420, width - 140)
        self.help_label.configure(wraplength=help_wrap)
        self.status_label.configure(wraplength=status_wrap)
        self.active_proxy_label.configure(wraplength=status_wrap)
        if self.api_hint_label is not None:
            self.api_hint_label.configure(wraplength=help_wrap)
        if self.hero_subtitle_label is not None:
            self.hero_subtitle_label.configure(wraplength=max(420, width - 160))
        if self.order_rules_label is not None:
            self.order_rules_label.configure(wraplength=help_wrap)
        if self.tariff_hint_label is not None:
            self.tariff_hint_label.configure(wraplength=help_wrap)

    def _schedule_async_poll(self) -> None:
        try:
            self.root.after(ASYNC_POLL_MS, self._process_async_events)
        except tk.TclError:
            return

    def _process_async_events(self) -> None:
        try:
            while True:
                event_type, payload, callback = self._async_events.get_nowait()
                if event_type == "success":
                    on_success = callback
                    if not callable(on_success):
                        raise RuntimeError("Async success callback is not callable.")
                    try:
                        self._on_async_success(payload, on_success)
                    except Exception as exc:
                        self._on_async_error(exc)
                else:
                    error = payload if isinstance(payload, Exception) else Exception(str(payload))
                    self._on_async_error(error)
        except queue.Empty:
            pass
        finally:
            self._schedule_async_poll()

    def _run_async(
        self,
        description: str,
        worker: Callable[[], Any],
        on_success: Callable[[Any], None],
    ) -> None:
        if self.busy:
            self._append_log("Другая операция уже выполняется. Подождите.")
            self._debug_log(f"Async skipped (busy): {description}")
            return

        self._set_busy(True)
        self.status_var.set(description)
        self._append_log(description)
        self._debug_log(f"Async scheduled: {description}")

        def run() -> None:
            started = time.monotonic()
            self._debug_log(f"Async worker start: {description}")
            try:
                result = worker()
            except Exception as exc:
                elapsed = time.monotonic() - started
                self._debug_log(f"Async worker error ({elapsed:.2f}s): {description}: {exc!r}")
                self._async_events.put(("error", exc, None))
                return

            elapsed = time.monotonic() - started
            self._debug_log(f"Async worker success ({elapsed:.2f}s): {description}")
            self._async_events.put(("success", result, on_success))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _on_async_success(
        self,
        result: Any,
        on_success: Callable[[Any], None],
    ) -> None:
        self._set_busy(False)
        self.status_var.set("Готово")
        self.status_label.configure(style="StatusReady.TLabel")
        self._debug_log("Async success handled on UI thread")
        on_success(result)

    def _on_async_error(self, error: Exception) -> None:
        self._set_busy(False)
        self.status_var.set("Ошибка")
        self.status_label.configure(style="StatusError.TLabel")
        self._append_log(f"Ошибка: {error}")
        self._debug_log(f"Async error handled: {type(error).__name__}: {error}")

        if isinstance(error, (ProxySellerAPIError, SystemProxyError)):
            message = str(error)
        else:
            message = f"Неожиданная ошибка: {error}"
        messagebox.showerror("Операция не выполнена", message)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        if busy:
            self.status_label.configure(style="StatusBusy.TLabel")
            if self.progress_bar is not None:
                self.progress_bar.grid()
                self.progress_bar.start(10)
        else:
            if self.progress_bar is not None:
                self.progress_bar.stop()
                self.progress_bar.grid_remove()
            if str(self.status_label.cget("style")) == "StatusBusy.TLabel":
                self.status_label.configure(style="StatusReady.TLabel")
        self.load_button.configure(state=state)
        self.connect_button.configure(state=state)
        self.connect_existing_button.configure(state=state)
        self.disconnect_button.configure(state=state)
        self.reconnect_last_button.configure(state=state)
        self.open_configs_button.configure(state=state)
        if self.show_active_button is not None:
            self.show_active_button.configure(state=state)
        if self.balance_button is not None:
            self.balance_button.configure(state=state)
        if self.more_button is not None:
            self.more_button.configure(state=state)
        if self.advanced_toggle_button is not None:
            self.advanced_toggle_button.configure(state=state)
        self.proxy_type_combo.configure(state="disabled" if busy else "readonly")
        self.protocol_combo.configure(state="disabled" if busy else "readonly")
        self.country_combo.configure(state="disabled" if busy else "readonly")
        self.period_combo.configure(state="disabled" if busy else "readonly")
        if self.tariff_combo is not None:
            self.tariff_combo.configure(state="disabled" if busy else "readonly")
        if self.payment_combo is not None:
            self.payment_combo.configure(state="disabled" if busy else "readonly")
        if self.generate_auth_combo is not None:
            self.generate_auth_combo.configure(state="disabled" if busy else "readonly")
        self.quantity_spin.configure(state=state)
        if self.custom_target_entry is not None:
            self.custom_target_entry.configure(state=state)
        if self.authorization_entry is not None:
            self.authorization_entry.configure(state=state)
        if self.order_filter_entry is not None:
            self.order_filter_entry.configure(state=state)
        if self.mobile_service_combo is not None:
            self.mobile_service_combo.configure(state="disabled" if busy else "readonly")
        if self.mobile_operator_combo is not None:
            self.mobile_operator_combo.configure(state="disabled" if busy else "readonly")
        if self.mobile_rotation_combo is not None:
            self.mobile_rotation_combo.configure(state="disabled" if busy else "readonly")
        self.api_key_entry.configure(state=state)
        if self.paste_api_button is not None:
            self.paste_api_button.configure(state=state)
        if self.clear_api_button is not None:
            self.clear_api_button.configure(state=state)
        self.save_button.configure(state=state)
        if self.logs_per_page_combo is not None:
            self.logs_per_page_combo.configure(state="disabled" if busy else "readonly")
        if self.log_newer_button is not None:
            self.log_newer_button.configure(state=state)
        if self.log_older_button is not None:
            self.log_older_button.configure(state=state)
        if not busy:
            self._render_logs_page()

    def _on_api_key_paste_shortcut(self, event: tk.Event) -> str:
        if self.busy:
            return "break"
        self._debug_log(
            f"Entry paste shortcut: keysym={getattr(event, 'keysym', '')}, keycode={getattr(event, 'keycode', '')}, state={getattr(event, 'state', 0)}"
        )
        self._paste_api_key_from_clipboard()
        return "break"

    def _paste_api_key_from_clipboard(self) -> None:
        try:
            clipboard_value = self.root.clipboard_get()
        except tk.TclError:
            self._debug_log("Clipboard get failed: TclError")
            messagebox.showinfo("Буфер обмена", "Буфер обмена пуст или недоступен.")
            return

        api_key = str(clipboard_value).strip()
        if not api_key:
            self._debug_log("Clipboard paste ignored: empty text")
            messagebox.showinfo("Буфер обмена", "В буфере обмена нет текста для вставки.")
            return

        self.api_key_var.set(api_key)
        self.api_key_entry.focus_set()
        self.api_key_entry.icursor("end")
        self._debug_log(f"API key pasted from clipboard, length={len(api_key)}")
        self._append_log("API-ключ вставлен из буфера обмена.")

    def _get_logs_per_page(self) -> int:
        try:
            value = int(self.logs_per_page_var.get())
        except Exception:
            value = 40
        return min(200, max(10, value))

    def _on_logs_per_page_changed(self, _event: Optional[tk.Event] = None) -> None:
        self.log_page_index = 0
        self._render_logs_page()

    def _show_older_logs(self) -> None:
        per_page = self._get_logs_per_page()
        total_pages = max(1, (len(self.log_entries) + per_page - 1) // per_page)
        if self.log_page_index < total_pages - 1:
            self.log_page_index += 1
            self._render_logs_page()

    def _show_newer_logs(self) -> None:
        if self.log_page_index > 0:
            self.log_page_index -= 1
            self._render_logs_page()

    def _render_logs_page(self) -> None:
        per_page = self._get_logs_per_page()
        total = len(self.log_entries)
        total_pages = max(1, (total + per_page - 1) // per_page)
        self.log_page_index = min(max(self.log_page_index, 0), total_pages - 1)

        end = total - self.log_page_index * per_page
        start = max(0, end - per_page)
        page_entries = self.log_entries[start:end]

        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        if page_entries:
            self.log_text.insert("end", "\n".join(page_entries) + "\n")
        self.log_text.configure(state="disabled")

        if self.log_page_index == 0:
            self.log_text.see("end")
        else:
            self.log_text.see("1.0")

        current_page = self.log_page_index + 1
        self.log_page_label_var.set(f"Страница {current_page} из {total_pages}")
        show_pager = total_pages > 1

        if self.log_newer_button is not None:
            self.log_newer_button.configure(
                state="disabled" if self.busy or self.log_page_index == 0 else "normal"
            )
            if show_pager:
                self.log_newer_button.grid()
            else:
                self.log_newer_button.grid_remove()
        if self.log_older_button is not None:
            self.log_older_button.configure(
                state="disabled" if self.busy or self.log_page_index >= total_pages - 1 else "normal"
            )
            if show_pager:
                self.log_older_button.grid()
            else:
                self.log_older_button.grid_remove()
        if self.log_page_label is not None:
            if show_pager:
                self.log_page_label.grid()
            else:
                self.log_page_label.grid_remove()

    def _append_log(self, line: str) -> None:
        self._debug_log(f"UI_LOG: {line}")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_entries.append(f"[{timestamp}] {line}")
        if len(self.log_entries) > 4000:
            self.log_entries = self.log_entries[-4000:]
        self._render_logs_page()

    def _set_active_proxy_label(self) -> None:
        if not self.active_proxy:
            self.active_proxy_var.set("Активный прокси: не подключен")
            return

        proxy = self.active_proxy
        auth_tag = "с авторизацией" if proxy.username else "без авторизации"
        country_tag = proxy.country_alpha3 or proxy.country or "страна неизвестна"
        self.active_proxy_var.set(
            f"Активный прокси: {proxy.protocol.upper()} {proxy.host}:{proxy.port} "
            f"({country_tag}, {auth_tag})"
        )

    def _store_last_proxy_state(
        self,
        purchased_proxy: PurchasedProxy,
        proxy_url: str,
        config_path: str,
    ) -> None:
        payload = {
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
            "proxy": asdict(purchased_proxy),
            "proxy_url": proxy_url,
            "config_path": config_path,
        }
        try:
            LAST_PROXY_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            self._append_log(f"Предупреждение: не удалось записать состояние последнего прокси: {exc}")

    @staticmethod
    def _build_label_mapping(
        items: Iterable[Dict[str, Any]],
        label_builder: Callable[[Dict[str, Any]], str],
    ) -> Dict[str, Dict[str, Any]]:
        mapping: Dict[str, Dict[str, Any]] = {}
        for item in items:
            base_label = label_builder(item).strip() or "Без названия"
            label = base_label

            if label in mapping:
                item_id = item.get("id")
                if item_id not in (None, ""):
                    label = f"{base_label} · {item_id}"
                index = 2
                while label in mapping:
                    label = f"{base_label} · {index}"
                    index += 1

            mapping[label] = item
        return mapping

    @staticmethod
    def _country_label(country: Dict[str, Any]) -> str:
        name = str(country.get("name", "Неизвестно")).strip()
        alpha3 = str(country.get("alpha3", "")).strip()
        if alpha3:
            return f"{name} ({alpha3})"
        return name or "Неизвестно"

    @staticmethod
    def _period_label(period: Dict[str, Any]) -> str:
        name = str(period.get("name", "Период")).strip()
        return name or "Период"

    @staticmethod
    def _tariff_label(tariff: Dict[str, Any]) -> str:
        name = str(tariff.get("name") or tariff.get("id") or "Тариф").strip() or "Тариф"
        if tariff.get("personal"):
            return f"{name} · personal"
        return name

    @staticmethod
    def _mobile_operator_label(operator: Dict[str, Any]) -> str:
        name = str(operator.get("name") or operator.get("id") or "Оператор").strip() or "Оператор"
        traffic = str(operator.get("traffic") or "").strip()
        if traffic:
            return f"{name} · {traffic}"
        return name

    @staticmethod
    def _mobile_rotation_label(rotation: Dict[str, Any]) -> str:
        return str(rotation.get("name") or rotation.get("id") or "Ротация").strip() or "Ротация"

    def _proxy_from_api_item(
        self,
        proxy_item: Dict[str, Any],
        protocol: str,
        order_id: str,
    ) -> PurchasedProxy:
        host = str(proxy_item.get("ip_only") or proxy_item.get("ip") or "").strip()
        if protocol == "socks5":
            raw_port = proxy_item.get("port_socks") or proxy_item.get("portSocks")
        else:
            raw_port = proxy_item.get("port_http") or proxy_item.get("portHttp")

        if raw_port is None:
            raw_port = proxy_item.get("port")

        if not host:
            raise ProxySellerAPIError("В ответе API отсутствует IP хоста прокси.")
        if raw_port is None:
            raise ProxySellerAPIError("В ответе API отсутствует порт прокси.")

        try:
            port = int(raw_port)
        except (TypeError, ValueError) as exc:
            raise ProxySellerAPIError("API вернул некорректный порт прокси.") from exc

        username = str(proxy_item.get("login") or "").strip()
        password = str(proxy_item.get("password") or "").strip()
        country = str(proxy_item.get("country") or "").strip()
        country_alpha3 = str(proxy_item.get("country_alpha3") or "").strip()

        return PurchasedProxy(
            host=host,
            port=port,
            protocol=protocol,
            username=username,
            password=password,
            country=country,
            country_alpha3=country_alpha3,
            order_id=order_id,
        )

    def _save_proxy_config(
        self,
        purchased_proxy: PurchasedProxy,
        calc_response: Dict[str, Any],
        order_response: Dict[str, Any],
        proxy_response: Dict[str, Any],
    ) -> Tuple[Path, str]:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = (purchased_proxy.country_alpha3 or purchased_proxy.country or "proxy").lower()
        safe_suffix = "".join(ch for ch in suffix if ch.isalnum()) or "proxy"
        file_path = OUTPUT_DIR / f"{timestamp}_{safe_suffix}.json"

        proxy_url = self._build_proxy_url(purchased_proxy)
        document = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "proxy-seller",
            "proxy": asdict(purchased_proxy),
            "proxy_url": proxy_url,
            "calc_response": calc_response,
            "order_response": order_response,
            "proxy_response": proxy_response,
        }
        file_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        return file_path, proxy_url

    @staticmethod
    def _build_proxy_url(purchased_proxy: PurchasedProxy) -> str:
        scheme = "socks5" if purchased_proxy.protocol.lower() == "socks5" else "http"
        if purchased_proxy.username:
            username = quote(purchased_proxy.username, safe="")
            password = quote(purchased_proxy.password, safe="")
            credentials = f"{username}:{password}@"
        else:
            credentials = ""
        return f"{scheme}://{credentials}{purchased_proxy.host}:{purchased_proxy.port}"

    def _extract_order_id(self, payload: Dict[str, Any]) -> str:
        value = self._recursive_lookup(payload, ORDER_ID_KEYS)
        if value is None:
            return ""
        if isinstance(value, list):
            for item in value:
                text = str(item).strip()
                if text:
                    return text
            return ""
        return str(value)

    def _recursive_lookup(
        self,
        value: Any,
        keys: Iterable[str],
    ) -> Optional[Any]:
        if isinstance(value, dict):
            for key in keys:
                candidate = value.get(key)
                if candidate not in (None, ""):
                    return candidate
            for nested in value.values():
                found = self._recursive_lookup(nested, keys)
                if found not in (None, ""):
                    return found
            return None

        if isinstance(value, list):
            for nested in value:
                found = self._recursive_lookup(nested, keys)
                if found not in (None, ""):
                    return found
        return None


def main() -> None:
    root = tk.Tk()
    app = ProxyDesktopApp(root)
    app.api_key_entry.focus_set()
    root.mainloop()


if __name__ == "__main__":
    main()
