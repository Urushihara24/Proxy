from __future__ import annotations

import ctypes
import platform
import subprocess
from dataclasses import dataclass
from typing import List


class SystemProxyError(RuntimeError):
    """Raised when system proxy settings cannot be changed automatically."""


@dataclass(frozen=True)
class SystemProxyConfig:
    host: str
    port: int
    protocol: str
    username: str = ""
    password: str = ""


def apply_system_proxy(config: SystemProxyConfig) -> str:
    host = config.host.strip()
    if not host:
        raise SystemProxyError("Proxy host is empty")

    if int(config.port) <= 0:
        raise SystemProxyError("Proxy port must be greater than zero")

    system_name = platform.system().lower()
    if system_name == "darwin":
        return _apply_macos_proxy(config)
    if system_name == "windows":
        return _apply_windows_proxy(config)

    raise SystemProxyError(
        "Automatic system proxy is supported on macOS and Windows in this build."
    )


def disable_system_proxy() -> str:
    system_name = platform.system().lower()
    if system_name == "darwin":
        return _disable_macos_proxy()
    if system_name == "windows":
        return _disable_windows_proxy()

    raise SystemProxyError(
        "Automatic system proxy disable is supported on macOS and Windows in this build."
    )


def _run_command(command: List[str]) -> str:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        details = stderr or stdout or f"exit code {completed.returncode}"
        raise SystemProxyError(f"Command failed: {' '.join(command)} ({details})")
    return completed.stdout


def _list_macos_services() -> List[str]:
    output = _run_command(["networksetup", "-listallnetworkservices"])
    services: List[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("An asterisk"):
            continue
        if line.startswith("*"):
            continue
        services.append(line)
    return services


def _set_macos_proxy(
    command: str,
    service: str,
    config: SystemProxyConfig,
) -> None:
    base = ["networksetup", command, service, config.host, str(config.port)]
    auth_enabled = bool(config.username and config.password)

    if auth_enabled:
        _run_command(base + ["on", config.username, config.password])
        return

    # Some macOS versions accept only short form, others expect auth flag.
    try:
        _run_command(base + ["off", "", ""])
    except SystemProxyError:
        _run_command(base)


def _set_macos_state(command: str, service: str, enabled: bool) -> None:
    state = "on" if enabled else "off"
    _run_command(["networksetup", command, service, state])


def _apply_macos_proxy(config: SystemProxyConfig) -> str:
    services = _list_macos_services()
    if not services:
        raise SystemProxyError("No active network services found on macOS")

    protocol = config.protocol.lower()
    for service in services:
        if protocol == "socks5":
            _set_macos_proxy("-setsocksfirewallproxy", service, config)
            _set_macos_state("-setsocksfirewallproxystate", service, True)
            _set_macos_state("-setwebproxystate", service, False)
            _set_macos_state("-setsecurewebproxystate", service, False)
        else:
            _set_macos_proxy("-setwebproxy", service, config)
            _set_macos_proxy("-setsecurewebproxy", service, config)
            _set_macos_state("-setwebproxystate", service, True)
            _set_macos_state("-setsecurewebproxystate", service, True)
            _set_macos_state("-setsocksfirewallproxystate", service, False)

    return "System proxy enabled for services: " + ", ".join(services)


def _disable_macos_proxy() -> str:
    services = _list_macos_services()
    if not services:
        raise SystemProxyError("No active network services found on macOS")

    for service in services:
        _set_macos_state("-setwebproxystate", service, False)
        _set_macos_state("-setsecurewebproxystate", service, False)
        _set_macos_state("-setsocksfirewallproxystate", service, False)

    return "System proxy disabled for services: " + ", ".join(services)


def _notify_windows_proxy_update() -> None:
    try:
        wininet = ctypes.windll.Wininet
        # INTERNET_OPTION_SETTINGS_CHANGED and INTERNET_OPTION_REFRESH.
        wininet.InternetSetOptionW(0, 39, 0, 0)
        wininet.InternetSetOptionW(0, 37, 0, 0)
    except Exception:
        # Best effort only; settings are still written in registry.
        return


def _apply_windows_proxy(config: SystemProxyConfig) -> str:
    try:
        import winreg  # type: ignore
    except ImportError as exc:
        raise SystemProxyError("winreg is not available on this Python build") from exc

    if config.protocol.lower() == "socks5":
        proxy_server = f"socks={config.host}:{config.port}"
    else:
        proxy_server = f"http={config.host}:{config.port};https={config.host}:{config.port}"

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_server)

    _notify_windows_proxy_update()

    if config.username and config.password:
        return (
            "System proxy enabled. Note: Windows internet proxy does not persist "
            "username/password globally; apps may ask for credentials."
        )

    return "System proxy enabled for current Windows user."


def _disable_windows_proxy() -> str:
    try:
        import winreg  # type: ignore
    except ImportError as exc:
        raise SystemProxyError("winreg is not available on this Python build") from exc

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)

    _notify_windows_proxy_update()
    return "System proxy disabled for current Windows user."
