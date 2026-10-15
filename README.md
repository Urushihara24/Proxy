# Proxy Seller Desktop Launcher

Desktop GUI application for macOS and Windows that automates work with Proxy-Seller:

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Tkinter](https://img.shields.io/badge/Tkinter-Desktop_GUI-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://docs.python.org/3/library/tkinter.html)
[![Requests](https://img.shields.io/badge/Requests-HTTP-2CA5E0?style=for-the-badge&logo=python&logoColor=white)](https://requests.readthedocs.io/)
[![Windows](https://img.shields.io/badge/Windows-Supported-0078D4?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![macOS](https://img.shields.io/badge/macOS-Supported-000000?style=for-the-badge&logo=apple&logoColor=white)](https://www.apple.com/macos/)
[![pytest](https://img.shields.io/badge/pytest-Tested-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org/)
[![CI](https://img.shields.io/github/actions/workflow/status/Urushihara24/Proxy/ci.yml?branch=main&style=for-the-badge&label=CI)](https://github.com/Urushihara24/Proxy/actions/workflows/ci.yml)
[![Security](https://img.shields.io/github/actions/workflow/status/Urushihara24/Proxy/security.yml?branch=main&style=for-the-badge&label=Security)](https://github.com/Urushihara24/Proxy/actions/workflows/security.yml)
[![Windows Build](https://img.shields.io/github/actions/workflow/status/Urushihara24/Proxy/windows-build.yml?branch=main&style=for-the-badge&label=Windows%20Build)](https://github.com/Urushihara24/Proxy/actions/workflows/windows-build.yml)

</div>

## Product snapshot

| Area | Capability |
|---|---|
| **Proxy catalog** | IPv4, IPv6, mobile, ISP, mix, resident and scraper flows |
| **API workflow** | reference data, order calculation, purchase, activation and active-proxy lookup |
| **Desktop integration** | applies and removes the operating-system proxy from the GUI |
| **Local state** | remembers selected parameters, API key state and the last connected proxy |
| **Platforms** | macOS and Windows; automated Windows artifact build in GitHub Actions |
| **Quality** | offline unit tests and compile checks on Python 3.11/3.12, dependency audit and local-secret guards |

> [!CAUTION]
> The application can create billable Proxy-Seller orders and change the operating system proxy configuration. CI does **not** perform live purchases or mutate the host proxy; those actions happen only when the application is explicitly configured with a real API key and the corresponding GUI action is used.

- select proxy type, country, period or tariff;
- calculate and create an order through the API;
- wait for proxy activation;
- apply the proxy automatically to the operating system;
- reconnect a previously purchased proxy.

The goal is to let the user complete the entire workflow through the GUI without manually generating or copying proxy configurations in a terminal.

## Implemented functionality

- Complete GUI flow for `ipv4`, `ipv6`, `mobile`, `isp`, `mix`, `mix_isp`, `resident`, and `scraper`.
- Reference-data loading from the API: countries, periods and tariffs.
- Pre-purchase constraint validation:
  - `ipv6`: minimum quantity;
  - `mix`/`mix_isp`: allowed quantities;
  - `mobile`: required `service/operator/rotation`.
- Additional order parameters:
  - `paymentId` (`1` balance, `43` card),
  - `authorization` (IP authorization),
  - `generateAuth` (`Y/N`),
  - `customTargetName`.
- Active-proxy filtering by `orderId` or `baseOrderNumber`.
- Resident configuration issuance without a new purchase through the API TOOL list when an active package still has traffic.
- UI actions:
  - `Купить и подключить` — buy and connect;
  - `Подключить купленный` — connect an already purchased proxy;
  - `Подключить последний` — reconnect the last proxy;
  - `Выпустить resident конфиг` — issue a resident configuration;
  - `Отключить прокси` — disable the system proxy;
  - `Проверить баланс` — check account balance;
  - `Показать активные` — show active proxies;
  - `Открыть папку конфигов` — open the configuration directory.
- Asynchronous API operations without blocking the GUI, plus a paginated event log.
- Paste an API key from the clipboard and remove it from settings.
- Persist local state: API key, selected parameters and last connected proxy.

> The application UI is currently Russian, so button labels are kept exactly as they appear in the product.

## Supported platforms

- macOS
- Windows

Linux is not supported in this build.

## Quick start for development

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Run from source

```bash
python app.py
```

## macOS: environment setup and `.app` build

Automated environment setup:

```bash
./setup_macos_env.sh
```

Build the application:

```bash
./build_macos_app.sh
```

Output:

- `dist/Proxy Seller Launcher.app`

## Windows: `.exe` build

Install dependencies on Windows before building:

```powershell
pip install -r requirements.txt
pip install pyinstaller
```

Then run:

```powershell
.\build_windows_app.ps1
```

or:

```bat
build_windows_app.bat
```

Output:

- `dist\Proxy Seller Launcher\Proxy Seller Launcher.exe`

## Automated Windows build with GitHub Actions

The repository includes:

- `.github/workflows/windows-build.yml`

Usage:

1. Open the `Actions` tab on GitHub.
2. Select the `Build Windows App` workflow.
3. Press `Run workflow`, or push changes to `main` when application/build files are affected.
4. After the run completes, download the `proxy-seller-launcher-windows` artifact.

The artifact contains the built `.exe` and the contents of `dist/Proxy Seller Launcher`.

## Using the application

1. Paste your Proxy-Seller API key.
2. Select a proxy type and protocol.
3. Press `Обновить данные`.
