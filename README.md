# Proxy Seller Desktop Launcher

Simple desktop GUI for purchasing and enabling a proxy through Proxy-Seller API.

## Features

- Enter Proxy-Seller API key in the app.
- Load available countries and periods dynamically from API.
- Load resident/scraper tariffs dynamically from API.
- Configure extra order params directly in UI:
  - `paymentId` (`1` balance, `43` linked card).
  - `authorization` (optional real IP for IP-auth).
  - `generateAuth` (`Y/N`).
  - `customTargetName` (purpose / site).
  - Mobile: `mobileServiceType`, `operatorId`, `rotationId`.
- Create an order directly from GUI.
- Reuse existing active proxies without creating a new order.
- Filter active proxies by `orderId` or `baseOrderNumber`.
- Check current account balance from UI.
- Reconnect the last saved proxy without API calls (`Reconnect last`).
- Wait for proxy activation automatically.
- Save generated proxy config to JSON in `~/.proxy-desktop-launcher/generated_proxy_configs/`.
- Keep latest successful proxy in `~/.proxy-desktop-launcher/last_proxy.json`.
- Save and restore API key, selected type/protocol/country/period/tariff, and quantity.
- Show confirmation dialog before creating a paid order.
- Show current active proxy in the status area.
- Validate type-specific rules before paid order:
  - IPv6 minimum quantity.
  - MIX / MIX_ISP allowed quantity set by selected country/package.
  - Mobile required fields (service/operator/rotation).
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
3. Click `Обновить список стран` (or tariffs for resident/scraper).
4. Select country+period for standard types, or tariff for resident/scraper. Then set quantity.
5. For `mobile`, also choose service type, operator, and rotation.
6. If needed, click `Показать расширенные параметры` to set `paymentId`, `authorization`, `generateAuth`, `customTargetName` and `orderId/baseOrderNumber` filter.
7. Click `Купить и подключить` (new paid order) or `Подключить купленный` (reuse active).
8. To disable system proxy, click `Отключить прокси`.
9. Open `Ещё` menu for secondary actions: reconnect last proxy, active list, balance, configs folder.

## Notes

- API key is stored locally in `~/.proxy-desktop-launcher/settings.json` to speed up repeated use.
- For Windows, username/password are returned and saved in JSON config, but many apps handle proxy auth separately.
- This project targets macOS and Windows only.
