from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import tkinter as tk
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, Iterable, Optional, Tuple
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
PROXY_TYPES = ("ipv4", "ipv6", "mobile", "isp", "mix", "mix_isp")
PROTOCOL_OPTIONS = ("HTTP", "SOCKS5")
ORDER_ID_KEYS = (
    "order_id",
    "orderId",
    "order_number",
    "orderNumber",
    "baseOrderNumber",
    "base_order_number",
)


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
        self.root.geometry("860x560")
        self.root.minsize(760, 520)

        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.api_key_var = tk.StringVar(value=os.getenv("PROXY_SELLER_API_KEY", ""))
        self.proxy_type_var = tk.StringVar(value="ipv4")
        self.protocol_var = tk.StringVar(value="HTTP")
        self.quantity_var = tk.IntVar(value=1)
        self.country_var = tk.StringVar()
        self.period_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Готово")
        self.active_proxy_var = tk.StringVar(value="Активный прокси: не подключен")

        self.countries_by_label: Dict[str, Dict[str, Any]] = {}
        self.periods_by_label: Dict[str, Dict[str, Any]] = {}
        self.active_proxy: Optional[PurchasedProxy] = None
        self.active_proxy_url = ""
        self.saved_country_id: Optional[Any] = None
        self.saved_period_id: Optional[Any] = None
        self.busy = False

        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, padding=14)
        root_frame.pack(fill="both", expand=True)
        root_frame.columnconfigure(0, weight=1)
        root_frame.rowconfigure(4, weight=1)

        credentials = ttk.LabelFrame(root_frame, text="Данные API", padding=12)
        credentials.grid(row=0, column=0, sticky="ew")
        credentials.columnconfigure(1, weight=1)

        ttk.Label(credentials, text="API ключ Proxy-Seller").grid(
            row=0, column=0, padx=(0, 10), sticky="w"
        )
        self.api_key_entry = ttk.Entry(
            credentials,
            textvariable=self.api_key_var,
            show="*",
        )
        self.api_key_entry.grid(row=0, column=1, sticky="ew")

        self.save_button = ttk.Button(
            credentials,
            text="Сохранить",
            command=self._on_save_settings,
        )
        self.save_button.grid(row=0, column=2, padx=(10, 0))

        settings = ttk.LabelFrame(root_frame, text="Параметры прокси", padding=12)
        settings.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

        ttk.Label(settings, text="Тип прокси").grid(row=0, column=0, sticky="w")
        self.proxy_type_combo = ttk.Combobox(
            settings,
            textvariable=self.proxy_type_var,
            values=PROXY_TYPES,
            state="readonly",
        )
        self.proxy_type_combo.grid(row=0, column=1, sticky="ew", padx=(8, 14))

        ttk.Label(settings, text="Протокол").grid(row=0, column=2, sticky="w")
        self.protocol_combo = ttk.Combobox(
            settings,
            textvariable=self.protocol_var,
            values=PROTOCOL_OPTIONS,
            state="readonly",
        )
        self.protocol_combo.grid(row=0, column=3, sticky="ew", padx=(8, 0))

        ttk.Label(settings, text="Страна").grid(row=1, column=0, sticky="w", pady=(12, 0))
        self.country_combo = ttk.Combobox(
            settings,
            textvariable=self.country_var,
            values=[],
            state="readonly",
        )
        self.country_combo.grid(row=1, column=1, sticky="ew", padx=(8, 14), pady=(12, 0))

        ttk.Label(settings, text="Период").grid(row=1, column=2, sticky="w", pady=(12, 0))
        self.period_combo = ttk.Combobox(
            settings,
            textvariable=self.period_var,
            values=[],
            state="readonly",
        )
        self.period_combo.grid(row=1, column=3, sticky="ew", padx=(8, 0), pady=(12, 0))

        ttk.Label(settings, text="Количество").grid(row=2, column=0, sticky="w", pady=(12, 0))
        self.quantity_spin = ttk.Spinbox(
            settings,
            from_=1,
            to=100,
            textvariable=self.quantity_var,
            width=8,
        )
        self.quantity_spin.grid(row=2, column=1, sticky="w", padx=(8, 14), pady=(12, 0))

        actions = ttk.Frame(root_frame, padding=(0, 12, 0, 0))
        actions.grid(row=2, column=0, sticky="ew")

        self.load_button = ttk.Button(
            actions,
            text="Загрузить страны",
            command=self.load_reference_data,
        )
        self.load_button.grid(row=0, column=0, padx=(0, 8))

        self.connect_button = ttk.Button(
            actions,
            text="Создать и подключить",
            command=self.connect_proxy,
        )
        self.connect_button.grid(row=0, column=1, padx=(0, 8))

        self.connect_existing_button = ttk.Button(
            actions,
            text="Подключить активный",
            command=self.connect_active_proxy,
        )
        self.connect_existing_button.grid(row=0, column=2, padx=(0, 8))

        self.disconnect_button = ttk.Button(
            actions,
            text="Отключить прокси",
            command=self.disconnect_proxy,
        )
        self.disconnect_button.grid(row=0, column=3)

        self.reconnect_last_button = ttk.Button(
            actions,
            text="Повторно подключить последний",
            command=self.reconnect_last_proxy,
        )
        self.reconnect_last_button.grid(row=1, column=0, pady=(8, 0), padx=(0, 8), sticky="w")

        self.open_configs_button = ttk.Button(
            actions,
            text="Открыть папку конфигов",
            command=self.open_configs_folder,
        )
        self.open_configs_button.grid(row=1, column=1, pady=(8, 0), sticky="w")

        status_bar = ttk.Frame(root_frame, padding=(0, 4, 0, 0))
        status_bar.grid(row=3, column=0, sticky="ew")
        status_bar.columnconfigure(1, weight=1)
        ttk.Label(status_bar, text="Статус:").grid(row=0, column=0, sticky="w")
        self.status_label = ttk.Label(status_bar, textvariable=self.status_var)
        self.status_label.grid(row=0, column=1, sticky="w")
        self.active_proxy_label = ttk.Label(status_bar, textvariable=self.active_proxy_var)
        self.active_proxy_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

        logs_frame = ttk.LabelFrame(root_frame, text="Логи", padding=10)
        logs_frame.grid(row=4, column=0, sticky="nsew", pady=(8, 0))
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            logs_frame,
            wrap="word",
            height=12,
            state="disabled",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(logs_frame, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)

        self._append_log("Введите API ключ, загрузите страны и подключитесь.")
        self._append_log(
            "Кнопка 'Создать и подключить' создает новый платный заказ,"
            " 'Подключить активный' использует уже купленный прокси."
        )
        self._append_log(
            "'Повторно подключить последний' применяет последний сохраненный прокси без API."
        )

    def _on_save_settings(self) -> None:
        self._save_settings(silent=False)

    def _save_settings(self, silent: bool = True) -> None:
        country_item = self.countries_by_label.get(self.country_var.get(), {})
        period_item = self.periods_by_label.get(self.period_var.get(), {})
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

        try:
            quantity = int(payload.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1
        self.quantity_var.set(max(1, quantity))

        self.saved_country_id = payload.get("country_id")
        self.saved_period_id = payload.get("period_id")
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

        def worker() -> Tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            client = ProxySellerClient(api_key=api_key)
            countries, periods = client.get_reference_options(proxy_type)
            if not countries:
                raise ProxySellerAPIError("API не вернул список стран.")
            if not periods:
                raise ProxySellerAPIError("API не вернул варианты периода.")
            return countries, periods

        def on_success(result: Tuple[list[dict[str, Any]], list[dict[str, Any]]]) -> None:
            countries, periods = result
            self.countries_by_label = {
                self._country_label(country): country for country in countries
            }
            self.periods_by_label = {self._period_label(period): period for period in periods}

            country_labels = list(self.countries_by_label.keys())
            period_labels = list(self.periods_by_label.keys())
            self.country_combo.configure(values=country_labels)
            self.period_combo.configure(values=period_labels)

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

            self._append_log(
                f"Загружено стран: {len(country_labels)}, периодов: {len(period_labels)}."
            )
            self._save_settings(silent=True)

        self._run_async(
            "Загрузка стран и периодов из Proxy-Seller API...",
            worker,
            on_success,
        )

    def connect_proxy(self) -> None:
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("API ключ", "Введите API ключ Proxy-Seller.")
            return

        country_item = self.countries_by_label.get(self.country_var.get())
        period_item = self.periods_by_label.get(self.period_var.get())
        if not country_item or not period_item:
            messagebox.showerror(
                "Нет выбора",
                "Сначала загрузите страны и выберите страну/период.",
            )
            return

        proxy_type = self.proxy_type_var.get().strip() or "ipv4"
        protocol = self.protocol_var.get().strip().upper()
        protocol_payload = "socks5" if protocol == "SOCKS5" else "http"

        try:
            quantity = int(self.quantity_var.get())
        except Exception:
            messagebox.showerror("Количество", "Количество должно быть числом.")
            return

        if quantity <= 0:
            messagebox.showerror("Количество", "Количество должно быть больше нуля.")
            return

        country_name = str(country_item.get("name", "неизвестно"))
        period_name = str(period_item.get("name", period_item.get("id", "неизвестно")))
        confirm = messagebox.askyesno(
            "Подтверждение платного заказа",
            "Это действие создаст платный заказ в Proxy-Seller.\n\n"
            f"Тип: {proxy_type}\n"
            f"Протокол: {protocol_payload}\n"
            f"Страна: {country_name}\n"
            f"Период: {period_name}\n"
            f"Количество: {quantity}\n\n"
            "Продолжить?",
        )
        if not confirm:
            self._append_log("Создание заказа отменено пользователем.")
            return

        def worker() -> Dict[str, Any]:
            client = ProxySellerClient(api_key=api_key)
            payload = client.build_order_payload(
                proxy_type=proxy_type,
                country_id=int(country_item["id"]),
                period_id=str(period_item["id"]),
                quantity=quantity,
                payment_id=1,
                protocol=protocol_payload,
            )
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

        def worker() -> Dict[str, Any]:
            client = ProxySellerClient(api_key=api_key)
            items = client.get_active_proxies(proxy_type=proxy_type)
            if not items:
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
                raise ProxySellerAPIError(
                    "Для выбранной страны нет активных прокси. "
                    "Попробуйте 'Создать и подключить' или выберите другую страну."
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
            self._append_log(
                f"Подключен активный прокси: {result['proxy_url']}. "
                f"Найдено совпадений: {result['available_count']}."
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

    def _run_async(
        self,
        description: str,
        worker: Callable[[], Any],
        on_success: Callable[[Any], None],
    ) -> None:
        if self.busy:
            self._append_log("Другая операция уже выполняется. Подождите.")
            return

        self._set_busy(True)
        self.status_var.set(description)
        self._append_log(description)

        def run() -> None:
            try:
                result = worker()
            except Exception as exc:
                self.root.after(0, lambda: self._on_async_error(exc))
                return

            self.root.after(0, lambda: self._on_async_success(result, on_success))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _on_async_success(
        self,
        result: Any,
        on_success: Callable[[Any], None],
    ) -> None:
        self._set_busy(False)
        self.status_var.set("Готово")
        on_success(result)

    def _on_async_error(self, error: Exception) -> None:
        self._set_busy(False)
        self.status_var.set("Ошибка")
        self._append_log(f"Ошибка: {error}")

        if isinstance(error, (ProxySellerAPIError, SystemProxyError)):
            message = str(error)
        else:
            message = f"Неожиданная ошибка: {error}"
        messagebox.showerror("Операция не выполнена", message)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.load_button.configure(state=state)
        self.connect_button.configure(state=state)
        self.connect_existing_button.configure(state=state)
        self.disconnect_button.configure(state=state)
        self.reconnect_last_button.configure(state=state)
        self.open_configs_button.configure(state=state)
        self.proxy_type_combo.configure(state="disabled" if busy else "readonly")
        self.protocol_combo.configure(state="disabled" if busy else "readonly")
        self.country_combo.configure(state="disabled" if busy else "readonly")
        self.period_combo.configure(state="disabled" if busy else "readonly")
        self.quantity_spin.configure(state=state)
        self.api_key_entry.configure(state=state)
        self.save_button.configure(state=state)

    def _append_log(self, line: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {line}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

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
    def _country_label(country: Dict[str, Any]) -> str:
        name = str(country.get("name", "Неизвестно"))
        alpha3 = str(country.get("alpha3", "")).strip()
        country_id = country.get("id")
        alpha3_suffix = f" ({alpha3})" if alpha3 else ""
        return f"{name}{alpha3_suffix} [id={country_id}]"

    @staticmethod
    def _period_label(period: Dict[str, Any]) -> str:
        name = str(period.get("name", "Период"))
        period_id = period.get("id")
        return f"{name} [id={period_id}]"

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
