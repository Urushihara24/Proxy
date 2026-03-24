# Proxy Seller Desktop Launcher

Simple desktop GUI for purchasing and enabling a proxy through Proxy-Seller API.

## Features

- Enter Proxy-Seller API key in the app.
- Load available countries and periods dynamically from API.
- Create an order directly from GUI.
- Reuse existing active proxies without creating a new order.
- Reconnect the last saved proxy without API calls (`Reconnect last`).
- Wait for proxy activation automatically.
- Save generated proxy config to JSON in `~/.proxy-desktop-launcher/generated_proxy_configs/`.
- Keep latest successful proxy in `~/.proxy-desktop-launcher/last_proxy.json`.
- Save and restore API key, selected type/protocol/country/period, and quantity.
- Show confirmation dialog before creating a paid order.
- Show current active proxy in the status area.
- Apply system proxy automatically:
  - macOS: HTTP/HTTPS and SOCKS5 via `networksetup`.
  - Windows: proxy values in user Internet Settings registry.

## Requirements

- Python 3.9+
- `pip install -r requirements.txt`

## Setup macOS Environment

One command to install dependencies and verify environment:

```bash
./setup_macos_env.sh
```

## Run (No Console)

After build, open this file with double click in Finder:

`dist/Proxy Seller Launcher.app`

No terminal interaction is required.

## Build macOS App

```bash
./build_macos_app.sh
```

This creates:

- `dist/Proxy Seller Launcher.app` (desktop app, windowed, no console)

For reliable Tk GUI build on macOS:

```bash
brew install python@3.12 python-tk@3.12
```

`build_macos_app.sh` uses `python3.12` from Homebrew and auto-creates `.venv-macos`.

## Build Windows App

Run one of these on Windows:

```powershell
.\build_windows_app.ps1
```

```bat
build_windows_app.bat
```

This creates:

- `dist\Proxy Seller Launcher\Proxy Seller Launcher.exe` (windowed, no console)

## Usage

1. Paste your Proxy-Seller API key.
2. Choose proxy type and protocol.
3. Click `Load countries`.
4. Select country and period.
5. Click `Create + connect` (new paid order) or `Connect active` (reuse active).
6. To disable system proxy, click `Disconnect proxy`.
7. To quickly restore previous proxy, click `Reconnect last`.
8. To inspect generated JSON files, click `Open configs folder`.

## Notes

- API key is stored locally in `~/.proxy-desktop-launcher/settings.json` to speed up repeated use.
- For Windows, username/password are returned and saved in JSON config, but many apps handle proxy auth separately.
- This project targets macOS and Windows only.
